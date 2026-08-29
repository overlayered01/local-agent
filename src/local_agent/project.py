from __future__ import annotations

import fnmatch
import os
import re
from dataclasses import dataclass
from pathlib import Path

from .errors import LocalAgentError


DEFAULT_IGNORED_DIRS = frozenset(
    name.lower()
    for name in {
        ".git",
        ".idea",
        ".pytest_cache",
        ".ruff_cache",
        ".venv",
        ".vs",
        ".vscode",
        "Binaries",
        "Build",
        "Builds",
        "DerivedDataCache",
        "Intermediate",
        "Library",
        "MemoryCaptures",
        "Obj",
        "Recordings",
        "Saved",
        "Temp",
        "UserSettings",
        "__pycache__",
        "dist",
        "logs",
        "models",
        "node_modules",
        "runtime",
        "sessions",
        "venv",
        "wheelhouse",
    }
)

DEFAULT_IGNORED_FILES = (
    ".env",
    ".env.*",
    "*.bin",
    "*.gguf",
    "*.key",
    "*.pem",
    "*.safetensors",
    "*.uasset",
    "*.umap",
    "id_ed25519",
    "id_rsa",
)

DEFAULT_IGNORED_PATHS = ("config/local.*",)

TEXT_EXTENSIONS = frozenset(
    {
        ".asmdef", ".asset", ".bat", ".c", ".cc", ".cfg", ".cginc", ".cmake",
        ".cmd", ".compute", ".cpp", ".cs", ".csproj", ".css", ".csv", ".cxx",
        ".editorconfig", ".gitignore", ".h", ".hlsl", ".hpp", ".html", ".ini",
        ".java", ".js", ".json", ".jsx", ".kt", ".lua", ".mat", ".md", ".meta",
        ".prefab", ".ps1", ".py", ".rs", ".shader", ".sh", ".sln", ".toml",
        ".ts", ".tsx", ".txt", ".unity", ".uproject", ".uplugin", ".usf", ".ush",
        ".uss", ".uxml", ".xml", ".yaml", ".yml",
    }
)


@dataclass(frozen=True)
class FileInfo:
    path: Path
    relative: str
    size: int


@dataclass(frozen=True)
class SearchMatch:
    path: str
    line: int
    text: str


class ProjectReader:
    def __init__(self, root: Path, *, max_file_bytes: int = 512_000) -> None:
        resolved = root.expanduser().resolve()
        if not resolved.is_dir():
            raise LocalAgentError(f"프로젝트 디렉터리를 찾을 수 없습니다: {resolved}")
        if max_file_bytes < 1:
            raise LocalAgentError("파일 크기 제한은 1 이상이어야 합니다.")
        self.root = resolved
        self.max_file_bytes = max_file_bytes

    def files(self) -> list[FileInfo]:
        result: list[FileInfo] = []
        for current, dirs, names in os.walk(self.root, topdown=True, followlinks=False):
            dirs[:] = sorted(
                directory
                for directory in dirs
                if directory.lower() not in DEFAULT_IGNORED_DIRS
                and not (Path(current) / directory).is_symlink()
            )
            for name in sorted(names):
                path = Path(current) / name
                relative = path.relative_to(self.root).as_posix()
                if path.is_symlink() or self._ignored_file(relative):
                    continue
                try:
                    size = path.stat().st_size
                except OSError:
                    continue
                if size > self.max_file_bytes or not self._is_text_candidate(path):
                    continue
                result.append(FileInfo(path, relative, size))
        return result

    def read(self, file: FileInfo) -> str:
        self._ensure_inside_root(file.path)
        try:
            data = file.path.read_bytes()
        except OSError as exc:
            raise LocalAgentError(f"파일 읽기 실패: {file.relative}: {exc}") from exc
        if b"\x00" in data[:8192]:
            return ""
        return data.decode("utf-8", errors="replace")

    def search(self, pattern: str, *, max_results: int = 100) -> list[SearchMatch]:
        if max_results < 1:
            raise LocalAgentError("검색 결과 제한은 1 이상이어야 합니다.")
        try:
            expression = re.compile(pattern, re.IGNORECASE)
        except re.error as exc:
            raise LocalAgentError(f"잘못된 정규식입니다: {exc}") from exc
        matches: list[SearchMatch] = []
        for file in self.files():
            text = self.read(file)
            for number, line in enumerate(text.splitlines(), start=1):
                if expression.search(line):
                    matches.append(SearchMatch(file.relative, number, line.strip()[:300]))
                    if len(matches) >= max_results:
                        return matches
        return matches

    def context(self, question: str, *, max_chars: int = 48_000, max_files: int = 20) -> str:
        if max_chars < 1 or max_files < 1:
            raise LocalAgentError("컨텍스트 크기와 파일 수 제한은 1 이상이어야 합니다.")
        terms = {term.lower() for term in re.findall(r"[\w.-]{3,}", question, re.UNICODE)}
        candidates: list[tuple[int, FileInfo, str]] = []
        for file in self.files():
            text = self.read(file)
            if not text:
                continue
            path_lower = file.relative.lower()
            text_lower = text.lower()
            score = sum(8 for term in terms if term in path_lower)
            score += sum(min(text_lower.count(term), 10) for term in terms)
            candidates.append((score, file, text))
            if len(candidates) > max_files:
                candidates.sort(key=lambda item: (-item[0], item[1].relative))
                del candidates[max_files:]
        candidates.sort(key=lambda item: (-item[0], item[1].relative))

        sections: list[str] = []
        used = 0
        for _, file, text in candidates:
            header = f"\n--- FILE: {file.relative} ---\n"
            remaining = max_chars - used - len(header)
            if remaining <= 0:
                break
            excerpt = text[:remaining]
            sections.append(header + excerpt)
            used += len(header) + len(excerpt)
            if used >= max_chars:
                break
        return "".join(sections).lstrip()

    def summary(self) -> str:
        files = self.files()
        total = sum(item.size for item in files)
        by_extension: dict[str, int] = {}
        for item in files:
            extension = item.path.suffix.lower() or "(없음)"
            by_extension[extension] = by_extension.get(extension, 0) + 1
        extensions = ", ".join(
            f"{extension} {count}개"
            for extension, count in sorted(by_extension.items(), key=lambda pair: (-pair[1], pair[0]))[:12]
        )
        return f"루트: {self.root}\n텍스트 파일: {len(files)}개\n총 크기: {total:,} bytes\n유형: {extensions or '없음'}"

    def _ensure_inside_root(self, path: Path) -> None:
        try:
            path.resolve().relative_to(self.root)
        except ValueError as exc:
            raise LocalAgentError(f"작업공간 밖의 파일은 읽을 수 없습니다: {path}") from exc

    @staticmethod
    def _ignored_file(relative: str) -> bool:
        relative_lower = relative.lower()
        name_lower = Path(relative).name.lower()
        return any(fnmatch.fnmatch(name_lower, pattern) for pattern in DEFAULT_IGNORED_FILES) or any(
            fnmatch.fnmatch(relative_lower, pattern) for pattern in DEFAULT_IGNORED_PATHS
        )

    @staticmethod
    def _is_text_candidate(path: Path) -> bool:
        return path.suffix.lower() in TEXT_EXTENSIONS or path.name in {
            "CMakeLists.txt", "Dockerfile", "LICENSE", "Makefile"
        }
