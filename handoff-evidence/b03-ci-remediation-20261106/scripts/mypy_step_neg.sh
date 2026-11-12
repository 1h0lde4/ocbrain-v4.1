set +e
export MYPYPATH=.
FILES="/tmp/claude-0/-home-claude/74c91717-34b2-58e0-a75e-e5d0b2f8f435/scratchpad/b03-ci-remediation/negctl/bad.py"
{
  python --version
  mypy --version
  python -m pip list 2>/dev/null | grep -i -E '^(pytest|mypy) '
  echo "files: $FILES"
} 2>&1 | tee /tmp/claude-0/-home-claude/74c91717-34b2-58e0-a75e-e5d0b2f8f435/scratchpad/b03-ci-remediation/evidence/local/M2_negative_control_mypy.txt
echo "== mypy (default) ==" | tee -a /tmp/claude-0/-home-claude/74c91717-34b2-58e0-a75e-e5d0b2f8f435/scratchpad/b03-ci-remediation/evidence/local/M2_negative_control_mypy.txt
mypy --explicit-package-bases --follow-imports=silent $FILES 2>&1 | tee -a /tmp/claude-0/-home-claude/74c91717-34b2-58e0-a75e-e5d0b2f8f435/scratchpad/b03-ci-remediation/evidence/local/M2_negative_control_mypy.txt
RC_DEFAULT=${PIPESTATUS[0]}
echo "== mypy --strict ==" | tee -a /tmp/claude-0/-home-claude/74c91717-34b2-58e0-a75e-e5d0b2f8f435/scratchpad/b03-ci-remediation/evidence/local/M2_negative_control_mypy.txt
mypy --strict --explicit-package-bases --follow-imports=silent $FILES 2>&1 | tee -a /tmp/claude-0/-home-claude/74c91717-34b2-58e0-a75e-e5d0b2f8f435/scratchpad/b03-ci-remediation/evidence/local/M2_negative_control_mypy.txt
RC_STRICT=${PIPESTATUS[0]}
echo "exit codes: default=$RC_DEFAULT strict=$RC_STRICT" | tee -a /tmp/claude-0/-home-claude/74c91717-34b2-58e0-a75e-e5d0b2f8f435/scratchpad/b03-ci-remediation/evidence/local/M2_negative_control_mypy.txt
[ "$RC_DEFAULT" = "0" ] && [ "$RC_STRICT" = "0" ]
