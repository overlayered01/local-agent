from __future__ import annotations

import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from local_agent.client import LlamaClient
from local_agent.errors import LocalAgentError


class MockLlamaHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        if self.path != "/health":
            self.send_error(404)
            return
        body = json.dumps({"status": "ok"}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers["Content-Length"])
        request = json.loads(self.rfile.read(length))
        if self.path != "/v1/chat/completions" or request.get("stream") is not True:
            self.send_error(400)
            return
        events = [
            {"choices": [{"delta": {"content": "hello "}}]},
            {"choices": [{"delta": {"content": "world"}}]},
        ]
        body = "".join(f"data: {json.dumps(event)}\n\n" for event in events) + "data: [DONE]\n\n"
        encoded = body.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, format: str, *args: object) -> None:
        pass


class LlamaClientTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), MockLlamaHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def test_health_status(self) -> None:
        status = LlamaClient(self.base_url).status()
        self.assertTrue(status.healthy)
        self.assertEqual(status.detail, "ok")

    def test_streaming_chat(self) -> None:
        chunks = LlamaClient(self.base_url).chat([{"role": "user", "content": "test"}])
        self.assertEqual("".join(chunks), "hello world")

    def test_blocks_remote_server_by_default(self) -> None:
        with self.assertRaises(LocalAgentError):
            LlamaClient("https://example.com")

    def test_allows_explicit_remote_server(self) -> None:
        client = LlamaClient("https://example.com", allow_remote=True)
        self.assertEqual(client.base_url, "https://example.com")

    def test_rejects_non_positive_timeout(self) -> None:
        with self.assertRaises(LocalAgentError):
            LlamaClient(self.base_url, timeout=0)


if __name__ == "__main__":
    unittest.main()
