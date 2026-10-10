"""Tkinter GUI (minimal): pick a folder, pick tables, pick a format, export."""

import os
import queue
import threading

from .core import collect_tables, run_export
from .exporters import xlsx_available

APP_TITLE = 'Экспорт Paradox (.DB)'


def main():
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk

    root = tk.Tk()
    root.title(APP_TITLE)
    root.minsize(660, 480)

    default_fmt = 'xlsx' if xlsx_available() else 'csv'

    frm_top = ttk.Frame(root, padding=8)
    frm_top.pack(fill='x')
    ttk.Label(frm_top, text='Папка с файлами .DB:').grid(row=0, column=0, sticky='w')
    ent_src = ttk.Entry(frm_top, width=60)
    ent_src.grid(row=0, column=1, sticky='ew', padx=4)
    frm_top.columnconfigure(1, weight=1)

    frm_list = ttk.Frame(root, padding=(8, 0))
    frm_list.pack(fill='both', expand=True)
    hdr = ttk.Frame(frm_list)
    hdr.pack(fill='x')
    ttk.Label(hdr, text='Таблицы:').pack(side='left')
    chk_all = tk.IntVar(value=1)
    lbl_cnt = ttk.Label(hdr, text='')
    lbl_cnt.pack(side='right')

    frm_lb = ttk.Frame(frm_list)
    frm_lb.pack(fill='both', expand=True, pady=2)
    sb = ttk.Scrollbar(frm_lb, orient='vertical')
    lb = tk.Listbox(frm_lb, selectmode='extended', exportselection=False,
                    yscrollcommand=sb.set, height=14)
    sb.config(command=lb.yview)
    sb.pack(side='right', fill='y')
    lb.pack(side='left', fill='both', expand=True)

    tables = []  # [(name, path)]

    def select_all(v):
        if v:
            lb.selection_set(0, 'end')
        else:
            lb.selection_clear(0, 'end')

    ttk.Checkbutton(hdr, text='выбрать все', variable=chk_all,
                    command=lambda: select_all(chk_all.get())).pack(side='left', padx=8)

    def refresh_list():
        lb.delete(0, 'end')
        tables[:] = collect_tables(ent_src.get().strip())
        for name, path in tables:
            try:
                size = '%.0f КБ' % (os.path.getsize(path) / 1024.0)
            except OSError:
                size = '?'
            lb.insert('end', '%s  (%s)' % (name, size))
        if tables:
            lb.selection_set(0, 'end')
        lbl_cnt.config(text='найдено таблиц: %d' % len(tables))

    def browse_src():
        d = filedialog.askdirectory(title='Выберите папку с .DB')
        if not d:
            return
        ent_src.delete(0, 'end')
        ent_src.insert(0, d)
        ent_dst.delete(0, 'end')
        ent_dst.insert(0, os.path.join(d, 'export'))
        refresh_list()

    ttk.Button(frm_top, text='Обзор...', command=browse_src).grid(row=0, column=2)

    frm_opts = ttk.Frame(root, padding=8)
    frm_opts.pack(fill='x')
    ttk.Label(frm_opts, text='Формат:').grid(row=0, column=0, sticky='w')
    fmt_var = tk.StringVar(value=default_fmt)
    col = 1
    for val, label in (('csv', 'CSV (UTF-8, разделитель «;»)'),
                       ('xlsx', 'XLSX (одна книга)'),
                       ('xml', 'XML')):
        rb = ttk.Radiobutton(frm_opts, text=label, value=val, variable=fmt_var)
        if val == 'xlsx' and not xlsx_available():
            rb.state(['disabled'])
        rb.grid(row=0, column=col, padx=6, sticky='w')
        col += 1

    frm_opts2 = ttk.Frame(root, padding=(8, 0, 8, 0))
    frm_opts2.pack(fill='x')
    ttk.Label(frm_opts2, text='Куда сохранить:').grid(row=0, column=0, sticky='w')
    ent_dst = ttk.Entry(frm_opts2, width=60)
    ent_dst.grid(row=0, column=1, sticky='ew', padx=4)
    frm_opts2.columnconfigure(1, weight=1)

    def browse_dst():
        d = filedialog.askdirectory(title='Каталог назначения')
        if d:
            ent_dst.delete(0, 'end')
            ent_dst.insert(0, d)

    ttk.Button(frm_opts2, text='Обзор...', command=browse_dst).grid(row=0, column=2)

    frm_run = ttk.Frame(root, padding=8)
    frm_run.pack(fill='x')
    uniq_var = tk.IntVar(value=0)
    ttk.Checkbutton(frm_run,
                    text='Только уникальные (убрать дубли по первому полю, оставить последнюю запись)',
                    variable=uniq_var).pack(side='left')
    btn_go = ttk.Button(frm_run, text='Экспорт')
    btn_go.pack(side='right')

    pb = ttk.Progressbar(root, maximum=100)
    pb.pack(fill='x', padx=8)

    frm_log = ttk.Frame(root, padding=8)
    frm_log.pack(fill='both', expand=True)
    log = tk.Text(frm_log, height=9, wrap='word', state='disabled')
    sb2 = ttk.Scrollbar(frm_log, command=log.yview)
    log.config(yscrollcommand=sb2.set)
    sb2.pack(side='right', fill='y')
    log.pack(side='left', fill='both', expand=True)

    def write_log(s):
        log.config(state='normal')
        log.insert('end', s + '\n')
        log.see('end')
        log.config(state='disabled')

    q = queue.Queue()

    def poll():
        try:
            while True:
                kind, payload = q.get_nowait()
                if kind == 'log':
                    write_log(payload)
                elif kind == 'progress':
                    pb['value'] = payload
                elif kind == 'done':
                    btn_go.state(['!disabled'])
                    ok, rows_n, errors = payload
                    pb['value'] = 100
                    msg = 'Готово.\nТаблиц: %d, записей: %s' % (ok, format(rows_n, ','))
                    if errors:
                        msg += '\nОшибок: %d (подробности в журнале)' % len(errors)
                    write_log('=' * 40)
                    write_log(msg)
                    messagebox.showinfo(APP_TITLE, msg)
        except queue.Empty:
            pass
        root.after(100, poll)

    def worker(selected, out_dir, fmt, unique):
        def log_fn(s):
            q.put(('log', s))

        def progress(pct):
            q.put(('progress', pct))

        result = run_export(selected, out_dir, fmt, unique, log_fn, progress)
        q.put(('done', result))

    def start():
        src = ent_src.get().strip()
        if not src or not os.path.isdir(src):
            messagebox.showwarning(APP_TITLE, 'Укажите папку с файлами .DB')
            return
        sel_idx = lb.curselection()
        if not sel_idx:
            messagebox.showwarning(APP_TITLE, 'Выберите таблицы для экспорта')
            return
        selected = [tables[i] for i in sel_idx]
        out_dir = ent_dst.get().strip() or os.path.join(src, 'export')
        fmt = fmt_var.get()
        unique = bool(uniq_var.get())
        btn_go.state(['disabled'])
        pb['value'] = 0
        write_log('Экспорт: %d таблиц, формат %s -> %s' % (len(selected), fmt.upper(), out_dir))
        threading.Thread(target=worker, args=(selected, out_dir, fmt, unique),
                         daemon=True).start()

    btn_go.config(command=start)

    # quick start: pick up ./data next to the current working directory
    default_src = os.path.join(os.getcwd(), 'data')
    if os.path.isdir(default_src):
        ent_src.insert(0, default_src)
        ent_dst.insert(0, os.path.join(default_src, 'export'))
        refresh_list()
    else:
        lbl_cnt.config(text='нажмите «Обзор...»')

    root.after(100, poll)
    root.mainloop()


if __name__ == '__main__':
    main()
