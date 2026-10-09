#!/usr/bin/env python3
"""Build per-record field_values JSON for the OF-306 batch fill.

Reads the frozen manifest (field_rules) + synthetic applicant records and the
inspected form_field_info.json (for authoritative field_ids, pages and types).
Writes output/field_values/<id>.json with ONLY the manifest field rules.
Protected fields are never emitted (they stay blank).
"""
import json
import sys
from pathlib import Path

WORK = Path(__file__).resolve().parent.parent
INPUT = WORK / "input"
OUT = WORK / "output"


def load_json(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def resolve_value(rule, record, shared):
    """Return the raw value for a rule, applying constant / choices / shared."""
    # explicit constant (e.g. "United States" or "/No")
    if "constant" in rule and "choices" not in rule:
        return rule["constant"]
    # boolean -> choice mapping
    if "choices" in rule:
        raw = record[rule["value_from"]]
        return rule["choices"]["true" if raw else "false"]
    # shared answers
    if rule.get("source") == "shared":
        path = rule["value_from"]  # e.g. shared_answers.continuation
        parts = path.split(".")
        cur = {"shared_answers": shared, "record": record}
        node = cur.get(parts[0])
        for p in parts[1:]:
            node = node[p]
        return node
    # plain record field
    return record[rule["value_from"]]


def main():
    manifest = load_json(INPUT / "dataset_manifest.json")
    records_doc = load_json(INPUT / manifest["records"])
    records = records_doc[manifest["records_key"]]
    shared = records_doc.get("shared_answers", {})
    rules = manifest["requirements"]["field_rules"]

    field_info = load_json(OUT / "form_field_info.json")
    by_id = {f["field_id"]: f for f in field_info}

    outdir = OUT / "field_values"
    outdir.mkdir(parents=True, exist_ok=True)

    written = []
    for rec in records:
        rid = rec["id"]
        entries = []
        for rule in rules:
            fid = rule["field_id"]
            info = by_id.get(fid)
            if info is None:
                raise SystemExit(f"Field id not found in inspection: {fid!r}")
            value = resolve_value(rule, rec, shared)
            entries.append({
                "field_id": fid,
                "description": rule.get("semantic", fid),
                "page": info["page"],
                "value": value,
            })
        path = outdir / f"{rid}.json"
        path.write_text(json.dumps(entries, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8")
        written.append(str(path))
    print(f"Wrote {len(written)} field_values files to {outdir}")
    for w in written:
        print(" ", w)


if __name__ == "__main__":
    main()
