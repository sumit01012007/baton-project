"""Streamlit interface for the Baton FastAPI service."""
import os

import requests
import streamlit as st


st.set_page_config(page_title="Baton | Project handover", page_icon="🧭", layout="wide")
st.markdown("""
<style>
.block-container {max-width: 1180px; padding-top: 2rem;}
[data-testid="stMetric"] {background: #f4f7fb; border: 1px solid #e4eaf2; padding: 14px 18px; border-radius: 12px;}
.stTabs [data-baseweb="tab-list"] {gap: 12px;}
</style>
""", unsafe_allow_html=True)
st.title("🧭 Baton")
st.caption("Evidence-linked, permission-aware project handover")

api_url = str(st.secrets.get("BATON_API_URL", os.getenv("BATON_API_URL", "http://localhost:8000"))).rstrip("/")
reviewer_key = str(st.secrets.get("REVIEWER_KEY", os.getenv("REVIEWER_KEY", "demo-reviewer")))

with st.sidebar:
    st.header("Connection")
    st.code(api_url, language=None)
    st.caption("Local default: http://localhost:8000")
    st.divider()
    st.caption("For Streamlit Cloud, set BATON_API_URL and REVIEWER_KEY in app Secrets.")


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
    st.error("Could not connect to the Baton API.")
    st.caption(f"{exc}")
    st.markdown("Start the backend in a second terminal, then refresh this page:")
    st.code("cd backend\npip install -r requirements.txt\nuvicorn main:app --reload --port 8000", language="powershell")
    st.markdown("For a hosted backend, configure `BATON_API_URL` in Streamlit Secrets.")
    st.stop()

review_tab, handover_tab, sources_tab = st.tabs(["Review", "Handover", "Sources"])

with review_tab:
    claims = state["claims"]
    reviewed = sum(claim["r"] != "pending" for claim in claims)
    attention = sum(claim["r"] == "pending" and claim["status"] in ("blocked", "conflict", "missing") for claim in claims)
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Claims", len(claims))
    m2.metric("Reviewed", f"{reviewed}/{len(claims)}")
    m3.metric("Need attention", attention)
    m4.metric("Handover", "Published" if state["published"] else "Draft")
    st.progress(reviewed / max(len(claims), 1), text="Review progress")
    st.caption(f"AI mode: {state['ai_mode']} · Storage: {state['storage']}")
    for claim in claims:
        title = f"{claim['type']}  ·  {claim['status'].title()}  ·  {claim['r'].title()}"
        with st.expander(title, expanded=claim["r"] == "pending"):
            st.write(claim["text"])
            levels = ["Public", "Team", "Confidential"]
            st.caption(f"{claim.get('date') or 'Undated'} · {levels[claim['lvl']]} sensitivity")
            for source_id, quote in claim.get("src", []):
                with st.expander(f"Evidence · {source_id}"):
                    st.markdown(f"> {quote}")
                    try:
                        source = api(f"/source/{source_id}?role=Reviewer")
                        st.caption(source["name"])
                        st.text(source["text"])
                    except Exception as exc:
                        st.caption(f"Could not load source: {exc}")
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

    if st.button("Re-run extraction", help="Rebuild claims from the current sources"):
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
            st.subheader(f"Handover v{handover['version']} · {role}")
            st.caption(f"{len(handover['visible'])} items visible · {handover['withheld']} withheld by clearance")
            st.markdown("### 5-day continuation plan")
            for day, items in handover["plan"]:
                with st.expander(day, expanded=True):
                    if items:
                        for item in items:
                            st.markdown(f"- **{item.get('type', 'Task')}:** {item['text']}")
                    else:
                        st.caption("No items for this phase.")
            for heading, items in [("Decisions and context", handover["context"]), ("Timeline", handover["timeline"])]:
                st.markdown(f"### {heading}")
                if items:
                    for item in items:
                        with st.container(border=True):
                            if item.get("date"):
                                st.caption(item["date"])
                            st.write(item["text"])
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
    st.subheader(f"Available sources ({len(state['sources'])})")
    for source in state["sources"]:
        with st.container(border=True):
            st.write(f"**{source['id']} · {source['name']}**")
            st.caption(f"{source['kind']} · {['Public', 'Team', 'Confidential'][source['lvl']]} access")
