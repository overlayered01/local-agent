from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from local_agent.errors import LocalAgentError
from local_agent.project import FileInfo, ProjectReader


class ProjectReaderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        (self.root / "src").mkdir()
        (self.root / "src" / "player.py").write_text(
            "class Player:\n    def jump(self):\n        return 'jump'\n", encoding="utf-8"
        )
        (self.root / "README.md").write_text("# Sample game\n", encoding="utf-8")
        (self.root / ".env").write_text("TOKEN=secret\n", encoding="utf-8")
        (self.root / "library").mkdir()
        (self.root / "library" / "generated.cs").write_text("secret generated", encoding="utf-8")
        (self.root / "asset.uasset").write_bytes(b"binary")
        (self.root / "level.unity").write_text("GameObject: Player", encoding="utf-8")
        (self.root / "config").mkdir()
        (self.root / "config" / "local.yaml").write_text("password: secret", encoding="utf-8")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_lists_only_safe_text_candidates(self) -> None:
        paths = [item.relative for item in ProjectReader(self.root).files()]
        self.assertEqual(paths, ["README.md", "level.unity", "src/player.py"])

    def test_search_returns_path_line_and_text(self) -> None:
        matches = ProjectReader(self.root).search(r"jump")
        self.assertEqual([(item.path, item.line) for item in matches], [("src/player.py", 2), ("src/player.py", 3)])

    def test_context_prioritizes_relevant_file(self) -> None:
        context = ProjectReader(self.root).context("How does Player jump?", max_chars=1000)
        self.assertTrue(context.startswith("--- FILE: src/player.py ---"))
        self.assertNotIn("TOKEN=secret", context)

    def test_read_rejects_file_outside_root(self) -> None:
        outside = self.root.parent / "outside.txt"
        info = FileInfo(outside, "../outside.txt", 0)
        with self.assertRaises(LocalAgentError):
            ProjectReader(self.root).read(info)


if __name__ == "__main__":
    unittest.main()
