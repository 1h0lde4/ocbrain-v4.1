"""
FILE_READING: formats, structure, identity/revision, selection, statuses.

Binary formats are parsed for real, in the isolated subprocess (no mocks of the
parsers). Every outcome the task names is exercised and must be distinguishable:
ok / partial / degraded / empty / unsupported / malformed / unreadable /
dependency_unavailable / limit_exceeded.
"""
import json
import subprocess
import sys

import pytest

from core.capabilities.capability import CapabilityRequest
from core.capabilities.descriptors import CapabilityStatus as S
from core.capabilities.foundation.file_reading import (
    ArtifactAccessError, FileReadingAdapter, ResolvedArtifact,
)
from core.capabilities.foundation.readers.base import (
    Dependency, MEDIA_PDF, ReadLimits, ReaderRegistry, ReaderSpec,
)
from core.capabilities.foundation.readers.defaults import default_reader_registry
from core.capabilities.foundation.schemas import sha256_hex
from tests.capability_foundation.fixtures import (
    make_docx, make_pdf, make_xlsx, traversal_zip, zip_bomb,
)

MD = ("# Annual Report\n\nIntro paragraph.\n\n## Revenue\n\nRevenue grew.\n\n"
      "## Risks\n\n- supply\n- fx\n\n### Detail\n\nMore detail.\n")


def _adapter(**kw):
    return FileReadingAdapter(**kw)


async def _read(adapter, artifacts, op="read_document", **payload):
    return await adapter.execute(CapabilityRequest(
        "file_reading", {"artifacts": artifacts, **payload}, operation=op), None)


def _doc(result, i=0):
    return result.output["documents"][i]["document"]


def _status(result, i=0):
    return result.output["documents"][i]["status"]


def art(aid="a1", content=MD, **kw):
    """Text content defaults to a *declared* Markdown type (callers, e.g. a UX,
    supply media_type/filename; with no hint at all, text reads as text/plain)."""
    if isinstance(content, str) and "media_type" not in kw and "filename" not in kw:
        kw["media_type"] = "text/markdown"
    return {"artifact_id": aid, "content": content, **kw}


# ── formats and structure ───────────────────────────────────────────────────

