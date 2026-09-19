"""Local stand-in for the /chat API, so the frontend can talk to `agentcore dev`.

The deployed frontend calls `POST /chat` and gets back one JSON object. That shape
is produced by the Lambda inside infra/api.yaml, which reads the AgentCore runtime's
SSE stream and flattens it. `agentcore dev` serves the raw SSE stream at
/invocations and knows nothing about /chat, so pointing the frontend straight at it
returns something the client cannot parse.

This script is that missing piece: same request and response contract as the Lambda,
but forwarding to the local dev server instead of a deployed runtime. It exists so a
change to the agent can be seen in the real UI without a deploy.

It is a development tool and is deliberately not production code — no auth, no
rate limiting, permissive CORS, single-threaded. It also lives outside
app/Agromemnon/ so it is not packaged into the deployment zip.

    Terminal 1:  agentcore dev --skip-deploy          # note the port it prints
    Terminal 2:  python backend/Agromemnon/dev/local_chat_api.py --agent-port 8081
    Terminal 3:  cd frontend && npm run dev

Then set NEXT_PUBLIC_AGENT_API_URL=http://localhost:8787 in frontend/.env.local.

Stdlib only, so it runs without installing anything.
"""

import argparse
import hashlib
import json
import re
import sys
import time
import urllib.error
import urllib.request
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# Mirrors the Lambda: the runtime requires a session id of at least 33 characters.
MIN_SESSION_LEN = 33
MAX_SESSION_LEN = 128

# The Lambda budgets against API Gateway's 30s ceiling. Locally there is no gateway,
# and a cold model plus a tool call can legitimately run longer, so this is looser —
# but still bounded, so a hung agent surfaces as an error rather than a spinner.
REQUEST_TIMEOUT_SECONDS = 180

AGENT_URL = "http://127.0.0.1:{port}/invocations"


def session_id(raw):
    cleaned = re.sub(r"[^A-Za-z0-9_-]", "-", (raw or "").strip())
    if not cleaned:
        return (uuid.uuid4().hex + uuid.uuid4().hex)[:40]
    if len(cleaned) < MIN_SESSION_LEN:
        cleaned += "-" + hashlib.sha256(cleaned.encode()).hexdigest()
    return cleaned[:MAX_SESSION_LEN]


def collect(stream):
    """Flatten the runtime's SSE stream into (text, stop_reason, usage, error).

    Only contentBlockDelta.delta.text is answer text. delta.toolUse carries tool
    arguments and delta.reasoningContent carries the model's thinking; including
    either would print raw JSON and reasoning traces into the farmer's reply.
    """
    chunks, stop_reason, usage, error = [], None, None, None

    for line in stream:
        line = line.strip()
        if not line.startswith(b"data:"):
            continue
        try:
            event = json.loads(line[5:].strip() or b"{}")
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict):
            continue

        if event.get("error"):
            error = str(event["error"])
            continue

        inner = event.get("event")
        if not isinstance(inner, dict):
            continue

        text = (inner.get("contentBlockDelta") or {}).get("delta", {}).get("text")
        if isinstance(text, str):
            chunks.append(text)
        stop_reason = (inner.get("messageStop") or {}).get("stopReason") or stop_reason
        usage = (inner.get("metadata") or {}).get("usage") or usage

    return "".join(chunks), stop_reason, usage, error


class Handler(BaseHTTPRequestHandler):
    agent_port = 8081

    def log_message(self, fmt, *args):
        sys.stderr.write("  %s\n" % (fmt % args))

    def _send(self, status, body):
        payload = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self._cors()
        self.end_headers()
        self.wfile.write(payload)

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.send_header("Access-Control-Max-Age", "300")
        self.end_headers()

    def do_POST(self):
        if self.path.rstrip("/") != "/chat":
            return self._send(404, {"error": "Only POST /chat is served here."})

        length = int(self.headers.get("Content-Length") or 0)
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            return self._send(400, {"error": "Request body must be JSON."})
        if not isinstance(body, dict):
            return self._send(400, {"error": "Request body must be a JSON object."})

        prompt = body.get("prompt", "")
        image = body.get("image")
        image = image if isinstance(image, str) else None
        if not isinstance(prompt, str) or not (prompt.strip() or image):
            return self._send(400, {"error": "Provide a 'prompt' string or an 'image'."})

        sid = session_id(body.get("sessionId"))
        payload = {"prompt": prompt, **({"image": image} if image else {})}
        note = f" +photo({len(image) // 1024} KB)" if image else ""
        print(f"→ /chat session={sid[:12]}…{note} prompt={prompt[:60]!r}", flush=True)

        started = time.monotonic()
        request = urllib.request.Request(
            AGENT_URL.format(port=self.agent_port),
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as stream:
                answer, stop_reason, usage, error = collect(stream)
        except urllib.error.URLError as exc:
            print(f"  agent unreachable: {exc}", flush=True)
            return self._send(502, {
                "error": f"Could not reach the dev agent on port {self.agent_port}. "
                         "Is `agentcore dev` running, and is --agent-port correct?",
                "sessionId": sid,
            })
        except TimeoutError:
            return self._send(504, {"error": "The agent did not answer in time.", "sessionId": sid})

        elapsed = time.monotonic() - started
        if not answer:
            print(f"  no text after {elapsed:.1f}s (error={error})", flush=True)
            return self._send(502, {"error": error or "The agent returned no text.", "sessionId": sid})

        print(f"  {len(answer)} chars in {elapsed:.1f}s", flush=True)
        result = {"response": answer, "sessionId": sid}
        if stop_reason:
            result["stopReason"] = stop_reason
        if usage:
            result["usage"] = usage
        if error:
            result["warning"] = error
        return self._send(200, result)


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--port", type=int, default=8787, help="Port to serve /chat on.")
    parser.add_argument("--agent-port", type=int, default=8081,
                        help="Port `agentcore dev` printed (it falls back if 8080 is busy).")
    args = parser.parse_args()

    Handler.agent_port = args.agent_port
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)

    print(f"Local /chat API  : http://localhost:{args.port}/chat")
    print(f"Forwarding to    : {AGENT_URL.format(port=args.agent_port)}")
    print(f"Put this in frontend/.env.local:")
    print(f"  NEXT_PUBLIC_AGENT_API_URL=http://localhost:{args.port}")
    print("Ctrl+C to stop.\n")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")


if __name__ == "__main__":
    main()
