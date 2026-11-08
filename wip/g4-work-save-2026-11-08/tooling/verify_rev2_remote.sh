#!/usr/bin/env bash
cd /home/claude/ocbrain-v4.1
BR=docs/g4-fts-errata-handoff-oct2026
echo "== fetch the remote branch into a verification ref (explicit refspec)"
git fetch origin "+refs/heads/$BR:refs/remotes/origin/$BR" 2>&1 | tail -3
echo "remote-tracking tip: $(git rev-parse origin/$BR)"; echo "local HEAD:          $(git rev-parse HEAD)"
[ "$(git rev-parse origin/$BR)" = "$(git rev-parse HEAD)" ] && echo "origin/$BR == HEAD: YES" || echo "origin/$BR == HEAD: NO"
echo "== live ls-remote again"; git ls-remote origin refs/heads/$BR
echo "== handoff.md blob on the remote tip vs local HEAD vs working file"
echo "remote: $(git rev-parse origin/$BR:handoff.md)"; echo "local:  $(git rev-parse HEAD:handoff.md)"; echo "work:   $(git hash-object handoff.md)"
echo "== history after the transfer commit eca2b96 on the remote branch"
git log --format='%H %an %s' eca2b96521fba8cf792ea16a58be997e4f949356..origin/$BR | cut -c1-150
echo "count: $(git rev-list --count eca2b96521fba8cf792ea16a58be997e4f949356..origin/$BR)"
echo "== the new remote tip's parent is the old tip; only handoff.md changed"
git rev-parse origin/$BR^; git diff --name-status origin/$BR^ origin/$BR
echo "== remote handoff.md: the new entry is present once, and the two checks it qualifies are still present"
git show origin/$BR:handoff.md | grep -c 'Effect on this file.s own checks'
git show origin/$BR:handoff.md | grep -c 'exactly one later commit'
echo "== all four other refs: REV3 tip and main unchanged, backup branches are local only"
git ls-remote origin refs/heads/docs/g4-fts-correctness-handoff-rev3-oct2026 refs/heads/main
git ls-remote origin 'refs/heads/wip-backup*' | wc -l
echo "== local status: $(git status --porcelain | wc -l) changed, stash: $(git stash list | wc -l)"
echo "== PR #90 head still the REV3 tip"; gh api repos/1h0lde4/ocbrain-v4.1/pulls/90 --jq '"state=\(.state) draft=\(.draft) head=\(.head.sha) commits=\(.commits) changed_files=\(.changed_files)"' 2>&1 | head -2
