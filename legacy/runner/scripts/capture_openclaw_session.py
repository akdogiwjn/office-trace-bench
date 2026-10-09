#!/usr/bin/env python3
"""Capture the OpenClaw JSONL selected by stdout metadata or session key."""

from __future__ import annotations

import glob
import json
import shutil
import sys
from pathlib import Path

case_id = sys.argv[1]
stdout_path = Path(sys.argv[2])
target_path = Path(sys.argv[3])
status_path = target_path.with_name("session_capture.json")
status: dict[str, object] = {
    "case_id": case_id,
    "strategy": "not-found",
    "source": None,
    "target": str(target_path),
    "bytes": 0,
}


def copy_session(source: Path, strategy: str) -> bool:
    if not source.is_file():
        return False
    target_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target_path)
    status.update(
        strategy=strategy,
        source=str(source),
        bytes=target_path.stat().st_size,
    )
    return True


try:
    stdout_data = json.loads(stdout_path.read_text(errors="replace"))
except (OSError, json.JSONDecodeError):
    stdout_data = {}

session_file = (
    stdout_data.get("meta", {}).get("agentMeta", {}).get("sessionFile")
    if isinstance(stdout_data, dict)
    else None
)
captured = copy_session(Path(session_file), "found-by-meta") if session_file else False

if not captured:
    candidates: list[Path] = []
    for pattern in (
        "/root/.openclaw/agents/main/sessions/*.jsonl",
        "/root/.openclaw/agents/*/sessions/*.jsonl",
    ):
        candidates.extend(Path(value) for value in glob.glob(pattern))
    candidates = [path for path in candidates if path.is_file()]
    session_key = f"agent:main:{case_id}"
    keyed = []
    for path in candidates:
        try:
            sample = path.read_text(errors="replace")[:200_000]
        except OSError:
            sample = ""
        if case_id in sample or session_key in sample:
            keyed.append(path)
    choices = keyed or sorted(
        candidates, key=lambda path: path.stat().st_mtime, reverse=True
    )
    if choices:
        copy_session(
            choices[0],
            "found-by-session-key" if keyed else "found-by-newest-session",
        )

status_path.write_text(json.dumps(status, indent=2, ensure_ascii=False) + "\n")
print(json.dumps(status, ensure_ascii=False))

