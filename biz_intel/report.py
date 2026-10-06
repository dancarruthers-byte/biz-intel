"""Generate a business intelligence report for a company using Claude + web search."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Callable, Iterator

import anthropic

MODEL = "claude-opus-5-5"
MAX_CONTINUATIONS = 5

SECTIONS = [
    "Executive Summary",
    "Company Overview (founding, HQ, leadership, ownership, employees)",
    "Products & Services",
    "Business Model & Revenue Streams",
    "Financial Snapshot (revenue, growth, profitability, funding or market cap - cite figures and their dates)",
    "Market & Competitive Landscape (key competitors, positioning, market share where known)",
    "Recent News & Developments (last 12 months)",
    "SWOT Analysis",
    "Key Risks & Watch Items",
    "Outlook",
]

SYSTEM_PROMPT = f"""You are a business intelligence analyst. Research the company the user names \
using web search (and web fetch for primary sources such as the company's own site, investor \
relations pages, and filings), then write a concise, factual report in GitHub-flavored Markdown.

Report structure - use these as level-2 headings, in this order:
{chr(10).join(f"- {s.split(' (')[0]}" for s in SECTIONS)}

Guidance per section:
{chr(10).join(f"- {s}" for s in SECTIONS)}

Rules:
- Start the report with a level-1 heading: "<Company Name> - Business Intelligence Report".
- Prefer recent, primary, and reputable sources. State the date or period for every financial figure.
- If information is unavailable or the company is private, say so plainly rather than guessing.
- If the name is ambiguous, pick the most prominent company, and note the assumption at the top.
- Use tables where they help (e.g. financials, competitors).
- Output only the report - no preamble about your research process.
Today's date is {date.today().isoformat()}."""

TOOLS = [
    {"type": "web_search_20260209", "name": "web_search", "max_uses": 10},
    {"type": "web_fetch_20260209", "name": "web_fetch", "max_uses": 5},
]


@dataclass
class Source:
    title: str
    url: str


@dataclass
class Report:
    company: str
    markdown: str
    sources: list[Source] = field(default_factory=list)


class ReportError(Exception):
    pass


def _build_prompt(company: str, focus: str | None) -> str:
    prompt = f"Produce a business intelligence report on: {company}"
    if focus:
        prompt += f"\n\nPay particular attention to: {focus}"
    return prompt


def _collect_sources(content, seen: dict[str, Source]) -> None:
    for block in content:
        if block.type == "web_search_tool_result" and isinstance(block.content, list):
            for result in block.content:
                if getattr(result, "url", None) and result.url not in seen:
                    seen[result.url] = Source(title=result.title or result.url, url=result.url)
        elif block.type == "text":
            for citation in block.citations or []:
                url = getattr(citation, "url", None)
                if url and url not in seen:
                    seen[url] = Source(title=getattr(citation, "title", None) or url, url=url)


def stream_report(
    company: str,
    focus: str | None = None,
    client: anthropic.Anthropic | None = None,
) -> Iterator[dict]:
    """Yield progress events while researching, ending with a ``{"type": "done"}`` event.

    Event shapes:
      {"type": "status", "message": str}
      {"type": "text", "delta": str}
      {"type": "done", "report": Report}
    """
    client = client or anthropic.Anthropic()
    messages = [{"role": "user", "content": _build_prompt(company, focus)}]
    sources: dict[str, Source] = {}
    text_parts: list[str] = []
    assistant_content: list = []

    for _ in range(MAX_CONTINUATIONS + 1):
        with client.beta.messages.stream(
            model=MODEL,
            max_tokens=64000,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
            thinking={"type": "adaptive"},
            output_config={"effort": "medium"},
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        ) as stream:
            for event in stream:
                if event.type == "content_block_stop" and event.content_block.type == "server_tool_use":
                    block = event.content_block
                    query = (block.input or {}).get("query") or (block.input or {}).get("url")
                    label = "Searching" if block.name == "web_search" else "Reading"
                    yield {"type": "status", "message": f"{label}: {query}" if query else f"{label}..."}
                elif event.type == "content_block_delta" and event.delta.type == "text_delta":
                    text_parts.append(event.delta.text)
                    yield {"type": "text", "delta": event.delta.text}
            message = stream.get_final_message()

        if message.stop_reason == "refusal":
            raise ReportError("The model declined to produce this report.")

        _collect_sources(message.content, sources)

        if message.stop_reason != "pause_turn":
            break
        # Server-side tool loop hit its iteration limit; resend so it resumes.
        assistant_content += message.content
        messages = [messages[0], {"role": "assistant", "content": assistant_content}]
        yield {"type": "status", "message": "Continuing research..."}
    else:
        raise ReportError("Research did not finish within the continuation limit.")

    markdown = "".join(text_parts).strip()
    if not markdown:
        raise ReportError("No report text was returned.")
    yield {"type": "done", "report": Report(company=company, markdown=markdown, sources=list(sources.values()))}


def generate_report(
    company: str,
    focus: str | None = None,
    on_event: Callable[[dict], None] | None = None,
) -> Report:
    """Blocking helper: run the stream to completion and return the final report."""
    for event in stream_report(company, focus):
        if event["type"] == "done":
            return event["report"]
        if on_event:
            on_event(event)
    raise ReportError("Report stream ended unexpectedly.")


def to_markdown(report: Report) -> str:
    out = report.markdown
    if report.sources:
        out += "\n\n## Sources\n\n" + "\n".join(f"- [{s.title}]({s.url})" for s in report.sources)
    return out + "\n"
