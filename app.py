import json
import os
from pathlib import Path

from dotenv import load_dotenv
import streamlit as st
from workbench.engine import Request, run
from workbench.providers import DemoProvider, live_providers
from workbench.store import Store
from workbench.github import load_pr, GitHubError

load_dotenv()
st.set_page_config(page_title="Dual Agent Workbench", page_icon="↔", layout="wide")
st.title("Dual Agent Code Workbench")
st.caption("One task. Two perspectives. Your decision.")
store = Store()

with st.sidebar:
    st.header("Session controls")
    mode = st.radio("Execution", ["demo", "live"], help="Demo is scripted and makes no network calls.")
    author = st.selectbox("Proposal author", ["GPT", "Claude"])
    st.caption(f"Independent reviewer: {'Claude' if author == 'GPT' else 'GPT'}")
    rounds = st.slider("Review rounds", 1, 2, 1)
    tokens = st.slider("Output tokens per call", 512, 8000, 3000, step=128)
    st.caption(f"At most {rounds * 2} provider calls. No automatic retries. This is not a dollar budget.")
    if mode == "live":
        st.caption("Model IDs and keys come from .env on this machine.")
        st.text(f"GPT: {os.getenv('OPENAI_MODEL') or 'not configured'}")
        st.text(f"Claude: {os.getenv('ANTHROPIC_MODEL') or 'not configured'}")
    st.divider()
    st.subheader("Saved runs")
    saved = store.list()
    selected = st.selectbox("Local history", [""] + [r[0] for r in saved],
                            format_func=lambda x: x[:12] if x else "Select a run")
    if selected and st.button("Open run"):
        st.session_state.result = store.get(selected)
    if selected and st.button("Delete saved run"):
        store.delete(selected)
        if st.session_state.get('result', {}).get('id') == selected:
            del st.session_state.result
        st.rerun()

st.info("Local PoC: proposals and peer review only. Code is not applied, tests are not run, and PRs are not posted.")
with st.expander("Import a GitHub PR (read-only)"):
    pr = st.text_input("PR URL")
    if st.button("Load PR context"):
        try:
            st.session_state.context = load_pr(pr, os.getenv("GITHUB_TOKEN", ""))
            st.success("Loaded a snapshot with base and head commit IDs. Add acceptance criteria below.")
        except GitHubError as e:
            st.error(str(e))

if "context" not in st.session_state:
    st.session_state.context = Path("examples/context.diff").read_text()
task = st.text_area("Task and acceptance criteria", value="Review this change. Reject empty input explicitly and preserve the existing behavior for nonempty lists.", height=100)
context = st.text_area("Source context or diff", key="context", height=230)
st.caption(f"{len(context):,} / 40,000 characters. Supply relevant surrounding source and test output when needed.")
consent = st.checkbox("Send this task/context and intermediate model replies to both API providers") if mode == "live" else True
persist = st.checkbox("Save task, code context and replies in local SQLite", value=False)
if st.button("Start collaboration", type="primary", disabled=not consent):
    try:
        request = Request(task, context, author, rounds, tokens, mode)
        request.validate()
        providers = live_providers() if mode == "live" else {n: DemoProvider(n) for n in ("GPT", "Claude")}
        with st.status("Agents are collaborating…", expanded=True) as status:
            result = run(request, providers, emit=lambda e: st.write(f"{e['provider']} · {e['role']} completed"))
            status.update(label="Run finished — inspect the record below", state="error" if result['status'] == 'incomplete' else "complete")
        st.session_state.result = result
        if persist:
            store.save(result)
    except ValueError as e:
        st.error(str(e))

if result := st.session_state.get("result"):
    st.divider()
    st.subheader("Collaboration record")
    a, b, c = st.columns(3)
    a.metric("State", result["status"])
    b.metric("Provider calls", result["calls"])
    c.metric("Executed tests", "None")
    if result["request"]["mode"] == "demo":
        st.warning("SCRIPTED DEMO — not live model output.")
    if result.get("error"):
        st.error(result["error"])
    left, right = st.columns(2)
    for e in result["events"]:
        with left if e["provider"] == "GPT" else right:
            st.markdown(f"### {e['provider']} · {e['role']}")
            st.code(e["text"], language="json" if e["role"] == "review" else "text", wrap_lines=True)
            st.caption(f"Reported tokens: input={e['input_tokens']}, output={e['output_tokens']}")
    st.caption("A positive review is a model opinion. Human review is always required; provider agreement is not a test result.")
    st.download_button("Download complete JSON record", json.dumps(result, indent=2),
                       file_name=f"run-{result['id']}.json", mime="application/json")
