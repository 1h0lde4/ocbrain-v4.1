"""Tests for scripts/ci_a9_verifier.py -- the H-D13 deny-rule verification method.

Everything here is pure or scripted: the classifier and the record validator are tested against
recorded observation fixtures (tests/fixtures/ci/a9/), and the collector against a scripted fake
`docker`.  No Docker host, no real kernel.  What this proves is the method's LOGIC (each mutation
in the spec's matrix MV-1..MV-16 must not yield MITIGATION_VERIFIED, or must yield the stated
classification); it says nothing about what a real kernel returns.  That needs a host with an
enforcing LSM (spec 4A.8) and is exactly what the hosted/qualifying-host run is for.
"""
from __future__ import annotations

import copy
import itertools
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import ci_a9_verifier as v  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures" / "ci" / "a9"
SHA = "a" * 64
IMG = "sha256:" + "b" * 64


# ------------------------------------------------------------------------------- helpers


def load(name: str) -> dict[str, Any]:
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


def obs_of(fx: dict[str, Any]) -> v.Observations:
    return v.observations_from_record(fx)


def label(fx: dict[str, Any]) -> v.Classification:
    return v.classify(obs_of(fx))


def conf(aa: str = "UNREADABLE", se: str = "UNREADABLE", at: str = "UNREADABLE") -> str:
    return f"CONFINEMENT apparmor=[{aa}] selinux=[{se}] attr=[{at}]\n"


AA_ENF = conf(aa="docker-default (enforce)", at="docker-default (enforce)")
AA_UNC = conf(aa="unconfined", at="unconfined")
OPEN = "SUCCEEDED fd=3 target=socket:[4242]\n"


def set_run(fx: dict[str, Any], name: str, rc: int | None, confinement: str, result: str, **extra: Any) -> dict[str, Any]:
    out = copy.deepcopy(fx)
    out["runs"][name] = {**out["runs"][name], "rc": rc, "stdout": confinement + result, **extra}
    return out


def drop_run(fx: dict[str, Any], name: str) -> dict[str, Any]:
    out = copy.deepcopy(fx)
    del out["runs"][name]
    return out


def with_host(fx: dict[str, Any], **kv: Any) -> dict[str, Any]:
    out = copy.deepcopy(fx)
    out["host"].update(kv)
    return out


# ------------------------------------------------------------------------------- calibration


def test_apparmor_fixture_is_verified_and_certifies_only_apparmor() -> None:
    c = label(load("verified_apparmor"))
    assert (c.label, c.reasons, c.deny_rule) == (v.MITIGATION_VERIFIED, ("verified",), "OBSERVED_BEHAVIORAL")
    assert c.verified_scope == ("apparmor",)


def test_selinux_fixture_is_verified_and_certifies_only_selinux() -> None:
    c = label(load("verified_selinux"))
    assert c.label == v.MITIGATION_VERIFIED and c.verified_scope == ("selinux",)


def test_the_lab_host_fingerprint_is_the_known_red_case() -> None:
    """Engine above the floor, no LSM policy: the bypass is reproduced.  The version cannot lift it (MV-6)."""
    fx = load("lab_host_bypass")
    assert fx["host"]["server_version"] == "29.8.2"
    c = label(fx)
    assert (c.label, c.reasons, c.deny_rule) == (v.BYPASS_REPRODUCED, ("bypass_open",), "NOT_OBSERVED")


def test_a_docker_29_4_2_style_host_is_inconclusive_with_the_wholesale_reason() -> None:
    c = label(load("docker_29_4_2_socketcall_blocked"))
    assert c.label == v.INCONCLUSIVE
    assert c.reasons == ("control_not_open", "socketcall_blocked_wholesale")


# ------------------------------------------------------------------------------- the table, row by row


def test_row_1_an_untrustworthy_subject_is_infrastructure_error() -> None:
    base = load("verified_apparmor")
    for rc in (125, 126, 127, 139, 2):
        c = label(set_run(base, "S", rc, "", ""))
        assert (c.label, c.reasons[0]) == (v.INFRASTRUCTURE_ERROR, "infra_subject"), rc
    assert label(drop_run(base, "S")).reasons[0] == "infra_subject"
    assert label(set_run(base, "S", 1, AA_ENF, "FAILED errno=13\n", timed_out=True)).reasons[0] == "infra_subject"
    assert label(set_run(base, "S", 1, "", "FAILED errno=13\n")).reasons[0] == "infra_subject"  # no CONFINEMENT line
    assert label(set_run(base, "S", 1, AA_ENF + AA_ENF, "FAILED errno=13\n")).reasons[0] == "infra_subject"
    assert label(set_run(base, "S", 1, "FAILED errno=13\n", AA_ENF)).reasons[0] == "infra_subject"  # reordered
    assert label(set_run(base, "S", 0, AA_ENF, "FAILED errno=13\n")).reasons[0] == "infra_subject"  # contradictory
    assert label(set_run(base, "S", 0, AA_ENF, "SUCCEEDED fd=3 target=UNKNOWN\n")).reasons[0] == "infra_subject"


def test_row_1_the_subject_must_be_the_probe_that_was_compiled_against_the_intended_image() -> None:
    base = load("verified_apparmor")
    a = copy.deepcopy(base)
    a["runs"]["S"]["probe_sha256"] = "c" * 64
    assert label(a).reasons[0] == "infra_subject"
    b = copy.deepcopy(base)
    b["runs"]["S"]["image_id"] = "sha256:" + "d" * 64
    assert label(b).reasons[0] == "infra_subject"


