-- 99_teardown.sql: removes everything this demo created, and nothing else.
-- Replace {{SNOWFLAKE_USER}} with the same user as in 01_setup.sql.
USE ROLE ACCOUNTADMIN;

DROP SECURITY INTEGRATION IF EXISTS LANGSMITH_TOOLS_OAUTH;
DROP DATABASE IF EXISTS FLEET_MCP;          -- data, semantic view, agent, both MCP servers
DROP WAREHOUSE IF EXISTS FLEET_MCP_WH;
ALTER USER {{SNOWFLAKE_USER}} UNSET DEFAULT_ROLE, DEFAULT_WAREHOUSE;
DROP ROLE IF EXISTS FLEET_MCP_ROLE;