class TestFormats:
    @pytest.mark.asyncio
    async def test_markdown_structure_sections_and_locators(self):
        r = await _read(_adapter(), [art(filename="report.md", revision="4")])
        assert r.status == S.OK
        d = _doc(r)
        assert d["title"] == "Annual Report"
        assert [s["heading"] for s in d["sections"]] == [
            "Annual Report", "Revenue", "Risks", "Detail"]
        risks = next(s for s in d["sections"] if s["heading"] == "Risks")
        detail = next(s for s in d["sections"] if s["heading"] == "Detail")
        assert detail["block_start"] > risks["block_start"] and detail["block_end"] <= risks["block_end"]
        assert all(b["locator"].startswith("lines=") for b in d["blocks"])
        assert d["reader"]["id"] == "markdown"

    @pytest.mark.asyncio
    async def test_csv_and_tsv_tables(self):
        r = await _read(_adapter(), [
            art("c1", "name,qty\nbolt,4\nnut,9\n", media_type="text/csv"),
            art("c2", "a\tb\n1\t2\n", media_type="text/tab-separated-values")])
        assert r.status == S.OK
        t = _doc(r, 0)["tables"][0]
        assert t["rows"] == [["name", "qty"], ["bolt", "4"], ["nut", "9"]]
        assert t["range"] == "A1:B3" and t["header_rows"] == 1
        assert _doc(r, 1)["tables"][0]["rows"][1] == ["1", "2"]
        assert any(w["code"] == "header_row_assumed" for w in _doc(r, 0)["warnings"])

    @pytest.mark.asyncio
    async def test_docx_reading_order_headings_and_tables(self):
        data = make_docx(["Sales rose."], table=[["Region", "Sales"], ["EU", "10"]])
        r = await _read(_adapter(), [art("d1", data, filename="q3.docx")])
        assert r.status == S.OK
        d = _doc(r)
        kinds = [b["kind"] for b in d["blocks"]]
        assert kinds == ["heading", "heading", "paragraph", "table"]
        assert d["title"] == "Quarterly Report"
        assert d["tables"][0]["rows"] == [["Region", "Sales"], ["EU", "10"]]
        assert d["reader"]["id"] == "ooxml" and d["reader"]["version"]
        assert r.output["documents"][0]["provenance"]["reader"]["isolation"] == "isolated"

    @pytest.mark.asyncio
    async def test_xlsx_sheets_ranges_and_hidden_sheet_policy(self):
        data = make_xlsx([("Region", "Q1"), ("EU", 5), ("US", 7)], extra_sheets=("Notes",))
        r = await _read(_adapter(), [art("x1", data)])
        d = _doc(r)
        sales = next(t for t in d["tables"] if t["sheet"] == "Sales")
        assert sales["range"] == "A1:B3" and sales["rows"][2] == ["US", "7"]
        assert sales["locator"] == "sheet=Sales;range=A1:B3"
        only = await _read(_adapter(), [art("x1", data)], selection={"sheets": ["Notes"]})
        assert [t["sheet"] for t in _doc(only)["tables"]] == ["Notes"]

    @pytest.mark.asyncio
    async def test_pdf_pages_and_page_selection(self):
        pdf = make_pdf(["Quarterly results overview", "Risk factors and outlook"])
        r = await _read(_adapter(), [art("p1", pdf)])
        d = _doc(r)
        assert r.status == S.OK and d["page_count"] == 2
        assert [(b["page"], b["text"]) for b in d["blocks"]] == [
            (1, "Quarterly results overview"), (2, "Risk factors and outlook")]
        assert d["blocks"][0]["locator"] == "page=1;para=1"
        sel = await _read(_adapter(), [art("p1", pdf)], selection={"pages": [2]})
        assert [b["page"] for b in _doc(sel)["blocks"]] == [2]
        missing = await _read(_adapter(), [art("p1", pdf)], selection={"pages": [2, 9]})
        assert missing.status == S.PARTIAL                       # asked for a page that does not exist
        assert any(w["code"] == "selection_not_found" for w in _doc(missing)["warnings"])

    @pytest.mark.asyncio
    async def test_all_formats_in_one_request(self):
        r = await _read(_adapter(), [
            art("m", MD), art("c", "a,b\n1,2\n", media_type="text/csv"),
            art("d", make_docx()), art("x", make_xlsx()), art("p", make_pdf(["hello world"]))])
        assert r.status == S.OK
        assert [o["status"] for o in r.output["documents"]] == [S.OK] * 5
        readers = {o["provenance"]["reader"]["id"] for o in r.output["documents"]}
        assert readers == {"markdown", "csv", "ooxml", "pdf"}


# ── identity, revision, freshness ───────────────────────────────────────────

