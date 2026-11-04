"""Persistence layer: MongoDB when MONGO_URI is set, otherwise a local JSON file.
Collections: sources, claims, meta (version/published/acks/log), audit (append-only event trail)."""
import json, os, pathlib, time
FILE = pathlib.Path(__file__).parent / "data" / "state.json"
_db = None

def kind(): return "mongodb" if os.getenv("MONGO_URI") else "file"

def db():
    global _db
    if not os.getenv("MONGO_URI"): return None
    if _db is None:
        from pymongo import MongoClient
        _db = MongoClient(os.environ["MONGO_URI"], serverSelectionTimeoutMS=3000)[os.getenv("MONGO_DB", "baton")]
    return _db

def load():
    d = db()
    if d is None: return json.loads(FILE.read_text()) if FILE.exists() else None
    m = d.meta.find_one({"_id": "main"})
    if not m: return None
    m.pop("_id")
    clean = lambda coll: [{k: v for k, v in x.items() if k not in ("_id", "ord")} for x in d[coll].find().sort("ord", 1)]
    return {**m, "sources": clean("sources"), "claims": clean("claims")}

def save(st):
    d = db()
    if d is None: FILE.write_text(json.dumps(st)); return
    for coll, items in (("sources", st["sources"]), ("claims", st["claims"])):
        ids = [x["id"] for x in items]
        d[coll].delete_many({"_id": {"$nin": ids}})
        for i, x in enumerate(items): d[coll].replace_one({"_id": x["id"]}, {**x, "_id": x["id"], "ord": i}, upsert=True)
    meta = {k: v for k, v in st.items() if k not in ("sources", "claims")}
    d.meta.replace_one({"_id": "main"}, {"_id": "main", **meta}, upsert=True)

def audit(msg):
    d = db()
    if d is not None: d.audit.insert_one({"ts": time.time(), "event": msg})
