#!/usr/bin/env bash
# Build a minimal rootfs tarball: python3 (system 3.12) + the tools the Docker-backed tests launch,
# each with its shared libraries.  Output: $1 (tar path).  Local-lab stand-in for python:3.12-alpine
# (the registry is unreachable from this sandbox); it is NOT the CI image.
set -euo pipefail
OUT="$1"
ROOT="$(mktemp -d "${TMPDIR:-/tmp}/rootfs.XXXXXX")"
trap 'rm -rf "$ROOT"' EXIT

add() {  # copy a file (resolving symlinked dirs) and its libraries, preserving the path
  local f="$1"
  [ -e "$f" ] || { echo "skip missing $f" >&2; return 0; }
  mkdir -p "$ROOT$(dirname "$f")"
  cp -a --remove-destination "$f" "$ROOT$f"
  if [ -L "$f" ]; then
    local t; t="$(readlink -f "$f")"; add "$t"
  fi
  if file -L "$f" | grep -q 'ELF'; then
    ldd "$f" 2>/dev/null | awk '/=>/ {print $3} /^\s*\/lib/ {print $1}' | while read -r lib; do
      [ -e "$lib" ] && { mkdir -p "$ROOT$(dirname "$lib")"; cp -aL --remove-destination "$lib" "$ROOT$lib"
        case "$lib" in /usr/local/*) mkdir -p "$ROOT/lib/x86_64-linux-gnu"; cp -aL --remove-destination "$lib" "$ROOT/lib/x86_64-linux-gnu/";; esac; }
    done
  fi
}

mkdir -p "$ROOT"/{proc,sys,dev,tmp,etc,usr/bin,usr/lib,bin,lib,lib64,root,var/tmp}
chmod 1777 "$ROOT/tmp" "$ROOT/var/tmp"
for b in sh dash true echo sleep printenv yes head grep cat ls rm date mv ln mkdir mkfifo hostname readlink; do  # EXACTLY the preflight list (+dash for sh)
  p="$(type -P "$b" || true)"; [ -n "$p" ] && [ -e "$p" ] && add "$(readlink -f "$p")" && { [ "$(basename "$(readlink -f "$p")")" = "$b" ] || ln -sf "$(basename "$(readlink -f "$p")")" "$ROOT/usr/bin/$b"; }
done
# POSIX layout: /bin is a symlink to usr/bin on this distro; mirror it.
rm -rf "$ROOT/bin" && ln -s usr/bin "$ROOT/bin"
[ -e "$ROOT/usr/bin/sh" ] || ln -sf dash "$ROOT/usr/bin/sh"
add /usr/bin/python3.12
ln -sf python3.12 "$ROOT/usr/bin/python3"
cp -a /usr/lib/python3.12 "$ROOT/usr/lib/python3.12"
# shared libraries of the stdlib extension modules (ssl, sqlite3, ...)
find /usr/lib/python3.12/lib-dynload -name '*.so' | while read -r so; do
  ldd "$so" 2>/dev/null | awk '/=>/ {print $3}' | while read -r lib; do
    [ -e "$lib" ] && { mkdir -p "$ROOT$(dirname "$lib")"; cp -aL --remove-destination "$lib" "$ROOT$lib"
      case "$lib" in /usr/local/*) mkdir -p "$ROOT/lib/x86_64-linux-gnu"; cp -aL --remove-destination "$lib" "$ROOT/lib/x86_64-linux-gnu/";; esac; }
  done
done
cp -aL /lib64/ld-linux-x86-64.so.2 "$ROOT/lib64/" 2>/dev/null || true
printf 'root:x:0:0:root:/root:/bin/sh\nnobody:x:65534:65534:nobody:/nonexistent:/usr/sbin/nologin\n' > "$ROOT/etc/passwd"
printf 'root:x:0:\nnogroup:x:65534:\n' > "$ROOT/etc/group"
printf 'hosts: files dns\n' > "$ROOT/etc/nsswitch.conf"
echo 127.0.0.1 localhost > "$ROOT/etc/hosts"
tar -C "$ROOT" -cf "$OUT" .
du -sh "$ROOT" | cut -f1
ls -l "$OUT"
