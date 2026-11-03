"""Minimal .env reader/writer (no third-party dependency)."""

import os
from pathlib import Path
from typing import Dict

_COMMENT_PREFIX = "#"
_SEPARATOR = "="
_ALLOWED_KEY_PREFIX = "DCP_"
_FORBIDDEN_VALUE_CHARS = ("\r", "\n", "\0")


def _parse_line(line: str):
    """Return (key, value) for a KEY=VALUE line, or None for blanks/comments."""
    stripped = line.strip()
    if not stripped or stripped.startswith(_COMMENT_PREFIX) or _SEPARATOR not in stripped:
        return None
    key, _, value = stripped.partition(_SEPARATOR)
    return key.strip(), value.strip().strip("'\"")


def load_env_file(path: Path) -> None:
    """Load KEY=VALUE pairs into os.environ without overriding existing vars.

    Real environment variables win so a shell override always beats the file.
    """
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        parsed = _parse_line(line)
        if parsed and parsed[0].startswith(_ALLOWED_KEY_PREFIX):
            os.environ.setdefault(*parsed)


def write_env_values(path: Path, values: Dict[str, str]) -> None:
    """Upsert keys in the .env file, preserving unrelated lines and comments.

    Raises ValueError on newline/NUL in keys or values to block line injection.
    """
    for key, value in values.items():
        if any(c in value or c in key for c in _FORBIDDEN_VALUE_CHARS):
            raise ValueError(f"Control characters are not allowed in {key!r}")
    lines = path.read_text(encoding="utf-8").splitlines() if path.is_file() else []
    remaining = dict(values)
    out = []
    for line in lines:
        parsed = _parse_line(line)
        if parsed and parsed[0] in remaining:
            out.append(f"{parsed[0]}={remaining.pop(parsed[0])}")
        else:
            out.append(line)
    out.extend(f"{key}={value}" for key, value in remaining.items())
    path.write_text("\n".join(out) + "\n", encoding="utf-8")