class TestIdentity:
    @pytest.mark.asyncio
    async def test_same_name_different_content_is_a_different_artifact_revision(self):
        a = _adapter()
        r1 = await _read(a, [art("report", "# v1\n\nold", filename="report.md", revision="1")])
        r2 = await _read(a, [art("report", "# v2\n\nnew", filename="report.md", revision="2")])
        i1, i2 = _doc(r1)["identity"], _doc(r2)["identity"]
        assert i1["display_name"] == i2["display_name"] == "report.md"     # same label...
        assert i1["content_sha256"] != i2["content_sha256"]                # ...never the same identity
        assert i1["identity_key"] != i2["identity_key"]

    @pytest.mark.asyncio
    async def test_identity_records_hash_size_media_type(self):
        content = b"# T\n\nbody"
        r = await _read(_adapter(), [art("a", content, revision="7")])
        i = _doc(r)["identity"]
        assert i["content_sha256"] == sha256_hex(content) and i["size_bytes"] == len(content)
        assert i["media_type"] == "text/plain" and i["revision"] == "7"

    @pytest.mark.asyncio
    async def test_stale_reference_is_refused_not_silently_read(self):
        expected = sha256_hex(b"# the revision I asked for")
        r = await _read(_adapter(), [art("a", "# a different revision", sha256=expected)])
        o = r.output["documents"][0]
        assert o["status"] == S.INVALID_REQUEST and o["reason"] == "content_hash_mismatch"
        ok = await _read(_adapter(), [art("a", "# the revision I asked for", sha256=expected)])
        assert ok.status == S.OK

    @pytest.mark.asyncio
    async def test_read_key_is_deterministic_and_tracks_every_input(self):
        a = _adapter()
        keys = []
        for content, sel, lim in (("# x\n\ny", {}, None), ("# x\n\ny", {}, None),
                                  ("# x\n\nz", {}, None), ("# x\n\ny", {"lines": [1, 1]}, None),
                                  ("# x\n\ny", {}, {"max_chars": 10})):
            r = await _read(a, [art("a", content)], selection=sel, limits=lim)
            keys.append(r.output["documents"][0]["provenance"]["read_key"])
        assert keys[0] == keys[1]                       # repeatable
        assert len(set(keys)) == 4                      # content / selection / limits all change it

    @pytest.mark.asyncio
    async def test_reading_is_repeatable(self):
        a = _adapter()
        strip = lambda o: json.dumps(o, sort_keys=True, default=str).replace(  # noqa: E731
            '"duration_ms"', '"d"')
        r1 = await _read(a, [art("a", MD)])
        r2 = await _read(a, [art("a", MD)])
        d1, d2 = _doc(r1), _doc(r2)
        assert d1 == d2 and r1.output["status"] == r2.output["status"]


# ── selection / progressive reading ─────────────────────────────────────────

class TestSelection:
    @pytest.mark.asyncio
    async def test_outline_then_targeted_read_by_stable_section_id(self):
        a = _adapter()
        outline = await _read(a, [art()], op="extract_structure")
        od = _doc(outline)
        assert od["outline_only"] and all(b["kind"] in ("heading", "table") for b in od["blocks"])
        risks = next(s for s in od["sections"] if s["heading"] == "Risks")
        got = await _read(a, [art()], selection={"sections": [risks["section_id"]]})
        d = _doc(got)
        texts = [b["text"] for b in d["blocks"]]
        assert "supply" in texts and "More detail." in texts       # the nested sub-section comes with it
        assert "Revenue grew." not in texts
        assert risks["section_id"] in [s["section_id"] for s in d["sections"]]   # ids are stable

    @pytest.mark.asyncio
    async def test_section_by_heading_text_and_table_by_id(self):
        a = _adapter()
        r = await _read(a, [art()], selection={"sections": ["revenue"]})
        assert [b["text"] for b in _doc(r)["blocks"]] == ["Revenue", "Revenue grew."]
        csv = await _read(a, [art("c", "a,b\n1,2\n", media_type="text/csv")],
                          selection={"tables": ["t1"]})
        assert _doc(csv)["tables"][0]["table_id"] == "t1"

    @pytest.mark.asyncio
    async def test_lines_selection(self):
        r = await _read(_adapter(), [art()], selection={"lines": [1, 3]})
        assert [b["text"] for b in _doc(r)["blocks"]] == ["Annual Report", "Intro paragraph."]

    @pytest.mark.asyncio
    async def test_unmatched_selection_is_empty_or_partial_never_a_silent_full_read(self):
        a = _adapter()
        none = await _read(a, [art()], selection={"sections": ["nonexistent"]})
        assert none.status == S.EMPTY and _doc(none)["blocks"] == []
        assert any(w["code"] == "selection_not_found" for w in _doc(none)["warnings"])
        some = await _read(a, [art()], selection={"sections": ["Revenue", "nonexistent"]})
        assert some.status == S.PARTIAL

    @pytest.mark.asyncio
    async def test_reader_specific_selector_on_wrong_format_is_unsupported(self):
        r = await _read(_adapter(), [art()], selection={"pages": [1]})       # markdown has no pages
        o = r.output["documents"][0]
        assert r.status == S.UNSUPPORTED and o["reason"] == "selection_unsupported:pages"

    @pytest.mark.asyncio
    async def test_unknown_selector_and_bad_selector_values(self):
        a = _adapter()
        assert (await _read(a, [art()], selection={"weird": 1})).status == S.INVALID_REQUEST
        r = await _read(a, [art()], selection={"lines": [5, 1]})
        assert r.status == S.INVALID_REQUEST

    @pytest.mark.asyncio
    async def test_context_budget_truncation_is_partial_and_explicit(self):
        big = "# T\n\n" + "\n\n".join(f"paragraph number {i}" for i in range(200))
        r = await _read(_adapter(), [art("big", big)], limits={"max_chars": 500})
        o = r.output["documents"][0]
        assert r.status == S.PARTIAL and _doc(r)["truncated"] is True
        assert o["reason"] == "max_chars" and _doc(r)["stats"]["chars"] <= 500

    @pytest.mark.asyncio
    async def test_request_can_tighten_but_never_raise_limits(self):
        a = _adapter(limits=ReadLimits(max_bytes=100))
        r = await _read(a, [art("a", "x" * 500)], limits={"max_bytes": 10**9})
        assert r.status == S.LIMIT_EXCEEDED


