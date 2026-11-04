# Baton – Evidence-Linked, Permission-Aware Knowledge Handover

```
baton/
├── backend/            FastAPI service (the only place trust decisions are made)
│   ├── main.py         REST API, review workflow, redaction, versioning, audit log
│   ├── ai.py           Claude integration: proposes structured claims from sources
│   ├── verifier.py     Deterministic quote check + confidence labels (never trusts the AI)
│   ├── data/seed.json  Synthetic project data (offline mode)
│   └── tests/          pytest: fabricated quotes, redaction, permissions
├── backend/store.py    MongoDB persistence (JSON-file fallback) + audit collection
├── frontend/           Static UI (HTML/CSS/JS), talks to /api only
├── .env.example
└── run.sh
```

## Run
```
./run.sh            # creates venv, installs deps, runs tests, serves http://localhost:8000
```
Windows: `cd backend && pip install -r requirements.txt && uvicorn main:app --port 8000`.

## AI integration
Set `ANTHROPIC_API_KEY` (see `.env.example`) and click **Re-extract with Claude** on the Review tab.
Claude returns claims with verbatim quotes; `verifier.py` then checks each quote exists in its source.
Fabricated quotes are *Blocked*; conflicts and gaps need a human edit; humans approve before anything is shared.
Without a key the app runs in offline mode using seed claims (the review, verification and permission flow all still work).

## Storage (MongoDB)
Set `MONGO_URI` (e.g. `mongodb://localhost:27017`) in `.env`. Quick local database: `docker compose up -d`.
Collections: `sources`, `claims`, `meta` (version, publish state, acknowledgements, history) and `audit` (append-only event trail).
With no `MONGO_URI` the app falls back to `backend/data/state.json`. For Atlas, use your `mongodb+srv://` URI.

## Data flow
Sources (with sensitivity labels) → Claude extraction → verifier → human review → publish → server-side redaction per role → incoming person → acknowledgement.

## Disclosure (hackathon rule 7)
- Code scaffolded with Claude (Anthropic); the AI component calls Claude via the Anthropic API.
- Team: <names> reviewed and tested the code. Your own changes: <list here>.

## Known limitations

