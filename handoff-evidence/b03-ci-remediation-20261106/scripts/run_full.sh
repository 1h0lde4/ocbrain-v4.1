#!/usr/bin/env bash
# Full CI-equivalent run, local lab: mirrors the workflow's "Run test suite" step (python 3.12 venv with requirements.txt).
SP=/tmp/claude-0/-home-claude/74c91717-34b2-58e0-a75e-e5d0b2f8f435/scratchpad
EV=$SP/b03-ci-remediation/evidence/local
cd /home/claude/ocbrain-v4.1
export OCBRAIN_SANDBOX_DOCKER_IMAGE=python:3.12-alpine
export PATH=$SP/venv312/bin:$PATH
unset NO_PROXY no_proxy
# huggingface.co is blocked in this sandbox: fail the model-download tests fast instead of after long retries
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
date -u +%FT%TZ > $EV/F1_start.txt
set +e
pytest tests/ -q --tb=short -rfEs -p no:cacheprovider 2>&1 | tee $EV/F1_full_pytest_output.txt
echo "${PIPESTATUS[0]}" > $EV/F1_full_pytest_exit_code.txt
date -u +%FT%TZ > $EV/F1_end.txt
