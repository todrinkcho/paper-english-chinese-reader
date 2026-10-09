#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""paper-bilingual-reader / step 4
glossary.json -> CSV (UTF-8 with BOM so Excel opens Chinese correctly)
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys

for _s in ("stdout", "stderr"):
    try:
        getattr(sys, _s).reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("glossary")
    ap.add_argument("-o", "--out", default=None)
    a = ap.parse_args()

    src = os.path.abspath(a.glossary)
    with open(src, "r", encoding="utf-8") as f:
        g = json.load(f)
    terms = g.get("terms", g) if isinstance(g, dict) else g
    terms = [t for t in terms if isinstance(t, dict) and t.get("en")]

    seen, rows = set(), []
    for t in terms:
        key = (t.get("en", "").strip().lower(), t.get("zh", "").strip())
        if key in seen:
            continue
        seen.add(key)
        rows.append((t.get("en", "").strip(), t.get("zh", "").strip(), t.get("note", "") or ""))
    rows.sort(key=lambda r: r[0].lower())

    out = os.path.abspath(a.out) if a.out else os.path.join(os.path.dirname(src), "glossary.csv")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["English", "中文", "备注"])
        w.writerows(rows)

    print("terms : %d" % len(rows))
    print("csv   : %s" % out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
