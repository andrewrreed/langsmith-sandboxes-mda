# Connecting LangSmith Tools to Snowflake's MCP server with per-user OAuth

This walks through every step that lets an agent call Snowflake's managed MCP server **as the person using it**, without the agent ever holding a Snowflake credential.

## The moving parts

```text
                  ┌──────────────────────────── LangSmith ─────────────────────────────┐
 agent / MCP      │  Tools server (gateway URL)          Agent Auth connection          │      Snowflake
 client ─────────►│  "which MCP endpoint, which      ──► "how to sign a user in,      ──┼──►  OAuth client
 (MDA, Claude     │   connection, who is calling"        and each user's token"         │     (security integration)
  Code, Cursor)   │            │                                                        │         │
                  │            └──── forwards the call with the caller's token ─────────┼──►  managed MCP server
                  └────────────────────────────────────────────────────────────────────┘     (runs as that user's role)
```

| Piece | Lives in | Job |
|---|---|---|
| **OAuth client** (`SECURITY INTEGRATION`) | Snowflake | Trusts LangSmith as an app; says where to send users after sign-in and which roles a token may use |
| **Agent Auth connection** | LangSmith | Stores the OAuth client's ID, secret and endpoints; runs the sign-in flow; keeps each person's token and refreshes it |
| **Tools server** | LangSmith | Registers the MCP endpoint once, links it to the connection, and gives every client one gateway URL |

### Why Snowflake needs "manual" OAuth

Every OAuth app must be registered with the provider as a *client* (client ID, client secret, redirect URI). Many MCP servers (Notion, Linear, …) support **dynamic client registration**: the app registers itself on the fly, so "Automatic OAuth" on the Tools page just works. **Snowflake does not**, so an admin creates the client in Snowflake and gives LangSmith its ID and secret. That is "manual OAuth".

If you register Snowflake with *Automatic OAuth*, Connect fails with:

> Authorization server does not support automatic OAuth client registration. Create the connection with manual OAuth provider fields…

## Prerequisites

- Snowflake objects from `../snowflake/01_setup.sql`–`04b_analyst_mcp_server.sql` (data, semantic view, Cortex Agent, read-only role `FLEET_MCP_ROLE`, and two managed MCP servers: `FLEET_MCP_SERVER` with all three tools, `ANALYST_MCP_SERVER` with only `sales_analyst` and `run_sql`). This guide registers `ANALYST_MCP_SERVER`: the agent needs only those two tools, and one MCP server per tool set keeps each client to least privilege.
- The Snowflake user who will sign in has `FLEET_MCP_ROLE` as its **default role** and a **default warehouse** (MCP sessions run as the default role).
- `mda` CLI (`pip install managed-deepagents`), and a LangSmith **personal access token** (`lsv2_pt_…`) plus workspace ID in `../.env`.

Placeholders below: `<account-url>` = `https://<org>-<account>.snowflakecomputing.com` (hyphens, not underscores).

## Step 1 — Snowflake: create the OAuth client

Run as `ACCOUNTADMIN` (`../snowflake/05_oauth.sql`):

```sql
CREATE SECURITY INTEGRATION IF NOT EXISTS LANGSMITH_TOOLS_OAUTH
  TYPE = OAUTH
  ENABLED = TRUE
  OAUTH_CLIENT = CUSTOM
  OAUTH_CLIENT_TYPE = 'CONFIDENTIAL'                -- has a client secret
  OAUTH_REDIRECT_URI = 'https://api.smith.langchain.com/v1/agent-auth/oauth/callback'
  OAUTH_ISSUE_REFRESH_TOKENS = TRUE                 -- users don't re-sign-in every 10 minutes
  OAUTH_REFRESH_TOKEN_VALIDITY = 86400
  OAUTH_USE_SECONDARY_ROLES = NONE                  -- token can't pick up the user's other roles
  ALLOWED_ROLES_LIST = ('FLEET_MCP_ROLE');          -- only the read-only role
```

