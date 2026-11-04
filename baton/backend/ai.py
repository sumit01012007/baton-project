"""AI integration. Claude proposes structured claims; the verifier (verifier.py) then audits every quote."""
import json, os, re
PROMPT = """You reconstruct the current state of a project for a handover.
Use ONLY the sources below. Return a JSON array. Each item:
{"type": one of Decision|Ownership|Risk|Dependency|Recurring problem|Next action|Contact|Overview|Conflict|Gap,
 "text": short factual statement, "date": optional string,
 "conflict": true only if sources disagree,
 "src": [[source_id, EXACT verbatim quote copied from that source], ...]}
Rules: every quote must be copied character-for-character. Never invent facts.
If sources disagree, use type Conflict and cite both. If something important is unknown, use type Gap with "src": [].
Return JSON only, no prose.

SOURCES:
"""
def mode():
    return "live" if os.getenv("ANTHROPIC_API_KEY") else "offline"

def extract_claims(sources, fallback):
    if mode() == "offline":
        return json.loads(json.dumps(fallback))
    import anthropic
    client = anthropic.Anthropic()
    body = "\n\n".join(f"[{s['id']}] {s['name']}\n{s['text']}" for s in sources)
    msg = client.messages.create(model=os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6"), max_tokens=4000,
                                 messages=[{"role": "user", "content": PROMPT + body}])
    txt = "".join(b.text for b in msg.content if b.type == "text")
    m = re.search(r"\[.*\]", txt, re.S)
    return json.loads(m.group(0)) if m else []
