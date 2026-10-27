-- 05_oauth.sql: OAuth client so LangSmith Tools can sign users in to Snowflake.
-- Snowflake does not support OAuth dynamic client registration, so LangSmith uses a
-- manually configured client (an "Agent Auth" connection) with this redirect URI.
-- Run as ACCOUNTADMIN after 04. Then read the client ID/secret (never commit them):
--   SELECT SYSTEM$SHOW_OAUTH_CLIENT_SECRETS('LANGSMITH_TOOLS_OAUTH');
-- and run scripts/create_snowflake_connection.sh.
--
-- Already have an OAuth integration for another LangSmith product? Add this callback
-- as an alternate redirect instead of creating a new one:
--   ALTER SECURITY INTEGRATION <name> SET OAUTH_ALTERNATE_REDIRECT_URIS =
--     ('https://api.smith.langchain.com/v1/agent-auth/oauth/callback');
USE ROLE ACCOUNTADMIN;

CREATE SECURITY INTEGRATION IF NOT EXISTS LANGSMITH_TOOLS_OAUTH
  TYPE = OAUTH
  ENABLED = TRUE
  OAUTH_CLIENT = CUSTOM
  OAUTH_CLIENT_TYPE = 'CONFIDENTIAL'
  OAUTH_REDIRECT_URI = 'https://api.smith.langchain.com/v1/agent-auth/oauth/callback'
  OAUTH_ISSUE_REFRESH_TOKENS = TRUE
  OAUTH_REFRESH_TOKEN_VALIDITY = 86400
  OAUTH_USE_SECONDARY_ROLES = NONE
  ALLOWED_ROLES_LIST = ('FLEET_MCP_ROLE')
  COMMENT = 'LangSmith Tools -> FLEET_MCP_SERVER';
