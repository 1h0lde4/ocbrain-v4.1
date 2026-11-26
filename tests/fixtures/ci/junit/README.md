# JUnit fixtures

`pytest9_all_outcomes.xml` is real pytest 9.2.0 output (`-o junit_family=xunit2`) from a toy package
that produces every outcome kind the checker classifies: a plain pass, two parametrized passes, a
runtime `pytest.skip`, a module-level `skipif` skip, a strict xfail, a strict XPASS (reported by
pytest as a `<failure>`), a real failure, a fixture setup error and a class-based pass. Only
`time`, `timestamp`, `hostname` and absolute paths were scrubbed; the structure is untouched.

Synthetic reports (untyped `<skipped>`, truncation, DOCTYPE, ...) are built inside
`tests/test_ci_junit_manifest.py` because pytest 9.2.0 does not produce them.
