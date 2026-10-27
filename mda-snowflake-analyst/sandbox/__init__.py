"""Managed LangSmith sandbox: one isolated microVM per conversation thread."""

from managed_deepagents import define_sandbox

sandbox = define_sandbox(
    # Stop after 30 idle minutes; files are kept and the sandbox wakes on the next turn.
    idle_ttl_seconds=1800,
    # Default per-command timeout, in seconds.
    default_timeout=300,
)
