import os, sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parents[1]))
os.environ.pop("ANTHROPIC_API_KEY", None)
from fastapi.testclient import TestClient
import main
c = TestClient(main.app); K = {"X-Reviewer-Key": "demo-reviewer"}

def setup_function(_): c.post("/api/reset", headers=K)

def test_reviewer_key_required(): assert c.get("/api/state").status_code == 401
def test_fabricated_quote_is_blocked():
    cl = {x["id"]: x for x in c.get("/api/state", headers=K).json()["claims"]}
    assert cl[12]["status"] == "blocked"
    assert c.patch("/api/claims/12", headers=K, json={"action": "approve"}).status_code == 409
def test_conflict_and_gap_need_human_edit():
    assert c.patch("/api/claims/3", headers=K, json={"action": "approve"}).status_code == 409
    assert c.patch("/api/claims/10", headers=K, json={"action": "edit", "text": "Sam approves."}).json()["status"] == "verified"
def test_publish_requires_full_review(): assert c.post("/api/publish", headers=K).status_code == 409
def test_redaction_and_source_access():
    for i in range(1, 15):
        s = c.get("/api/state", headers=K).json()["claims"][i - 1]
        if s["status"] == "blocked": c.patch(f"/api/claims/{i}", headers=K, json={"action": "reject"})
        elif s["status"] in ("conflict", "missing"): c.patch(f"/api/claims/{i}", headers=K, json={"action": "edit", "text": "Resolved by lead."}); c.patch(f"/api/claims/{i}", headers=K, json={"action": "approve"})
        else: c.patch(f"/api/claims/{i}", headers=K, json={"action": "approve"})
    assert c.post("/api/publish", headers=K).status_code == 200
    eng = c.get("/api/handover?role=Engineer").json(); mgr = c.get("/api/handover?role=Manager").json()
    assert eng["withheld"] == 2 and mgr["withheld"] == 0
    assert "Dana Whitfield" not in str(eng)
    assert c.get("/api/source/S5?role=Engineer").status_code == 403
    assert c.get("/api/source/S5?role=Manager").status_code == 200