def test_row_2_a_valid_reproduced_bypass_outranks_every_later_row() -> None:
    """Review correction A / MV-16: a failed or untrustworthy C, B1 or B2 never downgrades a bypass."""
    base = load("lab_host_bypass")
    mutants = [
        set_run(base, "C", 1, conf(), "FAILED errno=97\n"),  # control failed
        set_run(base, "C", 125, "", ""),  # control infrastructure error
        set_run(base, "B1", 1, conf(), "FAILED errno=13\n"),  # benign failed
        set_run(base, "B2", None, "", "", timed_out=True),  # benign timed out
        drop_run(drop_run(base, "B1"), "B2"),  # benign runs omitted
        drop_run(base, "C"),  # control omitted
    ]
    for m in mutants:
        c = label(m)
        assert (c.label, c.reasons) == (v.BYPASS_REPRODUCED, ("bypass_open",))


def test_row_3_an_untrustworthy_or_foreign_control_or_benign_run_is_infrastructure_error() -> None:
    base = load("verified_apparmor")
    for name in ("C", "B1", "B2"):
        assert label(set_run(base, name, 125, "", "")).reasons[0] == "infra"
        assert label(set_run(base, name, None, "", "", timed_out=True)).label == v.INFRASTRUCTURE_ERROR
        other_sha = copy.deepcopy(base)
        other_sha["runs"][name]["probe_sha256"] = "e" * 64
        assert label(other_sha).reasons[0] == "infra"
        other_img = copy.deepcopy(base)
        other_img["runs"][name]["image_id"] = "sha256:" + "f" * 64
        assert label(other_img).reasons[0] == "infra"


def test_row_4_a_control_that_is_not_open_is_inconclusive() -> None:
    base = load("verified_apparmor")
    for errno in (97, 38, 1, 13):
        c = label(set_run(base, "C", 1, AA_UNC, f"FAILED errno={errno}\n"))
        assert (c.label, c.reasons) == (v.INCONCLUSIVE, ("control_not_open",)), errno
    assert label(drop_run(base, "C")).reasons == ("control_not_open",)


def test_row_5_a_control_that_is_still_confined_is_investigation_required() -> None:
    c = label(set_run(load("verified_apparmor"), "C", 0, AA_ENF, OPEN))
    assert (c.label, c.reasons) == (v.INVESTIGATION_REQUIRED, ("control_invalid",))
    c2 = label(set_run(load("verified_selinux"), "C", 0, conf(se="system_u:system_r:container_t:s0:c1,c2"), OPEN))
    assert c2.reasons == ("control_invalid",)


def test_a_control_whose_confinement_cannot_be_read_proves_nothing() -> None:
    """Not in the spec's table (it is silent): an unreadable control line is INCONCLUSIVE, never verified."""
    c = label(set_run(load("verified_apparmor"), "C", 0, conf(), OPEN))
    assert (c.label, c.reasons) == (v.INCONCLUSIVE, ("control_confinement_unverified",))


def test_row_6_an_errno_outside_eperm_eacces_is_investigation_required() -> None:
    for errno in (97, 38, 22, 12, 111):
        c = label(set_run(load("verified_apparmor"), "S", 1, AA_ENF, f"FAILED errno={errno}\n"))
        assert (c.label, c.reasons[0]) == (v.INVESTIGATION_REQUIRED, "unexpected_errno"), errno
    for errno in (1, 13):
        assert label(set_run(load("verified_apparmor"), "S", 1, AA_ENF, f"FAILED errno={errno}\n")).label == v.MITIGATION_VERIFIED


def test_row_7_unreadable_enforcement_evidence_is_inconclusive() -> None:
    base = load("verified_apparmor")
    unreadable = set_run(base, "S", 1, conf(), "FAILED errno=13\n")
    assert label(unreadable).reasons[0] == "enforcement_unverified"
    unknown_host = with_host(base, apparmor="UNKNOWN")
    assert label(unknown_host).reasons[0] == "enforcement_unverified"
    no_options = with_host(base, docker_security_options=None)  # info alone does not decide AppArmor
    assert label(no_options).label == v.MITIGATION_VERIFIED


def test_row_8_a_denial_with_no_enforcing_lsm_is_not_attributed_to_one() -> None:
    base = load("verified_apparmor")
    for line in (conf(aa="docker-default (complain)"), conf(aa="unconfined")):
        c = label(set_run(base, "S", 1, line, "FAILED errno=13\n"))
        assert (c.label, c.reasons[0]) == (v.INVESTIGATION_REQUIRED, "denial_not_attributed")
    none_active = with_host(base, apparmor="DISABLED")
    assert label(none_active).reasons[0] == "denial_not_attributed"
    not_listed = with_host(base, docker_security_options=["name=seccomp,profile=builtin"])
    assert label(not_listed).reasons[0] == "denial_not_attributed"


def test_row_9_under_route_1_the_apparmor_profile_must_be_dockers() -> None:
    """MV-14."""
    base = load("verified_apparmor")
    c = label(set_run(base, "S", 1, conf(aa="my-profile (enforce)"), "FAILED errno=13\n"))
    assert (c.label, c.reasons[0]) == (v.INCONCLUSIVE, "profile_not_route_policy")


def test_row_10_benign_sockets_must_still_work() -> None:
    base = load("verified_apparmor")
    for name in ("B1", "B2"):
        c = label(set_run(base, name, 1, AA_ENF, "FAILED errno=13\n"))
        assert (c.label, c.reasons) == (v.INVESTIGATION_REQUIRED, ("over_blocking",))
        assert label(drop_run(base, name)).reasons == ("over_blocking",)


# ------------------------------------------------------------------------------- the MV matrix


def test_mv_1_a_control_not_weakened_never_verifies() -> None:
    base = load("verified_apparmor")
    same_as_s = set_run(base, "C", 1, AA_ENF, "FAILED errno=13\n")
    assert label(same_as_s).label == v.INCONCLUSIVE
    still_confined_but_open = set_run(base, "C", 0, AA_ENF, OPEN)
    assert label(still_confined_but_open).label == v.INVESTIGATION_REQUIRED


