#!/usr/bin/env python3
"""Report entity ids across all part outputs that probably denote the same concept.

Writes candidate groups to stdout. Confirmed aliases go into scripts/entity_aliases.json
({"ent:alias": "ent:canonical"}), which merge.py applies.
"""
import re
from collections import defaultdict

from common import PARTS_OUT, load


def norm(eid):
    s = eid[4:]
    s = s.replace("test-case", "testcase").replace("-definition", "").replace("-declaration", "")
    s = re.sub(r"-(type|operation|statement)$", "", s)
    s = s.replace("-", "")
    s = re.sub(r"(ies)$", "y", s)
    s = re.sub(r"s$", "", s)
    return s


def main():
    uses = defaultdict(set)
    for f in PARTS_OUT.glob("*.json"):
        for e in load(f).get("entities", []):
            uses[e["id"]].add(f.name.split(".b")[0].removesuffix(".json"))
    groups = defaultdict(list)
    for eid in uses:
        groups[norm(eid)].append(eid)
    n = 0
    for k, ids in sorted(groups.items()):
        if len(ids) > 1:
            n += 1
            print(k, ":", ", ".join(f"{i} ({len(uses[i])})" for i in sorted(ids, key=lambda i: -len(uses[i]))))
    print(f"{len(uses)} entity ids, {n} candidate alias groups")


if __name__ == "__main__":
    main()
