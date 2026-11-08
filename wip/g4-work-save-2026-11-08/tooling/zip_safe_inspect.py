#!/usr/bin/env python3
"""Safe, read-only inspection of a ZIP: names, path safety, duplicates, case collisions, entry types, sizes.
Extracts nothing. usage: python3 -I zip_safe_inspect.py ZIP"""
import sys, zipfile, collections, stat, posixpath
z = zipfile.ZipFile(sys.argv[1])
infos = z.infolist()
names = [i.filename for i in infos]
print("entries (all):", len(infos))
files = [i for i in infos if not i.is_dir()]
dirs = [i for i in infos if i.is_dir()]
print("regular-looking files:", len(files), "| directory entries:", len(dirs))
bad_abs = [n for n in names if n.startswith("/") or (len(n) > 1 and n[1] == ":") or "\\" in n]
bad_dd = [n for n in names if ".." in posixpath.normpath(n).split("/")]
dups = [n for n, c in collections.Counter(names).items() if c > 1]
lower = collections.defaultdict(set)
for n in names:
    lower[n.lower()].add(n)
case_coll = [sorted(v) for v in lower.values() if len(v) > 1]
sym = []
special = []
for i in infos:
    mode = (i.external_attr >> 16) & 0xFFFF
    if mode:
        if stat.S_ISLNK(mode):
            sym.append(i.filename)
        elif not (stat.S_ISREG(mode) or stat.S_ISDIR(mode)):
            special.append((i.filename, oct(mode)))
enc = [i.filename for i in infos if i.flag_bits & 0x1]
print("absolute / backslash / drive paths:", bad_abs)
print("parent-traversal paths:", bad_dd)
print("duplicate names:", dups)
print("case-collisions:", case_coll)
print("symlink entries:", sym)
print("special-mode entries:", special)
print("encrypted entries:", enc)
tot_c = sum(i.compress_size for i in infos); tot_u = sum(i.file_size for i in infos)
print("total compressed:", tot_c, "total uncompressed:", tot_u, "ratio: %.2f" % (tot_u / max(tot_c, 1)))
print("largest entry:", max(infos, key=lambda i: i.file_size).filename, max(i.file_size for i in infos))
print("zip comment:", repr(z.comment[:200]))
print("top-level prefixes:", sorted({n.split('/')[0] for n in names}))
bad = z.testzip()
print("testzip (first bad member or None):", bad)