def test_mv_2_a_probe_that_always_prints_a_denial_is_a_failed_control() -> None:
    fx = copy.deepcopy(load("verified_apparmor"))
    for name in v.RUN_NAMES:
        fx = set_run(fx, name, 1, AA_ENF, "FAILED errno=13\n")
    c = label(fx)
    assert c.label == v.INCONCLUSIVE and "control_not_open" in c.reasons


def test_mv_3_errno_97_or_38_is_never_read_as_a_denial() -> None:
    base = load("verified_apparmor")
    for errno in (97, 38):
        only_s = label(set_run(base, "S", 1, AA_ENF, f"FAILED errno={errno}\n"))
        assert only_s.label == v.INVESTIGATION_REQUIRED
        both = set_run(set_run(base, "S", 1, AA_ENF, f"FAILED errno={errno}\n"), "C", 1, AA_UNC, f"FAILED errno={errno}\n")
        assert label(both).label == v.INCONCLUSIVE


def test_mv_4_missing_or_failed_benign_runs_never_verify() -> None:
    base = load("verified_apparmor")
    for m in (drop_run(base, "B1"), drop_run(base, "B2"), drop_run(drop_run(base, "B1"), "B2"),
              set_run(base, "B1", 1, AA_ENF, "FAILED errno=1\n")):
        assert label(m).label == v.INVESTIGATION_REQUIRED


def test_mv_5_non_enforcing_or_unverified_confinement_never_verifies() -> None:
    aa = load("verified_apparmor")
    assert label(set_run(aa, "S", 1, conf(aa="docker-default (complain)"), "FAILED errno=13\n")).label == v.INVESTIGATION_REQUIRED
    se = load("verified_selinux")
    assert label(with_host(se, selinux="PERMISSIVE")).label == v.INVESTIGATION_REQUIRED
    # a container domain seen, but the host mode could not be read: the context alone is not enforcement
    assert label(with_host(se, selinux="UNKNOWN")).label == v.INCONCLUSIVE
    # a daemon that does not list selinux does not apply it
    assert label(with_host(se, docker_security_options=["name=seccomp,profile=builtin"])).label == v.INVESTIGATION_REQUIRED
    # the context is not a container domain
    unconfined_domain = set_run(se, "S", 1, conf(se="system_u:system_r:unconfined_t:s0"), "FAILED errno=1\n")
    assert label(unconfined_domain).label == v.INVESTIGATION_REQUIRED


def test_mv_6_an_engine_at_or_above_the_floor_cannot_lift_a_reproduced_bypass() -> None:
    for version in ("29.8.0", "29.8.2", "30.0.0"):
        assert label(with_host(load("lab_host_bypass"), server_version=version)).label == v.BYPASS_REPRODUCED


def test_mv_7_an_engine_below_the_floor_cannot_block_a_valid_custom_deny_rule() -> None:
    for version in ("29.4.2", "28.0.1", None):
        c = label(with_host(load("verified_apparmor"), server_version=version))
        assert c.label == v.MITIGATION_VERIFIED, version


def test_the_engine_version_is_never_an_input_to_the_classification() -> None:
    for name in ("verified_apparmor", "verified_selinux", "lab_host_bypass", "docker_29_4_2_socketcall_blocked"):
        results = {label(with_host(load(name), server_version=ver)) for ver in ("27.0.0", "29.4.2", "29.8.0", "31.1.0", None, "garbage")}
        assert len(results) == 1, name


def test_mv_8_a_timeout_is_never_read_as_lsm_not_active() -> None:
    base = load("verified_apparmor")
    assert label(set_run(base, "C", None, "", "", timed_out=True)).label == v.INFRASTRUCTURE_ERROR
    assert label(set_run(base, "S", None, "", "", timed_out=True)).reasons[0] == "infra_subject"
    for name in ("B1", "B2"):
        assert label(set_run(base, name, None, "", "", timed_out=True)).label == v.INFRASTRUCTURE_ERROR
    # unless S is already a valid reproduced bypass, which wins
    assert label(set_run(load("lab_host_bypass"), "C", None, "", "", timed_out=True)).label == v.BYPASS_REPRODUCED


def test_mv_9_runs_are_compared_with_each_other_even_when_no_expected_identity_was_established() -> None:
    fx = copy.deepcopy(load("verified_apparmor"))
    fx["expected"] = {"probe_sha256": None, "image_id": None}
    assert label(fx).label == v.MITIGATION_VERIFIED
    other_probe = copy.deepcopy(fx)
    other_probe["runs"]["B1"]["probe_sha256"] = "7" * 64
    assert label(other_probe).reasons[0] == "infra"
    other_image = copy.deepcopy(fx)
    other_image["runs"]["C"]["image_id"] = "sha256:" + "8" * 64
    assert label(other_image).reasons[0] == "infra"


def test_mv_9_a_probe_recompiled_between_runs_is_infrastructure_error() -> None:
    fx = copy.deepcopy(load("verified_apparmor"))
    fx["runs"]["C"]["probe_sha256"] = "9" * 64
    assert label(fx).label == v.INFRASTRUCTURE_ERROR


def test_mv_12_a_confinement_line_from_another_container_never_verifies() -> None:
    base = load("verified_apparmor")
    # S's attempt read with the control's (unconfined) line: S's own line is the evidence
    swapped = set_run(base, "S", 1, AA_UNC, "FAILED errno=13\n")
    assert label(swapped).label == v.INVESTIGATION_REQUIRED
    # no line at all for S: no evidence
    missing = set_run(base, "S", 1, "", "FAILED errno=13\n")
    assert label(missing).label == v.INFRASTRUCTURE_ERROR


def test_mv_16_a_valid_open_subject_is_never_outranked() -> None:
    test_row_2_a_valid_reproduced_bypass_outranks_every_later_row()


# ------------------------------------------------------------------------------- exhaustive lattice


