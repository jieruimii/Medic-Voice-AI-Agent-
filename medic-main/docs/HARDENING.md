# Final correctness and persistence pass

## Persistence and repeat testing

The authoritative runtime remains one Python process and the existing Guava number, **+1 (484) 972-8166**. SQLite is at `C:\Users\HP\medic\runtime\medic.sqlite3`, configurable with `MEDIC_DB_PATH`. Database files, journals, locks, logs, caches and environment files are ignored by Git.

The `encounters` table stores one JSON snapshot and resumable extraction state per encounter, indexed by ID, call/session ID and timestamps. Facts include their evidence and superseded history; snapshots include validation issues, source chunks, question history, status and end timestamp. SQLite transactions use WAL and full synchronization. Mutations are saved synchronously. The `metadata` table stores the current encounter pointer.

**Start new demo** creates a new record and atomically moves that pointer. A subsequent call fills that prepared record. A call after a completed encounter starts another record automatically. Nothing is deleted. **Recent encounters** lists up to 50 runs with IDs, timestamps, status and current/live labels. `/encounters/{id}` opens a read-only historical view; its draft/JSON downloads always refer to that ID. Viewing history never changes which encounter receives phone updates.

A backend restart restores the pointer and stored record. If the process died during a call, it preserves the sources and marks the encounter incomplete with a restart note. A new process does not try to resume an old Guava session. Earlier runs that were already erased by the old in-memory implementation cannot be recovered from the local application.

## Reported spoken-call failures

The old implementation extracted individual HUMAN chunks and selected the next question in the task-completion callback. Inspection of installed Guava SDK **0.48.0** confirms that its per-call event dispatcher invokes callbacks serially. Blocking task completion on extraction can delay later speech callbacks; there was also no whole-window reconciliation or final issue check at command enqueue. The old full call/event trace was not retained, so this is an identified implementation risk rather than proof of the exact timing of the reported call.

Task completion now returns promptly and reconciliation runs on a serialized worker. It drains received speech revisions, interprets split chunks together, validates the latest encounter, and checks both the speech version and target issue again while queuing the next command. Exact evidence is mapped to original HUMAN chunk IDs; quotes spanning chunks reference their IDs together. Generated Field summaries still do not establish facts. A short callback-drain interval is a correctness barrier, not a change to Guava's VAD or endpointing.

Explicit text hedges (`I guess`, `I think`, `maybe`, `not sure`) remain uncertain even if generated output is overconfident or omits the hedge from its quote. Vague transport wording stays verbatim; Medic does not decide CMS medical necessity. Plain `I don't know`/`I don't remember` answers are deterministically recorded as explicitly unspecified. Contextual unknowns stay visible as advisories and are not re-asked; required unknowns leave the encounter incomplete.

## Sharing tonight: one combined server, one database

| Question | Answer |
| --- | --- |
| Is the frontend static/separable enough for Vercel as-is? | It is dependency-free HTML/CSS/JS, so it is separable. A literal static deployment is not sufficient: FastAPI currently maps `/assets` to `frontend/src`, serves historical page routes, and provides all APIs. Vercel would need asset/history rewrites and API routing. |
| Where would Vercel API requests go? | Current fetches use relative `/api/...` URLs. On Vercel they would hit the Vercel origin and fail without an API proxy/rewrite to this backend. They do not reach Sai's localhost. |
| Must Python remain reachable? | Yes. The live Guava callbacks, SQLite and API live in this single process. Remote observers need an HTTPS path to it. Guava's phone connection itself remains outbound from Python and does not need this public HTTP path. |
| Is a temporary tunnel simpler? | Yes: it exposes the existing combined server and all observers see the exact same live state/history. No second Guava runtime, copied state, separate API deployment or new database is needed. |
| Is CORS/configuration needed? | No CORS is needed for the combined same-origin tunnel. Uvicorn accepts forwarded scheme headers only from loopback. If a proxy does not preserve that origin correctly, set `MEDIC_PUBLIC_ORIGIN` to the exact HTTPS origin before starting the backend; this permits that origin for reset requests without allowing arbitrary origins. A split frontend using direct cross-origin fetches would need explicit CORS and API-base configuration; a Vercel proxy avoids browser CORS but still needs the backend's write-origin configuration. |
| What command is recommended? | Keep the existing backend running and launch the email-restricted Cloudflare Quick Tunnel below. |

