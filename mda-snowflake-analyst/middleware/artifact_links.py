"""Put signed artifact URLs into answers without the model ever seeing or copying them.

Signed sandbox URLs carry long tokens that models truncate or reuse wrongly. The
tools keep each URL in the ToolMessage `artifact` (never sent to the model) and
give the model a per-file placeholder, `{{link:/workspace/out/<file>}}`. This
middleware:

- after the run, replaces placeholders in the final answer with the real URLs;
- before each model call, turns any real URL in earlier answers back into its
  placeholder, so follow-up turns never copy an old link.
"""

import re

from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import AIMessage, ToolMessage

LINK_TOOLS = {"share_file"}
PLACEHOLDER = re.compile(r"\{\{link:([^}]+)\}\}")


def _links(messages) -> dict[str, str]:
    """Path -> URL for every file the tools have shared in this thread."""
    links = {}
    for message in messages:
        if isinstance(message, ToolMessage) and message.name in LINK_TOOLS and isinstance(message.artifact, dict):
            if message.artifact.get("url") and message.artifact.get("path"):
                links[message.artifact["path"]] = message.artifact["url"]
    return links


def _map_text(message: AIMessage, fn) -> AIMessage:
    if isinstance(message.content, str):
        content = fn(message.content)
    else:
        content = [
            {**block, "text": fn(block["text"])} if isinstance(block, dict) and block.get("type") == "text" else block
            for block in message.content
        ]
    return message if content == message.content else message.model_copy(update={"content": content})


def _without_urls(request):
    """The model request with real URLs in earlier answers turned back into placeholders."""
    links = _links(request.messages)
    if not links:
        return request

    def hide(text: str) -> str:
        for path, url in links.items():
            text = text.replace(url, "{{link:" + path + "}}")
        return text

    return request.override(messages=[_map_text(m, hide) if isinstance(m, AIMessage) else m for m in request.messages])


class ArtifactLinksMiddleware(AgentMiddleware):
    def wrap_model_call(self, request, handler):
        return handler(_without_urls(request))

    async def awrap_model_call(self, request, handler):
        return await handler(_without_urls(request))

    def after_agent(self, state, runtime):
        messages = state["messages"]
        final = messages[-1] if messages else None
        links = _links(messages)
        if not links or not isinstance(final, AIMessage):
            return None
        filled = _map_text(final, lambda text: PLACEHOLDER.sub(lambda m: links.get(m.group(1).strip(), m.group(0)), text))
        return None if filled is final else {"messages": [filled]}
