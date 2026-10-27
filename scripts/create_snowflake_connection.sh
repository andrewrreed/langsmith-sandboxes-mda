#!/usr/bin/env bash
# Create the LangSmith "Agent Auth" OAuth connection that LangSmith Tools uses to sign
# users in to Snowflake, then register the Snowflake MCP server on the Tools page.
#
# Prerequisites: snowflake/01-05 applied; .env at the repo root with LANGSMITH_API_KEY
# (a personal access token) and LANGSMITH_WORKSPACE_ID; SNOWFLAKE_ACCOUNT_URL set,
# e.g. https://myorg-myaccount.snowflakecomputing.com
#
# The client secret is read from a hidden prompt and passed to mda through the
# environment only; it is never printed or written to disk.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SLUG="${CONNECTION_SLUG:-snowflake-sales-mcp}"
set -a; source "$ROOT/.env"; set +a
: "${SNOWFLAKE_ACCOUNT_URL:?Set SNOWFLAKE_ACCOUNT_URL, e.g. https://myorg-myaccount.snowflakecomputing.com}"

echo "From Snowsight: SELECT SYSTEM\$SHOW_OAUTH_CLIENT_SECRETS('LANGSMITH_TOOLS_OAUTH');"
read -r -p "OAUTH_CLIENT_ID: " CLIENT_ID
read -r -s -p "OAUTH_CLIENT_SECRET (hidden): " SF_OAUTH_CLIENT_SECRET; echo
export SF_OAUTH_CLIENT_SECRET

cd "$ROOT/mda-snowflake-analyst"
mda connections create "$SLUG" \
  --authorize-url "$SNOWFLAKE_ACCOUNT_URL/oauth/authorize" \
  --token-url "$SNOWFLAKE_ACCOUNT_URL/oauth/token-request" \
  --client-id "$CLIENT_ID" \
  --secret-from-env SF_OAUTH_CLIENT_SECRET \
  --auth-method client_secret_basic \
  --scope "session:role:FLEET_MCP_ROLE" \
  --scope "refresh_token"
unset SF_OAUTH_CLIENT_SECRET

echo "Registering the Snowflake MCP server on LangSmith Tools (workspace scope)..."
curl -sS -X POST "${LANGSMITH_ENDPOINT:-https://api.smith.langchain.com}/v1/managed-tools/servers" \
  -H "X-Api-Key: $LANGSMITH_API_KEY" -H "X-Tenant-Id: $LANGSMITH_WORKSPACE_ID" \
  -H "Content-Type: application/json" \
  -d "{\"name\": \"Snowflake-Sales-MCP\", \"scope\": \"workspace\",
       \"upstream_url\": \"$SNOWFLAKE_ACCOUNT_URL/api/v2/databases/FLEET_MCP/schemas/AGENTS/mcp-servers/ANALYST_MCP_SERVER\",
       \"connection\": {\"type\": \"oauth\", \"agent_auth_connection_slug\": \"$SLUG\"}}"
echo
echo "Next: Tools page -> MCP servers -> Workspace -> Snowflake-Sales-MCP -> Connect."
echo "Then set SNOWFLAKE_MCP_URL in mda-snowflake-analyst/.env to"
echo "  https://api.smith.langchain.com/v1/managed-tools/servers/<id from the response above>/mcp"
