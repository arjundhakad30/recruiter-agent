# Recruiter Agent (Agent Maker-2026)

Runs the hiring cycle from job description to released offer letter, with a human checkpoint on every offer and rejection.

## Run
```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-...      # optional; without it the agent runs a deterministic demo cycle
export CLAUDE_MODEL=claude-sonnet-5-5  # optional override
streamlit run app.py
python test_flow.py                  # headless end-to-end test
```

## Demo flow (matches slides: Brief → Source → Shortlist → Interview → Offer)
1. **Brief & JD**: draft a JD, edit rubric. Bias check blocks saving JDs with age/gender/etc. criteria.
2. Sidebar **Run hiring cycle**: agent sources and scores blind profiles, shortlists, runs screening checks (notice, expectation, location), books Tech interviews on the calendar and sends invites.
3. **Interviews & Offers**: mark Tech/HR pass or fail. HR pass → agent drafts offer; failures → rejection drafts. Negotiation: enter a counter-ask and the agent redrafts within the budget ceiling.
4. **Human Approvals**: named reviewer edits final CTC, approves or declines. Only this step releases offers or sends rejections.
5. **KPIs & Audit**: candidates sourced, shortlist-to-interview, time to hire, offer acceptance, plus outbox and full audit log.

## Design
| Slide element | Implementation |
|---|---|
| Role prompt, tool use | `agent.py` Claude tool loop (`source_and_score`, `shortlist`, `run_screening`, `schedule_screened`, `draft_offer`, `pipeline_status`) |
| Sourcing search strings | `search_string()` boolean query shown in UI |
| Interview calendar | SQLite slot calendar (`db.py`); Google/Outlook adapters are the swap-in point |
| Offer templates / email | drafts in `agent.py`; emails simulated into `outbox` |
| Bias check | `guardrails.check_text` on JD, rubric and rejection reasons |
| Privacy | `guardrails.sanitize` strips name, gender, age, contact before scoring/LLM; pipeline board shows blind IDs |
| Human sign-off | no release tool exists for the LLM; `agent.decide()` requires a pending draft and named reviewer |
| Audit log | every tool call, stage change, approval logged |

## Scope notes
Stack differs from the slide's proposal (Streamlit + SQLite instead of Next.js + Supabase) to keep the 48-hour build runnable with one command; the data layer and tools are isolated so they can be ported. ATS, job boards and calendars are mocked with a local candidate pool (`data/candidates.json`, synthetic).
