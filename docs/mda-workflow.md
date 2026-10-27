# Building, iterating and deploying with Managed Deep Agents

A Managed Deep Agent (MDA) is a directory. Each file's location gives it a role (`agent.py`, `instructions.md`, `tools/`, `sandbox/`, …), and the `mda` CLI compiles the directory into an agent running on LangSmith Deployments.

## The loop

```text
mda init ─► uv sync ─► edit ─► mda build ─► mda dev (Studio) ─► mda deploy ─► observe ─► edit …
```

| Step | Command | What it does |
|---|---|---|
| Scaffold | `mda init my-agent --model anthropic:claude-sonnet-5` then `cd my-agent && uv sync` | Creates the project, `.env` placeholders and a `sandbox/` folder (`--no-sandbox` skips it) |
| Compile check | `mda build` | Compiles into `.mda/build` without running anything; catches structure errors fast |
| Iterate locally | `mda dev` | Local Agent Server plus LangSmith Studio, hot reload, and a **real** LangSmith sandbox (bakes `sandbox/setup.sh` on start). Restart it after adding a new managed file (`tools/mcp.py`, `memory.py`, `schedules/`, `channels/`) |
| Chat from the terminal | `mda chat` | Same as Studio, in the shell |
| Credentials | `mda connections create / list / get` | Workspace-scoped secrets and OAuth clients the agent resolves at runtime |
| Ship | `mda deploy --agent-environment development` | Creates the deployment, or adds a new **revision** if it exists (details below) |
| Observe | Studio, the agent's traces, `mda logs` | Deployed runs trace to the agent's environment |
| Remove | `mda delete` | Deletes the deployment, its sandboxes and snapshots, and its Context Hub repo (traces stay) |

## What `mda deploy` does

1. **Compiles** the project into a managed LangGraph app.
2. **Syncs** `instructions.md` and `skills/` to Context Hub (editable in the UI; `--context-strategy overwrite|keep-hub` resolves UI edits).
3. **Forwards** non-reserved `.env` values as deployment secrets (model keys, `SNOWFLAKE_MCP_URL`, …). The shell environment is *not* forwarded.
4. **Bakes** the sandbox snapshot from `sandbox/setup.sh`, only when the script changed. New threads clone it.
5. **Uploads and builds**, then waits for `DEPLOYED` (`--no-wait` returns early; avoid it when schedules change).

Run it again after any change; each run is a new revision of the same deployment.

## Names, environments and deployment types

- **One name everywhere.** The agent's `name` in `agent.py` is its ID. Local `mda dev` runs trace to `<name>-local`; `mda deploy --agent-environment development|staging|production` deploys `<name>-<environment>`. All of them appear as **one agent with several environments** on the Agents page. Passing a different `--name` creates a separate agent.
- **Promote by environment.** Deploy `development`, test it, then deploy the same code with `--agent-environment staging` and `production`.
- **Deployment type is fixed at creation.** `--deployment-type dev` (the default) creates a **Serverless** deployment: one small replica that scales to zero when idle and wakes on the next request (cold start). `prod` creates a **Dedicated** deployment: always on, autoscaling, its own highly available database. Use Serverless for development and background agents, Dedicated for latency-sensitive production.

## Sandboxes inside an MDA

- Declared by `sandbox/__init__.py`; delete the folder to run without one.
- **One sandbox per conversation thread.** Follow-up turns in the same thread find the files from earlier turns.
- **Lifecycle:** running → *stopped* after `idle_ttl_seconds` of no activity → *deleted* 14 days after stopping (default). A stopped sandbox wakes in a few seconds on the next command, file read or URL request, **with its files intact**. Running processes (a web server, a background job) do not survive a stop.
- **`sandbox/setup.sh`** runs once at bake time; packages and files it installs are in every thread's sandbox. Never write secrets to disk there.
- **From your own code** (tools, middleware), `runtime.backend` reads and writes the thread's sandbox (`read`, `write`, `execute`, `upload_files`, `download_files`).
- **Sharing outputs:** download links (`generate_download_url`) suit static files and images; browsers open them with scripts disabled. For anything interactive (a dashboard, an app), serve it from the sandbox and share a **service URL** (`sandbox.service(port)`), which works while the sandbox is awake.
- **Outbound credentials** belong in `define_sandbox(proxy_config=…)` rules (workspace secrets or connections), not in sandbox environment variables.

## Secrets and connections

| Kind of credential | Put it in |
|---|---|
| Model key, simple config | `.env` (forwarded as a deployment secret) or a LangSmith workspace secret |
| A shared API key for a tool | `mda connections create <slug> --secret-from-env VAR` (agent-owned) |
| Each user's own account (OAuth) | A connection with user ownership, or a **LangSmith Tools** server (register once, reuse across agents) |
| Credentials sandbox code needs | Sandbox proxy rules (`workspace_secret` or a connection) |

## Who the agent acts as

| Caller | Identity |
|---|---|
| `mda dev` with a personal access token | You |
| Studio on a deployment | The signed-in user |
| Slack channel | The Slack user |
| SDK or app with a LangSmith API key | A service principal (per-user OAuth won't resolve; use agent-owned credentials, or configure `identity.py`) |

## Team practices

- **Deploy from GitHub** for shared agents: LangSmith builds on push, the repository is the source of truth for instructions and skills, and pull requests can get **preview builds** (temporary deployments with an idle TTL).
- Keep `.env` out of git (`mda init` adds it to `.gitignore`); check in `.env.example`.
- Test locally with `mda dev`, deploy to `development`, and promote the same commit to `staging` and `production`.
- Treat `mda delete` as destructive: it removes the deployment and its sandboxes and snapshots.
