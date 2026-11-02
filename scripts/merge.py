#!/usr/bin/env python3
"""Merge part outputs into requirements/<chapter>.json, plus index.json and issues.json."""
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

from common import DOCUMENT, REQ, REQ_ID_RE, SENT, combine, dump, load, part_fragments


ALIASES_FILE = Path(__file__).resolve().parent / "entity_aliases.json"
RELABELED = set(load(SENT / "relabeled_units.json")["units"]) if (SENT / "relabeled_units.json").exists() else set()


VOTES = defaultdict(lambda: {"name": Counter(), "category": Counter(), "term_ref": Counter()})


def entity_label(eid):
    """Name/category by majority over all parts; a glossary term wins for the name."""
    v = VOTES[eid]
    term = v["term_ref"].most_common(1)[0][0] if v["term_ref"] else None
    return {"name": term or v["name"].most_common(1)[0][0],
            "category": v["category"].most_common(1)[0][0],
            "term_ref": term}


def union(a, b):
    return a + [x for x in b if x not in a]


MISLABEL_RE = re.compile(r"example[- ]text|mislabel|labell?ed as (an )?example|PDF conversion|sentence splitter", re.I)


def clean_ambiguity(r, log):
    """Drop flags that stem from coordinator or tooling errors, not from the spec text."""
    a = r.get("ambiguity") or {}
    terms = a.get("improper_terms", [])
    kept = [t for t in terms
            if not ("control function" in t.get("used", "").lower() and "control part" in t.get("proper", "").lower())]
    if len(kept) != len(terms):
        log.append(f"{r['id']}: dropped inverted control-part terminology flag")
        a["improper_terms"] = kept
    if a.get("status") == "terminology" and not kept:
        a["status"] = "clear"
    if a.get("status") == "ambiguous" and len(a.get("readings", [])) < 2 and MISLABEL_RE.search(a.get("issue", "")):
        a["status"] = "terminology" if kept else "clear"
        log.append(f"{r['id']}: dropped tooling-only ambiguity note")
    if a.get("status") == "clear":
        a.pop("readings", None)
        if not kept:
            a.pop("improper_terms", None)
        if a.get("issue") and MISLABEL_RE.search(a["issue"]):
            a.pop("issue")
    r["ambiguity"] = a


def apply_aliases(data):
    if not ALIASES_FILE.exists():
        return
    aliases = load(ALIASES_FILE)
    canon = lambda i: aliases.get(i, i)
    for e in data["entities"]:
        e["id"] = canon(e["id"])
    for r in data["relationships"]:
        r["subject"], r["object"] = canon(r["subject"]), canon(r["object"])
    for r in data["requirements"]:
        r["subject"] = canon(r["subject"])


def merge_chapter(cfile, pids, warnings):
    inv = load(SENT / f"{cfile}.json")
    order = {u["id"]: i for i, u in enumerate(inv["units"])}
    frags = [f for pid in pids for f in part_fragments(pid)]
    data = combine(frags)
    apply_aliases(data)

    ents = {}
    for e in data["entities"]:
        if e["id"] in ents:
            old = ents[e["id"]]
            old["sentence_ids"] = union(old.get("sentence_ids", []), e.get("sentence_ids", []))
            if not old.get("term_ref") and e.get("term_ref"):
                old["term_ref"] = e["term_ref"]
        else:
            ents[e["id"]] = {k: v for k, v in e.items() if k not in ("name", "category")}
    for eid, e in ents.items():
        e.update(entity_label(eid))

    terms = {}
    for t in data["terms_used"]:
        k = t["term"].lower()
        if k in terms:
            terms[k]["sentence_ids"] = union(terms[k].get("sentence_ids", []), t.get("sentence_ids", []))
        else:
            terms[k] = dict(t)

    rels = {}
    for r in data["relationships"]:
        k = (r["subject"], r["predicate"], r["object"])
        if k in rels:
            rels[k]["sentence_ids"] = union(rels[k].get("sentence_ids", []), r.get("sentence_ids", []))
        else:
            rels[k] = dict(r)

    def req_key(r):
        m = REQ_ID_RE.match(r["id"])
        return (order.get(r["sentence_ids"][0], 10**9), len(m.group(3)) if m else 0, m.group(3) if m else r["id"])

    units = {u["id"]: u for u in inv["units"]}
    for r in data["requirements"]:
        srcs = [units[s] for s in r["sentence_ids"] if s in units]
        if not any(u["normative"] for u in srcs):
            r["normative"] = False
        elif not r["normative"] and all(u["id"] in RELABELED or not u["normative"] for u in srcs) \
                and any(u["kind"] != "note" for u in srcs):
            r["normative"] = True
        clean_ambiguity(r, warnings)
    reqs = sorted(data["requirements"], key=req_key)
    nonreq = sorted(data["non_requirement"], key=lambda n: order.get(n["sentence_id"], 10**9))
    out = {
        "document": DOCUMENT,
        "chapter": inv["chapter"],
        "title": inv["title"],
        "file": cfile,
        "source_lines": inv["lines"],
        "sentences": [{k: u[k] for k in ("id", "section", "kind", "normative", "text", "lines")} for u in inv["units"]],
        "entities": sorted(ents.values(), key=lambda e: e["id"]),
        "terms_used": sorted(terms.values(), key=lambda t: t["term"].lower()),
        "relationships": list(rels.values()),
        "requirements": reqs,
        "non_requirement": nonreq,
    }
    dump(REQ / f"{cfile}.json", out)
    return out


