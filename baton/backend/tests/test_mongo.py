import os, sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parents[1]))
import mongomock, pymongo, store, main

def test_state_persists_in_mongodb(monkeypatch):
    monkeypatch.setenv("MONGO_URI", "mongodb://test"); monkeypatch.setattr(pymongo, "MongoClient", mongomock.MongoClient)
    store._db = None
    main.load(reset=True)
    main.ST["claims"][0]["r"] = "approved"; main.log("approve claim #1")
    main.ST.clear(); main.load()                         # reload purely from MongoDB
    assert store.kind() == "mongodb"
    assert main.ST["claims"][0]["r"] == "approved" and len(main.ST["claims"]) == 14
    assert [s["id"] for s in main.ST["sources"]] == [f"S{i}" for i in range(1, 8)]
    assert store.db().audit.count_documents({}) == 1
    store._db = None