# ── multiple artifacts and aggregate status ─────────────────────────────────

class TestMultipleArtifacts:
    @pytest.mark.asyncio
    async def test_one_bad_artifact_makes_the_set_partial_not_failed(self):
        r = await _read(_adapter(), [art("good"), art("bad", b"\x89PNG\r\n\x1a\nxx")])
        assert r.success and r.status == S.PARTIAL
        assert [o["status"] for o in r.output["documents"]] == [S.OK, S.UNSUPPORTED]
        assert r.provenance["outcomes"][1]["reason"].startswith("unsupported_media_type")

    @pytest.mark.asyncio
    async def test_all_failing_the_same_way_reports_that_way(self):
        r = await _read(_adapter(), [art("a", b"\x89PNG\r\n\x1a\n1"), art("b", b"\xff\xd8\xff\xe0jj")])
        assert r.status == S.UNSUPPORTED and not r.success

    @pytest.mark.asyncio
    async def test_all_empty_is_empty_and_mixed_with_ok_is_ok(self):
        a = _adapter()
        assert (await _read(a, [art("a", b""), art("b", b"")])).status == S.EMPTY
        assert (await _read(a, [art("a", b""), art("b", MD)])).status == S.OK

    @pytest.mark.asyncio
    async def test_request_shape_errors(self):
        a = _adapter(limits=ReadLimits(max_artifacts=2))
        assert (await _read(a, [])).status == S.INVALID_REQUEST
        assert (await _read(a, [art("a"), art("b"), art("c")])).status == S.LIMIT_EXCEEDED
        assert (await _read(a, "not a list")).status == S.INVALID_REQUEST


# ── failure / degradation semantics: every case distinguishable ─────────────

