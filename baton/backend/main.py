import json, os, pathlib
from fastapi import FastAPI, Header, HTTPException, UploadFile, File, Form, Depends
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import ai, store
from verifier import status, level

BASE = pathlib.Path(__file__).parent
DATA = BASE / "data"
CLR = {"Intern": 0, "Engineer": 1, "Manager": 2}     # clearance per incoming role
app = FastAPI(title="Baton API")
ST = {}

def load(reset=False):
    saved = None if reset else store.load()
    if saved:
        ST.clear(); ST.update(saved); return
    seed = json.loads((DATA / "seed.json").read_text())
    ST.clear(); ST.update(sources=seed["sources"], claims=seed["claims"], published=False, version=1, acks={},
                          log=["v1 · Draft generated from %d sources" % len(seed["sources"])])
    for i, c in enumerate(ST["claims"], 1): c.update(id=c.get("id", i), r="pending", h=0)
    save()
def save(): store.save(ST)
def log(m): ST["version"] += 1; ST["log"].insert(0, f"v{ST['version']} · {m}"); store.audit(m); save()
load()

def reviewer(x_reviewer_key: str = Header(default="")):
    if x_reviewer_key != os.getenv("REVIEWER_KEY", "demo-reviewer"): raise HTTPException(401, "Reviewer key required")
def decorate(c):  # attach server-computed status and level
    return {**c, "status": status(c, ST["sources"]), "lvl": level(c, ST["sources"])}
def meta(s): return {k: s[k] for k in ("id", "name", "kind", "lvl")}
def find(cid):
    c = next((c for c in ST["claims"] if c["id"] == cid), None)
    if not c: raise HTTPException(404, "No such claim")
    return c

@app.get("/api/health")
def health(): return {"ok": True, "ai_mode": ai.mode(), "storage": store.kind()}

@app.get("/api/state", dependencies=[Depends(reviewer)])
def state():
    return {"ai_mode": ai.mode(), "storage": store.kind(), "sources": [meta(s) for s in ST["sources"]], "claims": [decorate(c) for c in ST["claims"]],
            "published": ST["published"], "log": ST["log"], "acks": ST["acks"]}

@app.post("/api/extract", dependencies=[Depends(reviewer)])
def extract():
    seed = json.loads((DATA / "seed.json").read_text())["claims"]
    try: new = ai.extract_claims(ST["sources"], seed)
    except Exception as e: raise HTTPException(502, f"AI extraction failed: {e}")
    ST["claims"] = [{**c, "id": i, "r": "pending", "h": 0, "src": c.get("src", [])} for i, c in enumerate(new, 1)]
    ST["published"] = False; ST["acks"] = {}
    log(f"Re-extracted {len(new)} claims ({ai.mode()} mode); verifier re-checked every quote")
    return {"count": len(new)}

@app.post("/api/sources", dependencies=[Depends(reviewer)])
async def add_source(file: UploadFile = File(...), lvl: int = Form(1), kind: str = Form("Document")):
    raw = await file.read()
    if len(raw) > 200_000 or lvl not in (0, 1, 2): raise HTTPException(400, "Text files under 200 KB, level 0-2")
    sid = f"S{len(ST['sources']) + 1}"
    ST["sources"].append({"id": sid, "name": file.filename, "kind": kind, "lvl": lvl, "auth": False,
                          "text": raw.decode("utf-8", "replace")})
    log(f"Imported source {sid} ({file.filename}, sensitivity {lvl})"); return {"id": sid}

class Review(BaseModel):
    action: str
    text: str | None = None

@app.patch("/api/claims/{cid}", dependencies=[Depends(reviewer)])
def review(cid: int, b: Review):
    c = find(cid); s = status(c, ST["sources"])
    if b.action == "approve":
        if s in ("blocked", "conflict", "missing"): raise HTTPException(409, f"Cannot approve a claim that is {s}")
        c["r"] = "approved"
    elif b.action == "reject": c["r"] = "rejected"
    elif b.action == "edit" and b.text and b.text.strip(): c.update(text=b.text.strip(), h=1, r="pending")
    else: raise HTTPException(400, "Bad action")
    log(f"{b.action} claim #{cid}"); return decorate(c)

@app.post("/api/publish", dependencies=[Depends(reviewer)])
def publish():
    if any(c["r"] == "pending" for c in ST["claims"]): raise HTTPException(409, "Review every claim first")
    ST["published"] = True; log("Handover approved and published"); return {"ok": True}

def src_ok(sid, role):
    s = next((s for s in ST["sources"] if s["id"] == sid), None)
    if not s: raise HTTPException(404, "No such source")
    if role != "Reviewer" and s["lvl"] > CLR.get(role, -1): raise HTTPException(403, "Above your clearance")
    return s

@app.get("/api/handover")
def handover(role: str):
    if role not in CLR: raise HTTPException(400, "Unknown role")
    if not ST["published"]: return {"published": False}
    ok = [decorate(c) for c in ST["claims"] if c["r"] == "approved"]
    vis = [c for c in ok if c["lvl"] <= CLR[role]]           # redaction happens here, before anything is sent
    for c in vis: c["src"] = [p for p in c["src"] if src_ok(p[0], role)]
    by = lambda t: [c for c in vis if c["type"] in t]
    plan = [["Day 1 · Clarify", by(["Gap", "Conflict"])], ["Day 2 · Take ownership", by(["Ownership", "Dependency", "Contact"])],
            ["Day 3 · Understand risks", by(["Risk", "Recurring problem"])], ["Day 4–5 · Execute", by(["Next action"])]]
    return {"published": True, "version": ST["version"], "role": role, "visible": vis, "withheld": len(ok) - len(vis),
            "plan": plan, "context": by(["Decision", "Overview"]), "timeline": [c for c in vis if c.get("date")], "acks": ST["acks"]}

@app.get("/api/source/{sid}")
def source(sid: str, role: str = "Reviewer", x_reviewer_key: str = Header(default="")):
    if role == "Reviewer": reviewer(x_reviewer_key)
    return src_ok(sid, role)

@app.post("/api/ack")
def ack(role: str):
    if role not in CLR or not ST["published"]: raise HTTPException(400, "Nothing to acknowledge")
    ST["acks"][role] = True; log(f"Receipt acknowledged by {role}"); return ST["acks"]

@app.post("/api/reset", dependencies=[Depends(reviewer)])
def reset(): load(reset=True); return {"ok": True}

app.mount("/", StaticFiles(directory=BASE.parent / "frontend", html=True), name="ui")
