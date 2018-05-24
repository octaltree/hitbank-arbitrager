#!/usr/bin/env python3

import sys
import re


def main() -> int:
    pat = re.compile('[ ]*計 ([0-9.]+)XRP ([0-9.]+)JPY ([0-9.]+)BTC$')
    matched = [
            tuple([float(s) for s in pat.match(l).group(1, 2, 3)])
            for l in sys.stdin.read().split('\n') if pat.match(l)]
    first = matched[0]
    last = matched[-1]
    subbed = (last[0] - first[0], last[1] - first[1], last[2] - first[2])
    print('{} {} {}'.format(*subbed))
    return 0


if __name__ == "__main__":
    exit(main())

# vim:fenc=utf-8 ff=unix ft=python ts=4 sw=4 sts=4 fdm=indent fdl=0 fdn=1:
# vim: si et cinw=if,elif,else,for,while,try,except,finally,def,class:
