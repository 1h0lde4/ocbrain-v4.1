#!/usr/bin/env python3
"""Check that expected sentences occur in the archive's raw HTML excerpts file (tags stripped, entities unescaped,
whitespace normalised). Data only; nothing is executed from the archive. usage: python3 -I passage_check.py EXCERPTS"""
import re, sys, html
raw = open(sys.argv[1], encoding="utf-8", errors="replace").read()
txt = html.unescape(re.sub(r"<[^>]+>", " ", raw))
txt = re.sub(r"\s+", " ", txt).replace("“", '"').replace("”", '"').replace("’", "'")
P = [
 ("4.4.3 external content: user responsibility", "It is still the responsibility of the user to ensure that the contents of an external content FTS5 table are kept up to date with the content table"),
 ("4.4.3 external content: AFTER DELETE trigger uses 'delete'", "VALUES('delete', old.a, old.b, old.c)"),
 ("6.x delete cmd: availability", "This command is only available with external content and contentless tables."),
 ("6.x delete cmd: values must match", "The values inserted into the other columns must match the values currently stored in the table."),
 ("6.x delete cmd: mismatch consequence", "are not the same as those currently stored within the table, the results"),
 ("6.6 integrity-check: rank=1 compares", "the contents of the index are only compared to the contents of the external content table if the value specified for the rank column is 1."),
 ("6.6 integrity-check: failure code", "SQLITE_CORRUPT_VTAB"),
 ("6.11 rebuild", "This command first deletes the entire full-text index, then rebuilds it based on the contents of the table or content table."),
 ("6.12 secure-delete: version gate", "earlier than 3.42.0"),
 ("6.12 secure-delete: default", "secure-delete"),
 ("VACUUM: rowids", "The VACUUM command may change the ROWIDs of entries in any tables that do not have an explicit INTEGER PRIMARY KEY."),
]
ok = 0
for name, s in P:
    s2 = s.replace("“", '"').replace("”", '"')
    found = s2 in txt
    ok += found
    print(("FOUND   " if found else "MISSING ") + name)
print(f"{ok}/{len(P)} expected fragments found in the excerpts text")
print("excerpt file size:", len(raw), "chars; normalised text:", len(txt), "chars")
