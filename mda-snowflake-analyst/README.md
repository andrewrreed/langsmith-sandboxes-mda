# Snowflake analyst (Managed Deep Agent)

A [Managed Deep Agent](https://docs.langchain.com/langsmith/python/managed-deep-agents-overview) that answers sales questions from Snowflake, analyzes the data with code in its own [LangSmith sandbox](https://docs.langchain.com/langsmith/sandboxes), and hands back charts and interactive dashboards.

```text
question ─► snowflake_sales_analyst ─► snowflake_run_sql     (LangSmith Tools, as the signed-in user)
         ─► write CSVs + Python script ─► execute              (sandbox: pandas, Altair, statsmodels)
         ─► share_file                                         (chart preview + dashboard link)
```

## Try it

In one conversation:

1. *"Build me a revenue dashboard: monthly revenue trend, revenue by region by year, and the top-line KPIs."*
2. *"Add a 6-month revenue forecast to the dashboard."*

The second answer reuses the data already in the sandbox (no new Snowflake queries), trains a forecasting model, backtests it on the last 6 known months, and produces `dashboard_v2.html` with the forecast and a "How I built the forecast" summary. `../notebooks/02_inside_the_agents_sandbox.ipynb` runs both turns and opens the sandbox afterwards.

## Project layout

```text
agent.py                      model (Claude Sonnet 5.5 via LangSmith LLM Gateway), tools, middleware
instructions.md               how the agent queries, analyzes and answers
skills/dashboard/SKILL.md     how to build a dashboard and add a forecast (loaded on demand)
tools/mcp.py                  Snowflake MCP server, reached through LangSmith Tools
tools/artifacts.py            share_file: 7-day download link to a file in /workspace/out
middleware/artifact_links.py  fills {{link:<file>}} placeholders in answers; hides real URLs from the model
sandbox/__init__.py           one sandbox per conversation, stopped after 30 idle minutes
sandbox/setup.sh              one pip install, baked into the sandbox snapshot
identity.py                   callers authenticate with a LangSmith API key
```

## Design notes

- **No credentials in the agent or the sandbox.** Snowflake access goes through LangSmith Tools, which attaches each caller's own OAuth token outside the agent. The sandbox holds only data and code.
- **The sandbox is per conversation and persists between turns.** Follow-up questions build on the files from earlier turns. After 30 idle minutes it stops (files kept, processes gone) and wakes in seconds on the next turn; it's deleted 14 days after stopping.
- **Static, shareable dashboards.** The agent renders charts to SVG with Altair inside the sandbox and embeds them in one HTML file, shared with a 7-day download link that keeps working after the sandbox stops. Download links open with scripts disabled, which is why the charts are static; for an interactive app you would serve it from the sandbox with a service URL. Files are versioned (`_v1`, `_v2`).
- **The model never sees or copies URLs.** Signed links carry long tokens that models truncate, and a model will happily reuse a link from an earlier answer. The tools keep URLs in the ToolMessage `artifact` (not sent to the model) and return a per-file placeholder; `ArtifactLinksMiddleware` fills placeholders in the final answer and turns links in earlier answers back into placeholders before each model call.
- **Skills carry the know-how.** The `dashboard` skill holds the layout, an HTML template and the forecasting recipe (backtest first, then fit), loaded only when a dashboard is requested. `setup.sh` just installs packages.
- **Data path.** Query results pass through the model on their way into the sandbox, which suits aggregated results (hundreds of rows). For large data, aggregate in Snowflake, write results straight into the sandbox from a tool, let the sandbox pull data through the auth proxy, or mount a bucket.
- **Identity.** In `mda dev` a personal access token counts as you. On a deployment, per-user tools need a person behind the call: LangSmith Studio, Slack, or an identity provider (`identity.py`). API-key callers are service principals; use agent-owned credentials (LangSmith Tools profiles) for headless runs.

## Run

Prerequisites: the Snowflake objects in `../snowflake/` and the LangSmith Tools connection from `../scripts/create_snowflake_connection.sh` ([walkthrough](../docs/snowflake-oauth-setup.md)).

```bash
cp .env.example .env   # fill in values
uv sync
mda dev                # opens LangSmith Studio
```

## Deploy

```bash
mda deploy --agent-environment development
```

See [`../docs/mda-workflow.md`](../docs/mda-workflow.md) for the build → dev → deploy loop, environments and deployment types.
