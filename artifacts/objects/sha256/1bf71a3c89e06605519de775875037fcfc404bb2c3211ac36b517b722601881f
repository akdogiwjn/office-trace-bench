#!/usr/bin/env python3
"""Batch driver: fill one PDF per record and render each filled PDF.

Invokes the Skill scripts exactly once per record for fill, and once per filled
PDF for render. Counts every invocation (successful or failed) and writes a
machine-readable invocation log.
"""
import json
import subprocess
import sys
from pathlib import Path

WORK = Path(__file__).resolve().parent.parent
SCRIPTS = Path("/root/.openclaw/skills/pdf/scripts")
INPUT = WORK / "input"
OUT = WORK / "output"

FILL = SCRIPTS / "fill_fillable_fields.py"
RENDER = SCRIPTS / "convert_pdf_to_images.py"

TEMPLATE = INPUT / "of306_aug2023.pdf"


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def run(cmd):
    """Run a subprocess, return (returncode, stdout, stderr)."""
    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=str(SCRIPTS))
    return proc.returncode, proc.stdout, proc.stderr


def main():
    records_doc = load(INPUT / "synthetic_applicants.json")
    applicants = records_doc["applicants"]

    fill_invocations = []
    render_invocations = []

    for rec in applicants:
        rid = rec["id"]
        values = OUT / "field_values" / f"{rid}.json"
        filled = OUT / "filled" / f"{rid}.pdf"
        render_dir = OUT / "rendered" / rid

        # ---- fill (exactly one invocation per record) ----
        cmd = [sys.executable, str(FILL), str(TEMPLATE), str(values), str(filled)]
        rc, out, err = run(cmd)
        fill_invocations.append({"id": rid, "cmd": cmd, "rc": rc,
                                 "stdout": out.strip(), "stderr": err.strip()})
        if rc != 0:
            print(f"FILL FAILED for {rid}: rc={rc}\n{out}\n{err}")
            continue

        # ---- render filled PDF (exactly one invocation per filled PDF) ----
        render_dir.mkdir(parents=True, exist_ok=True)
        cmd = [sys.executable, str(RENDER), str(filled), str(render_dir)]
        rc, out, err = run(cmd)
        render_invocations.append({"id": rid, "cmd": cmd, "rc": rc,
                                   "stdout": out.strip(), "stderr": err.strip()})
        if rc != 0:
            print(f"RENDER FAILED for {rid}: rc={rc}\n{out}\n{err}")

    log = {
        "fill_invocations": fill_invocations,
        "render_invocations": render_invocations,
        "fill_invocation_count": len(fill_invocations),
        "render_invocation_count": len(render_invocations),
        "fill_success": sum(1 for i in fill_invocations if i["rc"] == 0),
        "render_success": sum(1 for i in render_invocations if i["rc"] == 0),
    }
    (OUT / "invocation_log.json").write_text(
        json.dumps(log, indent=2) + "\n", encoding="utf-8")
    print(f"fill invocations: {log['fill_invocation_count']} "
          f"(success {log['fill_success']})")
    print(f"render invocations: {log['render_invocation_count']} "
          f"(success {log['render_success']})")


if __name__ == "__main__":
    main()
