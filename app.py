"""Web UI: enter a company name, watch the report stream in, download it as Markdown."""

import json

import anthropic
from flask import Flask, Response, render_template, request, stream_with_context

from biz_intel import ReportError, stream_report, to_markdown

app = Flask(__name__)


@app.get("/")
def index():
    return render_template("index.html")


@app.post("/api/report")
def report():
    payload = request.get_json(silent=True) or {}
    company = (payload.get("company") or "").strip()
    focus = (payload.get("focus") or "").strip() or None
    if not company:
        return {"error": "Company name is required."}, 400
    if len(company) > 200 or (focus and len(focus) > 500):
        return {"error": "Input is too long."}, 400

    def events():
        def sse(data: dict) -> str:
            return f"data: {json.dumps(data)}\n\n"

        try:
            for event in stream_report(company, focus):
                if event["type"] == "done":
                    r = event["report"]
                    yield sse({
                        "type": "done",
                        "markdown": to_markdown(r),
                        "sources": [{"title": s.title, "url": s.url} for s in r.sources],
                    })
                else:
                    yield sse(event)
        except ReportError as e:
            yield sse({"type": "error", "message": str(e)})
        except anthropic.AuthenticationError:
            yield sse({"type": "error", "message": "Invalid or missing ANTHROPIC_API_KEY."})
        except anthropic.RateLimitError:
            yield sse({"type": "error", "message": "Rate limited by the API - try again shortly."})
        except anthropic.APIStatusError as e:
            yield sse({"type": "error", "message": f"API error ({e.status_code}): {e.message}"})
        except anthropic.APIConnectionError:
            yield sse({"type": "error", "message": "Could not reach the Anthropic API."})
        except TypeError as e:
            # The SDK raises TypeError when no API key or auth token is configured.
            if "authentication" not in str(e):
                raise
            yield sse({"type": "error", "message": "No Anthropic credentials found - set ANTHROPIC_API_KEY and restart."})
        except Exception:
            app.logger.exception("Report generation failed")
            yield sse({"type": "error", "message": "Report generation failed - check the server logs."})

    return Response(
        stream_with_context(events()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


if __name__ == "__main__":
    app.run(debug=True, port=5000, threaded=True)
