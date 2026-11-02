import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SENT = ROOT / "sentences"
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