`https://api.smith.langchain.com/v1/agent-auth/oauth/callback` is LangSmith Agent Auth's callback on US cloud. Step 3 prints it too; they must match exactly.

**Already have an integration for another LangSmith surface** (for example a Fleet "OAuth 2.1 (Manual)" connection)? Don't create a second client. Add the Agent Auth callback as an **alternate** redirect URI; the existing redirect keeps working:

```sql
ALTER SECURITY INTEGRATION <existing_integration>
  SET OAUTH_ALTERNATE_REDIRECT_URIS = ('https://api.smith.langchain.com/v1/agent-auth/oauth/callback');

DESC SECURITY INTEGRATION <existing_integration>;   -- check OAUTH_REDIRECT_URI is unchanged
```

## Step 2 — Snowflake: read the client ID and secret

```sql
SELECT SYSTEM$SHOW_OAUTH_CLIENT_SECRETS('LANGSMITH_TOOLS_OAUTH');
```

Returns JSON with `OAUTH_CLIENT_ID` and `OAUTH_CLIENT_SECRET`. Treat the secret like a password: don't paste it into chat, tickets or files.

## Step 3 — LangSmith: create the Agent Auth connection

This stores the OAuth client in LangSmith under a name (slug). It's the equivalent of Fleet's "OAuth 2.1 (Manual)" form.

```bash
read -r -s -p "Client secret: " SF_OAUTH_CLIENT_SECRET; echo; export SF_OAUTH_CLIENT_SECRET

mda connections create snowflake-sales-mcp \
  --authorize-url "<account-url>/oauth/authorize" \
  --token-url     "<account-url>/oauth/token-request" \
  --client-id     "<OAUTH_CLIENT_ID>" \
  --secret-from-env SF_OAUTH_CLIENT_SECRET \
  --auth-method client_secret_basic \
  --scope "session:role:FLEET_MCP_ROLE" \
  --scope "refresh_token"

unset SF_OAUTH_CLIENT_SECRET
```

| Flag | Why |
|---|---|
| `--authorize-url`, `--token-url` | Snowflake's OAuth endpoints (also shown by `DESC SECURITY INTEGRATION` as `OAUTH_AUTHORIZATION_ENDPOINT` / `OAUTH_TOKEN_ENDPOINT`) |
| `--secret-from-env` | The secret goes from a hidden prompt into the CLI's environment; never on screen or in shell history |
| `--auth-method client_secret_basic` | How Snowflake expects the client to authenticate at the token endpoint |
| `--scope session:role:FLEET_MCP_ROLE` | Ask for a token limited to the read-only role |
| `--scope refresh_token` | Ask for a refresh token |

Output:

```text
◇  OAuth connection created
│  snowflake-sales-mcp
│  Redirect URI: https://api.smith.langchain.com/v1/agent-auth/oauth/callback
└  Scopes: session:role:FLEET_MCP_ROLE refresh_token
```

Check the redirect URI matches step 1. Inspect it any time with `mda connections get snowflake-sales-mcp`.

No user has signed in yet: the connection is a container. Each person's token is added when they click **Connect** (step 5).

## Step 4 — LangSmith: register the Tools server

The connection knows *how to get a Snowflake token*. The Tools server says *which MCP endpoint to call with it* and creates the gateway URL clients use.

**In the UI** (Tools → MCP servers → **+ Add MCP server**): name, URL `<account-url>/api/v2/databases/FLEET_MCP/schemas/AGENTS/mcp-servers/ANALYST_MCP_SERVER`, Authentication **OAuth**, OAuth Setup **Manual OAuth**, then pick the connection. Manual OAuth appears only when *Agent Auth Connections* is enabled for the organization.

**Through the API** (works whenever the connection exists):

```bash
curl -sS -X POST "https://api.smith.langchain.com/v1/managed-tools/servers" \
  -H "X-Api-Key: $LANGSMITH_API_KEY" -H "X-Tenant-Id: $LANGSMITH_WORKSPACE_ID" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Snowflake-Sales-MCP",
    "scope": "workspace",
    "upstream_url": "<account-url>/api/v2/databases/FLEET_MCP/schemas/AGENTS/mcp-servers/ANALYST_MCP_SERVER",
    "connection": {"type": "oauth", "agent_auth_connection_slug": "snowflake-sales-mcp"}
  }'
```

