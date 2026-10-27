import os

from langchain_anthropic import ChatAnthropic
from managed_deepagents import define_deep_agent

from middleware.artifact_links import ArtifactLinksMiddleware
from tools.artifacts import share_file

# Model calls go through the LangSmith LLM Gateway: ANTHROPIC_API_KEY is a
# LangSmith key and ANTHROPIC_BASE_URL points at the gateway's Anthropic route.
model = ChatAnthropic(
    model="claude-sonnet-5-5",
    base_url=os.environ.get("ANTHROPIC_BASE_URL"),
    max_tokens=16384,  # room for several files in one batch of parallel write_file calls
)

agent = define_deep_agent(
    name="snowflake-analyst",
    model=model,
    tools=[share_file],
    middleware=[ArtifactLinksMiddleware()],
)
