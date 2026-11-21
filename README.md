# Recruiter Agent (Agent Maker-2026)

Runs the hiring cycle from job notice to released offer letter. Every offer and every rejection needs human approval.

## Setup and run
```bash
pip install -r requirements.txt
streamlit run app.py          # opens http://localhost:8501
python test_flow.py           # optional headless end-to-end test
```
The app works with no API key (rule-based demo mode). To use an LLM with tool calling, set ONE option in the same terminal before `streamlit run app.py`:

| Option | Windows PowerShell | Mac / Linux |
|---|---|---|
| Groq (free tier) | `$env:LLM_BASE_URL="https://api.groq.com/openai/v1"`<br>`$env:LLM_API_KEY="<key>"`<br>`$env:LLM_MODEL="llama-3.3-70b-versatile"` | `export LLM_BASE_URL=https://api.groq.com/openai/v1`<br>`export LLM_API_KEY=<key>`<br>`export LLM_MODEL=llama-3.3-70b-versatile` |
| Ollama (local, free) | `ollama pull llama3.1`, then `$env:LLM_BASE_URL="http://localhost:11434/v1"`, `$env:LLM_MODEL="llama3.1"` | same with `export` |
| Claude (paid) | `$env:ANTHROPIC_API_KEY="<key>"` | `export ANTHROPIC_API_KEY=<key>` |

Delete `recruiter.db` to reset all data.

## Demo flow
1. **Brief & JD:** pick a role (16 roles), a company (6 per role), location and package. Review the notice, click *Confirm notice* to download the short drive notice PDF and the detailed job description PDF.
2. Click **Run hiring cycle** (sidebar): the agent sources and scores candidates, shortlists, runs screening checks (notice period, salary expectation, location), books Tech interviews, runs Tech and HR rounds, and drafts offers and rejections.
3. **Pipeline / Interviews & Offers:** see candidates by stage, interview results and the offer tracker; redraft an offer after a counter-ask.
4. **Human Approvals:** enter a reviewer name, then approve or decline each offer and rejection. Only this step sends them.
5. **KPIs & Audit:** sourced per role, shortlist-to-interview ratio, time to hire, offer acceptance, hiring funnel, emails sent and a plain-language activity log.

## Design
| Slide element | Implementation |
|---|---|
| Role prompt, tool use | `agent.py`: LLM tool loop (`source_and_score`, `shortlist`, `run_screening`, `schedule_screened`, `run_interviews`, `draft_offer`, `pipeline_status`); rule-based fallback runs the same functions |
| Sourcing and scoring | rubric: must-have skills 60, preferred 15, experience 25; scoring sees blind profiles only |
| Interview calendar | SQLite slot calendar (`db.py`); Google/Outlook adapters are the swap-in point |
| Offer and rejection letters | drafted in `agent.py`, emails simulated into an outbox |
| Bias check | `guardrails.py` checks job text and rejection reasons; protected fields are stripped before scoring or LLM calls |
| Human sign-off | the LLM has no tool to release offers or rejections; `agent.decide()` needs a pending draft and a named reviewer |
| Audit log | every tool call, stage change and approval is logged |

## Scope notes
Stack differs from the slide's proposal (Streamlit + SQLite instead of Next.js + Supabase) to keep the 48-hour build runnable with one command. ATS, job boards and calendars are mocked with a synthetic candidate pool (`data/candidates.json`). Company names, locations and packages are indicative samples, and apply links are placeholders. Interview outcomes are simulated by the agent from candidate score and round performance.