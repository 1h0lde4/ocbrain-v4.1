#!/usr/bin/env bash
cd /home/claude/ocbrain-v4.1
echo "== before repair: staged-deletion lines and untracked/modified lines"; git status --porcelain | cut -c1-2 | sort | uniq -c
echo "HEAD: $(git rev-parse HEAD)  (unchanged by the stray command: a commit-level read-only fact)"
echo "== restore the index from HEAD (does not touch the working tree or any commit)"
git read-tree HEAD && echo "read-tree HEAD exit 0"
echo "== after repair"; echo "status lines: $(git status --porcelain | wc -l)"; git status --short | head -3
echo "tracked files missing from the working tree: $(git ls-files -d | wc -l)"
echo "handoff.md blob (work vs HEAD): $(git hash-object handoff.md) $(git rev-parse HEAD:handoff.md)"
echo "remote tip: $(git ls-remote origin refs/heads/docs/g4-fts-errata-handoff-oct2026)"
echo "branch: $(git rev-parse --abbrev-ref HEAD)"