def test_classifier_lattice_properties() -> None:
    """Over a lattice of run outcomes, confinement lines, host state and identity flags:
    (a) every valid S-open outcome is BYPASS_REPRODUCED; (b) MITIGATION_VERIFIED occurs exactly when
    S was denied EPERM/EACCES, C opened and its own line says unconfined, B1 and B2 opened, S's own
    line says enforcing under docker-default on an enabled AppArmor host, and the identity matches."""
    base = load("verified_apparmor")
    s_opts = {"open": (0, AA_ENF, OPEN), "d13": (1, AA_ENF, "FAILED errno=13\n"), "d97": (1, AA_ENF, "FAILED errno=97\n"),
              "bad": (125, "", "")}
    c_opts = {"open_unc": (0, AA_UNC, OPEN), "open_conf": (0, AA_ENF, OPEN), "open_unread": (0, conf(), OPEN),
              "denied": (1, AA_UNC, "FAILED errno=13\n"), "bad": (125, "", ""), "absent": None}
    b_opts = {"open": (0, AA_ENF, OPEN), "denied": (1, AA_ENF, "FAILED errno=13\n"), "bad": (125, "", ""), "absent": None}
    line_opts = {"enf": AA_ENF, "custom": conf(aa="x (enforce)"), "complain": conf(aa="docker-default (complain)"),
                 "unconf": AA_UNC, "unread": conf()}
    host_opts = ("ENABLED", "DISABLED", "UNKNOWN")
    ident_opts = ("ok", "mismatch")
    n = verified = 0
    for s_k, c_k, b1_k, b2_k, line_k, host_k, ident_k in itertools.product(
            s_opts, c_opts, b_opts, b_opts, line_opts, host_opts, ident_opts):
        fx = with_host(base, apparmor=host_k)
        s = s_opts[s_k]
        # the S line is varied for denied runs only; an open S keeps its own printed line
        s_line = line_opts[line_k] if s_k in ("d13", "d97") else s[1]
        fx = set_run(fx, "S", s[0], s_line, s[2])
        for name, opt in (("C", c_opts[c_k]), ("B1", b_opts[b1_k]), ("B2", b_opts[b2_k])):
            fx = drop_run(fx, name) if opt is None else set_run(fx, name, *opt)
        if ident_k == "mismatch":
            fx["runs"]["S"]["probe_sha256"] = "0" * 64
        got = label(fx).label
        n += 1
        s_valid_open = s_k == "open" and ident_k == "ok"
        if s_valid_open:
            assert got == v.BYPASS_REPRODUCED, (s_k, c_k, b1_k, b2_k, line_k, host_k)
        conditions = (s_k == "d13" and c_k == "open_unc" and b1_k == "open" and b2_k == "open"
                      and line_k == "enf" and host_k == "ENABLED" and ident_k == "ok")
        assert (got == v.MITIGATION_VERIFIED) == conditions, (got, s_k, c_k, b1_k, b2_k, line_k, host_k, ident_k)
        verified += got == v.MITIGATION_VERIFIED
    assert n == 4 * 6 * 4 * 4 * 5 * 3 * 2 and verified == 1


# ------------------------------------------------------------------------------- probe protocol


@pytest.mark.parametrize("stdout, rc, kind", [
    (AA_ENF + OPEN, 0, "OPEN"),
    (AA_ENF + "FAILED errno=13\n", 1, "DENIED"),
    (AA_ENF + "SUCCEEDED fd=3 target=UNKNOWN\n", 0, "INDETERMINATE"),
    (AA_ENF + OPEN, 1, "BAD"),
    (AA_ENF + "FAILED errno=13\n", 0, "BAD"),
    ("", 0, "BAD"),
    (AA_ENF, 0, "BAD"),
    (OPEN, 0, "BAD"),
    (AA_ENF + OPEN + "extra\n", 0, "BAD"),
    (AA_ENF + "FAILED errno=\n", 1, "BAD"),
    ("garbage\n" + OPEN, 0, "BAD"),
])
def test_probe_protocol(stdout: str, rc: int, kind: str) -> None:
    run = v.RunRecord("S", (), None, rc, stdout, "", 0.1, False, SHA, IMG)
    assert v.parse_run(run).kind == kind


def test_parse_run_reads_errno_and_confinement() -> None:
    run = v.RunRecord("S", (), None, 1, AA_ENF + "FAILED errno=13\n", "", 0.1, False, SHA, IMG)
    p = v.parse_run(run)
    assert p.errno == 13 and p.confinement == v.Confinement("docker-default (enforce)", "UNREADABLE", "docker-default (enforce)")


def test_the_probe_source_is_pinned_and_only_creates_a_socket() -> None:
    assert v.PROBE_SOURCE_SHA256 == __import__("hashlib").sha256(v.PROBE_C.encode()).hexdigest()
    for forbidden in ("connect(", "bind(", "listen(", "system(", "exec"):
        assert forbidden not in v.PROBE_C
    assert "int $0x80" in v.PROBE_C and v.PROBE_C.count("CONFINEMENT") == 1


# ------------------------------------------------------------------------------- host LSM state


@pytest.mark.parametrize("aa, se, backend", [
    ("ENABLED", "DISABLED", "apparmor"), ("DISABLED", "ENFORCING", "selinux"),
    ("DISABLED", "PERMISSIVE", "selinux"), ("ENABLED", "ENFORCING", "both"),
    ("DISABLED", "DISABLED", "none"), ("UNKNOWN", "DISABLED", "unknown"),
    ("ENABLED", "UNKNOWN", "unknown"),
])
def test_lsm_backend(aa: str, se: str, backend: str) -> None:
    assert v.lsm_backend(aa, se) == backend


@pytest.mark.parametrize("version, expected", [
    ("29.8.0", True), ("29.8.2", True), ("29.10.0", True), ("30.0.0", True),
    ("29.7.2", False), ("29.4.2", False), ("28.9.9", False), (None, False), ("", False), ("x", False),
])
def test_engine_floor_corroboration(version: str | None, expected: bool) -> None:
    assert v.engine_floor_corroboration(version) is expected


# ------------------------------------------------------------------------------- argv (MV-10, MV-13)


