#!/usr/bin/env python3
"""Validate extraction output.

  validate.py part <part-id> [...]   check parts/<part-id>[.bNN].json against sentences/parts/<part-id>.json
  validate.py all                    check requirements/*.json against sentences/<chapter>.json, global ID uniqueness

Exit code 1 if any error is found.
"""
import sys
from collections import Counter

from common import (AMBIGUITY, ENT_CATEGORIES, ENT_ID_RE, MODALITIES, NONREQ_CATEGORIES, PARTS_OUT, REQ,
                    REQ_ID_RE, REQ_TYPES, SENT, combine, glossary_terms, load, part_fragments)


def check(data, units, label, glossary):
    errors, warnings = [], []
    E = lambda m: errors.append(f"{label}: {m}")
    W = lambda m: warnings.append(f"{label}: {m}")
    unit_ids = {u["id"]: u for u in units}
    covered = set()

    ents = {}
    for e in data["entities"]:
        eid = e.get("id", "")
        if not ENT_ID_RE.match(eid):
            E(f"entity id '{eid}' malformed")
        if not e.get("name"):
            E(f"entity {eid} has no name")
        if e.get("category") not in ENT_CATEGORIES:
            E(f"entity {eid} category '{e.get('category')}' not in {sorted(ENT_CATEGORIES)}")
        for s in e.get("sentence_ids", []):
            if s not in unit_ids:
                E(f"entity {eid} references unknown sentence {s}")
        ents[eid] = e

    for t in data["terms_used"]:
        term = t.get("term", "")
        if not term:
            E("terms_used entry without term")
            continue
        ing = term.lower() in glossary
        if t.get("in_glossary") is not ing:
            W(f"term '{term}': in_glossary should be {ing}")
        for s in t.get("sentence_ids", []):
            if s not in unit_ids:
                E(f"term '{term}' references unknown sentence {s}")

    for r in data["relationships"]:
        for k in ("subject", "object"):
            if r.get(k) not in ents:
                E(f"relationship {r.get('subject')} {r.get('predicate')} {r.get('object')}: {k} is not a declared entity")
        if not r.get("predicate"):
            E(f"relationship {r.get('subject')} -> {r.get('object')} has no predicate")
        for s in r.get("sentence_ids", []):
            if s not in unit_ids:
                E(f"relationship references unknown sentence {s}")

    ids = Counter()
    for r in data["requirements"]:
        rid = r.get("id", "")
        ids[rid] += 1
        m = REQ_ID_RE.match(rid)
        sids = r.get("sentence_ids") or []
        if not m:
            E(f"requirement id '{rid}' malformed")
        elif sids:
            expect = f"{m.group(1)}-s{m.group(2)}"
            if sids[0] != expect:
                E(f"{rid}: id must be derived from first sentence id, expected prefix of {sids[0]}")
            if r.get("section") != m.group(1):
                E(f"{rid}: section '{r.get('section')}' does not match id")
        if not sids:
            E(f"{rid}: no sentence_ids")
        for s in sids + r.get("examples", []):
            if s not in unit_ids:
                E(f"{rid}: unknown sentence {s}")
            covered.add(s)
        if r.get("type") not in REQ_TYPES:
            E(f"{rid}: type '{r.get('type')}' not in {sorted(REQ_TYPES)}")
        if r.get("modality") not in MODALITIES:
            E(f"{rid}: modality '{r.get('modality')}' not in {sorted(MODALITIES)}")
        for k in ("canonical", "original"):
            if not isinstance(r.get(k), str) or not r.get(k).strip():
                E(f"{rid}: '{k}' missing")
        if r.get("subject") not in ents:
            E(f"{rid}: subject '{r.get('subject')}' is not a declared entity")
        for k in ("normative", "testable"):
            if not isinstance(r.get(k), bool):
                E(f"{rid}: '{k}' must be boolean")
        if r.get("normative") is True and sids and all(unit_ids.get(s, {}).get("normative") is False for s in sids):
            E(f"{rid}: normative=true but all source units are informative (note/example)")
        if not isinstance(r.get("cross_refs", []), list):
            E(f"{rid}: cross_refs must be a list")
        a = r.get("ambiguity")
        if not isinstance(a, dict) or a.get("status") not in AMBIGUITY:
            E(f"{rid}: ambiguity.status missing or not in {sorted(AMBIGUITY)}")
        else:
            if a["status"] == "ambiguous":
                if len(a.get("readings", [])) < 2:
                    E(f"{rid}: ambiguous requires >= 2 readings")
                if not a.get("issue"):
                    E(f"{rid}: ambiguous requires an issue text")
            if a["status"] == "terminology" and not a.get("improper_terms"):
                E(f"{rid}: terminology requires improper_terms")
            for it in a.get("improper_terms", []):
                if not it.get("used") or not it.get("proper"):
                    E(f"{rid}: improper_terms entries need 'used' and 'proper'")
    for rid, n in ids.items():
        if n > 1:
            E(f"duplicate requirement id {rid} ({n}x)")

    for nr in data["non_requirement"]:
        s = nr.get("sentence_id")
        if s not in unit_ids:
            E(f"non_requirement references unknown sentence {s}")
        if nr.get("category") not in NONREQ_CATEGORIES:
            E(f"non_requirement {s}: category '{nr.get('category')}' not in {sorted(NONREQ_CATEGORIES)}")
        if not nr.get("reason"):
            E(f"non_requirement {s}: reason missing")
        if s in unit_ids and unit_ids[s]["normative"] and unit_ids[s]["kind"] in ("prose", "list-item", "static-semantics") \
                and nr.get("category") not in ("cross-reference", "heading", "duplicate", "editorial", "covered-elsewhere", "informative"):
            W(f"normative unit {s} marked as non-requirement ({nr.get('category')})")
        covered.add(s)

    missing = [u["id"] for u in units if u["id"] not in covered]
    for s in missing:
        E(f"sentence not covered: {s} [{unit_ids[s]['kind']}] {unit_ids[s]['text'][:90]!r}")
    return errors, warnings, ids


def report(errors, warnings, summary):
    for w in warnings:
        print("WARN ", w)
    for e in errors:
        print("ERROR", e)
    print(summary, f"errors={len(errors)} warnings={len(warnings)}")
    return 1 if errors else 0


def main(argv):
    glossary = glossary_terms()
    if len(argv) >= 2 and argv[0] == "part":
        rc = 0
        for pid in argv[1:]:
            inv = load(SENT / "parts" / f"{pid}.json")
            frags = part_fragments(pid)
            if not frags:
                print(f"ERROR {pid}: no output files in {PARTS_OUT}")
                rc = 1
                continue
            data = combine(frags)
            errors, warnings, ids = check(data, inv["units"], pid, glossary)
            rc |= report(errors, warnings,
                         f"{pid}: units={len(inv['units'])} requirements={len(data['requirements'])} "
                         f"entities={len(data['entities'])}")
        return rc
    if argv == ["all"]:
        rc = 0
        allids = Counter()
        for f in sorted(REQ.glob("*.json")):
            if f.name in ("index.json", "issues.json", "entities.json"):
                continue
            data = load(f)
            inv = load(SENT / f"{data['file']}.json")
            errors, warnings, ids = check(data, inv["units"], data["file"], glossary)
            allids.update(ids)
            rc |= report(errors, warnings, f"{data['file']}: requirements={len(data['requirements'])}")
        dups = [i for i, n in allids.items() if n > 1]
        for d in dups:
            print("ERROR global duplicate id", d)
        print(f"TOTAL requirements={sum(allids.values())} unique={len(allids)}")
        return rc | (1 if dups else 0)
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
