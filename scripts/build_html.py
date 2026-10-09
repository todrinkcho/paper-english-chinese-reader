#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""paper-english-chinese-reader / step 3
blocks.json + translations -> single-file bilingual HTML reader
"""
from __future__ import annotations

import argparse
import base64
import html
import json
import mimetypes
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATE = os.path.join(os.path.dirname(HERE), "assets", "reader_template.html")

for _s in ("stdout", "stderr"):
    try:
        getattr(sys, _s).reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def esc(s):
    return html.escape(s or "", quote=True)


def load_translations(path):
    out = {}
    if not path:
        return out
    if os.path.isdir(path):
        files = [os.path.join(path, f) for f in sorted(os.listdir(path))
                 if f.lower().endswith(".json")]
    elif os.path.isfile(path):
        files = [path]
    else:
        print("warn: no translations at " + path)
        return out
    for fp in files:
        try:
            with open(fp, "r", encoding="utf-8") as f:
                obj = json.load(f)
        except Exception as e:
            print("warn: skip %s (%s)" % (os.path.basename(fp), e))
            continue
        if isinstance(obj, dict) and isinstance(obj.get("translations"), dict):
            obj = obj["translations"]
        if isinstance(obj, dict):
            for k, v in obj.items():
                if isinstance(v, str):
                    out[k] = v
                elif isinstance(v, dict) and isinstance(v.get("zh"), str):
                    out[k] = v["zh"]
    return out


REF_NUM_RE = re.compile(r"\[\d{1,3}\]")


def split_reference(text):
    """One line per bibliography entry.

    Only breaks on a [n] that follows '.' or ';' AND whose number is larger than
    the previous one, so bracketed numbers inside a title are left alone."""
    if not text:
        return [text]
    marks, prev = [], None
    for m in REF_NUM_RE.finditer(text):
        i = m.start()
        n = int(m.group()[1:-1])
        if prev is not None and n <= prev:
            continue
        j = i - 1
        while j >= 0 and text[j] == " ":
            j -= 1
        if i == 0 or (j >= 0 and text[j] in ".;"):
            marks.append(i)
            prev = n
    if not marks:
        return [text]
    out = []
    if marks[0] > 0:
        head = text[:marks[0]].strip()
        if head:
            out.append(head)
    for k, i in enumerate(marks):
        end = marks[k + 1] if k + 1 < len(marks) else len(text)
        seg = text[i:end].strip()
        if seg:
            out.append(seg)
    return out


def expand_for_render(blocks):
    """Reference blocks become one render unit per entry (for line breaks)."""
    out, prev_ref = [], None
    for b in blocks:
        if b.get("type") == "reference":
            segs = split_reference(b.get("en") or b.get("text") or "")
            # an entry cut in half by the page break: its tail lands in the next
            # block with no [n] of its own - glue it back onto the previous line
            if segs and not REF_NUM_RE.match(segs[0].lstrip()):
                head = segs.pop(0)
                if prev_ref is not None:
                    prev_ref["en"] = (prev_ref["en"] + " " + head).strip()
                    prev_ref["zh"] = prev_ref["en"]
                else:
                    segs.insert(0, head)
            for k, seg in enumerate(segs):
                nb = dict(b)
                nb["id"] = "%s-r%02d" % (b["id"], k + 1)
                nb["en"] = seg
                nb["zh"] = seg
                nb["_first"] = (k == 0)
                out.append(nb)
                prev_ref = nb
        else:
            b["_first"] = True
            out.append(b)
    return out


def data_uri(root, rel):
    p = os.path.join(root, rel)
    if not os.path.isfile(p):
        return None
    mt = mimetypes.guess_type(p)[0]
    if rel.lower().endswith(".jpg") or rel.lower().endswith(".jpeg"):
        mt = "image/jpeg"
    elif rel.lower().endswith(".png"):
        mt = "image/png"
    if not mt:
        mt = "application/octet-stream"
    with open(p, "rb") as f:
        b = f.read()
    return "data:%s;base64,%s" % (mt, base64.b64encode(b).decode("ascii"))


def md_table_to_html(md):
    rows = []
    for line in (l.strip() for l in (md or "").splitlines()):
        if not line.startswith("|"):
            continue
        core = line[1:]
        if core.endswith("|"):
            core = core[:-1]
        rows.append([c.strip() for c in core.split("|")])
    rows = [r for r in rows if not all(re.fullmatch(r":?-{2,}:?", c or "-") for c in r)]
    if not rows:
        return "<pre>" + esc(md) + "</pre>"
    head, body = rows[0], rows[1:]
    out = ["<table><thead><tr>"]
    out += ["<th>" + esc(c) + "</th>" for c in head]
    out.append("</tr></thead><tbody>")
    for r in body:
        out.append("<tr>" + "".join("<td>" + esc(c) + "</td>" for c in r) + "</tr>")
    out.append("</tbody></table>")
    return "".join(out)


def render_block(b, lang, has_page_img, show_orig=True):
    t = b.get("type", "paragraph")
    txt = b.get(lang, "")
    parts = ['<div class="blk blk-%s" data-id="%s" data-page="%s">' % (t, b["id"], b.get("page", 0))]
    if t == "equation":
        asset = b.get("asset_uri") or b.get("asset") or ""
        if asset:
            parts.append('<figure class="eq"><img src="%s" alt="equation" loading="lazy"></figure>'
                         % esc(asset))
    elif t == "figure":
        asset = b.get("asset_uri") or b.get("asset") or ""
        if asset:
            parts.append('<figure><img src="%s" alt="figure" loading="lazy">' % esc(asset))
        else:
            parts.append("<figure>")
        parts.append('<figcaption class="txt">%s</figcaption></figure>' % esc(txt))
    elif t == "table":
        parts.append('<div class="tblwrap">%s</div>' % md_table_to_html(txt))
    elif t == "heading":
        parts.append('<h3 class="txt">%s</h3>' % esc(txt))
    elif t == "caption":
        parts.append('<p class="txt cap">%s</p>' % esc(txt))
    elif t == "reference":
        parts.append('<p class="txt ref">%s</p>' % esc(txt))
    elif t == "noise":
        parts.append('<p class="txt noise">%s</p>' % esc(txt))
    else:
        parts.append('<p class="txt">%s</p>' % esc(txt))
    if has_page_img and show_orig:
        parts.append('<button class="orig" title="查看原页">p%s</button>' % b.get("page", 0))
    parts.append("</div>")
    return "".join(parts)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("workdir", help="folder containing blocks.json (the *_pbr folder)")
    ap.add_argument("-o", "--out", default=None)
    ap.add_argument("--tr", default=None, help="translations file or folder (default <workdir>/tr)")
    ap.add_argument("--glossary", default=None)
    ap.add_argument("--title", default=None)
    ap.add_argument("--embed-assets", type=int, default=1)
    ap.add_argument("--embed-pages", type=int, default=1)
    a = ap.parse_args()

    work = os.path.abspath(a.workdir)
    bj = os.path.join(work, "blocks.json")
    if not os.path.isfile(bj):
        print("ERROR: blocks.json not found in " + work)
        return 2
    with open(bj, "r", encoding="utf-8") as f:
        data = json.load(f)
    meta = data.get("meta", {})
    blocks = data.get("blocks", [])

    tr_dir = a.tr or os.path.join(work, "tr")
    tr = load_translations(tr_dir)
    print("translations loaded: %d" % len(tr))

    glossary = []
    gp = a.glossary or os.path.join(work, "glossary.json")
    if os.path.isfile(gp):
        try:
            with open(gp, "r", encoding="utf-8") as f:
                g = json.load(f)
            glossary = g.get("terms", g) if isinstance(g, dict) else g
            glossary = [x for x in glossary if isinstance(x, dict) and x.get("en")]
        except Exception as e:
            print("warn: glossary unreadable (%s)" % e)

    missing = []
    for b in blocks:
        src = b.get("text", "") or ""
        b["en"] = src
        if b.get("no_translate") or b.get("type") == "reference":
            b["zh"] = src
            continue
        if b.get("type") in ("equation",) or not src.strip():
            b["zh"] = b.get("zh") or ""
            continue
        if b["id"] in tr and tr[b["id"]].strip():
            b["zh"] = tr[b["id"]]
        else:
            b["zh"] = src
            missing.append(b["id"])

    pageimg = {}
    for p in meta.get("page_images", []):
        rel = p.get("file")
        if not rel:
            continue
        uri = data_uri(work, rel) if a.embed_pages else rel
        if uri:
            pageimg[str(p["page"])] = {
                "src": uri, "w": p.get("w"), "h": p.get("h"),
                "pw": p.get("pw"), "ph": p.get("ph"),
            }
    has_page_img = bool(pageimg)

    for b in blocks:
        if b.get("asset"):
            b["asset_uri"] = data_uri(work, b["asset"]) if a.embed_assets else b["asset"]

    blocks = expand_for_render(blocks)

    texts = {}
    page_of = {}
    for b in blocks:
        texts[b["id"]] = {"en": b.get("en", ""), "zh": b.get("zh", "")}
        page_of[b["id"]] = b.get("page", 0)

    body_en = "".join(render_block(b, "en", has_page_img, b.get("_first", True)) for b in blocks)
    body_zh = "".join(render_block(b, "zh", has_page_img, b.get("_first", True)) for b in blocks)

    payload = {
        "meta": {
            "title": a.title or meta.get("title") or meta.get("stem") or "Paper",
            "source": meta.get("source", ""),
            "stem": meta.get("stem", "paper"),
            "pages": meta.get("pages", 0),
            "docId": meta.get("stem", "paper"),
        },
        "blocks": [{"id": b["id"], "page": b.get("page", 0), "bbox": b.get("bbox"), "type": b.get("type")} for b in blocks],
        "texts": texts,
        "page_of": page_of,
        "pageimg": pageimg,
        "glossary": glossary,
    }

    with open(TEMPLATE, "r", encoding="utf-8") as f:
        tpl = f.read()
    js = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    tpl = tpl.replace("__DOC_TITLE__", esc(a.title or meta.get("title") or meta.get("stem") or "Paper"))
    tpl = tpl.replace("__BODY_EN__", body_en)
    tpl = tpl.replace("__BODY_ZH__", body_zh)
    tpl = tpl.replace("__DATA__", js)

    out = os.path.abspath(a.out) if a.out else os.path.join(os.path.dirname(work), (meta.get("stem") or "paper") + "-bilingual.html")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(tpl)

    print("glossary terms : %d" % len(glossary))
    print("untranslated   : %d" % len(missing))
    if missing:
        print("  " + ", ".join(missing[:40]) + (" ..." if len(missing) > 40 else ""))
    print("html           : %s (%.1f MB)" % (out, os.path.getsize(out) / 1048576.0))
    return 0


if __name__ == "__main__":
    sys.exit(main())