class TestStatusSemantics:
    @pytest.mark.asyncio
    async def test_empty_is_distinct_from_failed(self):
        a = _adapter()
        zero = await _read(a, [art("z", b"")])
        blank = await _read(a, [art("b", "   \n\n  ")])
        assert zero.status == blank.status == S.EMPTY and zero.success and blank.success
        assert zero.output["documents"][0]["reason"] == "zero_length_artifact"
        bad = await _read(a, [art("m", b"PK\x03\x04garbage")])
        assert bad.status == S.MALFORMED and not bad.success

    @pytest.mark.asyncio
    async def test_unsupported_vs_malformed_vs_unreadable(self):
        a = _adapter()
        assert (await _read(a, [art("i", b"\x89PNG\r\n\x1a\nzz")])).status == S.UNSUPPORTED
        assert (await _read(a, [art("t", b"has\x00nul")])).status == S.UNSUPPORTED   # NUL => binary, no text reader
        assert (await _read(a, [art("p", b"%PDF-1.4 truncated")])).status == S.MALFORMED
        assert (await _read(a, [{"artifact_id": "r"}])).status == S.UNREADABLE       # no content, no resolver

    @pytest.mark.asyncio
    async def test_image_only_pdf_is_unsupported_not_empty(self):
        r = await _read(_adapter(), [art("scan", make_pdf([""]))])
        assert r.status == S.UNSUPPORTED
        assert r.output["documents"][0]["reason"] == "no_text_layer"

    @pytest.mark.asyncio
    async def test_degraded_when_read_with_reduced_fidelity(self):
        r = await _read(_adapter(), [art("w", "caf\xe9 au lait".encode("cp1252"))])
        assert r.status == S.DEGRADED and r.success                      # usable, but not clean
        assert any(w["code"] == "encoding_fallback_cp1252" for w in _doc(r)["warnings"])
        mixed = await _read(_adapter(), [art("p", make_pdf(["text here", ""]))])
        assert mixed.status == S.DEGRADED
        assert any(w["code"] == "pages_without_text" for w in _doc(mixed)["warnings"])

    @pytest.mark.asyncio
    async def test_declared_type_disagreeing_with_content_is_reported(self):
        r = await _read(_adapter(), [art("p", make_pdf(["hello"]), media_type="text/plain")])
        assert r.status == S.DEGRADED and _doc(r)["reader"]["id"] == "pdf"   # content wins
        assert any(w["code"] == "declared_media_type_mismatch" for w in _doc(r)["warnings"])
        liar = await _read(_adapter(), [art("t", "just text", media_type="application/pdf")])
        assert liar.status == S.DEGRADED                                     # never silently "clean"

    @pytest.mark.asyncio
    async def test_limits_exceeded_statuses(self):
        a = _adapter(limits=ReadLimits(max_bytes=1000))
        assert (await _read(a, [art("big", "x" * 5000)])).status == S.LIMIT_EXCEEDED
        b = _adapter(limits=ReadLimits(max_total_bytes=1500))
        r = await _read(b, [art("a", "x" * 1000), art("b", "y" * 1000)])
        assert [o["status"] for o in r.output["documents"]] == [S.OK, S.LIMIT_EXCEEDED]

    @pytest.mark.asyncio
    async def test_dependency_unavailable_then_fallback_to_a_second_reader(self):
        missing = ReaderSpec("pdf-lib-a", "1", ("pdf",), (MEDIA_PDF,), "isolated",
                             dependencies=(Dependency("no_such_module_xyz", "no-such-dist"),))
        reg = ReaderRegistry()
        reg.register(missing)
        only_missing = _adapter(readers=reg)
        r = await _read(only_missing, [art("p", make_pdf(["hi"]))])
        assert r.status == S.DEPENDENCY_UNAVAILABLE
        assert r.output["documents"][0]["reason"] == "no-such-dist_not_installed"

        def alt(data, opts):
            return {"blocks": [{"kind": "paragraph", "text": "read by B", "page": 1,
                                "locator": "page=1"}], "page_count": 1}
        reg.register(ReaderSpec("pdf-lib-b", "0.3", ("pdf",), (MEDIA_PDF,), "inline"), alt)
        r2 = await _read(_adapter(readers=reg), [art("p", make_pdf(["hi"]))])
        assert r2.status == S.OK and _doc(r2)["reader"] == {"id": "pdf-lib-b", "version": "0.3"}

    @pytest.mark.asyncio
    async def test_security_floor_marks_old_parser_unavailable(self):
        strict = ReaderSpec("pdf", "1", ("pdf",), (MEDIA_PDF,), "isolated",
                            dependencies=(Dependency("pypdf", "pypdf", "999.0.0"),))
        reg = ReaderRegistry()
        reg.register(strict)
        r = await _read(_adapter(readers=reg), [art("p", make_pdf(["hi"]))])
        assert r.status == S.DEPENDENCY_UNAVAILABLE
        assert "below_security_floor" in r.output["documents"][0]["reason"]

    @pytest.mark.asyncio
    async def test_reader_bug_is_contained_as_failed_not_a_crash(self):
        def boom(data, opts):
            raise RuntimeError("bug in reader")
        reg = ReaderRegistry()
        reg.register(ReaderSpec("t", "1", ("text",), ("text/plain", "text/markdown"), "inline"), boom)
        r = await _read(_adapter(readers=reg), [art("a", "hello")])
        assert r.status == S.FAILED
        assert r.output["documents"][0]["reason"] == "reader_internal_error"


