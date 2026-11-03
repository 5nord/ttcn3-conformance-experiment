import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SENT = ROOT / "sentences"
SENTENCES_SKIP = {"chapters.json", "parts.json"}
PARTS_OUT = ROOT / "parts"
REQ = ROOT / "requirements"
GLOSSARY = ROOT / "ttcn3-terms-3.1.json"
DOCUMENT = "ETSI ES 201 873-1 V4.17.1 (2025-09)"

REQ_ID_RE = re.compile(r"^TTCN3-CORE-((?:\d+|[A-D])(?:\.\d+[a-z]?)*)-(\d{3})([a-z]{1,2})$")
ENT_ID_RE = re.compile(r"^ent:[a-z0-9][a-z0-9-]*$")

REQ_TYPES = {"requirement", "restriction", "permission", "prohibition", "recommendation",
             "definition", "semantics", "static-semantics", "syntax", "information"}
MODALITIES = {"SHALL", "SHALL NOT", "SHOULD", "SHOULD NOT", "MAY", "NEED NOT", "CAN", "CANNOT", "IS", "IS NOT"}
AMBIGUITY = {"clear", "ambiguous", "terminology"}
ENT_CATEGORIES = {"language-element", "type", "value", "operation", "statement", "keyword", "modifier",
                  "operator", "attribute", "matching-mechanism", "predefined-function", "concept",
                  "error", "entity"}
NONREQ_CATEGORIES = {"informative", "example", "cross-reference", "heading", "duplicate", "editorial",
                     "syntax", "table-structure", "covered-elsewhere"}


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def dump(path, data):
    Path(path).write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


def glossary_terms():
    return {t["term"].lower() for t in load(GLOSSARY)["terms"]}


def part_fragments(pid):
    files = sorted(PARTS_OUT.glob(f"{pid}.json")) + sorted(PARTS_OUT.glob(f"{pid}.b*.json"))
    return files


def empty_fragment():
    return {"entities": [], "terms_used": [], "relationships": [], "requirements": [], "non_requirement": []}


def combine(fragments):
    out = empty_fragment()
    for f in fragments:
        d = load(f)
        for k in out:
            v = d.get(k, [])
            if not isinstance(v, list):
                raise ValueError(f"{f}: '{k}' must be a list")
            out[k].extend(v)
    return out


def pad_section(section):
    """15.4.1 -> 15.04.01, A.1.2a -> A.01.02a, 10 -> 10."""
    out = []
    for part in section.split("."):
        m = re.fullmatch(r"(\d+)([a-z]*)", part)
        out.append(f"{int(m.group(1)):02d}{m.group(2)}" if m else part)
    return ".".join(out)


def slug_title(title):
    """Sub-clause title to a filename segment (spaces -> underscore, etc.)."""
    s = re.sub(r"[^a-z0-9]+", "_", title.lower())
    return re.sub(r"_+", "_", s).strip("_")


def section_titles():
    titles = {}
    for path in sorted(SENT.glob("*.json")):
        if path.name in SENTENCES_SKIP:
            continue
        for sec, info in load(path).get("sections", {}).items():
            titles[sec] = info["title"]
    return titles


def section_slug(section, titles=None):
    titles = titles if titles is not None else section_titles()
    return slug_title(titles[section])


def test_basename(section, n, titles=None):
    return f"{pad_section(section)}_{section_slug(section, titles)}_{n:03d}"


def test_module(section, n, titles=None):
    padded = pad_section(section)
    slug = section_slug(section, titles)
    return "M_" + re.sub(r"\W", "_", padded) + f"_{slug}_{n:03d}"
