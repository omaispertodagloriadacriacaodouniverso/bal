#!/usr/bin/env python3
"""Run every examples/*.bal through balc (C) and bal (Python) and compare outputs.

Usage: python3 tests/run_examples.py
Exit 0 = all match, 1 = mismatch/failure.
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXAMPLES = ROOT / "examples"
BALC = ROOT / "balc" / "balc"
BAL = Path.home() / ".local" / "bin" / "bal"

# Examples that need CLI args or intentionally fail on both — skip comparison,
# but still check both fail the same way.
SKIP = {"analyze.bal", "freq.bal"}  # require a file argument
# bench.bal overflows int32 in both compilers — outputs differ from arbitrary
# precision, but both are deterministic C ints; compare anyway.


def run(cmd, cwd):
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=60)
    return r.returncode, r.stdout, r.stderr


def main():
    files = sorted(EXAMPLES.glob("*.bal"))
    if not files:
        print("no examples found")
        return 1

    failed = 0
    for f in files:
        rc_c, out_c, err_c = run([str(BALC), str(f)], ROOT)
        rc_p, out_p, err_p = run([str(BAL), str(f)], ROOT)

        if f.name in SKIP:
            ok = out_c == out_p and (rc_c != 0) == (rc_p != 0)
            status = "SKIP(match)" if ok else "SKIP-DIFF"
            if not ok:
                failed += 1
            print(f"{f.name}: {status}")
            continue

        if rc_c != 0 or rc_p != 0:
            failed += 1
            print(f"{f.name}: FAIL rc balc={rc_c} bal={rc_p}")
            print(f"  balc stderr: {err_c.strip()[:200]}")
            continue

        if out_c == out_p:
            print(f"{f.name}: OK ({len(out_c.splitlines())} lines match)")
        else:
            failed += 1
            print(f"{f.name}: MISMATCH")
            cl, pl = out_c.splitlines(), out_p.splitlines()
            for i in range(max(len(cl), len(pl))):
                c = cl[i] if i < len(cl) else "<none>"
                p = pl[i] if i < len(pl) else "<none>"
                if c != p:
                    print(f"  line {i+1}: balc={c!r} bal={p!r}")

    print(f"\n{len(files) - failed}/{len(files)} match")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
