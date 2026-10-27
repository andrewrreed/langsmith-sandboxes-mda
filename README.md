# LangSmith Sandboxes: from basics to an agent's workspace

Agents get far more capable when they can write and run code. [LangSmith Sandboxes](https://docs.langchain.com/langsmith/sandboxes) give them an isolated machine to do it in: a Firecracker microVM per sandbox, ready in under a second, with credentials kept outside it.

What is a LangSmith Sandbox, and how does a Managed Deep Agent use one?

| | What | Shows |
|---|---|---|
| [`notebooks/01_sandbox_basics.ipynb`](notebooks/01_sandbox_basics.ipynb) | The Sandbox SDK, step by step | create, run code, move files, preview an app, keep secrets out (auth proxy), egress allow lists, lifecycle (stop, wake, what survives), snapshots |
| [`notebooks/02_inside_the_agents_sandbox.ipynb`](notebooks/02_inside_the_agents_sandbox.ipynb) | The agent at work, then a look inside its sandbox | a dashboard, then a forecast in the same conversation; the data, code and outputs the agent left behind; state across turns |
| [`mda-snowflake-analyst/`](mda-snowflake-analyst/) | A Managed Deep Agent that analyzes Snowflake data in its sandbox | LangSmith Tools (per-user OAuth to Snowflake), skills, sandbox snapshots, shareable dashboards, deployment to an agent environment |
| [`slides/langsmith-sandboxes-mda.pdf`](slides/langsmith-sandboxes-mda.pdf) | The 11-slide deck | sandboxes, the auth proxy, lifecycle, the MDA runtime and folder, the LangSmith Tools gateway, deploying |
| [`docs/`](docs/) | How-tos | [Snowflake OAuth through LangSmith Tools](docs/snowflake-oauth-setup.md), [the MDA build → dev → deploy loop](docs/mda-workflow.md) |

## Setup

```bash
uv venv && uv pip install "langsmith>=0.14" langgraph-sdk python-dotenv ipykernel managed-deepagents mcp
cp .env.example .env   # LANGSMITH_API_KEY, LANGSMITH_WORKSPACE_ID
```

Notebook 01 needs only a LangSmith API key in a workspace with Sandboxes enabled. Notebook 02 talks to the agent running locally (`mda dev`), so it needs the agent set up first.

The agent also needs Snowflake (Cortex Analyst and managed MCP servers) and LangSmith Tools:

1. Run `snowflake/01_setup.sql` through `05_oauth.sql` (including `04b`) as `ACCOUNTADMIN`: TPC-H sample data, a semantic view, a Cortex Agent, managed MCP servers (the agent uses `ANALYST_MCP_SERVER`), and an OAuth client for LangSmith.
2. Run `scripts/create_snowflake_connection.sh` to create the OAuth connection and register the MCP server on the LangSmith **Tools** page, then click **Connect** there and sign in to Snowflake. [`docs/snowflake-oauth-setup.md`](docs/snowflake-oauth-setup.md) explains each step and why Snowflake needs manual OAuth; `scripts/verify_tools_server.py` checks the result.
3. Follow [`mda-snowflake-analyst/README.md`](mda-snowflake-analyst/README.md).

`snowflake/99_teardown.sql` removes the Snowflake objects.

New to MDA? [`docs/mda-workflow.md`](docs/mda-workflow.md) covers the build → dev → deploy loop, environments, deployment types and how sandboxes behave inside an agent.
