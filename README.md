# Biz Intel

A small app that generates a **business intelligence report** for any company. It uses Claude with live web search and web fetch to research the company, then writes a structured Markdown report with sources.

Each report covers:

- Executive summary
- Company overview (founding, HQ, leadership, ownership, headcount)
- Products & services
- Business model & revenue streams
- Financial snapshot (dated figures)
- Market & competitive landscape
- Recent news & developments
- SWOT analysis
- Key risks & watch items
- Outlook
- Sources

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...
```

## Web app

```bash
python app.py
```

Open http://localhost:5000, enter a company name (and an optional focus area), and watch the report stream in. When it's finished you can download it as Markdown or print it to PDF.

## Command line

```bash
python cli.py "Shopify"
python cli.py "Stripe" --focus "AI strategy" -o stripe.md
```

## Notes

- Model: `claude-opus-5-5`, with adaptive thinking at `medium` effort. Server-side refusal fallback (`fallbacks: "default"`) is turned on. Change these in `biz_intel/report.py`.
- A report usually takes 1–3 minutes and makes up to 10 web searches and 5 page fetches. Web search is billed per search on top of token usage.
- The report is generated from public web sources. Check important figures against the cited sources before relying on them.

## Tests

The tests use a fake client, so they run offline without an API key:

```bash
pip install pytest
pytest
```

## Hosted version

`hosted/company-dossier.html` is published as a claude.ai artifact: https://claude.ai/artifact/B5sXDkjDE1P8yq8QzE18gi

It needs no server or API key, because it calls Claude through the viewer's own claude.ai account. It can't browse the web, so its reports come from Claude's knowledge plus any recent notes the user pastes in. Use the Flask app above when you need live web research.