def main(argv):
    REQ.mkdir(exist_ok=True)
    parts = load(SENT / "parts.json")
    by_chapter = defaultdict(list)
    for p in parts:
        by_chapter[p["chapter_file"]].append(p["part"])
    only = set(argv)
    warnings = []
    for pid in [p["part"] for p in parts]:
        frags = part_fragments(pid)
        if not frags:
            continue
        d = combine(frags)
        apply_aliases(d)
        for e in d["entities"]:
            VOTES[e["id"]]["name"][e.get("name")] += 1
            VOTES[e["id"]]["category"][e.get("category")] += 1
            if e.get("term_ref"):
                VOTES[e["id"]]["term_ref"][e["term_ref"]] += 1
    for cfile, pids in by_chapter.items():
        if only and cfile not in only and cfile.split("-")[0] not in only:
            continue
        missing = [p for p in pids if not part_fragments(p)]
        if missing:
            print(f"skip {cfile}: missing parts {missing}")
            continue
        out = merge_chapter(cfile, pids, warnings)
        print(f"merged {cfile}: requirements={len(out['requirements'])} entities={len(out['entities'])}")

    index, issues = [], []
    gents = {}
    for f in sorted(REQ.glob("*.json")):
        if f.name in ("index.json", "issues.json", "entities.json"):
            continue
        d = load(f)
        for e in d["entities"]:
            g = gents.setdefault(e["id"], {**entity_label(e["id"]), "id": e["id"], "chapters": [], "requirements": 0})
            g["chapters"].append(d["chapter"])
        for r in d["requirements"]:
            if r["subject"] in gents:
                gents[r["subject"]]["requirements"] += 1
        for r in d["requirements"]:
            a = r.get("ambiguity", {})
            row = {"id": r["id"], "chapter": d["chapter"], "section": r["section"], "type": r["type"],
                   "modality": r["modality"], "normative": r["normative"], "testable": r["testable"],
                   "ambiguity": a.get("status"), "canonical": r["canonical"]}
            index.append(row)
            if a.get("status") in ("ambiguous", "terminology"):
                issues.append({**row, "original": r["original"], "issue": a.get("issue"),
                               "readings": a.get("readings", []), "improper_terms": a.get("improper_terms", [])})
    dump(REQ / "index.json", {"document": DOCUMENT, "count": len(index), "requirements": index})
    dump(REQ / "issues.json", {"document": DOCUMENT, "count": len(issues), "issues": issues})
    dump(REQ / "entities.json", {"document": DOCUMENT, "count": len(gents),
                                 "entities": sorted(gents.values(), key=lambda e: e["id"])})
    for w in warnings:
        print("WARN", w)
    print(f"index: {len(index)} requirements, issues: {len(issues)}")


if __name__ == "__main__":
    main(sys.argv[1:])
