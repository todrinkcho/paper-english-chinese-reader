#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""paper-english-chinese-reader / reflow
Re-run only the reading-order step on an existing blocks.json, keeping every
block id and its bbox intact. Translations live in tr/*.json keyed by id, so
they survive; no retranslation is needed.

    python3 reflow.py "C:/abs/path/paper.xml" -o "C:/abs/path/paper_pbr"
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys

try:
    import pymupdf as fitz
except ImportError:
    try:
        import fitz
    except ImportError:
        sys.stderr.write("ERROR: PyMuPDF is required.\n  pip install -U pymupdf pillow\n")
        raise SystemExit(2)

for _s in ("stdout", "stderr"):
    try:
        getattr(sys, _s).reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

HERE = os.path.dirname(os.path.abspath(__file__))


def load_extract():
    """Import extract.py as a module so the ordering logic stays single-sourced."""
    p = os.path.join(HERE, "extract.py")
    spec = importlib.util.spec_from_file_location("pbr_extract", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pdf")
    ap.add_argument("-o", "--out", required=True, help="the existing *_pbr folder")
    ap.add_argument("--cols", type=int, default=0, help="force column count (0=auto)")
    ap.add_argument("--no-split", action="store_true", help="disable column detection")
    ap.add_argument("--dry-run", action="store_true", help="report only, do not write")
    a = ap.parse_args()

    ex = load_extract()

    src = os.path.abspath(a.pdf)
    out = os.path.abspath(a.out)
    bj = os.path.join(out, "blocks.json")
    if not os.path.isfile(bj):
        print("ERROR: no blocks.json in " + out)
        return 2

    data = json.load(open(bj, encoding="utf-8"))
    blocks = data["blocks"]
    meta = data["meta"]
    ids = set(b["id"] for b in blocks)

    doc = fitz.open(src)

    # Group existing blocks by page; anything without a bbox keeps its place.
    by_page = {}
    for b in blocks:
        by_page.setdefault(b["page"], []).append(b)

    new_blocks = []
    changed = 0
    lost, gained = set(), set()

    for pno in range(1, meta["pages"] + 1):
        page_blocks = by_page.get(pno, [])
        if not page_blocks:
            continue
        page = doc[pno - 1]
        pw = page.rect.width
        ph = page.rect.height

        items = []
        for b in page_blocks:
            bb = b.get("bbox")
            items.append({
                "kind": "text",
                "bbox": tuple(bb) if bb else (0.0, 0.0, 0.0, 0.0),
                "text": b.get("text", ""),
                "size": b.get("size", meta.get("body_size", 10.0)),
                "bold": b.get("bold", False),
                "block": b,
            })

        if a.cols == 2:
            split = pw / 2.0
        elif a.no_split or a.cols == 1:
            split = None
        else:
            split = ex.detect_split(items, pw)

        ordered = ex.order_items(items, split, pw)
        for it in ordered:
            new_blocks.append(it["block"])
        old_ids = [b["id"] for b in page_blocks]
        new_ids = [it["block"]["id"] for it in ordered]
        if old_ids != new_ids:
            changed += 1

    missing = ids - set(b["id"] for b in new_blocks)
    if missing:
        print("WARN: %d blocks lost, appending at the end: %s" % (len(missing), sorted(missing)))
        for b in blocks:
            if b["id"] in missing:
                new_blocks.append(b)

    print("blocks: %d -> %d   order changed on %d page(s)" % (len(blocks), len(new_blocks), changed))
    if a.dry_run:
        print("dry run, nothing written")
        return 0

    data["blocks"] = new_blocks
    tmp = bj + ".bak"
    if not os.path.exists(tmp):
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"blocks": blocks, "meta": meta}, f, ensure_ascii=False, indent=1)
        print("backup : " + tmp)
    with open(bj, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    print("updated: " + bj)
    print("Now rebuild the HTML:  python3 build_html.py \"%s\" -o <out.html>" % out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
