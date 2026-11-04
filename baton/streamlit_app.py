"""Streamlit interface for the Baton FastAPI service.

Configure BATON_API_URL in Streamlit secrets with the deployed backend URL.
"""
import os

import requests
import streamlit as st


st.set_page_config(page_title="Baton handover", page_icon="🧭", layout="wide")
st.title("Baton")
st.caption("Evidence-linked, permission-aware project handover")

api_url = str(st.secrets.get("BATON_API_URL", os.getenv("BATON_API_URL", ""))).rstrip("/")
reviewer_key = str(st.secrets.get("REVIEWER_KEY", os.getenv("REVIEWER_KEY", "demo-reviewer")))

if not api_url:
    st.error("Set BATON_API_URL in Streamlit app settings → Secrets to your deployed FastAPI URL.")
    st.code('BATON_API_URL = "https://your-backend.example.com"\nREVIEWER_KEY = "your-reviewer-key"', language="toml")
    st.stop()


def api(path, method="GET", **kwargs):
    response = requests.request(
        method,
        f"{api_url}/api{path}",
        headers={"X-Reviewer-Key": reviewer_key},
        timeout=30,
        **kwargs,
    )
    try:
        body = response.json()
    except ValueError:
        body = {"detail": response.text or response.reason}
    if not response.ok:
        raise RuntimeError(body.get("detail", response.reason))
    return body


try:
    state = api("/state")
except Exception as exc:
    st.error(f"Could not connect to the Baton API: {exc}")
    st.stop()

review_tab, handover_tab, sources_tab = st.tabs(["Review", "Handover", "Sources"])

with review_tab:
    claims = state["claims"]
    reviewed = sum(claim["r"] != "pending" for claim in claims)
    st.subheader("Handover readiness")
    st.progress(reviewed / max(len(claims), 1), text=f"{reviewed} of {len(claims)} claims reviewed")
    st.caption(f"AI: {state['ai_mode']} · Storage: {state['storage']}")
    for claim in claims:
        title = f"{claim['type']} · {claim['status'].title()} · {claim['r'].title()}"
        with st.expander(title, expanded=claim["r"] == "pending"):
            st.write(claim["text"])
            st.caption(f"Sensitivity level: {claim['lvl']} · Sources: {', '.join(src for src, _ in claim.get('src', [])) or 'None'}")
            if claim["r"] == "pending":
                col1, col2 = st.columns(2)
                blocked = claim["status"] in ("blocked", "conflict", "missing")
                if col1.button("Approve", key=f"approve-{claim['id']}", disabled=blocked):
                    try:
                        api(f"/claims/{claim['id']}", "PATCH", json={"action": "approve"})
                        st.rerun()
                    except Exception as exc:
                        st.error(str(exc))
                if col2.button("Reject", key=f"reject-{claim['id']}"):
                    try:
                        api(f"/claims/{claim['id']}", "PATCH", json={"action": "reject"})
                        st.rerun()
                    except Exception as exc:
                        st.error(str(exc))
                corrected = st.text_area("Correct claim", value=claim["text"], key=f"edit-{claim['id']}")
                if st.button("Save correction", key=f"save-{claim['id']}"):
                    try:
                        api(f"/claims/{claim['id']}", "PATCH", json={"action": "edit", "text": corrected})
                        st.rerun()
                    except Exception as exc:
                        st.error(str(exc))

    if st.button("Re-run extraction"):
        try:
            api("/extract", "POST")
            st.rerun()
        except Exception as exc:
            st.error(str(exc))
    if reviewed == len(claims) and not state["published"]:
        if st.button("Approve and publish handover", type="primary"):
            try:
                api("/publish", "POST")
                st.rerun()
            except Exception as exc:
                st.error(str(exc))
    elif state["published"]:
        st.success("Handover published")

with handover_tab:
    role = st.selectbox("Incoming team member role", ["Intern", "Engineer", "Manager"])
    try:
        handover = api(f"/handover?role={role}")
        if not handover.get("published"):
            st.info("No approved handover has been published yet.")
        else:
            st.subheader(f"Handover v{handover['version']}")
            st.caption(f"{len(handover['visible'])} items visible · {handover['withheld']} withheld by clearance")
            for heading, items in [("5-day continuation plan", [item for _, group in handover["plan"] for item in group]),
                                   ("Decisions and context", handover["context"]),
                                   ("Timeline", handover["timeline"])]:
                st.markdown(f"#### {heading}")
                if items:
                    for item in items:
                        st.write(f"**{item.get('date', '')}** {item['text']}")
                else:
                    st.caption("No items to show.")
            if not handover["acks"].get(role):
                if st.button("Acknowledge receipt"):
                    try:
                        api(f"/ack?role={role}", "POST")
                        st.rerun()
                    except Exception as exc:
                        st.error(str(exc))
            else:
                st.success("Receipt acknowledged")
    except Exception as exc:
        st.error(str(exc))

with sources_tab:
    st.write("Import a text, Markdown, or CSV source and choose its sensitivity level.")
    uploaded = st.file_uploader("Source file", type=["txt", "md", "csv"])
    level = st.selectbox("Sensitivity", ["Public", "Team", "Confidential"], index=1)
    if uploaded and st.button("Import source"):
        try:
            api("/sources", "POST", files={"file": (uploaded.name, uploaded.getvalue())}, data={"lvl": ["Public", "Team", "Confidential"].index(level)})
            st.success("Source imported")
            st.rerun()
        except Exception as exc:
            st.error(str(exc))
    for source in state["sources"]:
        st.write(f"**{source['id']} · {source['name']}** — {source['kind']} · {['Public', 'Team', 'Confidential'][source['lvl']]}")
