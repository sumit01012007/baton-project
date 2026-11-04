"""Evidence verifier: deterministic, never trusts the AI. Decides each claim's status and sensitivity level."""
def _src(sources, sid):
    return next((s for s in sources if s["id"] == sid), None)

def level(claim, sources):
    lv = [s["lvl"] for sid, _ in claim["src"] if (s := _src(sources, sid))]
    return max(lv) if lv else 1

def status(claim, sources):
    spans = claim.get("src", [])
    if claim["type"] == "Gap" and not claim.get("h"):
        return "missing"
    for sid, quote in spans:                       # quote must exist verbatim in the cited source
        s = _src(sources, sid)
        if not s or quote not in s["text"]:
            return "blocked"
    if claim.get("conflict") and not claim.get("h"):
        return "conflict"
    if claim.get("h"):
        return "verified"
    return "verified" if len(spans) >= 2 or any(_src(sources, sid)["auth"] for sid, _ in spans) else "uncertain"
