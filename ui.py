"""Desktop layout and export dialog; extraction remains in core.py."""
from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pathlib import Path

from core import export_entries, export_grouped, group_alphabetically

BG = "#101318"
PANEL = "#191e26"
SURFACE = "#202731"
LINE = "#303946"
TEXT = "#e9edf4"
MUTED = "#95a2b4"
ACCENT = "#efb366"


def configure_style(app):
    app.configure(background=BG)
    style = ttk.Style(app)
    style.theme_use("clam")
    style.configure(".", background=BG, foreground=TEXT, font=("Segoe UI", 10))
    for name, color in (("TFrame", BG), ("Panel.TFrame", PANEL), ("Surface.TFrame", SURFACE)):
        style.configure(name, background=color)
    style.configure("TLabel", background=BG, foreground=TEXT, font=("Segoe UI", 10))
    style.configure("Muted.TLabel", foreground=MUTED)
    style.configure("Panel.TLabel", background=PANEL, foreground=TEXT)
    style.configure("PanelMuted.TLabel", background=PANEL, foreground=MUTED, font=("Segoe UI", 9))
    style.configure("Section.TLabel", foreground=MUTED, font=("Segoe UI Semibold", 9))
    style.configure("Title.TLabel", font=("Segoe UI Semibold", 25), foreground=TEXT)
    style.configure("TButton", background=SURFACE, foreground=TEXT, padding=(14, 10), borderwidth=0, font=("Segoe UI", 10))
    style.layout("TButton", [("Button.padding", {"children": [("Button.label", {"sticky": "nswe"})], "sticky": "nswe"})])
    style.map("TButton", background=[("disabled", PANEL), ("active", "#303a48")], foreground=[("disabled", "#687587")])
    style.configure("Primary.TButton", background=ACCENT, foreground="#261b0c", font=("Segoe UI Semibold", 10))
    style.map("Primary.TButton", background=[("disabled", "#60503a"), ("active", "#ffc57c")], foreground=[("disabled", MUTED)])
    style.configure("Nav.TButton", background=BG, foreground=MUTED, anchor="w", padding=(13, 11))
    style.configure("Selected.Nav.TButton", background="#342b20", foreground=ACCENT, anchor="w", padding=(13, 11), font=("Segoe UI Semibold", 10))
    style.map("Selected.Nav.TButton", background=[("active", "#413425")])
    style.configure("Small.TButton", background=BG, foreground=MUTED, padding=(5, 7), font=("Segoe UI", 9))
    style.configure("Letter.TButton", background=PANEL, foreground=MUTED, padding=(3, 6), font=("Segoe UI", 9))
    style.configure("Selected.Letter.TButton", background=ACCENT, foreground="#261b0c", padding=(3, 6), font=("Segoe UI Semibold", 9))
    style.map("Selected.Letter.TButton", background=[("active", "#ffc57c")])
    style.configure("TCombobox", fieldbackground=SURFACE, background=SURFACE, foreground=TEXT, arrowcolor=MUTED, bordercolor=LINE, lightcolor=LINE, darkcolor=LINE, padding=8, borderwidth=0)
    style.map("TCombobox", fieldbackground=[("readonly", SURFACE)], foreground=[("readonly", TEXT)], selectbackground=[("readonly", SURFACE)], selectforeground=[("readonly", TEXT)])
    app.option_add("*TCombobox*Listbox.background", SURFACE)
    app.option_add("*TCombobox*Listbox.foreground", TEXT)
    style.configure("Treeview", background=PANEL, fieldbackground=PANEL, foreground=TEXT, rowheight=36, borderwidth=0, font=("Consolas", 10))
    style.layout("Treeview", [("Treeview.treearea", {"sticky": "nswe"})])
    style.configure("Treeview.Heading", background=SURFACE, foreground=MUTED, padding=(10, 11), borderwidth=0, relief="flat", font=("Segoe UI Semibold", 9))
    style.layout("Treeview.Heading", [("Treeheading.padding", {"children": [("Treeheading.text", {"sticky": "we"})], "sticky": "nswe"})])
    style.map("Treeview", background=[("selected", "#3b3328")], foreground=[("selected", "#ffdaaa")])
    style.map("Treeview.Heading", background=[("active", "#2b3440")])
    style.configure("TScrollbar", background="#394452", troughcolor=PANEL, borderwidth=0, arrowcolor=MUTED, darkcolor=PANEL, lightcolor=PANEL, arrowsize=11)
    for direction, sticky in (("Vertical", "ns"), ("Horizontal", "we")):
        style.layout(f"{direction}.TScrollbar", [(f"{direction}.Scrollbar.trough", {
            "children": [(f"{direction}.Scrollbar.thumb", {"expand": "1", "sticky": "nswe"})], "sticky": sticky})])
    style.configure("TProgressbar", background=ACCENT, troughcolor=PANEL, borderwidth=0)
    style.configure("TPanedwindow", background=LINE, sashwidth=2)


