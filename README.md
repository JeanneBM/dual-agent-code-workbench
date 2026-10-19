# Dual Agent Code Workbench

One local window for GPT and Claude to propose, review and revise code changes.

**Status: local review-first PoC.** Working Streamlit UI, bounded orchestration,
GitHub PR import, separate provider adapters, optional SQLite history and JSON export.
Demo output is scripted. Live adapters are tested with mocked HTTP; real model
access, quality, quotas and billing require validation with your own accounts.

## Start locally

Python 3.11+ (CI: 3.12). From the project directory:

```bash
git clone https://github.com/JeanneBM/dual-agent-code-workbench.git
cd dual-agent-code-workbench
python -m venv .venv
# Linux/macOS:
source .venv/bin/activate
# PowerShell instead: .venv\Scripts\Activate.ps1
python -m pip install -e '.[dev]'
python -m streamlit run app.py
```

Open http://127.0.0.1:8501. Demo needs no keys or Azure resources. Stop with Ctrl+C.
UI telemetry is disabled. Run from the repository root.

## Connect GPT and Claude

Copy `.env.example` to `.env`, then set `OPENAI_API_KEY`, `OPENAI_MODEL`,
`ANTHROPIC_API_KEY` and `ANTHROPIC_MODEL` to values available in your accounts.
No model ID is assumed or silently substituted. Restart after changing configuration.
Select **live**, inspect the code context and explicitly consent to sending it.
The app uses OpenAI Responses and Anthropic Messages directly. API access and
billing are separate from this app; existing chat subscriptions are not used as credentials.

These are new API sessions, not your existing ChatGPT/Claude chats. Shared context
consists of the supplied task/source, candidate proposal and peer findings.

## One task, a bounded exchange

1. Paste source/diff and acceptance criteria, or import one GitHub PR snapshot.
2. Choose GPT or Claude as author; the other becomes reviewer.
3. Author proposes code; reviewer returns structured findings.
4. With two rounds, author revises once using the findings; reviewer reviews again.
5. Read both sides and download the record. No autonomous merge decision is made.

One round makes at most two calls; two rounds at most four. No automatic retries.
Output tokens are capped per call; context is capped at 40000 characters. This
limits request size/count but does not guarantee a dollar spend ceiling. Configure
provider account budgets separately. Usage fields are reported when available;
unknown usage is not assumed zero. API errors, malformed or truncated output stop
the run as `incomplete`, not as a code defect or approval. Any finding produces
`needs_changes`; an empty valid review produces `human_review`, never auto-approval.

## GitHub and local history

PR import only reads `api.github.com`, checks the head/base did not move during
import and includes their SHAs. Optional `GITHUB_TOKEN` enables private repository
reads; use minimum read permissions. Large, renamed, binary or missing-patch file
sets are rejected instead of silently summarised. A diff alone cannot establish
whole-repository correctness; add source and actual test output as needed.

Saving is opt-in. `.local/runs.sqlite` contains raw tasks, supplied code and replies,
not API keys. History can be opened/deleted in the sidebar. Deletion removes the
logical record, not forensic copies, backups or provider-side data. JSON exports
contain the same context. Do not commit them blindly. `.env` and `.local` are ignored.

## Boundaries

- No shell tools, repository writes, generated-code execution, automatic tests,
  PR publication, chat-history syncing or background autonomous loops.
- Prompts treat diff/peer content as untrusted. This is not a claim of prompt-injection
  immunity. Neither model has tools or access to credentials in its input.
- Intended for one local operator on loopback. No hosted multiuser authentication.
- Review findings remain probabilistic; independent review is not proof.
- This initial milestone is review/proposal collaboration. Applying patches in an
  isolated worktree, sandboxed tests and approved PR creation are future work.

## Validation

```bash
python -m pytest -q
```

Offline tests cover routing, revision feedback, bounded rounds, malformed reviews,
provider failures, truncation, provider request contracts, history and GitHub import.
Streamlit AppTest checks the demo interface. No paid calls are required by CI.

## Layout

| File | Purpose |
|---|---|
| `app.py` | One-window UI and optional persistence |
| `workbench/engine.py` | Bounded author/reviewer exchange and review validation |
| `workbench/providers.py` | GPT, Claude and clearly labelled demo adapters |
| `workbench/github.py` | Read-only PR snapshot import |
| `workbench/store.py` | Local run history |
| `tests/` | Offline contract, orchestration and UI checks |

API references: [OpenAI text generation](https://developers.openai.com/api/docs/guides/text)
and [Anthropic Messages](https://platform.claude.com/docs/en/build-with-claude/working-with-messages).
