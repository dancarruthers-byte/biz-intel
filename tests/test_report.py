"""Offline tests: a fake client replays stream events so no API key is needed."""

from types import SimpleNamespace as NS

import pytest

import app as webapp
from biz_intel import ReportError, report as rpt


class FakeStream:
    def __init__(self, events, final):
        self.events, self.final = events, final

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def __iter__(self):
        return iter(self.events)

    def get_final_message(self):
        return self.final


class FakeClient:
    def __init__(self, turns):
        self.turns, self.calls = list(turns), []
        self.beta = NS(messages=NS(stream=self._stream))

    def _stream(self, **kwargs):
        self.calls.append(kwargs)
        return FakeStream(*self.turns.pop(0))


def text_delta(t):
    return NS(type="content_block_delta", delta=NS(type="text_delta", text=t))


search_use = NS(type="server_tool_use", name="web_search", input={"query": "Acme revenue"})
search_result = NS(type="web_search_tool_result", content=[NS(url="https://acme.example", title="Acme")])
cited_text = NS(type="text", text="x", citations=[NS(url="https://news.example/a", title="News")])


def test_full_report_with_pause_turn():
    turn1 = ([NS(type="content_block_stop", content_block=search_use)],
             NS(stop_reason="pause_turn", content=[search_use, search_result]))
    turn2 = ([text_delta("# Acme\n"), text_delta("Body")],
             NS(stop_reason="end_turn", content=[cited_text]))
    client = FakeClient([turn1, turn2])

    events = list(rpt.stream_report("Acme", "AI", client=client))

    assert events[0] == {"type": "status", "message": "Searching: Acme revenue"}
    report = events[-1]["report"]
    assert report.markdown == "# Acme\nBody"
    assert [s.url for s in report.sources] == ["https://acme.example", "https://news.example/a"]
    # Continuation resends the user turn plus the paused assistant content.
    second = client.calls[1]["messages"]
    assert second[1]["role"] == "assistant" and second[1]["content"][0] is search_use
    assert "Pay particular attention to: AI" in client.calls[0]["messages"][0]["content"]
    assert "## Sources" in rpt.to_markdown(report)


def test_refusal_raises():
    client = FakeClient([([], NS(stop_reason="refusal", content=[]))])
    with pytest.raises(ReportError):
        list(rpt.stream_report("Acme", client=client))


def test_api_streams_sse(monkeypatch):
    def fake_stream(company, focus):
        yield {"type": "status", "message": "Searching"}
        yield {"type": "done", "report": rpt.Report(company, "# R", [rpt.Source("S", "https://s")])}

    monkeypatch.setattr(webapp, "stream_report", fake_stream)
    c = webapp.app.test_client()
    assert c.post("/api/report", json={}).status_code == 400
    body = c.post("/api/report", json={"company": "Acme"}).get_data(as_text=True)
    assert '"type": "status"' in body and '"type": "done"' in body and "https://s" in body
    assert c.get("/").status_code == 200