# ── access boundary: paths, URLs, resolver seam ─────────────────────────────

class TestAccessBoundary:
    @pytest.mark.asyncio
    async def test_paths_and_urls_are_refused_never_opened(self, tmp_path):
        secret = tmp_path / "secret.txt"
        secret.write_text("TOP-SECRET-CONTENT")
        a = _adapter()
        for key in ("path", "file_path", "uri", "url", "file", "location"):
            r = await _read(a, [{"artifact_id": "a", key: str(secret)}])
            o = r.output["documents"][0]
            assert r.status == S.INVALID_REQUEST and o["reason"] == "paths_not_accepted", key
            assert "TOP-SECRET" not in json.dumps(r.output)

    @pytest.mark.asyncio
    async def test_path_shaped_or_odd_artifact_ids_are_refused(self):
        a = _adapter()
        for bad in ("/etc/passwd", "../../x", "C:\\Windows\\x", "http://evil/x", "a b", "", None, 7):
            r = await _read(a, [{"artifact_id": bad, "content": "x"}])
            assert r.status == S.INVALID_REQUEST, bad
        assert (await _read(a, [{"artifact_id": "9f2c-uuid_like:1.2", "content": "x"}])).status == S.OK

    @pytest.mark.asyncio
    async def test_content_must_be_bytes_or_text(self, tmp_path):
        p = tmp_path / "f.txt"
        p.write_text("data")
        r = await _read(_adapter(), [{"artifact_id": "a", "content": p}])      # a Path object is not content
        assert r.status == S.INVALID_REQUEST
        assert (await _read(_adapter(), [{"artifact_id": "a", "content": bytearray(b"ok")}])).status == S.OK

    @pytest.mark.asyncio
    async def test_resolver_is_the_only_way_to_read_by_reference(self):
        class Resolver:
            async def resolve(self, ref, *, trace_id):
                if ref["artifact_id"] == "denied":
                    raise ArtifactAccessError("access_denied")
                return ResolvedArtifact(ref["artifact_id"], b"# resolved\n\nbody",
                                        revision="3", display_name="r.md")
        a = _adapter(resolver=Resolver())
        ok = await _read(a, [{"artifact_id": "granted"}])
        assert ok.status == S.OK and _doc(ok)["identity"]["revision"] == "3"
        denied = await _read(a, [{"artifact_id": "denied"}])
        assert denied.status == S.UNREADABLE
        assert denied.output["documents"][0]["reason"] == "access_denied"

    @pytest.mark.asyncio
    async def test_parser_libraries_never_load_in_the_host_process(self, tmp_path):
        # Fixtures are built HERE (which loads python-docx/openpyxl in the test
        # process); the child only ever sees bytes on disk.
        for name, data in (("p.pdf", make_pdf(["hi there"])), ("d.docx", make_docx()),
                           ("x.xlsx", make_xlsx())):
            (tmp_path / name).write_bytes(data)
        script = (
            "import asyncio, sys, pathlib\n"
            "from core.capabilities.capability import CapabilityRequest\n"
            "from core.capabilities.foundation.file_reading import FileReadingAdapter\n"
            f"root = pathlib.Path({str(tmp_path)!r})\n"
            "async def main():\n"
            "    arts = [{'artifact_id': n[0], 'content': (root / n).read_bytes()}\n"
            "            for n in ('p.pdf', 'd.docx', 'x.xlsx')]\n"
            "    r = await FileReadingAdapter().execute(\n"
            "        CapabilityRequest('file_reading', {'artifacts': arts}), None)\n"
            "    assert r.status == 'ok', r.status\n"
            "asyncio.run(main())\n"
            "loaded = [m for m in ('pypdf', 'docx', 'openpyxl', 'lxml') if m in sys.modules]\n"
            "print('LOADED:' + ','.join(loaded))\n")
        proc = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True,
                              timeout=120, cwd=str(__import__("pathlib").Path(__file__).parents[2]))
        assert proc.returncode == 0, proc.stderr[-500:]
        line = [l for l in proc.stdout.splitlines() if l.startswith("LOADED:")][-1]
        assert line == "LOADED:"        # parsers ran in child processes only
