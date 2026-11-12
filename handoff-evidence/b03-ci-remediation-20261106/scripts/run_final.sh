#!/usr/bin/env bash
# Final-tree acceptance run (local lab): full pytest like the workflow's "Run test suite" step, then the gate,
# then the new skip-assertion step's real run block.  Restores the config/*.toml files the suite rewrites.
SP=/tmp/claude-0/-home-claude/74c91717-34b2-58e0-a75e-e5d0b2f8f435/scratchpad
EV=$SP/b03-ci-remediation/evidence/local
REPO=/home/claude/ocbrain-v4.1
cd $REPO
pkill -9 dockerd; pkill -9 containerd; sleep 1
bash $SP/docker-lab/up.sh || exit 3
export OCBRAIN_SANDBOX_DOCKER_IMAGE=python:3.12-alpine
export PATH=$SP/venv312/bin:$PATH
unset NO_PROXY no_proxy
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
git rev-parse HEAD > $EV/F4_head.txt; git status --short > $EV/F4_status_before.txt
date -u +%FT%TZ > $EV/F4_start.txt
set +e
pytest tests/ -q --tb=short -rfEs -p no:cacheprovider 2>&1 | tee $EV/F4_full_pytest_output.txt
echo "${PIPESTATUS[0]}" > $EV/F4_full_pytest_exit_code.txt
date -u +%FT%TZ > $EV/F4_end.txt
python3 scripts/ci_test_gate.py --output $EV/F4_full_pytest_output.txt --exit-code-file $EV/F4_full_pytest_exit_code.txt \
  --allowlist docs/architecture/D10_KNOWN_ENVIRONMENTAL_FAILURES.txt > $EV/F4_gate_output.txt 2>&1
echo $? > $EV/F4_gate_exit.txt
python3 - <<'PY' > $EV/F4_skip_step_script.sh
import yaml
d = yaml.safe_load(open("/home/claude/ocbrain-v4.1/.github/workflows/ci.yml"))
step = next(s for s in d["jobs"]["tests"]["steps"] if s["name"].startswith("Assert the Docker-backed tests ran"))
print(step["run"].replace("/tmp/pytest-output.txt", "/tmp/claude-0/-home-claude/74c91717-34b2-58e0-a75e-e5d0b2f8f435/scratchpad/b03-ci-remediation/evidence/local/F4_full_pytest_output.txt"))
PY
bash -e $EV/F4_skip_step_script.sh > $EV/F4_skip_step_output.txt 2>&1
echo $? > $EV/F4_skip_step_exit.txt
git checkout -- config/ 2>/dev/null
git status --short > $EV/F4_status_after.txt
echo done > $EV/F4_done.txt
