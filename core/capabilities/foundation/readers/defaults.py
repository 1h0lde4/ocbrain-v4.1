"""
core/capabilities/foundation/readers/defaults.py — the default reader set.

Registered order matters: the first reader whose family/media type matches is
tried first; a reader that declines (unsupported / dependency_unavailable)
hands the artifact to the next matching one. To replace or supplement a parser,
register another ReaderSpec for the same format -- nothing else changes.
"""
from __future__ import annotations

from core.capabilities.foundation.readers import text_readers as tr
from core.capabilities.foundation.readers.base import (
    Dependency, MEDIA_CSV, MEDIA_DOCX, MEDIA_MD, MEDIA_PDF, MEDIA_TSV,
    MEDIA_TXT, MEDIA_XLSX, ReaderRegistry, ReaderSpec,
)

# Security floor for pypdf: verified via direct CVE/changelog lookup,
# 2026-09-22. Confirmed crafted-PDF infinite-loop DoS advisories, oldest
# fixed-in version first: CVE-2026-54530/-54531 (layout-mode extraction /
# outline merge, fixed 6.13.0), CVE-2026-54651 (thread/article merge, fixed
# 6.13.1), CVE-2026-59935/-59936 (non-terminated inline image, ASCII85/
# ASCIIHex vs. general, fixed 6.14.1/6.14.2), CVE-2026-84309
# (TreeObject.insert_child cycle, fixed 6.16.0 per that release's own
# changelog: "Security (SEC): Detect cycles in TreeObject.insert_child").
# 6.16.1 (2026-08-14) adds one further, not-yet-CVE-numbered DoS fix per its
# changelog ("Limit iterations for outline retrieval and XForm text
# extraction") -- floor set one patch above the last confirmed advisory for
# that margin. Re-verify against https://github.com/py-pdf/pypdf/security
# before raising SUPPORTED_MEDIA_TYPES' trust in any reader, and before
# every dependency bump. A library below its floor reports
# dependency_unavailable rather than being trusted (readers/base.py
# Dependency.check()).
PYPDF_SECURITY_FLOOR = "6.16.1"
ISOLATED_READER_VERSION = "1.0.0"  # == isolated_entry.READER_VERSION (tested)


def default_reader_registry() -> ReaderRegistry:
    reg = ReaderRegistry()
    reg.register(ReaderSpec("text", tr.READER_VERSION, ("text",), (MEDIA_TXT,),
                            "inline", supported_selection=("lines",)),
                 tr.read_text)
    reg.register(ReaderSpec("markdown", tr.READER_VERSION, ("text",), (MEDIA_MD,),
                            "inline", supported_selection=("lines",)),
                 tr.read_markdown)
    reg.register(ReaderSpec("csv", tr.READER_VERSION, ("text",),
                            (MEDIA_CSV, MEDIA_TSV), "inline"),
                 tr.read_csv)
    reg.register(ReaderSpec(
        "pdf", ISOLATED_READER_VERSION, ("pdf",), (MEDIA_PDF,), "isolated",
        supported_selection=("pages",),
        dependencies=(Dependency("pypdf", "pypdf", PYPDF_SECURITY_FLOOR),),
        libraries=("pypdf",)))
    reg.register(ReaderSpec(
        "ooxml", ISOLATED_READER_VERSION, ("zip",), (MEDIA_DOCX, MEDIA_XLSX),
        "isolated", supported_selection=("sheets",),
        libraries=("python-docx", "openpyxl")))
    return reg