- `"connection": {"type": "oauth"}` *without* a slug means **Automatic OAuth** — the setting that fails for Snowflake.
- `"scope": "workspace"` shares the server with the workspace (each person still signs in as themselves). `"personal"` is visible only to you, and can't be used by tool kits or profiles.
- An upstream URL can be registered only once per workspace, across scopes (`409 url_conflict`). Servers can't be edited through the API, only deleted and re-registered. Deleting a server keeps its connection and everyone's tokens.
- Tokens belong to the **connection**, not the server: a second server on the same connection shows as connected for anyone who already signed in.

The response includes `"id"`; the gateway URL is `https://api.smith.langchain.com/v1/managed-tools/servers/<id>/mcp`.

## Step 5 — Each user connects

Tools → MCP servers → find the server → **Connect** → normal Snowflake sign-in → done. LangSmith now holds that person's token.

Through the API, a call from someone who hasn't connected yet returns `428` with a `verification_url` to open:

```json
{"status": 428, "kind": "oauth", "slug": "snowflake-sales-mcp", "verification_url": "<account-url>/oauth/authorize?client_id=…&redirect_uri=https%3A%2F%2Fapi.smith.langchain.com%2Fv1%2Fagent-auth%2Foauth%2Fcallback&…"}
```

For agents with no person behind them (schedules, background jobs), a workspace admin connects a **profile** instead and the agent sends `X-LangSmith-Profile: <profile-id>`.

## Step 6 — Verify

```bash
python ../scripts/verify_tools_server.py <server-id>
```

Expected: the tool list (`sales_analyst`, `run_sql`), then SQL from `sales_analyst` and rows from `run_sql`.

## Step 7 — Use it from an agent

Point any MCP client at the gateway URL with a LangSmith key. In this repo's Managed Deep Agent (`../mda-snowflake-analyst/tools/mcp.py`):

```python
mcp = define_mcp(servers={
    "snowflake": {
        "transport": "http",
        "url": os.environ["SNOWFLAKE_MCP_URL"],   # .../managed-tools/servers/<id>/mcp
        "include_tools": ["sales_analyst", "run_sql"],
    },
})
```

No headers, no token: the MDA runtime authenticates the caller to LangSmith, and the gateway attaches that caller's Snowflake token.

Whose token is used depends on who is calling:

| Caller | Identity used |
|---|---|
| `mda dev` with a personal access token | You |
| LangSmith Studio on a deployment | The signed-in user |
| Slack channel | The Slack user |
| SDK / app with a LangSmith API key | A service principal: per-user OAuth fails (`user-owned connections require a person principal`); use a profile, or configure `identity.py` (Supabase, or a trusted backend that passes the user) |

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `oauth_manual_client_required` on Connect | Server registered with Automatic OAuth | Re-register with the Agent Auth connection (step 4) |
| `409 url_conflict` when registering | Another server (any scope) already uses that upstream URL | Delete it, or register a separate Snowflake MCP server (its own URL), like `ANALYST_MCP_SERVER` |
| Snowflake error `invalid redirect_uri` during sign-in | Callback not on the integration | Step 1 (`OAUTH_REDIRECT_URI` or `OAUTH_ALTERNATE_REDIRECT_URIS`) |
| `invalid_client` | Wrong client ID/secret, or a Snowflake network policy blocking LangSmith | Recheck step 2–3; allowlist LangSmith egress IPs |
| `428` with `verification_url` | That user hasn't connected | Step 5 |
| Tool calls fail with role/warehouse errors | User lacks default role or warehouse | `ALTER USER … SET DEFAULT_ROLE = FLEET_MCP_ROLE DEFAULT_WAREHOUSE = FLEET_MCP_WH` |
