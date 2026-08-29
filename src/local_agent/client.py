from __future__ import annotations

import ipaddress
import json
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from .errors import LocalAgentError


@dataclass(frozen=True)
class ServerStatus:
    healthy: bool
    detail: str


class LlamaClient:
    def __init__(self, base_url: str, timeout: float = 120.0, *, allow_remote: bool = False) -> None:
        if timeout <= 0:
            raise LocalAgentError("서버 제한 시간은 0보다 커야 합니다.")
        parsed = urlparse(base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise LocalAgentError(f"올바른 HTTP 서버 URL이 아닙니다: {base_url}")
        if not allow_remote and not self._is_loopback(parsed.hostname):
            raise LocalAgentError(
                f"로컬 주소가 아닌 서버 연결을 차단했습니다: {parsed.hostname}. "
                "의도한 연결이면 --allow-remote를 사용하세요."
            )
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def status(self) -> ServerStatus:
        for endpoint in ("/health", "/v1/models"):
            try:
                with urlopen(f"{self.base_url}{endpoint}", timeout=min(self.timeout, 5.0)) as response:
                    payload = response.read().decode("utf-8", errors="replace")
                    if 200 <= response.status < 300:
                        return ServerStatus(True, self._status_detail(endpoint, payload))
            except (HTTPError, URLError, TimeoutError, OSError):
                continue
        return ServerStatus(False, f"서버에 연결할 수 없습니다: {self.base_url}")

    def chat(
        self,
        messages: list[dict[str, str]],
        *,
        model: str = "local-model",
        temperature: float = 0.1,
    ) -> Iterator[str]:
        body = json.dumps(
            {
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "stream": True,
            }
        ).encode("utf-8")
        request = Request(
            f"{self.base_url}/v1/chat/completions",
            data=body,
            headers={"Content-Type": "application/json", "Accept": "text/event-stream"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                for raw_line in response:
                    line = raw_line.decode("utf-8", errors="replace").strip()
                    if not line or line.startswith(":") or not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        break
                    try:
                        event: dict[str, Any] = json.loads(data)
                        choices = event.get("choices") or []
                        if not choices:
                            continue
                        delta = choices[0].get("delta") or {}
                        content = delta.get("content")
                        if content:
                            yield str(content)
                    except (json.JSONDecodeError, AttributeError, IndexError, TypeError) as exc:
                        raise LocalAgentError(f"서버가 잘못된 스트리밍 응답을 반환했습니다: {data[:120]}") from exc
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:500]
            raise LocalAgentError(f"llama.cpp 요청 실패 (HTTP {exc.code}): {detail}") from exc
        except (URLError, TimeoutError, OSError) as exc:
            raise LocalAgentError(f"llama.cpp 서버 연결 실패: {exc}") from exc

    @staticmethod
    def _status_detail(endpoint: str, payload: str) -> str:
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            return f"정상 응답 ({endpoint})"
        if endpoint == "/health":
            return str(data.get("status") or "정상")
        models = data.get("data") or []
        names = [str(item.get("id")) for item in models if isinstance(item, dict) and item.get("id")]
        return f"사용 가능 모델: {', '.join(names)}" if names else "OpenAI 호환 API 정상"

    @staticmethod
    def _is_loopback(hostname: str) -> bool:
        if hostname.rstrip(".").lower() == "localhost":
            return True
        try:
            return ipaddress.ip_address(hostname).is_loopback
        except ValueError:
            return False
