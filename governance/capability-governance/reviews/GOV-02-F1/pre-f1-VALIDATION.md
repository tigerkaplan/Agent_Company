# GOV-02 validation evidence

Starting and current HEAD: `c5de47440973c87023bbd6652aca984262ab17f7`.
Implementation is uncommitted. V1 freeze is active; ORCH-01 is not started.

| Check | Actual evidence |
| --- | --- |
| Targeted/adversarial | PASS, 92 tests; `targeted-regression.json` |
| Affected review/GOV-01 F1/Worker recheck | PASS, 63 tests; `gov02-review-final-probe.log` |
| Expanded focused regression | PASS, 825 tests; exit 0; `focused-regression.json` |
| Complete full regression | PASS, 1,286 tests; exit 0; `full-regression.json` |
| Schema/static validation | PASS, 170 runtime Python AST files, 33 schema JSON/local-reference checks, 17 certificates; final recheck PASS |
| Git diff whitespace | Earlier checks PASS; final recheck PASS |

`validated-source.json` pins 207 runtime/schema/policy source files and HEAD.
Final source-manifest verification PASS: all 207 source files match and HEAD is unchanged.
`validation-history.json` preserves interrupted and failed earlier runs. These are
not passing regression evidence. Logs are local ignored validation artifacts,
with SHA-256 fingerprints in the machine reports.

The complete pre-repair 1,276-test run found four standalone fixture admission
migrations, one assertion expecting a later failure than the new exact-work trace
check, and one valid GOV-01 review-gate strengthening integration issue. The latter
was repaired using the existing verified monotonic gate rules. Later fixtures
were updated to use canonical claims, budget reservations and consumed intent
before simulating missing artifacts. No production guard was weakened for tests.

No live provider, remote forge, publication, deployment or VPS validation is
claimed. Git integrations use temporary repositories and a local bare remote.
Independent review has not been performed. READY FOR INDEPENDENT REVIEW: YES.
GOV-02 remains OPEN pending independent review and owner closure, with no commit authority or ORCH-01 authority inferred from these results.

## Completed regression fingerprints

| Run | Tests | Seconds | SHA-256 of complete log |
| --- | --- | --- | --- |
| targeted | 92 | 60.241 | `cc60b7651eead984c41e6e54ff253512042481f30f521d7918f00397830242c4` |
| focused | 825 | 1074.767 | `7932d57a4a1188ee242981a3c1442836fad8533ceb06e92c9296bb08b64df2c0` |
| full | 1286 | 1351.752 | `a7a28e45183448fe3fa4519880d614cfdd8ca92dea69e5726a475660f29c52cc` |

The final pre-fixture-repair focused/full runs completed with two obsolete concurrent-worker barrier errors. Those fixtures required both deliveries to reach an executor barrier; GOV-02 correctly admits only one. They now assert one actual executor invocation and one terminal event, with concurrent delivery preserved. The repaired 72-test progress/governance probe passed, followed by the complete passing focused and full runs above. Earlier failed/interrupted evidence remains in `validation-history.json`.

GOV-02 final runtime reality: certification, policy provenance, exact-work decision trace, blast/reversibility gates, profile/risk integration and authority preservation are SATISFIED on the supported frozen-V1 execution surfaces. Historical authority without the required provenance is denied for explicit recovery; no silent migration is performed.
