# TTCN-3 requirement tests: final report

Source: `requirements/index.json` (ETSI ES 201 873-1 V4.17.1). Testable requirements: 5,235 in 364 sections.
Tests: `tests/<chapter>/<section>_test_NNN.ttcn3`, one per testable requirement.
Batches and notes: `tests/_batches/` (`bNNN.json`, `bNNN.notes.json`, `manifest.json`, `check.json`).

## Status

- All 5,235 requirements have a test file.
- The checker (`python3 scripts/check_tests.py all`) reports 0 errors: every file has the exact `@requirement` header on line 1, a matching `@id`, a valid `@verdict`, and the expected module name.
- No stray files and no duplicate module names.
- No test has been executed. Only Titan's semantic check (`ttcn3_compiler -s`) was run.

## Verdicts

| Verdict | Tests |
|---|---|
| `pass accept, ttcn3verdict:pass` | 3,302 |
| `pass reject` (must fail to compile) | 1,387 |
| `pass accept, noexecution` (must only compile) | 286 |
| `pass accept, ttcn3verdict:error` (runtime error expected) | 250 |
| `ttcn3verdict:inconc` or `ttcn3verdict:fail` | 10 |

## Titan disagreements

852 tests (16%) disagree with Titan's semantic check.

- Accept tests Titan rejects: 592. Mostly features Titan does not implement: map types, automatic typing, `@deterministic`/`@fuzzy`, variadic parameters, `encvalue_o`/`decvalue_o`, attribute retrieval, template concatenation.
- Reject tests Titan accepts: 260. Mostly rules Titan does not check, especially the clause 16.1.4 restrictions on alt guards (Titan only warns).
- Notes: 1,447 notes in `tests/_batches/bNNN.notes.json`. 156 warned files have no note of their own; most fall under notes about the same unsupported feature.

## Items for review

Possible defects in the standard:
- B.1.2.1 e) forbids `omit` in template lists, but 15.14 assumes it can appear there (`15.14_test_006`).
- 16.1.2 and C.5.6 conflict on `decvalue_o` with an uninitialized encoded value.
- The grammar in 16.1.2 omits the `bit_length` argument of `encvalue_o`.

Verdicts open to dispute:
- `06.01.00_test_026`: rejects subtyping of `address`; the reading is arguable.
- `checkstate("Running")` (batch b076): tested as a compile-time reject; the standard may intend a runtime error.
- `b075` test 033: a `catch` on a message-based port expects a runtime error; a compile-time reject may be the better expectation.
- `15.07.02_test_015`: relies on a RAW codec.
- `16.01.00_test_035`: Titan rejects it only because it lacks `@control`; the targeted rule is not confirmed.
- `16.01.00_test_032`: Titan rejects a function with no `return` at compile time; the standard treats this as a runtime error.

Reject tests whose rejection does not confirm the targeted rule (Titan fails on an unsupported construct instead):
- Init-statement and loop-form tests in 19.3.1, 19.4.2, 19.5.
- `@control` tests in clause 16.
- `address` tests in 6.2.12.
- Component `call` tests in 21.3.10.
- Two `select` init-statement scope tests in batch b052.
- `22.03.01_test_037` and `_038`, and `16.03_test_007` and `_011`.

Not fully self-contained:
- Some `@decoded`, `decmatch`, `encvalue_unichar` and `setencode` tests assume a JSON, XML or RAW codec, or the made-up encodings "Codec1"/"Codec2".
- Clause 27 tests mostly only declare attributes; without a codec they are not executed.

Weak tests:
- `16.02.01_test_003` ("no new snapshot") catches a non-compliant tool only by chance.
- The port `stop`/`halt` tests in batch b066 check only that receiving is blocked, not that sending is disallowed.

## Validation done

- Titan's `ttcn3_compiler -s` on every file, with multi-module files split for Titan.
- One subagent (b073) built and ran its 18 executable tests with Titan: 16 gave the expected verdict; `22.03.04_test_039` and `_047` ended in `fail` because Titan raises no runtime error where the standard requires one.
- Titan caught several genuine mistakes during generation (duplicate union field, invalid `check` form, undeclared variable, `>=` on charstrings, misplaced `@nodefault`, and others); these were fixed.

## Next steps

- Execute the accept tests with a real TTCN-3 runtime and codecs to confirm their verdicts.
- Resolve the review items above, and raise the clause 15.14 and 16.1.2 conflicts with ETSI.

## Tooling

- `scripts/make_test_batches.py`: assigns file, module and batch for every testable requirement.
- `scripts/check_tests.py`: `batch bNNN`, `file PATH...`, or `all`.
- `scripts/test_status.py`: progress per batch.
- `scripts/test_agent_instructions.txt`: shared subagent instructions.
