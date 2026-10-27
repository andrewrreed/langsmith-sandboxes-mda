-- 04b_analyst_mcp_server.sql: a second, smaller MCP server with only the tools the
-- Snowflake analyst agent uses (sales_analyst -> run_sql). One server per tool set
-- keeps each client to least privilege, and gives it its own URL to register on
-- LangSmith Tools (an upstream URL can be registered only once per workspace).
-- Run as ACCOUNTADMIN after 04.
USE ROLE ACCOUNTADMIN;

CREATE MCP SERVER IF NOT EXISTS FLEET_MCP.AGENTS.ANALYST_MCP_SERVER
  FROM SPECIFICATION
  $$
  tools:
    - title: "Sales analyst (text-to-SQL)"
      name: "sales_analyst"
      type: "CORTEX_ANALYST_MESSAGE"
      identifier: "FLEET_MCP.SEMANTIC.SALES_SV"
      description: "Turns a natural-language sales question into SQL using the governed sales semantic view. Returns SQL only; run it with run_sql."
    - title: "Run read-only SQL"
      name: "run_sql"
      type: "SYSTEM_EXECUTE_SQL"
      description: "Executes a read-only SQL SELECT in Snowflake and returns rows. Use it to run SQL produced by sales_analyst."
      config:
        read_only: true
        query_timeout: 60
        warehouse: "FLEET_MCP_WH"
  $$;

GRANT USAGE ON MCP SERVER FLEET_MCP.AGENTS.ANALYST_MCP_SERVER TO ROLE FLEET_MCP_ROLE;
