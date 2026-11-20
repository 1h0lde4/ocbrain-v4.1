#!/usr/bin/env python3
"""DERIVED recovery of members from a zip damaged by a Windows PowerShell '>' redirect.

The damaged file (intake I005) is the zip's bytes decoded with the OEM code page cp850, split into lines
(every lone CR or LF becomes CRLF, an existing CRLF stays one CRLF), re-encoded as UTF-16LE with a BOM, with one
extra CRLF appended. The central directory of that file contains no CR/LF, so each member's CRC32, compressed
size and uncompressed size can be read exactly. Within each member's deflate data every observed CRLF was
originally LF or CR; this script searches those choices, guided by the shape of GitHub Actions log lines, and accepts a
candidate only if its compressed size, uncompressed size and CRC32 equal the central directory values.

Output files are DERIVED content, never the original archive bytes. Read-only on the input.
Usage: recover_ps_redirect_members.py <damaged.zip> <outdir> [--large-budget N]   (N = 0 skips large members)
"""
import argparse, datetime, pathlib, re, struct, sys, time, zlib

ap = argparse.ArgumentParser()
ap.add_argument("src"); ap.add_argument("outdir")
ap.add_argument("--large-budget", type=int, default=3_000_000,
                help="search nodes allowed for members with more than 10 ambiguous positions; 0 skips them")
args = ap.parse_args()
sys.setrecursionlimit(20000)
OUT = pathlib.Path(args.outdir); OUT.mkdir(parents=True, exist_ok=True)

raw = open(args.src, "rb").read()
assert raw[:2] == b"\xff\xfe", "input is not UTF-16LE with a BOM"
obs = raw[2:].decode("utf-16-le").encode("cp850")
assert obs.endswith(b"\r\n"); obs = obs[:-2]                       # the one CRLF the redirect appended
transform = lambda orig: re.sub(rb"\r\n|\r|\n", b"\r\n", orig)       # what the redirect does to a byte string
u32 = lambda bs: struct.unpack("<I", bs)[0]
heads = [m.start() for m in re.finditer(rb"PK\x03\x04", obs)]
cds = [m.start() for m in re.finditer(rb"PK\x01\x02", obs)]
eocd = obs.rindex(b"PK\x05\x06")
assert not re.search(rb"[\r\n]", obs[cds[0]:eocd]), "central directory region contains CR/LF"
print(f"observed bytes {len(obs)}; members {len(heads)}; central directory region free of CR/LF: yes")

TS = re.compile(rb"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{7}Z ")
TOL, UP = 30, 3600                                                  # allowed timestamp regression / jump, seconds
def tsec(ts):
    try: return datetime.datetime.strptime(ts[:19].decode(), "%Y-%m-%dT%H:%M:%S").timestamp() + int(ts[20:27]) / 1e7
    except ValueError: return None
def line_ts(line, first):
    t = line[3:] if first and line[:3] == b"\xef\xbb\xbf" else line
    mm = TS.match(t); return mm.group(0)[:27] if mm else None
def tail_ok(tail, first):
    t = tail[3:] if first and tail[:3] == b"\xef\xbb\xbf" else tail
    if first and len(tail) < 3 and b"\xef\xbb\xbf".startswith(tail): return True
    pat = b"dddd-dd-ddTdd:dd:dd.dddddddZ "
    for i, ch in enumerate(t[:len(pat)]):
        if not ((48 <= ch <= 57) if pat[i:i+1] == b"d" else ch == pat[i]): return False
    return True

def solve(data_obs, maxsol, budget):
    segs = data_obs.split(b"\r\n"); nseg = len(segs); sols = []; nodes = [0]
    def rec(i, d, tail, chain, fl, prev):
        nodes[0] += 1
        if nodes[0] > budget or len(sols) >= maxsol: return
        if i == nseg:
            if d.eof and not d.unused_data: sols.append(chain)
            return
        choices = [b""] if i == 0 else [b"\n", b"\r"]
        for t in choices:
            d2 = d.copy() if len(choices) > 1 else d
            try: out = d2.decompress(t + segs[i])
            except zlib.error: continue
            if d2.eof and i != nseg - 1: continue
            ls = (tail + out).split(b"\n"); nfl = fl and len(ls) == 1; ok = True; np_ = prev
            for j, ln in enumerate(ls[:-1]):
                ts = line_ts(ln, fl and j == 0)
                cs = tsec(ts) if ts else None
                if cs is None or (np_ and not (np_ - TOL <= cs <= np_ + UP)): ok = False; break
                np_ = max(np_, cs)
            if ok and not tail_ok(ls[-1], nfl): ok = False
            if ok: rec(i + 1, d2, ls[-1], (chain, i, t, out), nfl, np_)
    rec(0, zlib.decompressobj(-15), b"", None, True, 0.0)
    return sols, nodes[0], nseg - 1

def flatten(chain):
    parts = []
    while chain: chain, i, t, out = chain; parts.append((t, out))
    return parts[::-1]

verified = 0
for k, h in enumerate(heads):
    nl = struct.unpack("<H", obs[h+26:h+28])[0]; name = obs[h+30:h+30+nl].decode()
    c = cds[k]; crc, csize, usize = u32(obs[c+16:c+20]), u32(obs[c+20:c+24]), u32(obs[c+24:c+28])
    nxt = heads[k+1] if k + 1 < len(heads) else cds[0]
    d = obs.rindex(b"PK\x07\x08", h, nxt); data_obs = obs[h+30+nl:d]
    namb = data_obs.count(b"\r\n")
    print(f"\n{name}: central directory says csize={csize} usize={usize} crc={crc:08x}; "
          f"data region {len(data_obs)} observed bytes, ambiguous CRLF positions {namb}")
    small = namb <= 10
    if not small and args.large_budget == 0:
        print("  NOT ATTEMPTED (--large-budget 0)"); continue
    t0 = time.time(); budget = 10**7 if small else args.large_budget
    sols, nodes, nbr = solve(data_obs, 50 if small else 1, budget)
    good = None
    for chain in sols:
        parts = flatten(chain); segs = data_obs.split(b"\r\n")
        comp = segs[0] + b"".join(t + segs[i] for i, (t, _) in enumerate(parts) if i > 0)
        text = b"".join(o for _, o in parts)
        if (len(comp) == csize and len(text) == usize and zlib.crc32(text) & 0xffffffff == crc
                and transform(comp) == data_obs): good = text; break
    why = "" if good else (" (search budget exhausted)" if nodes > budget else " (no candidate matched size and CRC32)")
    print(f"  search nodes {nodes}, candidates examined {len(sols)}, {time.time()-t0:.1f}s -> "
          f"{'VERIFIED against central directory' if good else 'NOT RECOVERED' + why}")
    if good: (OUT / ("VERIFIED_" + name.replace("/", "__"))).write_bytes(good); verified += 1
print(f"\nmembers verified: {verified} of {len(heads)}")
