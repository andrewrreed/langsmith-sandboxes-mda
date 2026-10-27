"""Check a LangSmith Tools server end to end: list its tools, then ask Snowflake a question.

    python scripts/verify_tools_server.py <server-id> ["question"]

Calls run as the owner of LANGSMITH_API_KEY (use a personal access token), with that
person's own Snowflake sign-in. Reads LANGSMITH_API_KEY and LANGSMITH_WORKSPACE_ID from .env.
"""

import asyncio
import json
import os
import sys

from dotenv import load_dotenv
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

load_dotenv()


def text_of(result) -> str:
    return "".join(c.text for c in result.content if getattr(c, "type", "") == "text")


async def main(server_id: str, question: str) -> None:
    endpoint = os.environ.get("LANGSMITH_ENDPOINT", "https://api.smith.langchain.com")
    url = f"{endpoint}/v1/managed-tools/servers/{server_id}/mcp"
    headers = {"X-Api-Key": os.environ["LANGSMITH_API_KEY"], "X-Tenant-Id": os.environ["LANGSMITH_WORKSPACE_ID"]}

    async with streamablehttp_client(url, headers=headers) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            print("tools:", [t.name for t in tools.tools])

            analyst = text_of(await session.call_tool("sales_analyst", {"message": question}))
            statement = next((part["statement"] for part in json.loads(analyst) if "statement" in part), None)
            if not statement:
                sys.exit(f"sales_analyst returned no SQL:\n{analyst}")
            print("\nSQL:\n" + statement)

            rows = json.loads(text_of(await session.call_tool("run_sql", {"sql": statement})))
            data = rows["result_set"]["data"]
            print(f"\n{len(data)} rows, first 5:")
            for row in data[:5]:
                print("  ", row)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    asyncio.run(main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "Total revenue by region in 1995"))
