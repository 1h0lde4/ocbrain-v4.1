"""
core/decomposer.py — Splits classified labels into a task DAG.
Parallel: tasks with no shared output run simultaneously.
Sequential: tasks where one feeds the next have dep links.
"""
import re
from dataclasses import dataclass, field
from typing import Optional

from .classifier import Label
from .parser import ParsedQuery

# Words that signal sequential execution
_SEQ_SIGNALS = re.compile(
    r'\b(then|after(wards?)?|next|once|use the result|based on that|using that|'
    r'and then|followed by|finally|lastly)\b',
    re.IGNORECASE,
)
# Modules whose output is typically needed by another module
_NEEDS_UPSTREAM = {
    "coding": ["web_search"],   # coding often needs search results first
}


@dataclass
class Task:
    id: str
    module: str
    subtask: str
    deps: list[str] = field(default_factory=list)


def build(parsed: ParsedQuery, labels: list[Label]) -> list[Task]:
    """Return a list of Tasks with dependency links set."""
    if not labels:
        return []

    is_sequential = bool(_SEQ_SIGNALS.search(parsed.raw))

    tasks: list[Task] = []
    id_map: dict[str, str] = {}   # module → task_id

    for i, lbl in enumerate(labels):
        tid = f"t{i+1}"
        id_map[lbl.module] = tid
        subtask = _slice_subtask(parsed.raw, lbl.module, labels)
        tasks.append(Task(id=tid, module=lbl.module, subtask=subtask, deps=[]))

    # Assign deps
    for task in tasks:
        deps = []
        if is_sequential:
            # Each task depends on the one before it
            idx = int(task.id[1:]) - 1
            if idx > 0:
                deps.append(f"t{idx}")
        else:
            # Check structural upstreams
            for upstream_mod in _NEEDS_UPSTREAM.get(task.module, []):
                if upstream_mod in id_map:
                    deps.append(id_map[upstream_mod])
        task.deps = deps

    return tasks


def _slice_subtask(raw: str, module: str, labels: list[Label]) -> str:
    """
    For single-module queries, return the full query.
    For multi-module queries, extract the relevant segment.
    This is a best-effort heuristic — can be improved with NLP.
    """
    if len(labels) == 1:
        return raw

    # Split on sequential signal words
    parts = _SEQ_SIGNALS.split(raw)
    if len(parts) >= len(labels):
        idx = next((i for i, l in enumerate(labels) if l.module == module), 0)
        return parts[min(idx, len(parts) - 1)].strip()

    return raw
