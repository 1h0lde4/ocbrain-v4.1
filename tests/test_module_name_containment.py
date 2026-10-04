"""
tests/test_module_name_containment.py -- a module name is an identifier, never a path.

core/module_paths.module_child() is the single filesystem boundary for a
module name. These tests cover the helper itself and every sink that used to
build `ROOT / module_name` (or `ROOT / f"{module_name}.json"`) directly:
learning/{trainer,cleaner,crawler,evaluator,gap_detector,finetuner,distiller},
core/{module_registry,module_factory,brain_export}.

Two properties are pinned, on purpose separately:

  * WHERE a result may point: nothing outside the root, including via
    symlinks (resolve() follows them) and via the code-controlled suffix.
  * WHAT a name may be: wider than .isidentifier(). Registry directory names
    (module_registry.load_all) and /train's registry-membership guard are not
    identifier checks, so a name such as "my-module" must keep working.
"""
import asyncio  # noqa: F401  (pytest-asyncio auto mode)
import json
import os
import zipfile
from pathlib import Path

import pytest

import core.brain_export as be
from core.module_paths import InvalidModuleName, module_child, validate_module_name

TRAVERSAL = "../../escaped_by_module_name"
BAD_NAMES = [
    TRAVERSAL, "..", ".", "", "a/b", "a\\b", "/etc/passwd", "x\x00y",
    "sub/../../up",
]


def _tree(p: Path) -> set:
    return {str(x) for x in p.rglob("*")}


# ── the helper ─────────────────────────────────────────────────────────

@pytest.mark.parametrize("name", ["finance_helper", "my-module", "mod.v2", "Ünï", "a b"])
def test_single_component_names_are_accepted(tmp_path, name):
    assert module_child(tmp_path, name) == (tmp_path / name).resolve()


@pytest.mark.parametrize("name", BAD_NAMES)
def test_path_shaped_names_are_rejected_with_a_fixed_message(tmp_path, name):
    with pytest.raises(InvalidModuleName) as e:
        module_child(tmp_path, name)
    assert isinstance(e.value, ValueError)
    # Fixed text: identical for every input, so it cannot echo the name.
    assert str(e.value) == "Invalid module_name: must be a single path component."


def test_non_string_is_rejected(tmp_path):
    with pytest.raises(InvalidModuleName):
        validate_module_name(None)  # type: ignore[arg-type]


def test_suffix_is_part_of_the_contained_path(tmp_path):
    assert module_child(tmp_path, "x", ".json") == (tmp_path / "x.json").resolve()
    with pytest.raises(InvalidModuleName):
        module_child(tmp_path, "x", "/../../y")  # a suffix cannot climb out