`cloudflared` **2026.10.0** is already installed here and its local help confirms `--allowed-mail`. No tunnel has been created during this pass. In a second PowerShell terminal:

```powershell
cd C:\Users\HP\medic
$jeremyEmail = Read-Host "Jeremy's email for tunnel access"
$saiEmail = Read-Host "Sai's email for tunnel access"
cloudflared tunnel --url http://127.0.0.1:8000 --allowed-mail $jeremyEmail --allowed-mail $saiEmail
```

Share the printed HTTPS URL with Jeremy. He authenticates by email PIN in his browser. Keep the backend, tunnel process and laptop running. Stop the tunnel with Ctrl+C after the demo. Its hostname changes when restarted. Do not omit the email restriction when exposing encounter history. All admitted viewers can also start a new inactive demo; there are no application roles in this slice.

If the backend needs to be started manually, stop the existing instance first (only after a call ends), then:

```powershell
cd C:\Users\HP\medic
uv sync --frozen
uv run main.py
```

Do not run `main.py`, the old scaffold, or a Guava cloud deployment in parallel on this number. Duplicate server/phone ownership is refused by local process locks. The current demo process ID is recorded in the ignored `runtime/server.pid` file for this handoff.

This recommendation follows [Cloudflare's current Quick Tunnel instructions](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/), including email restrictions and the lack of an uptime guarantee. Polling works with Quick Tunnels. [Vercel's static build documentation](https://vercel.com/docs/builds/configure-a-build) confirms static hosting is possible; the routing/API limitations above come from inspecting Medic's source. Nothing has been deployed to Vercel or publicly exposed.

## Guava hooks for the later voice-quality pass

Checked against the current [full official reference](https://goguava.ai/docs/everything.md) and installed SDK 0.48.0. No aggressive voice tuning was made in this pass; voice remains `colin`, pacing `medium`, and existing conversational guidance remains in place.

| Concern | Verified surface and limits |
| --- | --- |
| Filler while callbacks execute | Task objectives/checklist instructions and [`send_instruction`](https://goguava.ai/docs/send-instruction) provide language guidance. There is no documented public SDK `disable_filler` setting in the inspected reference. The existing silence instruction is guidance, not a hard runtime guarantee. Application callback latency and task boundaries are relevant; correctness work now avoids blocking the event dispatcher. |
| Turn-taking | Guava's hosted Dialog System owns it. [`set_task`](https://goguava.ai/docs/set-task) objectives and completion criteria guide semantic task completion. They are not low-level audio turn thresholds. |
| End-of-turn detection | [`on_caller_speech`](https://goguava.ai/docs/on-caller-speech) supplies utterance text/ID and may revise an utterance. The documented event has no final-speech flag. No supported public silence/VAD/endpointing threshold was found in the inspected SDK/reference. Confirm any service-side tuning with Guava before changing it. |
| Interruption / barge-in | [`on_agent_speech`](https://goguava.ai/docs/on-agent-speech) includes `interrupted`, an observation hook. No documented public barge-in enable/threshold command was found. Do not invent one. |
| Persona and pacing | [`set_persona`](https://goguava.ai/docs/set-persona) supports voice, organization/name/purpose and `speech_speed`: `x-slow`, `slow`, `medium`, `fast`, `x-fast`. Agent construction also supports pacing. |

## Verification and physical QA

The existing suite and targeted regressions pass. A real backend stop/start preserved the current encounter ID, historical ID and record count; the previous record reopened without changing the current pointer. SQLite reload tests additionally preserve completed facts/provenance, issues, question history and timestamps, and retain interrupted-call sources. Browser QA checks recent/history routes and current-versus-historical labeling. No additional hosted voice scenarios were generated for this pass.

Sai and Jeremy own the final physical calls: split the respiratory narrative naturally, confirm Medic skips the already-said chief complaint, answer the rationale with the reported hedge and then an unknown, and compare saved runs afterward. Perform the later voice-quality pass separately.