def _product_builder(name: str, command: tuple[str, ...]) -> list[str]:
    from core.sandbox.backends.docker_backend import _build_container_env, _build_create_args

    return _build_create_args(
        container_name=name, request_id="a9-observation", image_digest="repo@sha256:" + "c" * 64,
        command=command, env=_build_container_env({}), workspace_dir="/tmp/a9-ws",
        read_only_paths=("/tmp/a9-probe",), memory_limit_mb=256, max_pids=64,
    )


def _normalise(argv: list[str], name: str) -> list[str]:
    return [tok.replace(name, "NAME") for tok in argv]


def test_the_subject_argv_is_exactly_the_products_argv() -> None:
    """MV-10: S's argv comes from the product's own builder; dropping a product flag must be detectable."""
    s = _product_builder("ocbrain-a9-s-x", ("/tmp/a9-probe/probe", "40", "1"))
    assert "no-new-privileges" in s and "--privileged" not in s and "--cap-add" not in s
    mutated = [t for i, t in enumerate(s) if not (t == "--security-opt" or s[i - 1] == "--security-opt")]
    assert v.argv_difference(mutated, s) is not None and v.argv_difference(s, mutated) is None


@pytest.mark.parametrize("lsm, expected", [
    ("apparmor", ["--security-opt", "apparmor=unconfined"]),
    ("selinux", ["--security-opt", "label=disable"]),
    ("both", ["--security-opt", "apparmor=unconfined", "--security-opt", "label=disable"]),
])
def test_mv_13_the_control_differs_from_the_subject_by_exactly_the_lsm_option(lsm: str, expected: list[str]) -> None:
    s = _product_builder("ocbrain-a9-s-x", ("/tmp/a9-probe/probe", "40", "1"))
    c = v.control_argv(s, lsm)
    assert v.argv_difference(s, c) == expected
    for forbidden in ("--privileged", "seccomp=unconfined", "--cap-add", "--pid=host", "--network=host"):
        assert not any(forbidden in tok for tok in c)
    assert c[:2] == ["docker", "create"]


def test_the_control_helper_refuses_anything_but_docker_create() -> None:
    with pytest.raises(ValueError):
        v.control_argv(["docker", "run", "x"], "apparmor")


def test_argv_difference_rejects_an_argv_that_is_not_the_base_plus_insertions() -> None:
    s = ["docker", "create", "--read-only", "img"]
    assert v.argv_difference(s, ["docker", "create", "--read-only", "--privileged", "img"]) == ["--privileged"]
    assert v.argv_difference(s, ["docker", "create", "img"]) is None  # a weakening that removes a flag


# ------------------------------------------------------------------------------- the record (MV-11, MV-15)


def _record(name: str = "verified_apparmor", **kw: Any) -> dict[str, Any]:
    fx = load(name)
    return v.build_record(obs_of(fx), invocation_id="inv-1", image_ref="img:tag", **kw)


def test_a_built_record_is_valid_and_round_trips() -> None:
    for name in ("verified_apparmor", "verified_selinux", "lab_host_bypass", "docker_29_4_2_socketcall_blocked"):
        rec = _record(name)
        assert v.validate_record(rec) == [], name
        assert v.validate_record(json.loads(json.dumps(rec))) == [], name
    assert _record()["engine_floor_corroboration"] is True
    assert _record("docker_29_4_2_socketcall_blocked")["engine_floor_corroboration"] is False


def test_the_record_carries_the_probe_identity_and_no_environment() -> None:
    rec = _record()
    assert rec["schema_version"] == v.SCHEMA_VERSION and rec["probe_source_sha256"] == v.PROBE_SOURCE_SHA256
    assert rec["expected"]["probe_sha256"] == SHA
    text = json.dumps(rec)
    for secret_like in ("GITHUB_TOKEN", "PASSWORD", "environ"):
        assert secret_like not in text
    assert set(rec["runs"]["S"]) >= {"name", "argv", "container_id", "rc", "stdout", "stderr", "errno", "duration_s", "timed_out"}


def test_mv_11_a_missing_malformed_or_foreign_record_is_red(tmp_path: Path) -> None:
    assert v.validate_record("not an object") == ["record is not a JSON object"]
    assert v.validate_record({}) != []
    rec = _record()
    for key in ("classification", "runs", "host", "schema_version", "invocation_id"):
        broken = {k: x for k, x in rec.items() if k != key}
        assert v.validate_record(broken) != [], key
    old = dict(rec, schema_version="a9-observation/1")
    assert v.validate_record(old) != []
    missing, problems = v.load_record(tmp_path / "nope.json")
    assert missing is None and problems
    bad = tmp_path / "bad.json"
    bad.write_text("{truncated", encoding="utf-8")
    assert v.load_record(bad)[0] is None
    arr = tmp_path / "arr.json"
    arr.write_text("[]", encoding="utf-8")
    assert v.load_record(arr)[0] is None


def test_mv_11_a_stale_record_is_red() -> None:
    rec = _record(generated_at=(datetime.now(timezone.utc) - timedelta(hours=3)).isoformat())
    assert v.validate_record(rec, max_age_s=600) != []
    assert v.validate_record(rec) == []
    assert v.validate_record(_record(), expect_invocation_id="another-invocation") != []
    assert v.validate_record(_record(), expect_invocation_id="inv-1") == []
    future = _record(generated_at=(datetime.now(timezone.utc) + timedelta(hours=3)).isoformat())
    assert v.validate_record(future, max_age_s=600) != []
    assert v.validate_record(_record(generated_at="yesterday"), max_age_s=600) != []