def test_symlink_pointing_outside_the_root_is_rejected(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    try:
        (root / "evil").symlink_to(outside, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks not available on this platform")
    with pytest.raises(InvalidModuleName):
        module_child(root, "evil")


def test_symlink_pointing_inside_the_root_is_accepted(tmp_path):
    root = tmp_path / "root"
    (root / "real").mkdir(parents=True)
    try:
        (root / "alias").symlink_to(root / "real", target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks not available on this platform")
    assert module_child(root, "alias") == (root / "real").resolve()


def test_root_itself_is_never_a_valid_child(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    (root / "self").symlink_to(root, target_is_directory=True)
    with pytest.raises(InvalidModuleName):
        module_child(root, "self")


# ── every sink rejects, and creates nothing ────────────────────────────

@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    import learning.cleaner as cleaner
    import learning.crawler as crawler
    import learning.distiller as distiller
    import learning.evaluator as evaluator
    import learning.finetuner as finetuner
    import learning.gap_detector as gap
    import learning.trainer as trainer

    d = {n: tmp_path / "data" / n for n in ("raw", "chunks", "gaps", "evals")}
    for p in d.values():
        p.mkdir(parents=True)
    modules = tmp_path / "modules"
    modules.mkdir()
    for mod in (cleaner, crawler, distiller, gap, trainer):
        monkeypatch.setattr(mod, "DATA_RAW", d["raw"], raising=False)
    for mod in (cleaner, trainer):
        monkeypatch.setattr(mod, "DATA_CHUNKS", d["chunks"])
    monkeypatch.setattr(gap, "DATA_GAPS", d["gaps"])
    monkeypatch.setattr(evaluator, "EVAL_DIR", d["evals"])
    monkeypatch.setattr(finetuner, "MODULES_DIR", modules)
    return {"tmp": tmp_path, "d": d, "modules": modules,
            "m": dict(cleaner=cleaner, crawler=crawler, distiller=distiller,
                      evaluator=evaluator, finetuner=finetuner, gap=gap,
                      trainer=trainer)}


SYNC_SINKS = {
    "trainer.prepare":          lambda m, n, t: m["trainer"].prepare(n, {}),
    "cleaner.run_module":       lambda m, n, t: m["cleaner"].run_module(n, {}),
    "evaluator._load_eval_set": lambda m, n, t: m["evaluator"]._load_eval_set(n),
    "evaluator.save_eval_set":  lambda m, n, t: m["evaluator"].save_eval_set(n, []),
    "gap._detect_gaps":         lambda m, n, t: m["gap"]._detect_gaps(n),
    "gap._save_gap_queue":      lambda m, n, t: m["gap"]._save_gap_queue(n, ["x"]),
    "gap.load_gap_queue":       lambda m, n, t: m["gap"].load_gap_queue(n),
    "gap.clear_gap_queue":      lambda m, n, t: m["gap"].clear_gap_queue(n),
    "gap._load_known_topics":   lambda m, n, t: m["gap"]._load_known_topics(n),
    "gap.mark_topic_known":     lambda m, n, t: m["gap"].mark_topic_known(n, "t"),
    "finetuner.train":          lambda m, n, t: m["finetuner"].train(n, t / "data.jsonl"),
}


@pytest.mark.parametrize("sink", sorted(SYNC_SINKS))
@pytest.mark.parametrize("name", [TRAVERSAL, "a/b", "..", "x\x00y"])
def test_sink_rejects_path_shaped_names_and_touches_nothing(sandbox, sink, name):
    before = _tree(sandbox["tmp"])
    with pytest.raises(InvalidModuleName):
        SYNC_SINKS[sink](sandbox["m"], name, sandbox["tmp"])
    assert _tree(sandbox["tmp"]) == before


@pytest.mark.parametrize("name", [TRAVERSAL, "a/b", "..", "x\x00y"])
def test_distiller_sink_rejects_and_touches_nothing(sandbox, name):
    # distiller._save_pairs keeps its stricter .isidentifier() guard (#37) in
    # front of module_child(); either way it must raise ValueError and write nothing.
    before = _tree(sandbox["tmp"])
    with pytest.raises(ValueError, match="Invalid module_name"):
        sandbox["m"]["distiller"]._save_pairs(name, "t", [{"query": "q", "answer": "a"}])
    assert _tree(sandbox["tmp"]) == before


@pytest.mark.asyncio
async def test_crawler_rejects_before_reading_config_or_touching_disk(sandbox, monkeypatch):
    crawler = sandbox["m"]["crawler"]

    def _no_config(*a, **kw):
        raise AssertionError("crawler consulted config before validating the name")

    monkeypatch.setattr(crawler.config, "get_sources", _no_config)
    before = _tree(sandbox["tmp"])
    with pytest.raises(InvalidModuleName):
        await crawler.run_module(TRAVERSAL)
    assert _tree(sandbox["tmp"]) == before


@pytest.mark.parametrize("name", [TRAVERSAL, "a/b", "..", "x\x00y"])
def test_reload_module_rejects_path_shaped_names(tmp_path, monkeypatch, name):
    # core.module_registry imports modules.base -> chromadb; skipped where it
    # is not installed (CI installs it).
    registry_mod = pytest.importorskip("core.module_registry")
    modules = tmp_path / "modules"
    modules.mkdir()
    monkeypatch.setattr(registry_mod, "MODULES_DIR", modules)
    before = _tree(tmp_path)
    with pytest.raises(InvalidModuleName):
        registry_mod.reload_module(name, {})
    assert _tree(tmp_path) == before


# ── what a name MAY be: registry-style names keep working ─────────────

def test_registry_style_name_round_trips_through_the_sinks(sandbox):
    gap, evaluator = sandbox["m"]["gap"], sandbox["m"]["evaluator"]
    name = "my-module"  # a legal directory basename; not an identifier
    gap._save_gap_queue(name, ["alpha"])
    assert gap.load_gap_queue(name) == ["alpha"]
    evaluator.save_eval_set(name, [{"query": "q", "answer": "a"}])
    assert evaluator._load_eval_set(name) == [("q", "a")]
    assert (sandbox["d"]["gaps"] / "my-module_gaps.json").exists()
    assert (sandbox["d"]["evals"] / "my-module.json").exists()


def test_legitimate_identifier_still_reaches_the_distiller_sink(sandbox):
    n = sandbox["m"]["distiller"]._save_pairs(
        "finance_helper", "topic", [{"query": "q", "answer": "a"}]
    )
    assert n == 1
    assert len(list((sandbox["d"]["raw"] / "finance_helper").glob("distil_*.json"))) == 1


# ── core/brain_export.py: a symlinked module dir must not escape ──────

def _fake_repo(tmp_path, monkeypatch):
    repo = tmp_path / "fake_repo"
    (repo / "modules").mkdir(parents=True)
    (repo / "data").mkdir(parents=True)
    monkeypatch.setattr(be, "MODULES", repo / "modules")
    monkeypatch.setattr(be, "DATA", repo / "data")
    monkeypatch.setattr(be, "EXPORTS", repo / "data" / "exports")
    return repo


def _symlink_module(repo, outside, name="evil"):
    try:
        (repo / "modules" / name).symlink_to(outside, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks not available on this platform")


def test_export_refuses_a_module_directory_that_is_a_symlink_out_of_modules(tmp_path, monkeypatch):
    repo = _fake_repo(tmp_path, monkeypatch)
    outside = tmp_path / "victim_area"
    (outside / "weights" / "active").mkdir(parents=True)
    (outside / "weights" / "active" / "secret.bin").write_text("must never be bundled")
    _symlink_module(repo, outside)
    with pytest.raises(ValueError, match="Invalid module_name"):
        be.export_module("evil")  # a perfectly valid identifier
    exports = repo / "data" / "exports"
    assert not exports.exists() or not any(exports.iterdir())


def test_import_refuses_to_replace_a_module_directory_that_is_a_symlink_out(tmp_path, monkeypatch):
    repo = _fake_repo(tmp_path, monkeypatch)
    # The bundle sits in the exports dir and the import root (issue #54: no
    # root configured => refused, there is no default) is pointed at it, so this
    # keeps testing the module_name boundary rather than the /import boundary.
    exports = repo / "data" / "exports"
    exports.mkdir(parents=True)
    monkeypatch.setattr(be, "import_root", lambda: os.path.realpath(exports))
    outside = tmp_path / "victim_area"
    outside.mkdir()
    (outside / "important.txt").write_text("irreplaceable")
    _symlink_module(repo, outside)
    bundle = exports / "b.ocbrain"
    with zipfile.ZipFile(bundle, "w") as zf:
        zf.writestr("manifest.json", json.dumps({
            "format": "ocbrain/1.0", "module_name": "evil",
            "stage": "bootstrap", "base_model": "mistral"}))
    with pytest.raises(ValueError, match="Invalid module_name"):
        be.import_module(bundle, overwrite=True)
    assert (outside / "important.txt").read_text() == "irreplaceable"
