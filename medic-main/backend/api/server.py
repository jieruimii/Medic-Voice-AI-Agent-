from pathlib import Path
import os
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from backend.store import store
from backend.domain.report import clinician_draft

ROOT = Path(__file__).resolve().parents[2]
app = FastAPI(title="Medic", docs_url=None, redoc_url=None)


@app.middleware("http")
async def local_write_guard(request: Request, call_next):
    # Same-origin only, including an explicitly configured temporary HTTPS origin.
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        origin = request.headers.get("origin")
        allowed = {str(request.base_url).rstrip('/')}
        if os.getenv('MEDIC_PUBLIC_ORIGIN'):
            allowed.add(os.environ['MEDIC_PUBLIC_ORIGIN'].rstrip('/'))
        if origin and origin not in allowed:
            return JSONResponse({"detail": "Cross-origin writes are disabled."}, status_code=403)
    response = await call_next(request)
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


@app.get("/api/encounter/current")
def current():
    return store.snapshot()


@app.get('/api/encounters')
def recent():
    return {'current_encounter_id': store.current.encounter.id, 'encounters': store.recent()}


def encounter_snapshot(encounter_id):
    try:
        return store.snapshot(encounter_id)
    except KeyError as exc:
        raise HTTPException(404, 'Encounter not found.') from exc


@app.get('/api/encounters/{encounter_id}')
def detail(encounter_id: str):
    return encounter_snapshot(encounter_id)


@app.get('/api/encounters/{encounter_id}/report')
def saved_report(encounter_id: str):
    return JSONResponse(encounter_snapshot(encounter_id),
                        headers={'Content-Disposition': f'attachment; filename="medic-{encounter_id}.json"'})


@app.get('/api/encounters/{encounter_id}/draft')
def saved_draft(encounter_id: str):
    return PlainTextResponse(clinician_draft(encounter_snapshot(encounter_id)),
                             headers={'Content-Disposition': f'attachment; filename="medic-{encounter_id}-draft.txt"'})


@app.post("/api/encounter/reset")
def reset():
    try:
        store.reset()
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    return store.snapshot()


@app.get("/api/encounter/report")
def report():
    return JSONResponse(store.snapshot(), headers={"Content-Disposition": 'attachment; filename="medic-encounter.json"'})


@app.get("/api/health")
def health():
    return {"status": "ok", "voice": store.connection}


@app.get("/api/encounter/draft")
def draft():
    return PlainTextResponse(clinician_draft(store.snapshot()),
                             headers={"Content-Disposition": 'attachment; filename="medic-review-draft.txt"'})


@app.get("/")
@app.get('/encounters/{encounter_id}')
def dashboard():
    return FileResponse(ROOT / "frontend" / "index.html")


app.mount("/assets", StaticFiles(directory=ROOT / "frontend" / "src"), name="assets")
