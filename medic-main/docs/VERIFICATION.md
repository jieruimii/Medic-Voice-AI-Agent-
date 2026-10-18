# Verification — October 17, 2026

The following checks ran against this implementation using synthetic encounter data:

| Check | Result |
| --- | --- |
| Local deterministic/API regression suite | **48 passed** |
| JavaScript syntax, Python compilation, whitespace checks | Passed |
| Golden respiratory encounter through Guava `agent.test()` | Passed; exactly two documentation questions, then clinician review |
| Uncertain repeat saturation, followed by “I don't remember” | Passed through Guava; no exact number selected, unknown accepted |
| Explicit 148/92 → 138/92 correction | Passed through Guava; 148 retained as superseded |
| Secondary chest-pain encounter | Passed through Guava; route, response, rationale follow-ups |
| Medication administration contradiction | Passed through Guava; explicit reconciliation before response/rationale questions |
| Live model extraction safety script | Passed; absent fields, history, uncertainty, unknowns, denial and negative transport rationale |
| Desktop/mobile dashboard inspection | Passed; sourced facts and final/advisory states render |
| Expand fact source and reset inactive demo | Verified in browser |
| Browser console | No errors observed |
| Existing inbound phone number | Listener registered; Guava reported zero other listeners |

Hosted-runtime tests inject caller transcripts and exercise Guava's real conversational runtime and Medic's callbacks. They do not test a person speaking over the telephone. **A spoken inbound call is the remaining acceptance check for audio recognition, turn-taking and voice quality.**

Some hosted test connections encountered transient TLS/WebSocket timeouts. Subsequent sequential retries passed. The Guava SDK reconnects the inbound listener, and the dashboard tracks connection/reconnection status. There is no offline extraction fallback: failed or pending extraction blocks completion.

Synthetic transcripts/results are written to the ignored `runtime/` folder by the opt-in scripts. The screenshot `dashboard-review.jpg` shows a completed synthetic test session on port 8001. The actual inbound dashboard runs on port 8000 and starts empty.

## Persistence/correctness hardening

Sai reported that the first real spoken phone test worked end-to-end before this pass. The hardened version is now ready for Sai and Jeremy's physical regression calls; no further hosted voice scenarios were run for this pass.

- **59 tests pass**: the existing 48 plus 11 targeted cases for split HUMAN chunks, speech arriving during extraction, final stale-question rechecking, four explicit text hedges, a hedge in a separate chunk, completed-record reload/reset, interrupted-call recovery, and historical API/download routes.
- A real server stop/start preserved the current ID `2D4F78FB`, historical ID `1C52BBB7`, and the two-record history. The historical record reopened without switching the current pointer. These two empty records are restart-verification demos, not clinical encounters.
- Browser QA verified **Recent encounters**, ID/timestamp display, **HISTORICAL ENCOUNTER · READ ONLY**, return-to-current navigation, and the connected phone line. `dashboard-history.jpg` records this check.
- SQLite files, journals, process locks, caches, logs and environment files are ignored; no runtime database is included in the commits.
- Sharing architecture and verified Guava controls are documented in [HARDENING.md](HARDENING.md). No public tunnel or deployment was started.
