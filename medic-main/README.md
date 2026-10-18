# MEDIC

**AI understands language. Code enforces documentation policy. Humans establish clinical truth.**

A Guava-powered inbound voice workflow that turns an EMS clinician's account into a sourced, structured encounter. A Python validator selects documentation gaps, the conversation asks one contextual follow-up at a time, and a live dashboard shows the record and provenance. Completion means **READY FOR CLINICIAN REVIEW**.

## Run

Python 3.11+ and `uv` are required. The checked-in lockfile pins Guava SDK **0.48.0**.

```powershell
uv sync
guava login
uv run main.py
```

Open **http://127.0.0.1:8000** and call **+1 (484) 972-8166**. This is the existing account-owned number in `guava.toml`; no additional number was purchased. The local Expert makes outbound connections to Guava; no public tunnel is needed. Keep this process running for calls. Only one encounter is active at a time.

If the CLI is not on PATH on this Windows machine, it is available at `$env:LOCALAPPDATA\guava\bin\guava.exe`. The SDK can use that existing CLI login directly. Alternatively set `GUAVA_API_KEY` and `GUAVA_AGENT_NUMBER` in the process environment. Never commit keys. Run `uv run main.py --dashboard-only` for the interface without a phone connection.

The dashboard displays the actual voice connection state. Wait for **CONNECTED** before calling. **Start new demo** creates a new encounter and keeps previous runs in **Recent encounters**. End a call before starting a new demo. Overlapping callers are declined without touching the current record. The server prevents another Medic process from claiming the same database or phone listener.

Encounter data is stored in `runtime/medic.sqlite3` (ignored by Git). It includes structured facts, provenance/history, source chunks, issues, questions and timestamps. Restarting the backend preserves completed records and the current pointer. An interrupted live call is retained as incomplete; it is not silently resumed. Historical views are read-only and their downloads refer to that encounter's ID. Set `MEDIC_DB_PATH` to override the SQLite location.

For tonight's shared dashboard and the current Guava voice-control reference, see [hardening and sharing notes](docs/HARDENING.md).

## Golden demo

1. Say: “68-year-old male, called for difficulty breathing. We found him sitting upright on the couch, alert and oriented. Initial oxygen saturation was 88 percent on room air, pressure 148 over 92, pulse 112. We put him on four liters by nasal cannula and transported him to County.”
2. Medic asks about the oxygen response. Say: “It came up to 95.”
3. Medic asks what, if anything, made another form of transportation inappropriate. Say: “He remained short of breath and needed continuous oxygen during transport.”
4. The dashboard reaches **READY FOR CLINICIAN REVIEW**. Transport priority remains an advisory. Expand a fact to inspect its exact source; download the readable draft or the JSON record from Source & audit.

Try a correction: “Pressure was 148 over 92 — sorry, 138 over 92.” The old systolic value stays in superseded history. For uncertainty, say “I think the second saturation was around 94 or 95,” then “I don't remember.” Medic leaves it explicitly unspecified and retains an advisory. “Nothing” is an accepted transport rationale; the system does not coach a different answer.

The chest-pain path also supports medication name, dose, units, route and response. “Gave aspirin” never establishes a dose or route. Conflicting medication administration statements require explicit reconciliation.

## Verification

```powershell
uv run pytest -q -p no:cacheprovider
uv run python scripts/check_extraction.py
uv run python scripts/live_golden.py
uv run python scripts/live_scenarios.py all
```

The unit suite covers source checks, corrections/history, uncertainty/unknowns, oxygen and medication rules, negative transport answers, contradictions, ASR revisions, question selection, advisory handling, completion gating, reset, and API behavior. It requires no credentials or network.

The opt-in scripts use synthetic encounters against the real Guava service and require authentication/network access. The golden test uses Guava's `agent.test()` runtime with injected caller transcripts; it does **not** dial a telephone or test microphone/audio quality. `scripts/live_scenarios.py` also checks uncertainty, corrections, chest pain and medication contradictions. `scripts/live_golden.py --dashboard` exposes that synthetic test on **port 8001**, distinctly labeled as a test session, for browser QA. The live phone demo remains on port 8000.

## Boundaries

- `backend/domain/`: facts, provenance/history and readable review draft.
- `backend/agent/extraction.py`: Guava structured generation with schema, exact evidence checks and uncertainty safeguards. Caller speech is data, not policy instructions.
- `backend/agent/controller.py`: narrative/reconciliation/review state, ASR snapshot replay and fail-closed extraction errors.
- `backend/validation/rules.py`: twelve inspectable prototype rule IDs; required/contextual issues block, advisories do not. Explicit contextual unknowns remain advisory; required unknowns leave the record incomplete.
- `backend/agent/question_planner.py`: rules select what to ask; context selects phrasing.
- `backend/agent/conversation.py`: verified Guava Tasks, Fields, Say and speech/task/session callbacks. Only caller-speech events establish provenance; generated Field summaries do not.
- `backend/api/server.py`: polling, reset, draft and export endpoints.
- `frontend/`: dependency-free responsive observation/review dashboard, polling every 750 ms. The phone is the data-entry interface.

## API

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/encounter/current` | Current encounter, facts, issues, question history and connection state |
| POST | `/api/encounter/reset` | Clear an inactive demo encounter |
| GET | `/api/encounter/draft` | Download readable clinician-review draft |
| GET | `/api/encounter/report` | Download JSON record including provenance/history |
| GET | `/api/health` | Web process and voice status |

## Prototype scope

This is a limited **NEMSIS-inspired documentation-validation prototype**, not a full EMS standard implementation. It does not establish legal compliance, payment, certification, or clinical correctness. It gives no treatment recommendations. Exact evidence checks establish traceability, not a guarantee that language extraction is correct; clinician review is required.

SQLite preserves local encounter history across restart/reset. The dashboard binds to loopback and has no application authentication. Use synthetic demo encounters. For external demo access, use the email-restricted temporary HTTPS tunnel described in the sharing notes. Guava's service-side call history/recordings remain separate from this local store. Local SDK telemetry is disabled by default. Organizational privacy agreements and production retention controls remain outside this slice.

Official integration references: [coding-agent starter](https://goguava.ai/docs/coding-agent-starter.md), [CLI](https://goguava.ai/docs/cli-reference.md), [agent testing](https://goguava.ai/docs/agent-testing.md). The CLI scaffold was inspected before integration. A later-appearing nested `medic-guava/` scaffold was also inspected and is preserved unchanged; it uses the same SDK and phone number. Its example agent should not run alongside Medic on the same number.
