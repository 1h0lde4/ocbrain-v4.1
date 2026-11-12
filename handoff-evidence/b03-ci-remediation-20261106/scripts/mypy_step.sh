set +e
export MYPYPATH=.
FILES="core/sandbox/backends/_sandbox_network.py tests/core/sandbox/test_sandbox_network_guards.py"
{
  python --version
  mypy --version
  python -m pip list 2>/dev/null | grep -i -E '^(pytest|mypy) '
  echo "files: $FILES"
} 2>&1 | tee /tmp/mypy-b03.txt
echo "== mypy (default) ==" | tee -a /tmp/mypy-b03.txt
mypy --explicit-package-bases --follow-imports=silent $FILES 2>&1 | tee -a /tmp/mypy-b03.txt
RC_DEFAULT=${PIPESTATUS[0]}
echo "== mypy --strict ==" | tee -a /tmp/mypy-b03.txt
mypy --strict --explicit-package-bases --follow-imports=silent $FILES 2>&1 | tee -a /tmp/mypy-b03.txt
RC_STRICT=${PIPESTATUS[0]}
echo "exit codes: default=$RC_DEFAULT strict=$RC_STRICT" | tee -a /tmp/mypy-b03.txt
[ "$RC_DEFAULT" = "0" ] && [ "$RC_STRICT" = "0" ]
