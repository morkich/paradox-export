"""Table discovery and the export loop shared by the CLI and the GUI."""

import glob
import os

from .exporters import (export_csv, export_xlsx, export_xml, prepare,
                        xlsx_available)


def collect_tables(src_dir):
    """Return ``[(table_name, path)]`` for every .DB file in a directory."""
    paths = sorted(set(glob.glob(os.path.join(src_dir, '*.DB')) +
                       glob.glob(os.path.join(src_dir, '*.db'))))
    return [(os.path.splitext(os.path.basename(p))[0], p) for p in paths]


def run_export(items, out_dir, fmt, unique, log, progress=None):
    """Export ``items`` (list of ``(name, path)``) into ``out_dir``.

    ``log(str)`` receives progress messages, ``progress(percent)`` optional
    integer updates. Returns ``(ok_tables, total_rows, errors)``.
    """
    os.makedirs(out_dir, exist_ok=True)
    total = len(items) or 1
    ok, rows_total, errors = 0, 0, []
    xlsx_buf = []
    if fmt == 'xlsx' and not xlsx_available():
        log('Для XLSX нужен модуль openpyxl:  pip install openpyxl')
        return 0, 0, ['openpyxl not installed']
    for i, (name, path) in enumerate(items):
        try:
            header, rows = prepare(path, unique=unique)
            if fmt == 'csv':
                out = os.path.join(out_dir, name + '.csv')
                n = export_csv(header, rows, out)
                log('[%d/%d] %s -> %s (%s строк)' % (i + 1, len(items), name,
                                                     os.path.basename(out), format(n, ',')))
            elif fmt == 'xml':
                out = os.path.join(out_dir, name + '.xml')
                n = export_xml(name, header, rows, out)
                log('[%d/%d] %s -> %s (%s строк)' % (i + 1, len(items), name,
                                                     os.path.basename(out), format(n, ',')))
            else:
                xlsx_buf.append((name, header, rows))
                n = len(rows)
                log('[%d/%d] %s (%s строк)' % (i + 1, len(items), name, format(n, ',')))
            rows_total += n
            ok += 1
        except Exception as e:
            errors.append('%s: %s' % (name, e))
            log('[%d/%d] ОШИБКА %s: %s' % (i + 1, len(items), name, e))
        if progress:
            progress(int(100.0 * (i + 1) / total))
    if fmt == 'xlsx' and xlsx_buf:
        out = os.path.join(out_dir, 'export.xlsx')
        try:
            n = export_xlsx(xlsx_buf, out)
            log('XLSX: %d листов, %s строк -> %s' % (len(xlsx_buf), format(n, ','), out))
        except Exception as e:
            errors.append('xlsx: %s' % e)
            log('ОШИБКА XLSX: %s' % e)
    return ok, rows_total, errors
