#!/usr/bin/env python3
"""Check generated requirement tests.

Usage:
  check_tests.py batch bNNN     check all tests of one batch
  check_tests.py file PATH...   check individual test files
  check_tests.py all            check every batch and write tests/_batches/check.json

Per file it checks: existence, the exact @requirement header on line 1, an
@verdict line, the module name, and the Titan semantic analyser result
(ttcn3_compiler -s). Titan does not implement every feature of V4.17.1, so a
Titan mismatch is reported as a warning, not as an error.
"""
import glob
import json
import os
import re
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BATCH_DIR = os.path.join(ROOT, "tests", "_batches")
VERDICT_RE = re.compile(
    r"pass accept, ttcn3verdict:(none|pass|inconc|fail|error)|pass accept, noexecution|pass reject"
)


def titan(path):
    text = open(path, encoding="utf-8").read()
    starts = [m.start() for m in re.finditer(r"^module\b", text, re.M)] or [0]
    starts[0] = 0
    with tempfile.TemporaryDirectory() as tmp:
        # Titan accepts only one module per file: split, keeping line numbers.
        files = []
        for i, start in enumerate(starts):
            end = starts[i + 1] if i + 1 < len(starts) else len(text)
            chunk = "\n" * text.count("\n", 0, start) + text[start:end]
            name = os.path.join(tmp, f"part{i}.ttcn")
            open(name, "w", encoding="utf-8").write(chunk)
            files.append(name)
        env = dict(os.environ, TTCN3_DIR=os.environ.get("TTCN3_DIR", "/opt/titan"))
        proc = subprocess.run(
            ["ttcn3_compiler", "-s", *files],
            cwd=tmp, env=env, capture_output=True, text=True, timeout=60,
        )
    errors = [l for l in proc.stderr.splitlines() if ": error:" in l]
    return errors


def check(path, expected=None):
    errors, warnings = [], []
    full = os.path.join(ROOT, path)
    if not os.path.exists(full):
        return {"file": path, "errors": ["missing"], "warnings": []}
    text = open(full, encoding="utf-8").read()
    lines = text.splitlines()
    if expected:
        if not lines or lines[0] != expected["header"]:
            errors.append("line 1 is not the expected @requirement header")
        if not re.search(r"^\s*module\s+%s\b" % re.escape(expected["module"]), text, re.M):
            errors.append(f"module {expected['module']} not found")
    elif not lines or not lines[0].startswith("// @requirement: "):
        errors.append("line 1 is not an @requirement header")
    m = re.search(r"^// @verdict: (.*)$", text, re.M)
    verdict = m.group(1).strip() if m else None
    if not verdict or not VERDICT_RE.fullmatch(verdict):
        errors.append(f"missing or invalid @verdict line: {verdict!r}")
    titan_errors = titan(full)
    if verdict and verdict.startswith("pass accept") and titan_errors:
        warnings.append("titan rejects an accept test: " + " | ".join(titan_errors[:3]))
    if verdict == "pass reject" and not titan_errors:
        warnings.append("titan accepts a reject test")
    return {"file": path, "verdict": verdict, "errors": errors, "warnings": warnings}


def check_batch(name):
    batch = json.load(open(os.path.join(BATCH_DIR, name + ".json")))
    return [check(e["file"], e) for e in batch["requirements"]]


def report(results):
    for r in results:
        for e in r["errors"]:
            print(f"ERROR   {r['file']}: {e}")
        for w in r["warnings"]:
            print(f"WARNING {r['file']}: {w}")
    n_err = sum(1 for r in results if r["errors"])
    n_warn = sum(1 for r in results if r["warnings"])
    print(f"{len(results)} files, {n_err} with errors, {n_warn} with titan warnings")
    return n_err


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    cmd = sys.argv[1]
    if cmd == "batch":
        results = [r for name in sys.argv[2:] for r in check_batch(name)]
    elif cmd == "file":
        results = [check(os.path.relpath(os.path.abspath(p), ROOT)) for p in sys.argv[2:]]
    elif cmd == "all":
        results = []
        for path in sorted(glob.glob(os.path.join(BATCH_DIR, "b[0-9][0-9][0-9].json"))):
            results += check_batch(os.path.splitext(os.path.basename(path))[0])
        with open(os.path.join(BATCH_DIR, "check.json"), "w") as f:
            json.dump(results, f, indent=1)
    else:
        sys.exit(__doc__)
    sys.exit(1 if report(results) else 0)


if __name__ == "__main__":
    main()
