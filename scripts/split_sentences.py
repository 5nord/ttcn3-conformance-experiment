#!/usr/bin/env python3
"""Split ETSI ES 201 873-1 (markdown) into numbered sentence units per chapter.

Output: sentences/<chapter-file>.json and sentences/chapters.json (manifest).
Unit IDs have the form <section>-s<NNN>, numbered in document order per section.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPEC = ROOT / "TTCN-3 Core Language, ETSI ES 201 873-1.md"
OUT = ROOT / "sentences"
DOCUMENT = "ETSI ES 201 873-1 V4.17.1 (2025-09)"

CHAPTER_RE = re.compile(r"^### (\d+) (.+)$")
ANNEX_RE = re.compile(r"^### Annex ([A-H]) \((normative|informative)\): (.+)$")
HEADING_RE = re.compile(r"^#{2,6}\s+(.*)$")
SECNUM_RE = re.compile(r"^((?:\d+|[A-D])(?:\.\d+[a-z]?)+|\d+|Annex [A-D])\s+(.*)$")
BARE_HEADING_RE = re.compile(r"^ +((?:\d+|[A-D])(?:\.\d+[a-z]?)+) ([A-Z][^.]{0,80})$")
PAGE_FOOTER_RE = re.compile(r"^\*\*\d+\*\* \*\*ETSI ES 201 873")
MARKER_RE = re.compile(r"^\*\*_(Syntactical Structure|Semantic Description|Restrictions|Examples?)_\*\*\s*$")
CAPTION_RE = re.compile(r"^\*\*(Table [0-9A-Z.]+[a-z]?: .*)\*\*\s*$")
NOTE_RE = re.compile(r"^\s*NOTE(\s+\d+)?\s*:")
EXAMPLE_RE = re.compile(r"^\s*EXAMPLE(\s+\d+)?\s*:?")
LIST_RE = re.compile(r"^\s*(?:[-\u2022*]\s+|[a-z]\)\s+|\d+\)\s+|[ivx]+\)\s+)")
COMMENT_RE = re.compile(r"/\*\s*(STATIC SEMANTICS?|REFERENCE)\s*[-\u2013](.*?)\*/", re.S)

NORMATIVE_HINT_RE = re.compile(r"\b(shall|should|is not allowed|are not allowed|is allowed|are allowed)\b")

ABBREV = ("e.g.", "i.e.", "etc.", "cf.", "vs.", "No.", "approx.", "resp.", "incl.")

CHAPTER_SLUGS = {}


def slug(title):
    s = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return s[:50].rstrip("-")


def chapter_of(line):
    m = CHAPTER_RE.match(line)
    if m and 5 <= int(m.group(1)) <= 27:
        return m.group(1), m.group(2).strip()
    m = ANNEX_RE.match(line)
    if m and m.group(1) in "ABCD":
        return m.group(1), m.group(3).strip()
    return None


def is_chapter_end(line):
    m = CHAPTER_RE.match(line)
    if m:
        return True
    return bool(ANNEX_RE.match(line))


def split_sentences(text):
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z\"(\[`_*'])", text)
    out = []
    for p in parts:
        if out and (out[-1].endswith(ABBREV) or re.search(r"\b(?:NOTE|EXAMPLE)\s*\d*:?$", out[-1])
                    or re.search(r"\b[A-Z]\.$", out[-1])):
            out[-1] = out[-1] + " " + p
        else:
            out.append(p)
    return [s.strip() for s in out if s.strip()]


class Chapter:
    def __init__(self, cid, title, start):
        self.id = cid
        self.title = title
        self.start = start
        self.end = start
        self.units = []
        self.sections = {}  # section -> {"title", "start"}
        self.counters = {}

    def add(self, section, kind, context, text, lines, normative=None):
        text = text.strip()
        if not text:
            return
        n = self.counters.get(section, 0) + 1
        self.counters[section] = n
        if normative is None:
            normative = kind not in ("note", "example-text", "example-code", "caption")
        self.units.append({
            "id": f"{section}-s{n:03d}",
            "section": section,
            "kind": kind,
            "context": context,
            "normative": normative,
            "text": text,
            "lines": list(lines),
        })


def parse(lines):
    chapters = []
    ch = None
    section = None
    context = None
    in_example = False
    table_region = False
    para = []  # list of (lineno, text)
    para_kind = None
    code = None  # list of (lineno, text) when inside fence
    code_start = None
    pipe = None  # current pipe table rows

    def flush_para():
        nonlocal para, para_kind, in_example, context
        if not para or ch is None:
            para, para_kind = [], None
            return
        text = " ".join(t.strip() for _, t in para)
        rng = (para[0][0], para[-1][0])
        kind = para_kind or "prose"
        if kind in ("prose", "list-item"):
            if table_region and kind == "prose":
                kind = "table-text"
            elif in_example or context == "Examples":
                if kind == "list-item" or NORMATIVE_HINT_RE.search(text):
                    # PDF conversion places "Examples" markers mid-clause; normative text ends the example region
                    in_example = False
                    if context == "Examples":
                        context = None
                else:
                    kind = "example-text"
        for s in split_sentences(text):
            ch.add(section, kind, context, s, rng)
        para, para_kind = [], None

    def flush_pipe():
        nonlocal pipe
        if not pipe or ch is None:
            pipe = None
            return
        rows = [(ln, [c.strip() for c in t.strip().strip("|").split("|")]) for ln, t in pipe]
        header = rows[0][1] if rows else []
        for ln, cells in rows[1:]:
            if all(re.fullmatch(r":?-{3,}:?", c) for c in cells if c):
                continue
            nonempty = [c for c in cells if c]
            if not nonempty:
                continue
            if NOTE_RE.match(nonempty[0]):
                for s in split_sentences(" ".join(nonempty)):
                    ch.add(section, "note", context, s, (ln, ln))
                continue
            text = "; ".join(f"{h or '_'}: {c}" for h, c in zip(header, cells) if c)
            ch.add(section, "table-row", context, text, (ln, ln))
        hdr = "; ".join(h for h in header if h)
        if hdr:
            ch.add(section, "table-header", context, hdr, (rows[0][0], rows[0][0]))
        pipe = None

    def flush_code():
        nonlocal code, in_example
        if ch is None or code is None:
            code = None
            return
        body = "\n".join(t for _, t in code).strip("\n")
        rng = (code_start, code[-1][0] if code else code_start)
        if not body.strip():
            code = None
            return
        if ch.id == "A" and section.startswith("A.1.6"):
            for m in COMMENT_RE.finditer(body):
                kind = "static-semantics" if m.group(1).startswith("STATIC") else "bnf-reference"
                txt = re.sub(r"\s+", " ", m.group(2)).strip()
                ch.add(section, kind, context, txt, rng)
        elif table_region:
            ch.add(section, "table-text", context, re.sub(r"\s+", " ", body), rng)
        elif context == "Syntactical Structure":
            ch.add(section, "syntax", context, body, rng)
        elif in_example or context == "Examples":
            ch.add(section, "example-code", context, body, rng)
            in_example = False
        else:
            ch.add(section, "code", context, body, rng)
        code = None

    def new_section(num, title, ln):
        nonlocal section, context, in_example, table_region
        flush_para(); flush_pipe()
        section = num
        context = None
        in_example = False
        table_region = False
        ch.sections.setdefault(num, {"title": title.strip(), "start": ln})

    for i, raw in enumerate(lines, start=1):
        line = raw.rstrip("\n")

        if line.startswith("### ") and is_chapter_end(line):
            if code is not None:
                flush_code()
            flush_para(); flush_pipe()
            if ch is not None:
                ch.end = i - 1
                chapters.append(ch)
                ch = None
            c = chapter_of(line)
            if c:
                ch = Chapter(c[0], c[1], i)
                section = c[0]
                context = None
                ch.sections[section] = {"title": c[1], "start": i}
            continue
        if line.startswith("### ") and ch is not None and ch.id == "C" and re.match(r"^### C\.\d+ ", line):
            m = re.match(r"^### (C\.\d+) (.*)$", line)
            new_section(m.group(1), m.group(2), i)
            continue
        if line.startswith("### ") and ch is not None and ch.id == "D" and re.match(r"^### D\.\d+ ", line):
            m = re.match(r"^### (D\.\d+) (.*)$", line)
            new_section(m.group(1), m.group(2), i)
            continue
        if line.startswith("### Annex E"):
            if ch is not None:
                flush_para(); flush_pipe()
                ch.end = i - 1
                chapters.append(ch)
                ch = None
            break
        if ch is None:
            continue

        # page artefacts
        if line.strip() == "-----" or PAGE_FOOTER_RE.match(line):
            continue

        # code fences
        if line.strip().startswith("```"):
            if code is None:
                flush_para(); flush_pipe()
                code = []
                code_start = i
            else:
                flush_code()
            continue
        if code is not None:
            hm = HEADING_RE.match(line)
            if MARKER_RE.match(line.strip()) or (hm and SECNUM_RE.match(hm.group(1))):
                # stray opening fence: re-interpret buffered lines as prose
                buffered = code
                code = None
                for ln, t in buffered:
                    if t.strip():
                        para.append((ln, t))
                    else:
                        flush_para()
                flush_para()
            else:
                code.append((i, line))
                continue

        # headings
        hm = HEADING_RE.match(line)
        if hm:
            sm = SECNUM_RE.match(hm.group(1).strip())
            if sm and (sm.group(1) == ch.id or sm.group(1).startswith(ch.id + ".")):
                new_section(sm.group(1), sm.group(2), i)
                continue
            line = hm.group(1)
        bm = BARE_HEADING_RE.match(line)
        if bm and (bm.group(1).startswith(ch.id + ".")):
            new_section(bm.group(1), bm.group(2), i)
            continue

        stripped = line.strip()
        mm = MARKER_RE.match(stripped)
        if mm:
            flush_para(); flush_pipe()
            context = "Examples" if mm.group(1).startswith("Example") else mm.group(1)
            in_example = False
            table_region = False
            continue
        if stripped == "**_Examples_**":
            continue

        # pipe tables
        if stripped.startswith("|"):
            flush_para()
            table_region = False
            if pipe is None:
                pipe = []
            pipe.append((i, stripped))
            continue
        elif pipe is not None:
            flush_pipe()

        if not stripped:
            flush_para()
            continue

        cm = CAPTION_RE.match(stripped)
        if cm:
            flush_para()
            ch.add(section, "caption", context, cm.group(1), (i, i))
            table_region = True
            continue

        if NOTE_RE.match(stripped):
            flush_para()
            para_kind = "note"
            table_region = False
            para.append((i, stripped))
            continue
        if EXAMPLE_RE.match(stripped) and stripped.upper().startswith("EXAMPLE"):
            flush_para()
            in_example = True
            table_region = False
            para_kind = "example-text"
            para.append((i, stripped))
            continue
        if LIST_RE.match(line) and not table_region:
            flush_para()
            para_kind = "list-item"
            para.append((i, LIST_RE.sub("", line, count=1) if line.lstrip().startswith(("-", "\u2022", "*")) else stripped))
            continue

        # paragraph continuation across page breaks is handled by joining
        para.append((i, stripped))

    if ch is not None:
        flush_para(); flush_pipe()
        chapters.append(ch)
    return chapters


def merge_page_breaks(ch):
    """Join prose units that were split by a page break mid-sentence."""
    merged = []
    for u in ch.units:
        if (merged and u["kind"] == merged[-1]["kind"] and u["kind"] in ("prose", "list-item", "note", "example-text")
                and u["section"] == merged[-1]["section"]
                and not re.search(r"[.:;!?)\]]$", merged[-1]["text"])
                and re.match(r"^[a-z(]", u["text"])):
            merged[-1]["text"] += " " + u["text"]
            merged[-1]["lines"][1] = u["lines"][1]
            continue
        merged.append(u)
    # renumber
    counters = {}
    for u in merged:
        n = counters.get(u["section"], 0) + 1
        counters[u["section"]] = n
        u["id"] = f"{u['section']}-s{n:03d}"
    ch.units = merged


def chapter_file(ch):
    prefix = f"{int(ch.id):02d}" if ch.id.isdigit() else ch.id
    return f"{prefix}-{slug(ch.title)}"


def main():
    lines = SPEC.read_text(encoding="utf-8").splitlines()
    chapters = parse(lines)
    OUT.mkdir(exist_ok=True)
    manifest = []
    overrides_file = OUT / "kind_overrides.json"
    overrides = json.loads(overrides_file.read_text())["prose"] if overrides_file.exists() else []
    for ch in chapters:
        merge_page_breaks(ch)
        for u in ch.units:
            if u["id"] in overrides:
                u["kind"], u["normative"] = "prose", True
        name = chapter_file(ch)
        data = {
            "document": DOCUMENT,
            "chapter": ch.id,
            "title": ch.title,
            "file": name,
            "lines": [ch.start, ch.end],
            "sections": ch.sections,
            "units": ch.units,
        }
        (OUT / f"{name}.json").write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        kinds = {}
        for u in ch.units:
            kinds[u["kind"]] = kinds.get(u["kind"], 0) + 1
        manifest.append({"chapter": ch.id, "title": ch.title, "file": name, "lines": [ch.start, ch.end],
                         "units": len(ch.units), "kinds": kinds})
    (OUT / "chapters.json").write_text(json.dumps(manifest, indent=1) + "\n", encoding="utf-8")
    for m in manifest:
        print(f"{m['chapter']:>3} {m['units']:5d} {m['file']}")
    print("total", sum(m["units"] for m in manifest))


if __name__ == "__main__":
    sys.exit(main())