def input_field(parent, variable, font=("Segoe UI", 10)):
    return tk.Entry(parent, textvariable=variable, background=SURFACE, foreground=TEXT,
                    insertbackground=ACCENT, selectbackground="#4e3d28", selectforeground=TEXT,
                    relief="flat", borderwidth=0, highlightthickness=1,
                    highlightbackground=LINE, highlightcolor=ACCENT, font=font)


def build_layout(app):
    root = ttk.Frame(app, padding=(24, 20, 24, 14))
    root.pack(fill="both", expand=True)
    header = ttk.Frame(root)
    header.pack(fill="x", pady=(0, 18))
    brand = tk.Label(header, text=">_", bg=ACCENT, fg="#261b0c", font=("Consolas", 21, "bold"), padx=10, pady=3)
    brand.pack(side="left", padx=(0, 14))
    names = ttk.Frame(header)
    names.pack(side="left")
    ttk.Label(names, text="Command browser", style="Title.TLabel").pack(anchor="w")
    ttk.Label(names, text="COUNTER-STRIKE 2  /  LOCAL CATALOG", style="Section.TLabel").pack(anchor="w", pady=(1, 0))
    app.export_button = ttk.Button(header, text="Export  ▾", style="Primary.TButton", command=app._export_menu)
    app.export_button.pack(side="right", padx=(14, 0))
    ttk.Label(header, textvariable=app.build_value, foreground=ACCENT, font=("Consolas", 10)).pack(side="right")

    source = ttk.Frame(root, style="Panel.TFrame", padding=(14, 11))
    source.pack(fill="x")
    ttk.Label(source, text="GAME FOLDER", style="PanelMuted.TLabel").pack(side="left", padx=(0, 12))
    app.path_entry = input_field(source, app.path_value)
    app.path_entry.pack(side="left", fill="x", expand=True, ipady=9)
    app.path_entry.bind("<Return>", lambda _: app.start_scan())
    app.browse_button = ttk.Button(source, text="Browse…", command=app._browse)
    app.browse_button.pack(side="left", padx=(8, 8))
    app.scan_button = ttk.Button(source, text="Refresh catalog", command=app.start_scan)
    app.scan_button.pack(side="left")
    ttk.Label(root, textvariable=app.summary_value, style="Muted.TLabel").pack(anchor="w", pady=(10, 20))

    content = ttk.Frame(root)
    content.pack(fill="both", expand=True)
    sidebar = ttk.Frame(content, width=174)
    sidebar.pack(side="left", fill="y", padx=(0, 20))
    sidebar.pack_propagate(False)
    ttk.Label(sidebar, text="LIBRARY", style="Section.TLabel").pack(anchor="w", pady=(0, 9))
    app.nav_buttons = {}
    for name in ("All entries", "Variables", "Commands"):
        button = ttk.Button(sidebar, text=name, style="Nav.TButton", command=lambda value=name: app.kind_value.set(value))
        button.pack(fill="x", pady=2)
        app.nav_buttons[name] = button
    ttk.Separator(sidebar).pack(fill="x", pady=14)
    ttk.Label(sidebar, text="FILTERS", style="Section.TLabel").pack(anchor="w", pady=(0, 10))
    for label, variable, choices in (
        ("Flags & availability", app.flag_value, ("Any flags", "Cheat-protected", "Hidden", "Development only", "Client module", "Server module", "Has description")),
        ("Compared with scan", app.change_value, ("All changes", "Added", "Changed", "Removed", "Unchanged")),
    ):
        ttk.Label(sidebar, text=label, style="Muted.TLabel").pack(anchor="w", pady=(0, 5))
        ttk.Combobox(sidebar, textvariable=variable, values=choices, state="readonly", width=16).pack(fill="x", pady=(0, 14))
    ttk.Button(sidebar, text="Reset filters", style="Nav.TButton", command=app._reset_filters).pack(fill="x")
    ttk.Separator(sidebar).pack(fill="x", pady=14)
    app.tools_button = ttk.Button(sidebar, text="Tools  ▾", style="Nav.TButton", command=app._tools_menu)
    app.tools_button.pack(fill="x")
    ttk.Label(sidebar, text="Your game files.\nNo game launch needed.", style="Muted.TLabel", justify="left").pack(side="bottom", anchor="w", pady=(15, 12))

    main = ttk.Frame(content)
    main.pack(side="left", fill="both", expand=True)
    search_row = ttk.Frame(main)
    search_row.pack(fill="x", pady=(0, 9))
    app.search_entry = input_field(search_row, app.query_value, ("Segoe UI", 12))
    app.search_entry.pack(side="left", fill="x", expand=True, ipady=11)
    app.search_entry.bind("<Escape>", lambda _: app.query_value.set(""))
    ttk.Button(search_row, text="Clear", style="Small.TButton", command=lambda: app.query_value.set("")).pack(side="left", padx=(8, 0))
    app.bind("<Control-f>", lambda _: app.search_entry.focus_set())
    ttk.Label(main, text="Search names, descriptions, or flags    ·    Ctrl+F", style="Muted.TLabel").pack(anchor="w", pady=(0, 12))
    result_header = ttk.Frame(main)
    result_header.pack(fill="x", pady=(0, 9))
    ttk.Label(result_header, textvariable=app.count_value, font=("Segoe UI Semibold", 11)).pack(side="left")
    ttk.Label(result_header, textvariable=app.comparison_value, style="Muted.TLabel").pack(side="right")

    panes = ttk.Panedwindow(main, orient="horizontal")
    panes.pack(fill="both", expand=True)
    catalog = ttk.Frame(panes, style="Panel.TFrame", padding=1)
    alphabet = ttk.Frame(catalog, style="Panel.TFrame", padding=(6, 6))
    alphabet.pack(fill="x")
    app.letter_buttons = {}
    for letter in ("All", *"ABCDEFGHIJKLMNOPQRSTUVWXYZ", "#"):
        button = ttk.Button(alphabet, text=letter, width=3 if letter == "All" else 2, style="Letter.TButton",
                            command=lambda value=letter: app.letter_value.set(value))
        button.pack(side="left", fill="x", expand=True, padx=1)
        app.letter_buttons[letter] = button
    table_frame = ttk.Frame(catalog, style="Panel.TFrame")
    table_frame.pack(fill="both", expand=True)
    app.table = ttk.Treeview(table_frame, columns=("name", "kind", "default", "change"), show="headings", selectmode="browse")
    for column, title, width in (("name", "NAME", 350), ("kind", "KIND", 85), ("default", "DEFAULT", 110), ("change", "CHANGE", 95)):
        app.table.heading(column, text=title, anchor="w", command=lambda key=column: app._sort(key))
        app.table.column(column, width=width, minwidth=70, stretch=column == "name", anchor="w")
    app.table.configure(displaycolumns=("name", "kind", "default"))
    yscroll = ttk.Scrollbar(table_frame, orient="vertical", command=app.table.yview)
    xscroll = ttk.Scrollbar(catalog, orient="horizontal", command=app.table.xview)
    app.table.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
    yscroll.pack(side="right", fill="y")
    app.table.pack(side="left", fill="both", expand=True)
    xscroll.pack(fill="x")
    app.table.tag_configure("even", background=PANEL)
    app.table.tag_configure("odd", background="#1d232c")
    for tag, color in (("Removed", "#ef9f97"), ("Added", "#a7d7a0"), ("Changed", ACCENT)):
        app.table.tag_configure(tag, foreground=color)
    app.table.bind("<<TreeviewSelect>>", app._show_detail)
    app.table.bind("<Control-c>", lambda _: app._copy_name())
    panes.add(catalog, weight=4)

    inspector = ttk.Frame(panes, style="Panel.TFrame", padding=20, width=320)
    ttk.Label(inspector, text="COMMAND DETAILS", style="PanelMuted.TLabel").pack(anchor="w", pady=(0, 12))
    app.detail_title = ttk.Label(inspector, text="Select an entry", style="Panel.TLabel", font=("Consolas", 13, "bold"), wraplength=280)
    app.detail_title.pack(anchor="w", fill="x", pady=(0, 10))
    app.detail_kind = ttk.Label(inspector, text="", style="PanelMuted.TLabel", foreground=ACCENT)
    app.detail_kind.pack(anchor="w", pady=(0, 16))
    text_frame = ttk.Frame(inspector, style="Panel.TFrame")
    text_frame.pack(fill="both", expand=True)
    app.detail = tk.Text(text_frame, width=30, height=8, wrap="word", bg=PANEL, fg=TEXT, relief="flat", borderwidth=0,
                        font=("Segoe UI", 11), spacing1=3, spacing3=5, padx=0, pady=0, state="disabled", cursor="arrow")
    detail_scroll = ttk.Scrollbar(text_frame, orient="vertical", command=app.detail.yview)
    app.detail.configure(yscrollcommand=detail_scroll.set)
    app.detail.pack(side="left", fill="both", expand=True)
    detail_scroll.pack(side="right", fill="y")
    app.detail.tag_configure("label", foreground=MUTED, font=("Segoe UI Semibold", 9), spacing1=12)
    app.detail.tag_configure("value", foreground=TEXT, font=("Consolas", 10))
    app.detail.tag_configure("note", foreground=ACCENT)
    detail_actions = ttk.Frame(inspector, style="Panel.TFrame")
    detail_actions.pack(side="bottom", fill="x", before=text_frame, pady=(16, 0))
    ttk.Button(detail_actions, text="Copy default command", command=app._copy_default).pack(fill="x", pady=(0, 7))
    ttk.Button(detail_actions, text="Copy name", command=app._copy_name).pack(fill="x")
    panes.add(inspector, weight=2)
    app.inspector = inspector
    def resize_detail(event):
        app.detail_title.configure(wraplength=max(160, event.width - 40))
    inspector.bind("<Configure>", resize_detail)
    # Keep the inspector readable instead of squeezing both panes equally.
    app.after(80, lambda: panes.sashpos(0, max(500, panes.winfo_width() - 335)))

    footer = ttk.Frame(root)
    footer.pack(side="bottom", fill="x", pady=(13, 0), before=content)
    app.progress = ttk.Progressbar(footer, mode="indeterminate", length=65)
    app.status_label = ttk.Label(footer, textvariable=app.status_value, style="Muted.TLabel", wraplength=950)
    app.status_label.pack(side="left", fill="x", expand=True)
    ttk.Label(footer, text="v1.1", style="Muted.TLabel").pack(side="right", padx=(10, 0))


