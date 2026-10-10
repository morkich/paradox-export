# paradox-export

Export **Borland Paradox** (`.DB`) tables to **CSV**, **XLSX** or **XML** — with a
minimal GUI or from the command line. Works without ODBC, BDE or the Borland
drivers: the file format is read directly in pure Python.

Written for databases produced by Delphi/BDE applications (dental clinics,
medical records, small business software from the 2000s–2010s) whose original
tooling no longer runs on modern Windows.

[Русская версия README](README.ru.md)

## Features

- Reads Paradox `.DB` tables directly: header, code pages (CP866 / CP1251 /
  CP1252), dates, numbers, currency, logicals, times, memos.
- No ODBC/BDE installation needed; works on 64-bit Windows.
- Walks the full data-block chain instead of trusting the record counter in
  the header (many real files under-report their row count).
- Three output formats:
  - **CSV** — UTF-8 with BOM, `;` separator (opens correctly in Excel);
  - **XLSX** — one workbook, one sheet per table, typed columns
    (real dates/times/numbers), frozen header and auto-filter;
  - **XML** — one file per table.
- Duplicate-key detection: rows are flagged with a `_dup_key` column, or you
  can keep only the last copy of each key (`--unique`).
- Minimal GUI: pick a folder, pick tables, pick a format, export.

## Requirements

- Python **3.9+** (tkinter, included with the standard Python installer)
- [`openpyxl`](https://pypi.org/project/openpyxl/) — only for XLSX output

## Installation

```bash
git clone https://github.com/CHANGE_ME/paradox-export.git
cd paradox-export
pip install .            # or: pip install -e ".[xlsx]"  (with openpyxl)
```

Without installing, run straight from the source tree:

```bash
python -m paradox_export                 # GUI  (PYTHONPATH=src, see below)
PYTHONPATH=src python -m paradox_export data out --fmt csv
```

On Windows you can double-click `start_export.bat` — it sets `PYTHONPATH`
itself and starts the GUI.

## Usage

### GUI

```bash
paradox-export-gui
```

1. Choose the folder that contains the `.DB` files (tables are listed
   automatically);
2. select the tables (or leave "select all");
3. choose the format and the output folder;
4. press **Экспорт** (Export).

### CLI

```bash
# every table in data/ -> CSV
paradox-export data out --fmt csv

# one table, unique keys only, XLSX
paradox-export data out --fmt xlsx --unique PATIENT

# several tables to XML
paradox-export data out --fmt xml PATIENT RECEPT
```

| Option | Meaning |
|--------|---------|
| `--fmt {csv,xlsx,xml}` | output format (default `csv`) |
| `--unique` | keep only the last physical copy of each key |
| `TABLE ...` | table names without extension; default: all tables |

Exit code is `0` on success, `1` if any table failed.

## Output notes

- **Encoding** — everything is written as UTF-8, so Cyrillic and other
  non-Latin text survives regardless of the source code page.
- **Dates** in XLSX become real Excel dates, times become real Excel times,
  numeric columns become numbers; strings with leading zeros (zip codes) are
  deliberately kept as text.
- **Duplicate keys** — some real-world files contain two physical copies of
  the same record (usually after an abnormal shutdown or a manual copy of the
  database). By default such rows are kept and marked in the `_dup_key`
  column; with `--unique` only the newest copy of each key is exported.
- **Declared vs actual rows** — the record counter in the Paradox header can
  be wrong; this tool exports every non-empty row it finds in the block chain.

## Data & privacy

This repository contains **only source code**. Database files, table dumps
and anything derived from them are **not** included — you point the tool at
your own `.DB` files. The `.gitignore` refuses `*.DB` and export folders as a
safety net.

## Project layout

```
paradox-export/
├── src/paradox_export/
│   ├── reader.py      # Paradox .DB format reader (pure Python)
│   ├── exporters.py   # CSV / XML / XLSX writers, dedup, type detection
│   ├── core.py        # table discovery + export loop (shared)
│   ├── cli.py         # command line interface
│   └── gui.py         # tkinter GUI
├── pyproject.toml
├── README.md          # this file
└── README.ru.md       # Russian version
```

## License

MIT — see [LICENSE](LICENSE).
