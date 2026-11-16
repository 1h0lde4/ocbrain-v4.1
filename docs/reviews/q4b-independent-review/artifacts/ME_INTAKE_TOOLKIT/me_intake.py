#!/usr/bin/env python3
"""Evidence intake for the Q4-b review (ME items). Hashing and recording only: it never runs, parses or edits the files it receives.

Usage:
  python3 me_intake.py --dest ./ME_INTAKE --me ME-01 --label "Q4-b brief, Markdown" \
      [--revision 19] [--sender-note "downloaded 2026-11-12 14:05 CET"] [--expect-sha256 HEX] FILE [FILE ...]

What it does for every FILE:
  1. Opens the file read-only and reads its bytes once; computes SHA-256 and byte count of those bytes (no line-ending or other normalization).
  2. Copies the bytes unchanged to <dest>/received/<intake_id>__<original filename>, re-reads the copy and refuses to continue unless the copy's SHA-256 equals the original's.
  3. Appends one row to <dest>/INTAKE_REGISTER.tsv (append-only; existing rows are never rewritten) with: intake id, ME item, label, original filename, receipt time (UTC),
     byte count, SHA-256, copy path, copy SHA-256, extension-based type, file modification time (informational only), plus the fields the sender asserted (--revision, --sender-note),
     recorded as ASSERTED and not verified.
  4. For .zip files, also appends one row per member to <dest>/ZIP_MEMBERS.tsv (name, size, member SHA-256) computed in memory; nothing is extracted to disk.
It refuses to overwrite an existing copy. It does not modify the files it is given and does not touch any other directory.
"""
import argparse, csv, datetime, hashlib, mimetypes, os, shutil, sys, zipfile

REG_HDR = ["intake_id", "related_ME_item", "label", "original_filename", "receipt_time_UTC", "byte_count", "sha256_original_bytes",
           "copy_path", "sha256_of_copy", "type_by_extension", "file_mtime_UTC_informational", "sender_asserted_revision", "sender_note",
           "provenance_status", "notes"]
ZIP_HDR = ["intake_id", "member_name", "member_bytes", "member_sha256"]


def utc_now():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


def append_rows(path, header, rows):
    new = not os.path.exists(path)
    with open(path, "a", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter="\t", lineterminator="\n")
        if new:
            w.writerow(header)
        for r in rows:
            w.writerow(r)


def next_id(register):
    n = 0
    if os.path.exists(register):
        with open(register, encoding="utf-8") as f:
            n = max(0, sum(1 for _ in f) - 1)
    return n + 1


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dest", required=True, help="intake directory (created if missing); keep it outside any repository")
    ap.add_argument("--me", required=True, help="related ME item, e.g. ME-01")
    ap.add_argument("--label", required=True, help="what the sender says the file is")
    ap.add_argument("--revision", default="", help="revision or date the sender asserts (recorded as asserted)")
    ap.add_argument("--sender-note", default="", help="free text from the sender (recorded as asserted)")
    ap.add_argument("--expect-sha256", default="", help="a digest published by the source (for example GitHub's artifact digest, with or without a 'sha256:' prefix); the comparison is recorded in the notes, never used to alter anything")
    ap.add_argument("files", nargs="+")
    a = ap.parse_args()

    missing = [f for f in a.files if not os.path.isfile(f)]
    if missing:
        sys.exit("not regular files; nothing was recorded or copied: " + ", ".join(missing))
    os.makedirs(os.path.join(a.dest, "received"), exist_ok=True)
    register = os.path.join(a.dest, "INTAKE_REGISTER.tsv")
    zipreg = os.path.join(a.dest, "ZIP_MEMBERS.tsv")
    done = 0
    for src in a.files:
        receipt = utc_now()
        with open(src, "rb") as fh:
            data = fh.read()
        h = sha256_bytes(data)
        iid = f"I{next_id(register):03d}"
        name = os.path.basename(src)
        copy = os.path.join(a.dest, "received", f"{iid}__{name}")
        if os.path.exists(copy):
            sys.exit(f"refusing to overwrite {copy}")
        shutil.copyfile(src, copy)
        with open(copy, "rb") as fh:
            ch = sha256_bytes(fh.read())
        if ch != h:
            os.remove(copy)
            sys.exit(f"copy hash differs from the original for {src}; nothing recorded for it")
        os.chmod(copy, 0o444)
        mt = datetime.datetime.fromtimestamp(os.path.getmtime(src), datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        typ = mimetypes.guess_type(name)[0] or "unknown"
        note = "bytes hashed as received; no normalization"
        if a.expect_sha256:
            exp = a.expect_sha256.lower().replace("sha256:", "").strip()
            note += "; expected digest " + ("MATCH" if exp == h else f"MISMATCH (expected {exp}, computed {h})")
        members = []
        if name.lower().endswith(".zip"):
            try:
                with zipfile.ZipFile(copy) as z:
                    members = [[iid, i.filename, i.file_size, sha256_bytes(z.read(i))] for i in z.infolist() if not i.is_dir()]
            except zipfile.BadZipFile:
                note += "; NOT a readable zip archive"
        # the register row is written immediately after the verified copy, so a later failure never leaves an unrecorded copy
        append_rows(register, REG_HDR, [[iid, a.me, a.label, name, receipt, len(data), h, copy, ch, typ, mt, a.revision, a.sender_note,
                                         "RECEIVED; origin and revision are sender-asserted and UNVERIFIED", note]])
        if members:
            append_rows(zipreg, ZIP_HDR, members)
        done += 1
        print(f"{iid}  {len(data):>10} bytes  {h}  {name}")
    print(f"recorded {done} file(s) in {register}")


if __name__ == "__main__":
    main()