def test_a_verdict_that_does_not_follow_from_the_recorded_evidence_is_invalid() -> None:
    rec = _record("lab_host_bypass")
    forged = dict(rec, classification=v.MITIGATION_VERIFIED, deny_rule="OBSERVED_BEHAVIORAL", reasons=["verified"],
                  verified_scope=[])
    problems = v.validate_record(forged)
    assert problems and any("does not follow" in p or "MITIGATION_VERIFIED must certify" in p for p in problems)
    tampered = copy.deepcopy(_record())
    tampered["runs"]["S"]["stdout"] = AA_ENF + OPEN  # evidence edited after the fact
    assert any("does not follow" in p for p in v.validate_record(tampered))
    reasons_edit = dict(_record(), reasons=["something_else"])
    assert v.validate_record(reasons_edit) != []


def test_a_record_whose_label_alone_was_edited_is_invalid() -> None:
    """Reasons, deny_rule and scope still agree with the evidence; only the label was changed."""
    rec = _record("docker_29_4_2_socketcall_blocked")
    assert rec["classification"] == v.INCONCLUSIVE
    for forged_label in (v.INVESTIGATION_REQUIRED, v.INFRASTRUCTURE_ERROR, v.BYPASS_REPRODUCED):
        assert any("does not follow" in p for p in v.validate_record(dict(rec, classification=forged_label)))


def test_mv_15_a_record_cannot_certify_a_backend_that_was_not_active() -> None:
    rec = _record("verified_apparmor")
    assert rec["verified_scope"] == ["apparmor"]
    for scope in (["selinux"], ["apparmor", "selinux"], []):
        problems = v.validate_record(dict(rec, verified_scope=scope))
        assert problems, scope
    non_verified = _record("lab_host_bypass")
    assert v.validate_record(dict(non_verified, verified_scope=["apparmor"])) != []
    assert v.validate_record(dict(rec, combined_scope=True)) != []


def test_a_both_backend_record_states_the_combined_scope() -> None:
    fx = with_host(load("verified_apparmor"), selinux="ENFORCING",
                   docker_security_options=["name=apparmor", "name=selinux"])
    fx = set_run(fx, "S", 1, conf(aa="docker-default (enforce)", se="system_u:system_r:container_t:s0"), "FAILED errno=13\n")
    fx = set_run(fx, "C", 0, conf(aa="unconfined", se="system_u:system_r:spc_t:s0"), OPEN)
    fx = set_run(fx, "B1", 0, conf(aa="docker-default (enforce)", se="system_u:system_r:container_t:s0"), OPEN)
    fx = set_run(fx, "B2", 0, conf(aa="docker-default (enforce)", se="system_u:system_r:container_t:s0"), OPEN)
    rec = v.build_record(obs_of(fx), invocation_id="i", image_ref=None)
    assert rec["classification"] == v.MITIGATION_VERIFIED
    assert rec["lsm_backend"] == "both" and rec["verified_scope"] == ["apparmor", "selinux"] and rec["combined_scope"] is True
    assert v.validate_record(rec) == []
    # with both active, one backend unreadable is not verified
    unread = set_run(fx, "S", 1, conf(aa="docker-default (enforce)"), "FAILED errno=13\n")
    assert label(unread).label == v.INCONCLUSIVE


# ------------------------------------------------------------------------------- the CLI


