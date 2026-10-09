import subprocess, sys, re, os
from pathlib import Path
CASES = [
 ("M1 raw wf_result.error returned again (the leak)", "core/orchestrator.py",
  '        return ("Sorry, I encountered an internal error: "\n                                f"WorkflowFailure (ref {ref})")',
  '        return ("Sorry, I encountered an internal error: "\n                                f"{wf_result.error}")'),
 ("M2 raw text appended after the ref", "core/orchestrator.py",
  'f"WorkflowFailure (ref {ref})")', 'f"WorkflowFailure (ref {ref}) {wf_result.error}")'),
 ("M3 ref not in the answer", "core/orchestrator.py",
  'f"WorkflowFailure (ref {ref})")', 'f"WorkflowFailure")'),
 ("M4 ref minted but the text is not logged", "core/error_ref.py",
  'logger.error("%s failed; error_id=%s: %s", context, ref, text)', 'logger.error("%s failed; error_id=%s", context, ref)'),
 ("M5 same ref for every failure", "core/error_ref.py",
  "def log_text_and_ref(logger: logging.Logger, context: str, text: str) -> str:\n", "def log_text_and_ref(logger: logging.Logger, context: str, text: str) -> str:\n    return _fixed(logger, context, text)\n\n\ndef _fixed(logger, context, text):\n    ref = '00000000-0000-0000-0000-000000000000'\n    logger.error('%s failed; error_id=%s: %s', context, ref, text)\n    return ref\n\n\ndef _unused(logger: logging.Logger, context: str, text: str) -> str:\n"),
 ("M6 internal event payload redacted too (C3 broken)", "core/orchestrator.py",
  '"error": wf_result.error,\n                            "error_type": "WorkflowFailure",', '"error": "redacted",\n                            "error_type": "WorkflowFailure",'),
 ("M7 sibling branch leaks str(e) (C4 broken)", "core/orchestrator.py",
  'return (f"Sorry, I encountered an internal error: "\n                            f"{type(e).__name__}")', 'return (f"Sorry, I encountered an internal error: "\n                            f"{e}")'),
]
survivors = []
for name, f, old, new in CASES:
    p = Path(f); good = p.read_bytes().decode(); crlf = "\r\n" in good
    o, n = (old.replace("\n", "\r\n"), new.replace("\n", "\r\n")) if crlf else (old, new)
    assert good.count(o) == 1, f"{name}: anchor count {good.count(o)}"
    p.write_bytes(good.replace(o, n, 1).encode())
    try:
        r = subprocess.run([sys.executable, "-m", "pytest", "-q", "--no-header", "-p", "no:cacheprovider", "-W", "ignore", "tests/test_workflow_failure_disclosure.py"],
                           capture_output=True, text=True, env={**os.environ, "PYTHONPATH": "."})
    finally:
        p.write_bytes(good.encode())
    out = r.stdout + r.stderr
    caught, clean = r.returncode != 0, "INTERNALERROR" not in out
    failed = re.findall(r"FAILED \S+::(\S+)", out)
    print(f"{'CAUGHT  ' if caught else 'SURVIVED'} {'clean' if clean else 'CRASHED'} {name:50s} -> {len(failed)} failing: {', '.join(x.split(' ')[0] for x in failed)[:150]}")
    if not caught: survivors.append(name)
print("survivors:", survivors or "none")
