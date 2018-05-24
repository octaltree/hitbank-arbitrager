#!/usr/bin/env python3

import sys

def main() -> int:
    xj = float(sys.argv[1])
    bj = float(sys.argv[2])
    (x, j, b) = [float(l) for l in sys.stdin.read().split(' ')]
    print(x * xj + j + b * bj)
    return 0


if __name__ == "__main__":
    exit(main())

# vim:fenc=utf-8 ff=unix ft=python ts=4 sw=4 sts=4 fdm=indent fdl=0 fdn=1:
# vim: si et cinw=if,elif,else,for,while,try,except,finally,def,class:
