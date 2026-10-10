"""Command line interface: ``paradox-export <src> <dst> [options] [tables]``."""

import argparse
import sys

from .core import collect_tables, run_export

PROG = 'paradox-export'


def build_parser():
    p = argparse.ArgumentParser(
        prog=PROG,
        description='Export Borland Paradox (.DB) tables to CSV / XLSX / XML.')
    p.add_argument('src', help='directory containing .DB files')
    p.add_argument('dst', help='output directory')
    p.add_argument('--fmt', choices=['csv', 'xlsx', 'xml'], default='csv',
                   help='output format (default: csv)')
    p.add_argument('--unique', action='store_true',
                   help='keep only unique records (last copy of each key)')
    p.add_argument('tables', nargs='*',
                   help='table names without .DB extension; default: all tables')
    return p


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    p = build_parser()
    # parse_known_args: argparse cannot interleave a nargs='*' positional with
    # trailing option values (e.g. "src dst --fmt csv TABLE"), so table names
    # that end up unparsed are collected manually.
    a, unknown = p.parse_known_args(argv)
    bad = [u for u in unknown if u.startswith('-')]
    if bad:
        p.error('unrecognized options: %s' % ' '.join(bad))
    tables = list(a.tables) + unknown

    items = collect_tables(a.src)
    if tables:
        want = {t.lower() for t in tables}
        items = [it for it in items if it[0].lower() in want]
    if not items:
        print('No tables found in %s' % a.src, file=sys.stderr)
        return 1

    def log(s):
        print(s)

    ok, rows_n, errors = run_export(items, a.dst, a.fmt, a.unique, log)
    print('Done. Tables: %d, rows: %s, errors: %d' % (ok, format(rows_n, ','), len(errors)))
    return 1 if errors else 0


if __name__ == '__main__':
    sys.exit(main())
