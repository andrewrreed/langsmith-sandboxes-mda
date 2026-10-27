"""Share files the agent produced in its sandbox as signed links.

The URL goes in the ToolMessage `artifact` (never sent to the model); the model
gets a placeholder that middleware/artifact_links.py turns into the real link.
"""

import mimetypes
import posixpath

from langchain.tools import tool
from langchain_core.messages import ToolMessage
from langsmith.sandbox import SandboxClient
from managed_deepagents import ManagedDeepAgentRuntime

OUTPUT_DIR = "/workspace/out"
LINK_TTL_SECONDS = 7 * 24 * 3600


@tool(parse_docstring=True)
def share_file(path: str, runtime: ManagedDeepAgentRuntime) -> ToolMessage:
    """Create a link to a file you produced, such as a chart PNG or an HTML dashboard.

    The link opens the file in a browser for 7 days, with no login, even after the
    sandbox stops. Browsers open it with scripts disabled, so HTML must be static.
    Never modify a file after sharing it; write a new version instead.

    Args:
        path: File under /workspace/out, e.g. /workspace/out/dashboard_v1.html.
    """
    path = posixpath.normpath(path)
    if not path.startswith(OUTPUT_DIR + "/"):
        raise ValueError(f"only files under {OUTPUT_DIR}/ can be shared")
    if runtime.backend is None:
        raise RuntimeError("share_file requires the managed sandbox")
    # MDA resolves the sandbox lazily; until then `id` is a "pending:" placeholder.
    if runtime.backend.id.startswith("pending:"):
        runtime.backend.execute("true")
    sandbox = SandboxClient().get_sandbox(runtime.backend.id)

    content_type = mimetypes.guess_type(path)[0] or "application/octet-stream"
    url = sandbox.generate_download_url(
        path, expires_in_seconds=LINK_TTL_SECONDS, content_type=content_type, content_disposition="inline"
    ).download_url

    placeholder = "{{link:" + path + "}}"
    usage = f"![Chart]({placeholder})" if content_type.startswith("image/") else f"[Open the dashboard]({placeholder})"
    return ToolMessage(
        content=f"Shared {posixpath.basename(path)}. Put it in your answer as {usage} (write the placeholder exactly).",
        artifact={"url": url, "path": path, "sandbox": sandbox.name},
        tool_call_id=runtime.tool_call_id,
        name="share_file",
    )
