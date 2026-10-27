import os

from dotenv import find_dotenv, load_dotenv
from managed_deepagents import define_mcp

# mda compiles this file before it loads the project .env; deployments get the
# value from the forwarded deployment secret instead.
load_dotenv(find_dotenv(usecwd=True))

# Snowflake's managed MCP server, registered once on the LangSmith Tools page.
# LangSmith Tools signs each caller in to Snowflake with their own OAuth grant;
# the agent never sees a Snowflake credential.
# SNOWFLAKE_MCP_URL is the server's Tools URL:
#   https://api.smith.langchain.com/v1/managed-tools/servers/<server-id>/mcp
mcp = define_mcp(
    servers={
        "snowflake": {
            "transport": "http",
            "url": os.environ["SNOWFLAKE_MCP_URL"],
            "include_tools": ["sales_analyst", "run_sql"],
        },
    },
)
