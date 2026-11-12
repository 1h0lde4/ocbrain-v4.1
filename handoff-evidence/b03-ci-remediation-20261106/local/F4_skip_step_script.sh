if grep -E '^SKIPPED .*(requires a reachable Docker daemon|requires the test image)' /tmp/claude-0/-home-claude/74c91717-34b2-58e0-a75e-e5d0b2f8f435/scratchpad/b03-ci-remediation/evidence/local/F4_full_pytest_output.txt; then
  echo "::error::Docker-backed tests were skipped although the preflight proved the daemon and the image"
  exit 1
fi
echo "no Docker-prerequisite skips"

