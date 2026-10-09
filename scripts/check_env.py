#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""paper-bilingual-reader / step 0
Verify the environment before running the pipeline.
Usage:  python3 check_env.py
"""
import os
import sys

for _s in ("stdout", "stderr"):
    try:
        getattr(sys, _s).reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

ok = True


def check(label, fn):
    global ok
    try:
        fn()
        print("  [ok]   %s" % label)
    except Exception as e:
        ok = False
        print("  [FAIL] %s -> %s" % (label, e))


print("python   : %s" % sys.version.split()[0])
print("skill dir: %s" % ROOT)


def _py():
    if sys.version_info < (3, 9):
        raise RuntimeError("Python 3.9+ required")


def _mupdf():
    try:
        import pymupdf  # noqa: F401
    except ImportError:
        import fitz  # noqa: F401


def _pillow():
    import PIL  # noqa: F401


def _scripts():
    for f in ("extract.py", "build_html.py", "make_glossary.py"):
        p = os.path.join(HERE, f)
        if not os.path.isfile(p):
            raise RuntimeError("missing " + f)


def _template():
    p = os.path.join(ROOT, "assets", "reader_template.html")
    if not os.path.isfile(p):
        raise RuntimeError("missing assets/reader_template.html")


check("python >= 3.9", _py)
check("PyMuPDF (pip install -U pymupdf)", _mupdf)
check("Pillow (pip install -U pillow)", _pillow)
check("scripts/*.py present", _scripts)
check("assets/reader_template.html present", _template)

print()
if ok:
    print("READY. Next: python3 %s <paper.pdf> -o <workdir>" % os.path.join(HERE, "extract.py"))
else:
    print("NOT READY - fix the items above, then re-run.")
sys.exit(0 if ok else 1)
