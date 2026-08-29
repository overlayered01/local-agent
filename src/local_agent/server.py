from __future__ import annotations

import subprocess
from pathlib import Path

from .errors import LocalAgentError


def build_server_command(
    executable: Path,
    model: Path,
    *,
    host: str,
    port: int,
    context_size: int,
    gpu_layers: int,
    extra_args: list[str] | None = None,
) -> list[str]:
    executable = executable.expanduser().resolve()
    model = model.expanduser().resolve()
    if not executable.is_file():
        raise LocalAgentError(f"llama.cpp 서버 실행 파일을 찾을 수 없습니다: {executable}")
    if not model.is_file():
        raise LocalAgentError(f"GGUF 모델을 찾을 수 없습니다: {model}")
    if model.suffix.lower() != ".gguf":
        raise LocalAgentError(f"GGUF 모델 파일이 아닙니다: {model}")
    if not 1 <= port <= 65535:
        raise LocalAgentError("포트는 1~65535 범위여야 합니다.")
    if context_size < 512:
        raise LocalAgentError("컨텍스트 크기는 512 이상이어야 합니다.")
    if gpu_layers < 0:
        raise LocalAgentError("GPU 레이어 수는 0 이상이어야 합니다.")

    command = [
        str(executable),
        "--model",
        str(model),
        "--host",
        host,
        "--port",
        str(port),
        "--ctx-size",
        str(context_size),
        "--n-gpu-layers",
        str(gpu_layers),
    ]
    command.extend(extra_args or [])
    return command


def run_server(command: list[str]) -> int:
    """Run llama-server in the foreground without invoking a command shell."""
    try:
        return subprocess.run(command, shell=False, check=False).returncode
    except KeyboardInterrupt:
        return 130
    except OSError as exc:
        raise LocalAgentError(f"llama.cpp 서버 실행 실패: {exc}") from exc

