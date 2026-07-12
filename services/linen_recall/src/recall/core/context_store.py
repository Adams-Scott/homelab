from __future__ import annotations

from pathlib import Path


def ensure_context_file(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text("", encoding="utf-8")
    return path


def load_context_text(path: Path) -> str:
    context_path = ensure_context_file(path)
    return context_path.read_text(encoding="utf-8")


def save_context_text(path: Path, content: str) -> Path:
    context_path = ensure_context_file(path)
    context_path.write_text(content, encoding="utf-8")
    return context_path