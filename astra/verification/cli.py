"""CLI for verification (optional, not required for tests).

Usage:
  python -m astra.verification.cli verify --steps 20
  python -m astra.verification.cli report --output verification_report.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def cmd_verify(args):
    from .integration import full_integration_report

    report = full_integration_report(steps=args.steps, dt=args.dt)
    print(report.summary)
    for c in report.checks:
        status = "PASS" if c.passed else "FAIL"
        print(f"  [{status}] {c.name} ({c.duration_ms}ms)" + (f" error={c.error}" if c.error else ""))
    if args.output:
        report.save(args.output)
        print(f"Report saved to {args.output}")
    sys.exit(0 if report.passed else 1)


def cmd_hash(args):
    from .state_hash import hash_snapshot
    import json as js

    data = js.loads(Path(args.file).read_text())
    h = hash_snapshot(data)
    print(h)


def main():
    parser = argparse.ArgumentParser(prog="astra-verification")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_verify = sub.add_parser("verify", help="run full verification")
    p_verify.add_argument("--steps", type=int, default=20)
    p_verify.add_argument("--dt", type=float, default=1.0)
    p_verify.add_argument("--output", type=str, default="")
    p_verify.set_defaults(func=cmd_verify)

    p_hash = sub.add_parser("hash", help="hash a snapshot file")
    p_hash.add_argument("file")
    p_hash.set_defaults(func=cmd_hash)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
