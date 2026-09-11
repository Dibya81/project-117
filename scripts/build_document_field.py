#!/usr/bin/env python3
"""Build the web artifact the Documents page renders as moving pages.

Reads Project 117's own knowledge corpus:

    data/knowledge/*.md              SOPs and operating policies
    data/knowledge/refinery/*.md     the generated 5-year knowledge base
    data/demo/**/*.md                inspection reports, manuals, records

and emits

    apps/web/public/knowledge/refinery-document.json

one entry per document section, carrying the real heading, body lines, the
first table it finds, and the entity tags mentioned in the text. Nothing is
invented: if the corpus does not contain it, it is not in the output.

Run:  python3 scripts/build_document_field.py
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SOURCES = [
    REPO / "data" / "knowledge" / "refinery",
    REPO / "data" / "knowledge",
    REPO / "data" / "demo",
]
OUT = REPO / "apps" / "web" / "public" / "knowledge" / "refinery-document.json"

# Entity shapes that actually appear in this corpus.
ENTITY_RE = re.compile(
    r"\b(?:"
    r"[A-Z]{2,4}-\d{2,4}[A-Z]?"      # C-3, P-1042, TK-1101, PT-1001A, SOP-14.2 handled below
    r"|(?:SOP|OPS|IR|ME|WO|INC|EV|APR|A)-\d+(?:\.\d+)?(?:[A-Za-z]*)?"  # SOP-14.2, IR-204, WO-8852
    r"|\d+\.\d+\s*mm/s"
    r"|\d+\s*bar"
    r"|\d[\d,]*\s*rpm"
    r")\b"
)
FRONTMATTER = re.compile(r"^---\n.*?\n---\n", re.DOTALL)


def first_heading(text: str) -> str:
    for line in text.splitlines():
        if line.startswith("#"):
            return line.lstrip("# ").strip()
    return "Untitled section"


def tables(text: str) -> list[list[str]]:
    """Return the first markdown table as a list of rows."""
    rows: list[list[str]] = []
    in_table = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("|") and stripped.endswith("|"):
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            if all(set(c) <= set("-: ") for c in cells):
                continue  # separator row
            if not in_table:
                in_table = True
            rows.append(cells)
            if len(rows) >= 4:
                break
        elif in_table:
            break
    return rows


def body_lines(text: str, limit: int = 7) -> list[str]:
    out: list[str] = []
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("#") or s.startswith("|") or s.startswith("---"):
            continue
        s = re.sub(r"^[-*]\s+", "", s)
        s = re.sub(r"\*\*(.+?)\*\*", r"\1", s)
        s = re.sub(r"`(.+?)`", r"\1", s)
        if len(s) < 24:
            continue
        out.append(s)
        if len(out) >= limit:
            break
    return out


def slug(path: Path) -> str:
    return re.sub(r"[^a-z0-9]+", "-", path.stem.lower()).strip("-")


def kind_for(name: str) -> str:
    n = name.lower()
    if "ir-" in n or "inspection" in n:
        return "inspection"
    if "sop" in n or "ops" in n:
        return "procedure"
    if "baseline" in n:
        return "baseline"
    if "manual" in n:
        return "manual"
    if "me-" in n or "record" in n or "history" in n:
        return "record"
    return "register"


# Project 117's demo domain is the refinery. The corpus also carries a
# steelmaking thread from an earlier phase; it stays on disk but is not part of
# the refinery document archive.
STEEL_MARKERS = ("steel", "ironmaking", "steelmaking", "blast furnace", "bof", "caster")


def is_steel(path: Path, text: str) -> bool:
    hay = f"{path.stem}\n{text[:4000]}".lower()
    return any(m in hay for m in STEEL_MARKERS)


def main() -> int:
    sections: list[dict] = []
    seen: set[str] = set()
    skipped_steel = 0

    for root in SOURCES:
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*.md")):
            if path.name.lower().startswith(("readme", "manifest")):
                continue
            raw = path.read_text(encoding="utf-8", errors="ignore")
            text = FRONTMATTER.sub("", raw, count=1)
            if is_steel(path, text):
                skipped_steel += 1
                continue
            title = first_heading(text)
            slug_ = slug(path)
            if slug_ in seen:
                continue
            seen.add(slug_)
            ents = sorted({m.group(0) for m in ENTITY_RE.finditer(text)})[:8]
            sections.append({
                "slug": slug_,
                "title": title,
                "doc": path.name,
                "source": str(path.relative_to(REPO)),
                "kind": kind_for(path.name),
                "lines": body_lines(text),
                "table": tables(text) or None,
                "entities": ents,
                "chars": len(text),
            })

    sections.sort(key=lambda s: -s["chars"])

    payload = {
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source_dirs": [str(s.relative_to(REPO)) for s in SOURCES if s.is_dir()],
        "count": len(sections),
        "skipped_steel": skipped_steel,
        "sections": sections,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {OUT.relative_to(REPO)}  {OUT.stat().st_size / 1024:.0f} KB")
    print(f"  {len(sections)} refinery document sections ({skipped_steel} steel docs skipped)")
    for s in sections[:6]:
        print(f"    {s['doc']:<44} {len(s['lines'])} lines, {len(s['table'] or [])} table rows, {len(s['entities'])} entities")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