class ExportDialog(tk.Toplevel):
    def __init__(self, app, scope="results", grouped=False):
        super().__init__(app)
        self.app = app
        self.title("Export catalog")
        self.configure(bg=BG)
        self.resizable(False, False)
        self.transient(app)
        self.scope = tk.StringVar(value=scope)
        self.organization = tk.StringVar(value="Alphabetical groups (A–Z)" if grouped else "Single file")
        self.file_format = tk.StringVar(value="Text (.txt)")
        frame = ttk.Frame(self, padding=26)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="Export catalog", font=("Segoe UI Semibold", 22)).pack(anchor="w")
        ttk.Label(frame, text="Choose what to include and how to organize it.", style="Muted.TLabel").pack(anchor="w", pady=(3, 22))
        ttk.Label(frame, text="INCLUDE", style="Section.TLabel").pack(anchor="w", pady=(0, 8))
        options = (("results", f"Current results  ·  {len(app.rows):,} entries"),
                   ("all", f"All current entries  ·  {len(app.entries):,} entries"),
                   ("changes", f"Changes only  ·  {len(app._export_items('changes')):,} entries"))
        for value, label in options:
            radio = tk.Radiobutton(frame, text=label, variable=self.scope, value=value, bg=BG, fg=TEXT, selectcolor=SURFACE,
                                   activebackground=BG, activeforeground=ACCENT, font=("Segoe UI", 11), anchor="w", padx=0, pady=5)
            if value == "changes" and not app._export_items("changes"):
                radio.configure(state="disabled", disabledforeground="#657182")
            radio.pack(fill="x")
        ttk.Label(frame, text="ORGANIZE", style="Section.TLabel").pack(anchor="w", pady=(20, 8))
        ttk.Combobox(frame, textvariable=self.organization, values=("Single file", "Alphabetical groups (A–Z)"), state="readonly", width=44).pack(fill="x")
        ttk.Label(frame, text="FORMAT", style="Section.TLabel").pack(anchor="w", pady=(20, 8))
        ttk.Combobox(frame, textvariable=self.file_format, values=("Text (.txt)", "JSON (.json)", "CSV (.csv)", "Markdown (.md)"), state="readonly", width=44).pack(fill="x")
        self.preview = tk.StringVar()
        ttk.Label(frame, textvariable=self.preview, style="Muted.TLabel", wraplength=430).pack(anchor="w", pady=(18, 20))
        buttons = ttk.Frame(frame)
        buttons.pack(fill="x")
        ttk.Button(buttons, text="Cancel", command=self.destroy).pack(side="left")
        self.save_button = ttk.Button(buttons, text="Choose destination…", style="Primary.TButton", command=self.save)
        self.save_button.pack(side="right")
        for variable in (self.scope, self.organization, self.file_format):
            variable.trace_add("write", lambda *_: self.update_preview())
        self.bind("<Escape>", lambda _: self.destroy())
        self.update_preview()
        self.update_idletasks()
        self.geometry(f"+{app.winfo_rootx() + max(20, (app.winfo_width()-self.winfo_reqwidth())//2)}+{app.winfo_rooty()+60}")
        self.grab_set()

    def update_preview(self):
        items = self.app._export_items(self.scope.get())
        if self.organization.get().startswith("Alphabetical"):
            groups = len(group_alphabetically(items))
            self.preview.set(f"{len(items):,} entries → {groups} alphabetical files in one ZIP, with an index. All current entries ignores your search and filters.")
        else:
            self.preview.set(f"{len(items):,} entries → one file, sorted by name. Descriptions, defaults, flags, and change status are included.")
        self.save_button.configure(state="normal" if items else "disabled")

    def save(self):
        items = self.app._export_items(self.scope.get())
        suffix = {"Text (.txt)": "txt", "JSON (.json)": "json", "CSV (.csv)": "csv", "Markdown (.md)": "md"}[self.file_format.get()]
        grouped = self.organization.get().startswith("Alphabetical")
        extension = "zip" if grouped else suffix
        build = self.app.metadata.get("version", {}).get("ClientVersion", "catalog")
        path = filedialog.asksaveasfilename(parent=self, title="Save export", initialfile=f"cs2-{self.scope.get()}{'-A-Z' if grouped else ''}-{build}.{extension}",
            defaultextension="."+extension, filetypes=(("ZIP archive" if grouped else self.file_format.get(), "*."+extension),))
        if not path:
            return
        metadata = {key: value for key, value in self.app.metadata.items() if key != "entries"}
        metadata.update({"export_scope": self.scope.get(), "export_includes_comparison_rows": any(self.app.change_states.get(entry.key) == "Removed" for entry in items)})
        try:
            if grouped:
                export_grouped(Path(path), items, suffix, metadata, self.app.change_states)
            else:
                export_entries(Path(path), items, metadata, self.app.change_states)
        except (OSError, ValueError) as exc:
            messagebox.showerror("Export failed", str(exc), parent=self)
            return
        self.app.status_value.set(f"Exported {len(items):,} entries{' in alphabetical groups' if grouped else ''} to {Path(path).name}.")
        self.destroy()
