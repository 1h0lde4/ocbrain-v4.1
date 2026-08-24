"""Allowlisted user-safe projection of canonical execution state."""

from typing import Any


def project_node(node: dict[str, Any]) -> dict[str, Any]:
    """Return only fields approved for user-facing execution inspection."""
    return {
        "id": node.get("node_id", ""),
        "parent_id": node.get("parent_id", ""),
        "operation_type": node.get("operation_type", "operation"),
        "title": node.get("title", ""),
        "status": node.get("status", "pending"),
        "summary": node.get("summary", ""),
        "progress": node.get("progress"),
        "progress_units": node.get("progress_units", {}),
        "started_at": node.get("started_at", 0.0),
        "updated_at": node.get("updated_at", 0.0),
        "completed_at": node.get("completed_at", 0.0),
        "last_progress_at": node.get("last_progress_at", 0.0),
        "children": list(node.get("children", [])),
        "current_action": node.get("current_action", ""),
        "failure_type": node.get("failure_type", ""),
        "failure_message": _safe_failure(node.get("failure_message", "")),
        "recovery_action": node.get("recovery_action", ""),
    }


def project_graph(snapshot: dict[str, Any]) -> dict[str, Any]:
    return {
        "execution_id": snapshot.get("execution_id", ""),
        "root_id": snapshot.get("root_id", ""),
        "nodes": [project_node(node) for node in snapshot.get("nodes", [])],
    }


def _safe_failure(message: str) -> str:
    if not message:
        return ""
    lowered = message.lower()
    if any(secret in lowered for secret in ("api key", "token=", "password", "authorization:")):
        return "The operation failed. Sensitive diagnostic details are hidden."
    return message[:500]