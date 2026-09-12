#!/usr/bin/env python3
"""Make the register dataset agree with the refinery dossier on `model`.

The dossier's Section 4 register carries curated, kind-appropriate commercial
model designations. `equipment.json` used to carry tag-masked placeholders
(`P-1001` → `P-101X`); it was patched once from a local table, which left the
two sources disagreeing on all 58 units.

This makes the dossier the authority for `model` and writes its values back into
the dataset, so one canonical value exists and both agree. Only `model` is
written; every other field is untouched.

Run:  python3 scripts/sync_register_models.py
Exit 0 only if all 58 units agree afterwards.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DOC = REPO / "data" / "knowledge" / "REFINERY-TECHNICAL-KNOWLEDGE-BASE.md"
TARGET = REPO / "apps" / "web" / "public" / "simulation" / "refinery" / "equipment.json"

# The register table lives under "### 4.1"; stop at the next heading of any level.
REGISTER = re.compile(r"### 4\.1[^\n]*\n(.*?)(?=\n###|\n## )", re.S)
MODEL_TAG = re.compile(r"^[A-Z]{1,4}-\d+X$")


def parse_register(text: str) -> dict[str, str]:
    m = REGISTER.search(text)
    if not m:
        raise SystemExit("could not locate the ### 4.1 register table in the dossier")
    rows = [line for line in m.group(1).splitlines() if line.strip().startswith("|")]
    rows = [r for r in rows if not re.match(r"^\|[\s:|-]+\|$", r.strip())]
    out: dict[str, str] = {}
    for r in rows[1:]:
        cells = [c.strip() for c in r.strip().strip("|").split("|")]
        if len(cells) >= 11:
            out[cells[0]] = cells[7]
    return out


def main() -> int:
    doc_models = parse_register(DOC.read_text(encoding="utf-8"))
    units = json.loads(TARGET.read_text(encoding="utf-8"))
    print(f"dossier register models: {len(doc_models)}   dataset units: {len(units)}")

    masked_doc = [t for t, m in doc_models.items() if MODEL_TAG.match(m)]
    if masked_doc:
        print(f"refusing to sync: dossier still has masked models {masked_doc[:5]}", file=sys.stderr)
        return 1

    missing = [u["tag"] for u in units if u["tag"] not in doc_models]
    if missing:
        print(f"refusing to sync: dossier has no model for {missing[:5]}", file=sys.stderr)
        return 1

    changed = 0
    for u in units:
        want = doc_models[u["tag"]]
        if u.get("model") != want:
            u["model"] = want
            changed += 1
    TARGET.write_text(json.dumps(units, indent=1) + "\n", encoding="utf-8")

    after = json.loads(TARGET.read_text(encoding="utf-8"))
    agree = sum(1 for u in after if u.get("model") == doc_models[u["tag"]])
    masked_ds = [u["tag"] for u in after if MODEL_TAG.match(str(u.get("model", "")))]

    print(f"models rewritten: {changed}")
    print(f"agreement afterwards: {agree}/{len(after)}")
    print(f"masked models remaining in dataset: {len(masked_ds)}")
    ok = agree == len(after) and not masked_ds
    print("RESULT:", "PASS" if ok else "FAIL")
    if ok:
        for u in after[:5]:
            print(f"   {u['tag']:<10} {u.get('kind',''):<10} {u['model']}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
