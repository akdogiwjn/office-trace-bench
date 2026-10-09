#!/usr/bin/env python3
"""Copy host OpenClaw state into an ephemeral container, like the original runner."""

from __future__ import annotations

import fnmatch
import shutil
import sys
from pathlib import Path


EXCLUDES = (
    "agents/*/sessions",
    "logs",
    "cache",
    "media",
    "attachments",
    "generated_images",
    "shell_snapshots",
    "tmp",
    ".tmp",
)


def is_excluded(relative_path: str) -> bool:
    normalized = relative_path.strip("/")
    return any(
        fnmatch.fnmatch(normalized, pattern)
        or normalized.startswith(f"{pattern}/")
        for pattern in EXCLUDES
    )


def main() -> int:
    if len(sys.argv) != 3:
        print(f"usage: {sys.argv[0]} SOURCE DESTINATION", file=sys.stderr)
        return 2

    source = Path(sys.argv[1]).resolve()
    destination = Path(sys.argv[2])
    if not (source / "openclaw.json").is_file():
        print(f"missing {source / 'openclaw.json'}", file=sys.stderr)
        return 2
    if destination.exists():
        print(f"destination already exists: {destination}", file=sys.stderr)
        return 2

    def ignore(directory: str, names: list[str]) -> set[str]:
        relative_directory = Path(directory).relative_to(source)
        return {
            name
            for name in names
            if is_excluded((relative_directory / name).as_posix())
        }

    shutil.copytree(source, destination, symlinks=True, ignore=ignore)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
