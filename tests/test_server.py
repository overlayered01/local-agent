from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from local_agent.errors import LocalAgentError
from local_agent.server import build_server_command


class ServerCommandTests(unittest.TestCase):
    def test_builds_argument_list_without_shell_string(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            executable = root / "llama server.exe"
            model = root / "model.gguf"
            executable.touch()
            model.touch()
            command = build_server_command(
                executable,
                model,
                host="127.0.0.1",
                port=8080,
                context_size=8192,
                gpu_layers=99,
                extra_args=["--threads", "8"],
            )
            self.assertEqual(command[0], str(executable.resolve()))
            self.assertIn(str(model.resolve()), command)
            self.assertEqual(command[-2:], ["--threads", "8"])

    def test_rejects_non_gguf_model(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            executable = root / "llama-server.exe"
            model = root / "model.bin"
            executable.touch()
            model.touch()
            with self.assertRaises(LocalAgentError):
                build_server_command(
                    executable,
                    model,
                    host="127.0.0.1",
                    port=8080,
                    context_size=8192,
                    gpu_layers=99,
                )


if __name__ == "__main__":
    unittest.main()