def test_the_cli_exit_codes(tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    ok = tmp_path / "ok.json"
    ok.write_text(json.dumps(_record()), encoding="utf-8")
    assert v.main(["check", "--record", str(ok)]) == 0
    assert "MITIGATION_VERIFIED" in capsys.readouterr().out
    for name in ("lab_host_bypass", "docker_29_4_2_socketcall_blocked"):
        p = tmp_path / f"{name}.json"
        p.write_text(json.dumps(_record(name)), encoding="utf-8")
        assert v.main(["check", "--record", str(p)]) == 1, name
        assert "red by design" in capsys.readouterr().out
    assert v.main(["check", "--record", str(tmp_path / "missing.json")]) == 2
    assert "INVALID" in capsys.readouterr().out
    forged = tmp_path / "forged.json"
    forged.write_text(json.dumps(dict(_record("lab_host_bypass"), classification=v.MITIGATION_VERIFIED)), encoding="utf-8")
    assert v.main(["check", "--record", str(forged)]) == 2


def test_the_cli_writes_a_step_summary_when_asked(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    rec = tmp_path / "r.json"
    rec.write_text(json.dumps(_record("lab_host_bypass")), encoding="utf-8")
    assert v.main(["check", "--record", str(rec)]) == 1
    text = summary.read_text(encoding="utf-8")
    assert "BYPASS_REPRODUCED" in text and "never an input" in text


# ------------------------------------------------------------------------------- the collector, scripted fake docker


IMG_ID = "sha256:" + "1" * 64


class FakeDocker:
    """A scripted `docker`/`gcc`/`getenforce`.  Probe behaviour is decided by (probe args, LSM flags)."""

    def __init__(self, behaviour: dict[str, tuple[int, str]] | None = None, *, no_gcc: bool = False,
                 rewrite_probe_after: str | None = None, daemon_down: bool = False, start_fails: bool = False) -> None:
        self.calls: list[list[str]] = []
        self.created: dict[str, list[str]] = {}
        self.exits: dict[str, int] = {}
        self.behaviour = behaviour if behaviour is not None else self.verified_behaviour()
        self.no_gcc = no_gcc
        self.rewrite_probe_after = rewrite_probe_after
        self.daemon_down = daemon_down
        self.start_fails = start_fails
        self.probe: Path | None = None

    @staticmethod
    def verified_behaviour() -> dict[str, tuple[int, str]]:
        return {
            "S": (1, AA_ENF + "FAILED errno=13\n"), "C": (0, AA_UNC + OPEN),
            "B1": (0, AA_ENF + OPEN), "B2": (0, AA_ENF + OPEN),
        }

    @staticmethod
    def _which(argv: list[str]) -> str:
        args = argv[-2:]
        unconfined = any("unconfined" in t or "label=disable" in t for t in argv)
        if args == ["40", "1"]:
            return "C" if unconfined else "S"
        return {"1": "B1", "2": "B2"}[args[0]]

    def __call__(self, argv: Any, timeout: float) -> v.CommandResult:
        argv = list(argv)
        self.calls.append(argv)
        head = argv[0]
        if head == "getenforce":
            return v.CommandResult(None, "", "getenforce: not found", not_found=True)
        if head == "gcc":
            if self.no_gcc:
                return v.CommandResult(1, "", "gcc: error: unrecognized command-line option '-m32'")
            self.probe = Path(argv[argv.index("-o") + 1])
            self.probe.write_bytes(b"\x7fELF-fake-probe")
            return v.CommandResult(0, "", "")
        if head != "docker":
            raise AssertionError(argv)
        if self.daemon_down:
            return v.CommandResult(1, "", "Cannot connect to the Docker daemon")
        sub = argv[1]
        if sub == "info":
            return v.CommandResult(0, '["name=apparmor","name=seccomp,profile=builtin"]\n', "")
        if sub == "version":
            return v.CommandResult(0, "29.8.2\n", "")
        if sub == "inspect" and "--format" in argv:
            return v.CommandResult(0, IMG_ID + "\n", "")
        if sub == "create":
            cid = f"cid{len(self.created) + 1}"
            self.created[cid] = argv
            return v.CommandResult(0, cid + "\n", "")
        if sub == "start" and self.start_fails:
            return v.CommandResult(1, "", "Error response from daemon: OCI runtime create failed: executable file not found")
        if sub == "start":
            cid = argv[-1]
            which = self._which(self.created[cid])
            rc, out = self.behaviour[which]
            self.exits[cid] = rc
            if self.rewrite_probe_after == which and self.probe is not None:
                self.probe.write_bytes(b"\x7fELF-recompiled")
            return v.CommandResult(rc, out, "")
        if sub == "inspect":
            cid = argv[-1]
            state = ({"Status": "created", "ExitCode": 0, "Error": "executable file not found", "OOMKilled": False}
                     if self.start_fails else
                     {"Status": "exited", "ExitCode": self.exits[cid], "Error": "", "OOMKilled": False})
            body = [{"State": state,
                     "HostConfig": {"SecurityOpt": ["no-new-privileges"]}, "AppArmorProfile": "docker-default (enforce)",
                     "Image": IMG_ID}]
            return v.CommandResult(0, json.dumps(body), "")
        if sub == "rm":
            return v.CommandResult(0, argv[-1] + "\n", "")
        raise AssertionError(argv)


def _files(path: str) -> tuple[str | None, str]:
    return ("Y\n", "OK") if path.endswith("apparmor/parameters/enabled") else (None, "ABSENT")


def _collect(tmp_path: Path, fake: FakeDocker) -> tuple[v.Observations, str]:
    probe_dir = tmp_path / "probe"
    probe_dir.mkdir()
    return v.collect(fake, argv_builder=lambda n, c: _product_builder(n, c), image_ref="img:tag", workdir=probe_dir,
                     read_text=_files, kernel_release="6.8.0-fake", invocation_id="inv-collect")


def test_the_collector_runs_s_c_b1_b2_and_the_method_verifies(tmp_path: Path) -> None:
    fake = FakeDocker()
    obs, inv = _collect(tmp_path, fake)
    assert inv == "inv-collect"
    assert list(obs.runs) == ["S", "C", "B1", "B2"]
    assert obs.host.lsm_backend == "apparmor" and obs.host.server_version == "29.8.2"
    assert v.classify(obs).label == v.MITIGATION_VERIFIED
    rec = v.build_record(obs, invocation_id=inv, image_ref="img:tag")
    assert v.validate_record(rec, expect_invocation_id=inv) == []
    # one container per run, id recorded, each removed afterwards
    assert [obs.runs[n].container_id for n in v.RUN_NAMES] == ["cid1", "cid2", "cid3", "cid4"]
    removed = [c[-1] for c in fake.calls if c[:3] == ["docker", "rm", "-f"]]
    assert removed == ["cid1", "cid2", "cid3", "cid4"]
    # the probe binary and image are the same in every run
    assert len({r.probe_sha256 for r in obs.runs.values()}) == 1 and len({r.image_id for r in obs.runs.values()}) == 1


def test_the_collector_builds_the_control_from_the_subject_plus_only_the_lsm_option(tmp_path: Path) -> None:
    fake = FakeDocker()
    obs, _ = _collect(tmp_path, fake)
    s = _normalise(list(obs.runs["S"].argv), "ocbrain-a9-s-inv-coll")
    c = _normalise(list(obs.runs["C"].argv), "ocbrain-a9-c-inv-coll")
    assert v.argv_difference(s, c) == ["--security-opt", "apparmor=unconfined"]
    # B runs use the product's argv unchanged apart from the probe arguments
    b1 = _normalise(list(obs.runs["B1"].argv), "ocbrain-a9-b1-inv-coll")
    assert b1[:-2] == s[:-2] and b1[-2:] == ["1", "1"]
    assert obs.runs["B2"].argv[-2:] == ("2", "1")
    for run in obs.runs.values():
        assert "--privileged" not in run.argv and not any("seccomp=unconfined" in a for a in run.argv)


def test_a_daemon_error_is_rc_125_and_never_a_security_verdict(tmp_path: Path) -> None:
    fake = FakeDocker(daemon_down=True)
    obs, _ = _collect(tmp_path, fake)
    assert obs.host.apparmor == "ENABLED" and obs.host.docker_security_options is None and obs.host.server_version is None
    c = v.classify(obs)
    assert c.label == v.INFRASTRUCTURE_ERROR and c.reasons[0] == "infra_subject"
    assert obs.runs["S"].rc == 125 and obs.runs["S"].container_id is None


def test_a_container_that_never_started_is_rc_125_not_a_clean_exit(tmp_path: Path) -> None:
    obs, _ = _collect(tmp_path, FakeDocker(start_fails=True))
    assert all(obs.runs[n].rc == 125 for n in v.RUN_NAMES)
    assert obs.runs["S"].inspect["status"] == "created"
    assert v.classify(obs).reasons[0] == "infra_subject"


def test_a_failed_compile_is_infrastructure_error_with_the_diagnostic(tmp_path: Path) -> None:
    obs, inv = _collect(tmp_path, FakeDocker(no_gcc=True))
    assert obs.runs == {} and "-m32" in (obs.compile_error or "")
    assert v.classify(obs).label == v.INFRASTRUCTURE_ERROR
    assert v.build_record(obs, invocation_id=inv, image_ref="img:tag")["compile_error"]


def test_a_probe_binary_changed_between_runs_is_seen(tmp_path: Path) -> None:
    """MV-9 through the collector: the binary is re-hashed before every run."""
    obs, _ = _collect(tmp_path, FakeDocker(rewrite_probe_after="S"))
    assert obs.runs["S"].probe_sha256 == obs.expected_probe_sha256
    assert obs.runs["C"].probe_sha256 != obs.expected_probe_sha256
    assert v.classify(obs).label == v.INFRASTRUCTURE_ERROR


def test_the_collector_reports_a_reproduced_bypass_through_the_whole_pipeline(tmp_path: Path) -> None:
    behaviour = {"S": (0, conf() + OPEN), "C": (0, conf() + OPEN), "B1": (0, conf() + OPEN), "B2": (0, conf() + OPEN)}
    obs, inv = _collect(tmp_path, FakeDocker(behaviour))
    rec = v.build_record(obs, invocation_id=inv, image_ref="img:tag")
    assert rec["classification"] == v.BYPASS_REPRODUCED and v.validate_record(rec) == []


def test_collect_host_never_reads_a_failed_query_as_disabled() -> None:
    def boom(path: str) -> tuple[str | None, str]:
        return None, "ERROR"

    class Down:
        def __call__(self, argv: Any, timeout: float) -> v.CommandResult:
            if argv[0] == "getenforce":
                return v.CommandResult(None, "", "", timed_out=True)
            return v.CommandResult(None, "", "", timed_out=True)

    host = v.collect_host(Down(), read_text=boom)
    assert (host.apparmor, host.selinux, host.docker_security_options, host.server_version) == ("UNKNOWN", "UNKNOWN", None, None)
    assert host.lsm_backend == "unknown"


def test_collect_host_reads_selinux_from_selinuxfs_when_getenforce_is_missing() -> None:
    class NoGetenforce:
        def __call__(self, argv: Any, timeout: float) -> v.CommandResult:
            if argv[0] == "getenforce":
                return v.CommandResult(None, "", "", not_found=True)
            return v.CommandResult(1, "", "")

    def files(path: str) -> tuple[str | None, str]:
        return {"/sys/fs/selinux/enforce": ("1", "OK"), "/sys/module/apparmor/parameters/enabled": (None, "ABSENT")}[path]

    host = v.collect_host(NoGetenforce(), read_text=files)
    assert (host.apparmor, host.selinux) == ("DISABLED", "ENFORCING")
    assert v.collect_host(NoGetenforce(), read_text=lambda p: (None, "ABSENT")).selinux == "DISABLED"


def test_the_real_runner_reports_timeouts_and_missing_executables() -> None:
    missing = v.subprocess_runner(["definitely-not-a-real-binary-a9"], 5)
    assert missing.not_found and missing.rc is None
    slow = v.subprocess_runner([sys.executable, "-c", "import time; time.sleep(30)"], 0.5)
    assert slow.timed_out and slow.rc is None
    ok = v.subprocess_runner([sys.executable, "-c", "print('hi')"], 20)
    assert ok.rc == 0 and ok.stdout.strip() == "hi"


def test_the_script_does_not_name_the_inert_b03_module() -> None:
    text = (ROOT / "scripts" / "ci_a9_verifier.py").read_text(encoding="utf-8")
    assert "_sandbox_network" not in text  # the inertness pin scans scripts/ too


def test_classify_never_reads_the_engine_version() -> None:
    """The version is corroboration only: no attribute access or call in classify() (or in the
    helpers it uses) may touch it.  Checked on the AST so a docstring cannot fool it."""
    import ast

    tree = ast.parse((ROOT / "scripts" / "ci_a9_verifier.py").read_text(encoding="utf-8"))
    fns = {n.name: n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    for name in ("classify", "evaluate_enforcement", "control_confinement", "parse_run", "lsm_backend"):
        seen = {n.attr for n in ast.walk(fns[name]) if isinstance(n, ast.Attribute)}
        seen |= {n.id for n in ast.walk(fns[name]) if isinstance(n, ast.Name)}
        assert not seen & {"server_version", "engine_floor_corroboration", "ENGINE_FLOOR", "_version_tuple"}, name


# ------------------------------------------------------------------------------- --text (evidence artifact)


def test_the_cli_text_file_holds_what_was_printed_for_every_outcome(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    verified, bypass = tmp_path / "verified.json", tmp_path / "bypass.json"
    verified.write_text(json.dumps(_record()), encoding="utf-8")
    bypass.write_text(json.dumps(_record("lab_host_bypass")), encoding="utf-8")
    cases = {
        "verified": (verified, 0, "A9: MITIGATION_VERIFIED"),
        "bypass": (bypass, 1, "red by design"),
        "missing": (tmp_path / "missing.json", 2, "A9 RECORD INVALID (red):"),
    }
    for label, (record, rc, needle) in cases.items():
        text = tmp_path / f"{label}.txt"
        assert v.main(["check", "--record", str(record), "--text", str(text)]) == rc, label
        printed = capsys.readouterr().out
        assert text.read_text() == printed and needle in printed, label


def test_the_cli_writes_no_text_file_unless_asked(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    rec = tmp_path / "r.json"
    rec.write_text(json.dumps(_record()), encoding="utf-8")
    assert v.main(["check", "--record", str(rec)]) == 0
    assert [p.name for p in tmp_path.iterdir()] == ["r.json"]
