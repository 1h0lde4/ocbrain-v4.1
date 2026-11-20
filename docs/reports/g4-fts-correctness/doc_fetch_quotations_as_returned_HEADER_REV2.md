# SQLite documentation wording — archive of fetch-tool output (not raw source text)

**Record type and authority.** This file preserves text returned by a summarising web-fetch tool on 2026-10-21. It is an archival record of that tool's response, **not a raw copy of the live SQLite pages and not an authority for current wording or section numbering**. The quotation marks and displayed section labels below must be understood in that provenance context; they must not be promoted into normative citations.

**Subsequent verification for SQLite 3.45.1.** After this file was created, the quoted passages relied on by the packet were checked against raw HTML extracted from the SQLite 3.45.1 documentation package obtained from a signature-verified Ubuntu archive. All 11 expected passages were present; the chain of custody and check are recorded in `raw_sqlite_docs_verification.md`, with raw excerpts in `raw_html_excerpts_sqlite3-doc_3.45.1-1ubuntu2.8.txt`. That establishes presence in the packaged **3.45.1 documentation only**; it does not establish that the live website was read raw, that the fetch output is identical to current live content, or that wording is unchanged in other SQLite releases.

**Live-page limitation and section labels.** The audit shell could not read `sqlite.org` directly (HTTP 403 from the allow-list proxy). The only record of live-page text here is the fetch tool's response, copied into this file on 2026-10-21; that tool reported reading the first 100,000 of 106,793 characters of `fts5.html` (through about §7.1). Its reported FTS5 section numbers differ from the packaged 3.45.1 documentation: the fetch response labels the integrity-check, rebuild and secure-delete passages §6.7, §6.12 and §6.13, whereas the 3.45.1 documentation labels them §6.6, §6.11 and §6.12. **Those fetch-reported numbers are retained below only to preserve the historical record.** For packet claims, use the heading IDs (for example, `#the_integrity_check_command`) and the packaged raw 3.45.1 excerpts; do not cite the fetch-returned section numbers as current/live-page authority.

**Independent evidence boundary.** The behaviours described by these passages were separately checked against SQLite 3.45.1 source and the packaged runtime probes (`source_excerpts_raw.txt` and probe outputs). That does not validate untested SQLite versions, establish physical-erasure guarantees, or explain the FTS5 secure-delete `integrity-check` anomaly. The maintainer should re-read raw documentation for each supported version where version-specific wording matters before ratifying a claim that depends on it.

## `https://www.sqlite.org/fts5.html`

### §6.3 The 'delete' Command (anchor `#the_delete_command`, as listed in the page's table of contents)
> This command is only available with external content and contentless tables. It is used to delete the index entries associated with a single row from the full-text index. […]
>
> The values inserted into the other columns must match the values currently stored in the table. […]
>
> If the values "inserted" into the text columns as part of a 'delete' command are not the same as those currently stored within the table, the results may be unpredictable.
>
> The reason for this is easy to understand: […] So if the data supplied to FTS5 when a row is deleted using this command is different from that used to determine the set of token instances when it was inserted, some full-text index entries may not be correctly deleted, or FTS5 may try to remove index entries that do not exist. This can leave the full-text index in an unpredictable state, making future query results unreliable.

### §6.7 The 'integrity-check' Command (anchor `#the_integrity_check_command`)
> This command is used to verify that the full-text index is internally consistent, and, optionally, that it is consistent with any external content table.
>
> The integrity-check command is invoked by inserting the text value 'integrity-check' into the special column with the same name as the FTS5 table. If a value is supplied for the "rank" column, it must be either 0 or 1. […]
>
> The three forms above are equivalent for all FTS tables that are not external content tables. […]
>
> For an external content table, the contents of the index are only compared to the contents of the external content table if the value specified for the rank column is 1.
>
> In all cases, if any discrepancies are found, the command fails with an SQLITE_CORRUPT_VTAB error.

### §6.12 The 'rebuild' Command (anchor `#the_rebuild_command`)
> This command first deletes the entire full-text index, then rebuilds it based on the contents of the table or content table. It is not available with contentless tables.
>
> `INSERT INTO ft(ft) VALUES('rebuild');`

### §6.13 The 'secure-delete' Configuration Option (first fetch only)
> The default value of the secure-delete option is 0.
>
> **Warning:** Once one or more table rows have been updated or deleted with this option set, the FTS5 table may no longer be read or written by any version of FTS5 earlier than 3.42.0 (the first version in which this option was available). […] The FTS5 file format may be reverted, so that it may be read by earlier versions of FTS5, by running the 'rebuild' command on the table using version 3.42.0 or later.

### §4.4.3 External Content Tables (AFTER DELETE trigger)
> It is still the responsibility of the user to ensure that the contents of an external content FTS5 table are kept up to date with the content table. One way to do this is with triggers. For example:

The trigger block that follows (comment `-- Triggers to keep the FTS index up to date.`, triggers `t1_ai`, `t1_ad`, `t1_au`) contains, as returned by the first fetch:
```
CREATE TRIGGER t1_ad AFTER DELETE ON t1 BEGIN
  INSERT INTO fts_idx(fts_idx, rowid, b, c) VALUES('delete', old.a, old.b, old.c);
END;
```

## `https://www.sqlite.org/lang_vacuum.html`
> The VACUUM command may change the ROWIDs of entries in any tables that do not have an explicit INTEGER PRIMARY KEY.

(The fetch tool joined a line-wrapped sentence. It reported that the page makes no statement about whether `VACUUM INTO` preserves rowids; the 3.45.1 source, `source_excerpts_raw.txt`, and the control probe show that `VACUUM INTO` preserved them in both test tables on that build.)
Upstream test `test/e_vacuum.test` (SQLite repository, text returned by a tool) carries `# EVIDENCE-OF: R-17495-17419 The VACUUM command may change the ROWIDs of …`, i.e. the sentence is a documented, tested requirement of `lang_vacuum.html`.

## Python 3.12 `sqlite3` — NOT fetched; verified at raw source
`Doc/library/sqlite3.rst` at CPython tag `v3.12.3` (excerpts in `source_excerpts_raw.txt`): "The `executescript()` method implicitly commits any pending transaction before execution of the given SQL script, regardless of the value of `isolation_level`." and "`sqlite3` used to implicitly commit an open transaction before DDL statements. This is no longer the case." (3.6). The `Cursor.executescript` entry additionally says the implicit `COMMIT` happens "If the autocommit is `LEGACY_TRANSACTION_CONTROL` and there is a pending transaction"; the probe observed that with `autocommit=False` `executescript` did **not** commit (T7), so the two sentences are consistent with the observed behaviour only when read together with the mode.