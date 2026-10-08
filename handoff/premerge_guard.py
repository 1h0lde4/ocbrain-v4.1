#!/usr/bin/env python3
"""premerge_guard.py -- fail-closed pre-merge checks for a GitHub pull request.

WHY THIS EXISTS. On 2026-09-30 an inline "final guard" PRINTED that `main` had
moved and the PR was `behind`, but did not ABORT; the merge then succeeded only
because the token was an admin and `enforce_admins` was off. A guard that only
prints is not a guard. This one exits non-zero, and treats "could not verify" as
a failure too (fail closed).

USAGE (token from the environment only -- never from argv, never printed):
    export GITHUB_TOKEN=...                      # needs read access (merge needs write)
    python3 premerge_guard.py --repo owner/name --pr 41 --expect-head <40-char sha> \\
        [--require-enforce-admins] [--merge --title "..." --message "..."]
    python3 premerge_guard.py --self-test        # offline tests, incl. the incident replay

EXIT CODES: 0 every check passed (and, with --merge, the merge was performed)
            1 a check FAILED -> do NOT merge
            2 could not evaluate (API/network/parse error) -> do NOT merge

Checks (all must pass): PR open, not draft, not merged; head SHA == --expect-head;
GitHub reports mergeable and mergeable_state == "clean" (not "behind"/"blocked"/...);
the head CONTAINS the current tip of the base branch (compare behind_by == 0);
every REQUIRED status check from branch protection completed/success on the head
(protection unreadable => fail); and, with --require-enforce-admins, that
`enforce_admins` is on, so an admin token cannot skip the rules server-side.
Default is a dry run. --merge re-collects fresh state, re-evaluates, then merges with
a merge commit pinned to the verified head SHA.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from typing import Any, Callable, Dict, List, Optional

API = "https://api.github.com"


class GuardError(Exception):
    """Could not evaluate (exit 2). Never swallowed into a pass."""


# --------------------------------------------------------------------------
# Pure decision logic (no I/O): a snapshot in, a list of failures out.
# --------------------------------------------------------------------------

def evaluate(snap: Dict[str, Any], expect_head: str,
             require_enforce_admins: bool = False) -> List[str]:
    fails: List[str] = []
    pr = snap.get("pr") or {}
    if pr.get("merged"):
        fails.append("PR is already merged")
    if pr.get("state") != "open":
        fails.append(f"PR state is {pr.get('state')!r}, not 'open'")
    if pr.get("draft"):
        fails.append("PR is a draft")
    head = (pr.get("head") or {}).get("sha", "")
    if head != expect_head:
        fails.append(f"head SHA {head[:7]!r} != expected {expect_head[:7]!r} (unverified commits)")
    if pr.get("mergeable") is not True:
        fails.append(f"GitHub mergeable={pr.get('mergeable')!r} (None = not computed yet; re-run)")
    if pr.get("mergeable_state") != "clean":
        fails.append(f"mergeable_state is {pr.get('mergeable_state')!r}, not 'clean' "
                     "('behind' = base moved; update the branch and re-verify)")
    cmp_ = snap.get("compare") or {}
    behind = cmp_.get("behind_by")
    if behind is None:
        fails.append("could not determine whether the head contains the base tip")
    elif behind != 0:
        fails.append(f"head is {behind} commit(s) BEHIND the base branch tip "
                     "(base moved after verification)")
    prot = snap.get("protection")
    runs = snap.get("check_runs")
    if prot is None:
        fails.append("branch protection unreadable -> required checks cannot be verified")
    else:
        required = sorted({c.get("context") for c in
                           ((prot.get("required_status_checks") or {}).get("checks") or [])}
                          | set((prot.get("required_status_checks") or {}).get("contexts") or []))
        if runs is None:
            fails.append("check runs unreadable -> required checks cannot be verified")
        else:
            by_name = {r.get("name"): r for r in runs}
            for name in required:
                r = by_name.get(name)
                if r is None:
                    fails.append(f"required check {name!r} has not run on the head")
                elif r.get("status") != "completed":
                    fails.append(f"required check {name!r} is {r.get('status')!r}")
                elif r.get("conclusion") != "success":
                    fails.append(f"required check {name!r} concluded {r.get('conclusion')!r}")
        if require_enforce_admins and not (prot.get("enforce_admins") or {}).get("enabled"):
            fails.append("enforce_admins is OFF: an admin token can bypass these rules server-side")
    return fails


# --------------------------------------------------------------------------
# I/O
# --------------------------------------------------------------------------

def make_fetch(token: str) -> Callable[..., Any]:
    def fetch(path: str, method: str = "GET", body: Optional[dict] = None,
              allow_404: bool = False) -> Any:
        req = urllib.request.Request(
            API + path, method=method,
            data=json.dumps(body).encode() if body is not None else None,
            headers={"Authorization": f"Bearer {token}",
                     "Accept": "application/vnd.github+json",
                     "X-GitHub-Api-Version": "2022-11-28"})
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode() or "null")
        except urllib.error.HTTPError as e:
            if allow_404 and e.code in (403, 404):
                return None
            raise GuardError(f"{method} {path} -> HTTP {e.code}") from None
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
            raise GuardError(f"{method} {path} failed: {type(e).__name__}") from None
    return fetch


def collect(fetch: Callable[..., Any], repo: str, pr_no: int) -> Dict[str, Any]:
    pr = fetch(f"/repos/{repo}/pulls/{pr_no}")
    base_ref = pr["base"]["ref"]
    head_sha = pr["head"]["sha"]
    tip = fetch(f"/repos/{repo}/git/ref/heads/{base_ref}")["object"]["sha"]
    cmp_ = fetch(f"/repos/{repo}/compare/{tip}...{head_sha}")
    prot = fetch(f"/repos/{repo}/branches/{base_ref}/protection", allow_404=True)
    runs = fetch(f"/repos/{repo}/commits/{head_sha}/check-runs?per_page=100")
    return {"pr": pr, "base_tip": tip, "compare": cmp_, "protection": prot,
            "check_runs": (runs or {}).get("check_runs")}


def run(fetch: Callable[..., Any], repo: str, pr_no: int, expect_head: str,
        require_enforce_admins: bool, merge: bool, title: str = "",
        message: str = "", out: Callable[[str], None] = print) -> int:
    try:
        fails = evaluate(collect(fetch, repo, pr_no), expect_head, require_enforce_admins)
    except (GuardError, KeyError, TypeError) as e:
        out(f"[ERROR] could not evaluate: {e}")
        out("RESULT: CANNOT VERIFY -> do NOT merge")
        return 2
    for f in fails:
        out(f"[FAIL] {f}")
    if fails:
        out(f"RESULT: {len(fails)} check(s) failed -> do NOT merge")
        return 1
    out("RESULT: all checks passed")
    if not merge:
        out("(dry run; pass --merge to merge)")
        return 0
    try:   # fresh state, immediately before the irreversible step
        fails = evaluate(collect(fetch, repo, pr_no), expect_head, require_enforce_admins)
        if fails:
            for f in fails:
                out(f"[FAIL] (re-check) {f}")
            out("RESULT: state changed during the guard -> NOT merged")
            return 1
        res = fetch(f"/repos/{repo}/pulls/{pr_no}/merge", method="PUT",
                    body={"merge_method": "merge", "sha": expect_head,
                          "commit_title": title or f"Merge pull request #{pr_no}",
                          "commit_message": message})
    except (GuardError, KeyError, TypeError) as e:
        out(f"[ERROR] merge not confirmed: {e}")
        return 2
    out(f"MERGED: {res.get('sha', '?')[:7]} ({res.get('message')})")
    return 0


# --------------------------------------------------------------------------
# Self-test (offline). Includes a replay of the real 2026-09-30 incident.
# --------------------------------------------------------------------------

def _good_snap() -> Dict[str, Any]:
    H = "7" * 40
    return {"pr": {"state": "open", "draft": False, "merged": False, "mergeable": True,
                   "mergeable_state": "clean", "head": {"sha": H}, "base": {"ref": "main"}},
            "compare": {"behind_by": 0, "ahead_by": 3},
            "protection": {"required_status_checks": {
                "checks": [{"context": "tests"}, {"context": "drift-and-ownership"}],
                "contexts": ["tests", "drift-and-ownership"], "strict": True},
                "enforce_admins": {"enabled": True}},
            "check_runs": [{"name": "tests", "status": "completed", "conclusion": "success"},
                           {"name": "drift-and-ownership", "status": "completed",
                            "conclusion": "success"},
                           {"name": "CodeQL", "status": "completed", "conclusion": "success"}]}


def self_test() -> int:
    H = "7" * 40
    results: List[tuple] = []

    def t(name: str, ok: bool) -> None:
        results.append((name, bool(ok)))

    g = _good_snap
    t("clean snapshot passes", evaluate(g(), H, True) == [])

    # INCIDENT REPLAY: main moved (PR was 'behind'); required checks were green.
    s = g(); s["pr"]["mergeable_state"] = "behind"; s["compare"]["behind_by"] = 1
    f = evaluate(s, H)
    t("incident replay: stale main is a HARD failure", len(f) == 2 and any("BEHIND" in x for x in f))
    s = g(); s["compare"]["behind_by"] = 2
    t("behind_by alone (mergeable_state clean) still fails", any("BEHIND" in x for x in evaluate(s, H)))
    s = g(); s["pr"]["mergeable_state"] = "behind"
    t("mergeable_state 'behind' alone still fails", bool(evaluate(s, H)))

    s = g(); s["pr"]["head"]["sha"] = "8" * 40
    t("head SHA mismatch fails", any("expected" in x for x in evaluate(s, H)))
    for k, v in (("state", "closed"), ("draft", True), ("merged", True)):
        s = g(); s["pr"][k] = v
        t(f"pr.{k}={v!r} fails", bool(evaluate(s, H)))
    s = g(); s["pr"]["mergeable"] = None
    t("mergeable=None (not computed) fails closed", bool(evaluate(s, H)))
    s = g(); s["compare"] = {}
    t("unknown compare result fails closed", bool(evaluate(s, H)))
    s = g(); s["protection"] = None
    t("unreadable protection fails closed", bool(evaluate(s, H)))
    s = g(); s["check_runs"] = None
    t("unreadable check runs fails closed", bool(evaluate(s, H)))
    s = g(); s["check_runs"] = [r for r in s["check_runs"] if r["name"] != "tests"]
    t("required check missing fails", any("'tests'" in x for x in evaluate(s, H)))
    s = g(); s["check_runs"][0]["status"] = "in_progress"; s["check_runs"][0]["conclusion"] = None
    t("required check pending fails", bool(evaluate(s, H)))
    s = g(); s["check_runs"][1]["conclusion"] = "failure"
    t("required check failing fails", bool(evaluate(s, H)))
    s = g(); s["check_runs"][2]["conclusion"] = "failure"
    t("a NON-required failing check does not by itself fail", evaluate(s, H) == [])
    s = g(); s["protection"]["enforce_admins"]["enabled"] = False
    t("enforce_admins off: ignored by default", evaluate(s, H) == [])
    t("enforce_admins off: fails with --require-enforce-admins", bool(evaluate(s, H, True)))

    # run(): exit codes, merge gating, error handling, token hygiene
    secret = "ghp_SELFTESTSECRET"
    calls: List[tuple] = []

    def fake_factory(snap: Dict[str, Any], boom: bool = False):
        def fetch(path, method="GET", body=None, allow_404=False):
            calls.append((method, path))
            if boom:
                raise GuardError("network down")
            if path.endswith("/merge"):
                return {"sha": "a" * 40, "merged": True, "message": "ok"}
            if "/pulls/" in path:
                return snap["pr"]
            if "/git/ref/" in path:
                return {"object": {"sha": "b" * 40}}
            if "/compare/" in path:
                return snap["compare"]
            if "/protection" in path:
                return snap["protection"]
            if "/check-runs" in path:
                return {"check_runs": snap["check_runs"]}
            raise AssertionError(path)
        return fetch

    buf: List[str] = []
    calls.clear()
    t("good + dry run: exit 0, no merge call",
      run(fake_factory(g()), "o/r", 1, H, True, False, out=buf.append) == 0
      and not any(m == "PUT" for m, _ in calls))
    calls.clear()
    bad = g(); bad["compare"]["behind_by"] = 1
    t("stale + --merge: exit 1 and NO merge call",
      run(fake_factory(bad), "o/r", 1, H, False, True, out=buf.append) == 1
      and not any(m == "PUT" for m, _ in calls))
    calls.clear()
    t("stale + DRY RUN: exit 1 (a dry run must report the failure, not 'passed')",
      run(fake_factory(bad), "o/r", 1, H, False, False, out=buf.append) == 1)

    def racing_factory():
        """Good on the first collect, stale on every later one (main moves mid-guard)."""
        n = {"pulls": 0}
        good, stale = g(), g()
        stale["compare"]["behind_by"] = 1
        stale["pr"]["mergeable_state"] = "behind"
        f_good, f_stale = fake_factory(good), fake_factory(stale)

        def fetch(path, method="GET", body=None, allow_404=False):
            if method == "GET" and "/pulls/" in path:
                n["pulls"] += 1
            return (f_good if n["pulls"] <= 1 else f_stale)(path, method, body, allow_404)
        return fetch

    calls.clear()
    t("state changes between check and merge: exit 1 and NO merge call",
      run(racing_factory(), "o/r", 1, H, True, True, out=buf.append) == 1
      and not any(m == "PUT" for m, _ in calls))
    calls.clear()
    t("good + --merge: exit 0, exactly one PUT merge",
      run(fake_factory(g()), "o/r", 1, H, True, True, "T", "M", out=buf.append) == 0
      and sum(1 for m, _ in calls if m == "PUT") == 1)
    calls.clear()
    t("API error: exit 2 (cannot verify), no merge call",
      run(fake_factory(g(), boom=True), "o/r", 1, H, False, True, out=buf.append) == 2
      and not any(m == "PUT" for m, _ in calls))
    t("output never contains the token", secret not in "\n".join(buf))

    width = max(len(n) for n, _ in results)
    for n, ok in results:
        print(f"[{'PASS' if ok else 'FAIL'}] {n}")
    bad_n = [n for n, ok in results if not ok]
    print(f"\n{len(results) - len(bad_n)}/{len(results)} self-tests passed")
    return 1 if bad_n else 0


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--repo"); ap.add_argument("--pr", type=int)
    ap.add_argument("--expect-head", help="the full 40-char SHA you verified")
    ap.add_argument("--require-enforce-admins", action="store_true")
    ap.add_argument("--merge", action="store_true")
    ap.add_argument("--title", default=""); ap.add_argument("--message", default="")
    a = ap.parse_args(argv)
    if a.self_test:
        return self_test()
    if not (a.repo and a.pr and a.expect_head and len(a.expect_head) == 40):
        print("[ERROR] --repo, --pr and a full 40-char --expect-head are required")
        return 2
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        print("[ERROR] GITHUB_TOKEN is not set")
        return 2
    return run(make_fetch(token), a.repo, a.pr, a.expect_head,
               a.require_enforce_admins, a.merge, a.title, a.message)


if __name__ == "__main__":
    sys.exit(main())
