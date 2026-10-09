#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""paper-english-chinese-reader / step 1
Turn a PDF into a structured intermediate layer:
    blocks.json  +  assets/*.png (figures)  +  pages/*.jpg (page renders)
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter

try:  # PyMuPDF >= 1.24 renamed the import; support both
    import pymupdf as fitz
except ImportError:
    try:
        import fitz
    except ImportError:
        sys.stderr.write(
            "ERROR: PyMuPDF is required.\n"
            "  pip install -U pymupdf pillow\n")
        raise SystemExit(2)

for _s in ("stdout", "stderr"):
    try:
        getattr(sys, _s).reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

CAPTION_RE = re.compile(
    r"^\s*(Figure|Fig\.?|Scheme|Table|Chart|Graph|Plate)\s*S?\s?\d*\s*[.:|]", re.I
)
CAPTION_LOOSE_RE = re.compile(
    r"^\s*(Figure|Fig\.?|Scheme|Table|Chart|Graph|Plate)\b", re.I
)
REF_SECTION_RE = re.compile(
    r"^\s*(references|notes and references|reference list|literature cited)\s*$", re.I
)
LIST_RE = re.compile(r"^\s*(\d{1,2}|[a-z])[\.\)]\s+\S")
# journal furniture: running heads, footers, category labels
NOISE_RE = re.compile(
    r"(Wiley-VCH|Angewandte|Chemie Forschungsartikel|Forschungsartikel|Hot Paper|"
    r"^\s*\(\d+\s+of\s+\d+\)|Royal Society of Chemistry|American Chemical Society|"
    r"^\s*www\.|Received:|Accepted:|Published online|Downloaded from)", re.I
)
# a bibliography entry such as "[12] A. Author, J. Am. Chem. Soc. 2019, 141, 1-9."
REF_ENTRY_RE = re.compile(r"^\s*\[\d+\]")
CITATION_RE = re.compile(r"\b(19|20)\d{2}\s*,\s*\d+")
MIN_FIG_W, MIN_FIG_H = 70.0, 45.0
# math / symbol fonts: text pulled out of these is almost always mojibake,
# so their region is rendered as an image instead
MATH_FONT_RE = re.compile(
    r"(TeX_CM_Maths|CMMI|CMSY|CMEX|MSAM|MSBM|Symbol|MT\s*Extra|Greek|"
    r"MathType|Euclid|LucidaNewMath|Cambria\s*Math)", re.I
)
# NB: some publishers encode glyphs such as the minus sign at control code
# points, so a single control char means nothing - only a high density does.
CTRL_DENSITY = 0.06
CTRL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


# ---------------------------------------------------------------- text helpers
def clean(s: str) -> str:
    s = s.replace("\u00ad", "").replace("\u200b", "")
    return re.sub(r"[ \t]+", " ", s).strip()


def join_text(a, b):
    """Join two fragments that were split across a line or column break."""
    if not a:
        return b
    if not b:
        return a
    if a.rstrip().endswith(("-", "–", "—")) and not a.rstrip().endswith("--"):
        nxt = b.lstrip()[:1]
        if nxt.islower() or nxt.isdigit():
            return a.rstrip()[:-1] + b.lstrip()
    return a + " " + b


def block_text(b):
    """Return (text, dominant size, mostly-bold, math-char ratio, has control chars)."""
    lines, sizes = [], []
    bold_chars = total_chars = math_chars = 0
    ctrl = False
    for line in b.get("lines", []):
        parts = []
        for sp in line.get("spans", []):
            t = sp.get("text", "")
            if not t:
                continue
            parts.append(t)
            sizes.append(round(sp.get("size", 0.0), 1))
            n = len(t.strip())
            total_chars += n
            f = sp.get("font") or ""
            if "bold" in f.lower() or (sp.get("flags", 0) & 16):
                bold_chars += n
            if MATH_FONT_RE.search(f):
                math_chars += n
            if CTRL_RE.search(t):
                ctrl = True
        ln = "".join(parts).strip()
        if ln:
            lines.append(ln)
    if not lines:
        return "", 0.0, False, 0.0, False
    out = lines[0]
    for ln in lines[1:]:
        out = join_text(out, ln)
    size = Counter(sizes).most_common(1)[0][0] if sizes else 0.0
    bold = total_chars > 0 and bold_chars / total_chars > 0.6
    math_ratio = (math_chars / total_chars) if total_chars else 0.0
    return clean(out), size, bold, math_ratio, ctrl


def rows_to_md(rows):
    if not rows:
        return ""
    width = max(len(r) for r in rows)
    norm = [list(r) + [""] * (width - len(r)) for r in rows]
    out = ["| " + " | ".join(str(c).replace("|", "\\|") for c in norm[0]) + " |",
           "| " + " | ".join(["---"] * width) + " |"]
    for r in norm[1:]:
        out.append("| " + " | ".join(str(c).replace("|", "\\|") for c in r) + " |")
    return "\n".join(out)


# ------------------------------------------------------------ layout analysis
def detect_split(items, page_width: float):
    """Find the vertical whitespace band that separates two columns.
    Full-width blocks (titles, banners) are ignored - they would fill the gutter."""
    res = 120
    hist = [0.0] * res
    narrow = []
    for it in items:
        x0, x1 = it["bbox"][0], it["bbox"][2]
        if x1 <= x0:
            continue
        if x1 - x0 > page_width * 0.62:
            continue
        narrow.append(it)
        for i in range(res):
            a = page_width * i / res
            c = page_width * (i + 1) / res
            ov = max(0.0, min(x1, c) - max(x0, a))
            if ov > 0:
                hist[i] += ov * (it["bbox"][3] - it["bbox"][1])
    if not any(hist):
        return None
    lo, hi = int(res * 0.30), int(res * 0.70)
    best_len, best_mid = 0, None
    i = lo
    while i < hi:
        if hist[i] <= 0:
            j = i
            while j < hi and hist[j] <= 0:
                j += 1
            if j - i > best_len:
                best_len = j - i
                best_mid = (i + j) / 2 / res * page_width
            i = j
        else:
            i += 1
    if best_len >= 3 and best_mid:
        return best_mid

    # fallback: a clean left / right split around the page centre
    if len(narrow) >= 6:
        c = page_width / 2.0
        nl = sum(1 for it in narrow if it["bbox"][2] <= c)
        nr = sum(1 for it in narrow if it["bbox"][0] >= c)
        if nl >= 2 and nr >= 2 and (nl + nr) / len(narrow) >= 0.75:
            return c
    return None


def _spans_columns(it, split, page_width, has_left=True, has_right=True):
    """Does this block cross the gutter *and* live inside the two-column body?

    A page-wide masthead or a full-width title sits in the margins above the body,
    so it must not be mistaken for a flow separator - hence the width cap.
    A spanning block also needs a real column on *both* sides to separate, so a
    full-width footnote / reference list on an otherwise one-column page is not
    treated as a separator either.
    """
    if not (has_left and has_right):
        return False
    x0, x1 = it["bbox"][0], it["bbox"][2]
    return x0 < split < x1 and (x1 - x0) <= page_width * 0.75


def order_items(items, split, page_width):
    """Reading order: single column -> by y; two columns -> left stream then right
    stream, cut into segments by any block that spans both columns."""
    if split is None:
        return sorted(items, key=lambda it: (round(it["bbox"][1] / 5), it["bbox"][0]))

    def is_spanning(it):
        x0, x1 = it["bbox"][0], it["bbox"][2]
        return x0 < split < x1 and (x1 - x0) <= page_width * 0.75

    cand = [it for it in items if is_spanning(it)]
    others = [it for it in items if not is_spanning(it)]
    # A spanning block only separates two columns if there really are two columns.
    has_left = any(it["bbox"][2] <= split for it in others)
    has_right = any(it["bbox"][0] >= split for it in others)

    left, right, mid = [], [], []
    for it in items:
        x0, x1 = it["bbox"][0], it["bbox"][2]
        if _spans_columns(it, split, page_width, has_left, has_right):
            mid.append(it)
        elif (x0 + x1) / 2 < split:
            left.append(it)
        else:
            right.append(it)
    for lst in (left, right, mid):
        lst.sort(key=lambda it: (round(it["bbox"][1] / 5), it["bbox"][0]))
    out, li, ri = [], 0, 0

    def flush_strict(y_end):
        """Columns flow in parallel: emit everything that ends above y_end."""
        nonlocal li, ri
        while li < len(left) and left[li]["bbox"][3] <= y_end:
            out.append(left[li]); li += 1
        while ri < len(right) and right[ri]["bbox"][3] <= y_end:
            out.append(right[ri]); ri += 1

    def flush_all(y_end):
        """Columns are independent beyond y_end: drain the left one completely."""
        nonlocal li, ri
        while li < len(left) and left[li]["bbox"][1] < y_end:
            out.append(left[li]); li += 1
        while ri < len(right) and right[ri]["bbox"][1] < y_end:
            out.append(right[ri]); ri += 1

    # A block that spans the gutter behaves differently depending on its kind.
    # A teaser line / full-width abstract sits in the margin column and belongs at
    # the top of the reading flow. A heading printed across a line boundary ends
    # the two-column region above it, so the left column must be drained first -
    # otherwise the heading jumps ahead of the text it follows.
    #
    # The test has to be absolute, not relative to the *first* spanning block:
    # a full-width footer always spans the gutter and would drag the boundary to
    # the bottom of the page, disabling the flush for every real heading.
    is_marker = []
    for m in mid:
        sz = m.get("size", 0.0)
        txt = m.get("text", "")
        # "kind" is set later by classify(); fall back to the font size.
        marker = ("heading" in m.get("kind", "")
                  or (not m.get("bold") and sz >= 11.5 and len(txt) < 200))
        is_marker.append(marker)

    for m, marker in zip(mid, is_marker):
        if marker:
            flush_all(m["bbox"][1])
        else:
            flush_strict(m["bbox"][1])
        out.append(m)
    flush_all(float("inf"))
    out.extend(left[li:])
    out.extend(right[ri:])
    return out


def math_regions(items, body_size, page_h):
    """Group math-font blocks into contiguous regions -> render as images later."""
    def is_math(it):
        if it.get("math", 0.0) >= 0.25:
            return True
        n = max(1, len(it["text"]))
        dense = len(CTRL_RE.findall(it["text"])) / n >= CTRL_DENSITY
        return dense and len(it["text"]) <= 300

    cand = [it for it in items if it["kind"] == "text" and is_math(it)]
    if not cand:
        return []
    groups = []
    for c in sorted(cand, key=lambda i: (i["bbox"][1], i["bbox"][0])):
        hit = None
        for g in groups:
            if (c["bbox"][1] <= g["y1"] + body_size * 1.8
                    and not (c["bbox"][2] < g["x0"] - 3 or c["bbox"][0] > g["x1"] + 3)):
                hit = g
                break
        if hit is None:
            groups.append({"x0": c["bbox"][0], "x1": c["bbox"][2],
                           "y0": c["bbox"][1], "y1": c["bbox"][3], "items": [c]})
        else:
            hit["x0"] = min(hit["x0"], c["bbox"][0]); hit["x1"] = max(hit["x1"], c["bbox"][2])
            hit["y0"] = min(hit["y0"], c["bbox"][1]); hit["y1"] = max(hit["y1"], c["bbox"][3])
            hit["items"].append(c)
    out = []
    for g in groups:
        if (g["y1"] - g["y0"]) > page_h * 0.45:
            continue
        g["items"] = set(id(i) for i in g["items"])
        out.append(g)
    return out


def absorb_into_math(items, regions, body_size):
    """Replace the text blocks belonging to a formula with a single image region."""
    if not regions:
        return items
    pad = max(4.0, body_size)  # generous when deciding what belongs to a formula
    kept, eq = [], []
    for it in items:
        if it["kind"] != "text":
            kept.append(it)
            continue
        x0, y0, x1, y1 = it["bbox"]
        taken = False
        for g in regions:
            inside = (x0 >= g["x0"] - pad and x1 <= g["x1"] + pad
                      and y0 >= g["y0"] - pad and y1 <= g["y1"] + pad)
            if not inside:
                continue
            if id(it) in g["items"] or len(it["text"]) <= 24:
                taken = True
                break
            short = len(it["text"]) <= 6
            vov = min(y1, g["y1"]) - max(y0, g["y0"])
            if short and vov > 0 and abs(x0 - g["x1"]) <= body_size * 2.5:
                taken = True
                break
        if taken:
            continue
        kept.append(it)
    ip = 2.0  # tight padding for the rendered image
    for g in regions:
        eq.append({"kind": "equation",
                   "bbox": (max(0.0, g["x0"] - ip), max(0.0, g["y0"] - ip),
                            g["x1"] + ip, g["y1"] + ip)})
    kept.extend(eq)
    return kept


def merge_blocks(blocks):
    """Re-join blocks that PDF extraction split mid-sentence.

    Reference lists flow continuously, so neighbouring reference blocks are always
    joined. Other blocks are joined only when the next one clearly continues the
    sentence (lower-case start, previous not terminated) - this must not swallow
    real paragraph breaks."""
    out = []
    for b in blocks:
        if out:
            a = out[-1]
            if (a.get("bbox") and b.get("bbox")
                    and a["page"] == b["page"]
                    and a.get("type") in ("paragraph", "reference", "list")
                    and b.get("type") == a.get("type")):
                ax0, ay0, ax1, ay1 = a["bbox"]
                bx0, by0, bx1, by1 = b["bbox"]
                gap = by0 - ay1
                ov = min(ax1, bx1) - max(ax0, bx0)
                narrow = min(ax1 - ax0, bx1 - bx0)
                if -1.0 <= gap <= 3.5 and narrow > 0 and ov / narrow >= 0.6:
                    ref = a["type"] == "reference"
                    cont = (b["text"][:1].islower()
                            and not a["text"].rstrip().endswith((".", "!", "?", ":", "]", "”")))
                    if ref or cont:
                        a["text"] = join_text(a["text"], b["text"])
                        a["bbox"] = [min(ax0, bx0), min(ay0, by0), max(ax1, bx1), max(ay1, by1)]
                        continue
        out.append(b)
    return out


def classify(txt, size, body_size, bold, in_refs):
    if NOISE_RE.search(txt):
        return "noise"
    if in_refs:
        return "reference"
    if REF_SECTION_RE.match(txt):
        return "heading_refs"
    if REF_ENTRY_RE.match(txt):
        return "ref_first"
    if in_refs and CITATION_RE.search(txt):
        return "reference"
    if CAPTION_RE.match(txt) or (CAPTION_LOOSE_RE.match(txt) and len(txt) < 400):
        return "caption"
    if size >= body_size * 1.12 and len(txt) < 160:
        return "heading"
    if bold and len(txt) < 110 and not txt.rstrip().endswith("."):
        return "heading"
    if LIST_RE.match(txt) and len(txt) < 400:
        return "list"
    return "paragraph"


def merge_captions(blocks):
    """Attach a caption block to its neighbouring figure / table."""
    out, i, used = [], 0, set()
    while i < len(blocks):
        b = blocks[i]
        if b["type"] in ("figure", "table") and not b.get("text"):
            nxt = blocks[i + 1] if i + 1 < len(blocks) else None
            if nxt and nxt["type"] == "caption":
                b["text"] = nxt["text"]
                used.add(nxt["id"])
        out.append(b)
        i += 1
    return [b for b in out if b["id"] not in used]


# ----------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("-o", "--out", default=None)
    ap.add_argument("--page-dpi", type=int, default=110)
    ap.add_argument("--fig-dpi", type=int, default=200)
    ap.add_argument("--cols", type=int, default=0, help="force column count (0=auto)")
    ap.add_argument("--no-split", action="store_true", help="disable column detection")
    ap.add_argument("--drop-refs", action="store_true", help="omit reference entries")
    ap.add_argument("--max-pages", type=int, default=0)
    a = ap.parse_args()

    src = os.path.abspath(a.pdf)
    if not os.path.isfile(src):
        print("ERROR: no such file: " + src)
        return 2
    stem = os.path.splitext(os.path.basename(src))[0]
    out = os.path.abspath(a.out) if a.out else os.path.join(os.path.dirname(src), stem + "_pbr")
    assets_dir = os.path.join(out, "assets")
    pages_dir = os.path.join(out, "pages")
    for d in (out, assets_dir, pages_dir):
        os.makedirs(d, exist_ok=True)

    doc = fitz.open(src)
    n = len(doc) if not a.max_pages else min(len(doc), a.max_pages)

    size_counter = Counter()
    for pno in range(n):
        for b in doc[pno].get_text("dict")["blocks"]:
            if b["type"] != 0:
                continue
            for line in b.get("lines", []):
                for sp in line.get("spans", []):
                    t = sp.get("text", "").strip()
                    if t:
                        size_counter[round(sp.get("size", 0.0), 1)] += len(t)
    body_size = size_counter.most_common(1)[0][0] if size_counter else 10.0

    blocks, page_images = [], []
    in_refs = False
    bid = 0
    nfig = 0
    neq = 0

    for pno in range(n):
        page = doc[pno]
        pw, ph = page.rect.width, page.rect.height

        try:
            pix = page.get_pixmap(dpi=a.page_dpi)
            pname = "page_%d.jpg" % (pno + 1)
            with open(os.path.join(pages_dir, pname), "wb") as f:
                f.write(pix.tobytes("jpeg", jpg_quality=78))
            page_images.append({
                "page": pno + 1,
                "file": "pages/" + pname,
                "w": pix.width, "h": pix.height, "pw": pw, "ph": ph,
            })
        except Exception as e:
            print("warn: page render failed p%d: %s" % (pno + 1, e))

        items, tab_regions = [], []
        try:
            for t in page.find_tables().tables:
                try:
                    md = t.to_markdown()
                except Exception:
                    try:
                        md = rows_to_md(t.extract())
                    except Exception:
                        md = ""
                if md and md.strip():
                    tb = tuple(t.bbox)
                    tab_regions.append(tb)
                    items.append({"kind": "table", "bbox": tb, "md": md.strip()})
        except Exception:
            pass

        for b in page.get_text("dict")["blocks"]:
            bx = tuple(b["bbox"])
            if b["type"] == 1:
                # skip journal logos / running-head graphics / rule lines
                if bx[2] - bx[0] >= MIN_FIG_W and bx[3] - bx[1] >= MIN_FIG_H:
                    items.append({"kind": "figure", "bbox": bx})
                continue
            if b["type"] != 0:
                continue
            cx, cy = (bx[0] + bx[2]) / 2, (bx[1] + bx[3]) / 2
            if any(r[0] - 2 <= cx <= r[2] + 2 and r[1] - 2 <= cy <= r[3] + 2 for r in tab_regions):
                continue
            txt, size, bold, mratio, ctrl = block_text(b)
            if len(txt) < 2:
                continue
            items.append({"kind": "text", "bbox": bx, "text": txt, "size": size,
                          "bold": bold, "math": mratio, "ctrl": ctrl})

        regions = math_regions(items, body_size, ph)
        if regions:
            items = absorb_into_math(items, regions, body_size)

        if a.cols == 2:
            split = pw / 2.0
        elif a.no_split or a.cols == 1:
            split = None
        else:
            split = detect_split([it for it in items if it["kind"] == "text"], pw)

        for it in order_items(items, split, pw):
            bx = it["bbox"]
            if it["kind"] == "equation":
                try:
                    pix = page.get_pixmap(clip=fitz.Rect(bx), dpi=max(a.fig_dpi, 300))
                    fn = "eq_p%d_%d.png" % (pno + 1, neq)
                    pix.save(os.path.join(assets_dir, fn))
                    neq += 1
                except Exception as e:
                    print("warn: equation render failed: %s" % e)
                    continue
                bid += 1
                blocks.append({
                    "id": "b%04d" % bid, "page": pno + 1,
                    "bbox": [round(v, 2) for v in bx],
                    "type": "equation", "text": "", "asset": "assets/" + fn,
                })
                continue
            if it["kind"] == "figure":
                try:
                    pix = page.get_pixmap(clip=fitz.Rect(bx), dpi=a.fig_dpi)
                    fn = "fig_p%d_%d.png" % (pno + 1, nfig)
                    pix.save(os.path.join(assets_dir, fn))
                    nfig += 1
                except Exception as e:
                    print("warn: figure extract failed: %s" % e)
                    continue
                bid += 1
                blocks.append({
                    "id": "b%04d" % bid, "page": pno + 1,
                    "bbox": [round(v, 2) for v in bx],
                    "type": "figure", "text": "", "asset": "assets/" + fn,
                })
            elif it["kind"] == "table":
                bid += 1
                blocks.append({
                    "id": "b%04d" % bid, "page": pno + 1,
                    "bbox": [round(v, 2) for v in bx],
                    "type": "table", "text": it["md"],
                })
            else:
                txt, size, bold = it["text"], it["size"], it["bold"]
                t = classify(txt, size, body_size, bold, in_refs)
                if t == "heading_refs" or t == "ref_first":
                    in_refs = True
                    t = "heading" if t == "heading_refs" else "reference"
                elif t == "heading" or t == "caption":
                    in_refs = False
                if t == "reference" and a.drop_refs:
                    continue
                bid += 1
                blocks.append({
                    "id": "b%04d" % bid, "page": pno + 1,
                    "bbox": [round(v, 2) for v in bx],
                    "type": t, "text": txt,
                    "no_translate": t in ("reference", "noise"),
                })

    blocks = merge_blocks(merge_captions(blocks))
    for i, b in enumerate(blocks):
        b["id"] = "b%04d" % (i + 1)

    meta_title = (doc.metadata or {}).get("title") or ""
    if not meta_title:
        for b in blocks:
            if b["type"] == "heading" and len(b["text"]) > 8:
                meta_title = b["text"]
                break
    if not meta_title:
        meta_title = stem

    data = {
        "meta": {
            "title": meta_title,
            "source": os.path.basename(src),
            "stem": stem,
            "pages": n,
            "body_size": body_size,
            "page_images": page_images,
            "counts": dict(Counter(b["type"] for b in blocks)),
        },
        "blocks": blocks,
    }
    with open(os.path.join(out, "blocks.json"), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)

    chars = sum(len(b["text"]) for b in blocks if not b.get("no_translate"))
    print("blocks: %d" % len(blocks))
    print("types : %s" % json.dumps(data["meta"]["counts"], ensure_ascii=False))
    print("chars to translate: %d" % chars)
    print("out   : %s" % out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
