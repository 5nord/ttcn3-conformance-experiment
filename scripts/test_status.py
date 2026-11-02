#!/usr/bin/env python3
"""Show per-batch progress of the requirement tests (files written / total, notes file present)."""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BATCH_DIR = os.path.join(ROOT, "tests", "_batches")

manifest = json.load(open(os.path.join(BATCH_DIR, "manifest.json")))
done = partial = todo = 0
lines = []
for b in manifest["batches"]:
    reqs = json.load(open(os.path.join(BATCH_DIR, b["batch"] + ".json")))["requirements"]
    n = sum(os.path.exists(os.path.join(ROOT, r["file"])) for r in reqs)
    notes = os.path.exists(os.path.join(BATCH_DIR, b["batch"] + ".notes.json"))
    if n == len(reqs) and notes:
        done += 1
        state = "done"
    elif n:
        partial += 1
        state = "partial"
    else:
        todo += 1
        state = "todo"
    lines.append(f"{b['batch']} {state:7} {n:3}/{len(reqs):3}")
print("  ".join(lines))
print(f"done {done}, partial {partial}, todo {todo} of {len(manifest['batches'])}")
