"""
interface/token_cli.py -- `ocbrain token`: locate, show or rotate the local API token.

One implementation, two entry points, because the word `ocbrain` means different
things depending on how OCBrain was installed:

* pip/source install: ``ocbrain`` is the click CLI (interface/cli.py), which
  delegates here;
* packaged binary (install/build.py, deb/service file): ``ocbrain`` IS the server
  (main.py), which hands ``ocbrain token ...`` to ``main()`` here before it imports
  anything heavy or starts anything.

Only stdlib and interface.auth are imported, so it is fast and has no side effects.
The token is printed only with --show, alone on stdout (safe inside ``$(...)``);
every notice goes to stderr in that mode.
"""
from __future__ import annotations

import argparse
import os
import sys
from typing import Optional, Sequence, TextIO

from interface import auth


def run(show: bool = False, rotate: bool = False,
        out: Optional[TextIO] = None, err: Optional[TextIO] = None) -> int:
    out = out or sys.stdout
    err = err or sys.stderr

    if rotate:
        try:
            new, path = auth.rotate_token()
        except auth.AuthConfigError as exc:
            print(f"Error: {exc}", file=err)
            return 1
        print(f"New API token written to {path}. The previous token no longer works.",
              file=err if show else out)
        if show:
            print(new, file=out)
        return 0

    from_env = bool(os.environ.get(auth.ENV_TOKEN, "").strip())
    where = f"the {auth.ENV_TOKEN} environment variable" if from_env else str(auth.token_path())
    value = auth.read_token()
    if value is None:
        print(f"No token yet: OCBrain creates it when it first starts ({where}).", file=err)
        return 1
    if show:
        print(f"Token source: {where}", file=err)
        print(value, file=out)
    else:
        print(f"Token source: {where}", file=out)
        print("Show it with: ocbrain token --show   Replace it with: ocbrain token --rotate", file=out)
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="ocbrain token", description="Locate, show or rotate the local API token.")
    parser.add_argument("--show", action="store_true",
                        help="print the token itself (nothing else on stdout); it is a secret")
    parser.add_argument("--rotate", action="store_true",
                        help="replace the token; the old one stops working at once")
    args = parser.parse_args(list(argv) if argv is not None else None)
    return run(show=args.show, rotate=args.rotate)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
