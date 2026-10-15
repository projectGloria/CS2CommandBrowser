"""CS2 Command Browser — a local Windows desktop interface."""
from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime
import json
import os
from pathlib import Path
import queue
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from core import Entry, ScanError, alphabetical_group, app_data, atomic_json, check_config, compare, load_snapshot, run_scan
from ui import ExportDialog, build_layout, configure_style


def resource_root() -> Path:
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))


class Browser(tk.Tk):
    def __init__(self, storage: Path | None = None):
        super().__init__()
        self.storage = storage or app_data()
        self.title("CS2 Command Browser")
        self.geometry(f"{min(1440, max(1160, self.winfo_screenwidth()-60))}x{min(900, max(720, self.winfo_screenheight()-100))}")
        self.minsize(1160, 720)
        self.configure(background="#111820")
        self.entries: list[Entry] = []
        self.previous: list[Entry] = []
        self.metadata = {}
        self.snapshot_path: Path | None = None
        self.rows: dict[str, Entry] = {}
        self.change_states = {}
        self.messages = queue.Queue()
        self.busy = False
        self.pending_filter = None
        self.path_value = tk.StringVar()
        self.query_value = tk.StringVar()
        self.kind_value = tk.StringVar(value="All entries")
        self.flag_value = tk.StringVar(value="Any flags")
        self.change_value = tk.StringVar(value="All changes")
        self.letter_value = tk.StringVar(value="All")
        self.build_value = tk.StringVar(value="NO SCAN YET")
        self.comparison_value = tk.StringVar(value="")
        self.status_value = tk.StringVar(value="Choose your CS2 folder, then select Refresh from game files.")
        self.summary_value = tk.StringVar(value="No scan loaded")
        self.count_value = tk.StringVar(value="0 entries")
        self._style()
        self._layout()
        self._restore()
        for value in (self.query_value, self.kind_value, self.flag_value, self.change_value, self.letter_value):
            value.trace_add("write", self._schedule_filter)
        self.protocol("WM_DELETE_WINDOW", self._close)
        self.after(100, self._poll)

    def _style(self):
        configure_style(self)

    def _layout(self):
        build_layout(self)

    def _reset_filters(self):
        self.query_value.set("")
        self.kind_value.set("All entries")
        self.flag_value.set("Any flags")
        self.change_value.set("All changes")
        self.letter_value.set("All")

    def _restore(self):
        try:
            settings = json.loads((self.storage / "settings.json").read_text(encoding="utf-8"))
            self.path_value.set(settings.get("game_path", ""))
        except (OSError, ValueError):
            pass
        try:
            pointer = json.loads((self.storage / "latest.json").read_text(encoding="utf-8"))
            self._load(Path(pointer["snapshot"]))
        except (OSError, ValueError, KeyError, TypeError, ScanError):
            pass

    def _browse(self):
        folder = filedialog.askdirectory(title="Choose your CS2 installation folder", parent=self)
        if folder:
            self.path_value.set(folder)

    def start_scan(self):
        if self.busy:
            return
        from core import resolve_game
        try:
            game = resolve_game(self.path_value.get())
            atomic_json(self.storage / "settings.json", {"game_path": self.path_value.get()})
        except (ScanError, OSError) as exc:
            messagebox.showerror("Check the game folder", str(exc), parent=self)
            return
        self.busy = True
        for widget in (self.scan_button, self.browse_button, self.path_entry):
            widget.configure(state="disabled")
        self.progress.pack(side="left", padx=(0, 12), before=self.status_label)
        self.progress.start(12)
        self.status_value.set("Starting the offline scan…")
        def worker():
            try:
                result = run_scan(str(game), resource_root() / "tools/DumpSource2-CS2.exe", self.storage,
                                  progress=lambda message: self.messages.put(("progress", message)))
                self.messages.put(("done", result))
            except Exception as exc:
                self.messages.put(("error", str(exc)))
        threading.Thread(target=worker, daemon=True).start()

    def _poll(self):
        try:
            while True:
                kind, value = self.messages.get_nowait()
                if kind == "progress":
                    self.status_value.set(value)
                    continue
                self.busy = False
                self.progress.stop()
                self.progress.pack_forget()
                for widget in (self.scan_button, self.browse_button, self.path_entry):
                    widget.configure(state="normal")
                if kind == "done":
                    try:
                        self._load(value)
                    except Exception as exc:
                        self.status_value.set("Scan saved, but results could not be displayed.")
                        messagebox.showerror("Could not display results", str(exc), parent=self)
                else:
                    self.status_value.set("Scan did not finish. Previously saved results are still available.")
                    messagebox.showerror("Scan could not finish", value, parent=self)
        except queue.Empty:
            pass
        self.after(100, self._poll)

    def _load(self, path: Path):
        self.metadata, self.entries = load_snapshot(path)
        self.snapshot_path = path
        self.previous = []
        for candidate in sorted((self.storage / "snapshots").glob("*/snapshot.json"), reverse=True):
            if candidate.resolve() == path.resolve() or candidate.parent.name >= path.parent.name:
                continue
            try:
                old_meta, old_entries = load_snapshot(candidate)
                if old_meta.get("game_path", "").casefold() == self.metadata.get("game_path", "").casefold():
                    self.previous = old_entries
                    break
            except (OSError, ValueError, KeyError, TypeError, ScanError):
                continue
        version = self.metadata.get("version", {})
        stamp = datetime.fromisoformat(self.metadata["scanned_at"]).astimezone().strftime("%d %b %Y, %H:%M")
        self.build_value.set(f"BUILD {version.get('ClientVersion', '?')}")
        self.summary_value.set(f"Patch {version.get('PatchVersion', '?')}   ·   Last scanned {stamp}   ·   Showing built-in defaults")
        self._filter()
        self.status_value.set("Scan complete. Game-supplied descriptions are shown as written; some entries have no description.")

    def _schedule_filter(self, *_):
        if self.pending_filter is not None:
            self.after_cancel(self.pending_filter)
        self.pending_filter = self.after(160, self._filter)

    def _filter(self):
        self.pending_filter = None
        self.change_states = compare(self.previous, self.entries) if self.previous else {}
        self.table.configure(displaycolumns=("name", "kind", "default", "change") if any(value != "Unchanged" for value in self.change_states.values()) else ("name", "kind", "default"))
        for name, button in self.nav_buttons.items():
            button.configure(style="Selected.Nav.TButton" if name == self.kind_value.get() else "Nav.TButton")
        for letter, button in self.letter_buttons.items():
            button.configure(style="Selected.Letter.TButton" if letter == self.letter_value.get() else "Letter.TButton")
        combined = {entry.key: entry for entry in self.previous}
        combined.update({entry.key: entry for entry in self.entries})
        query = self.query_value.get().casefold().split()
        kind, flag, change = self.kind_value.get(), self.flag_value.get(), self.change_value.get()
        selected = self.table.selection()
        self.table.delete(*self.table.get_children())
        self.rows = {}
        for key, entry in sorted(combined.items(), key=lambda pair: pair[1].name.casefold()):
            state = self.change_states.get(key, "")
            if self.letter_value.get() != "All" and alphabetical_group(entry.name) != self.letter_value.get():
                continue
            if kind != "All entries" and entry.kind != kind[:-1]:
                continue
            if flag == "Cheat-protected" and "cheat" not in entry.flags:
                continue
            if flag == "Hidden" and "hidden" not in entry.flags:
                continue
            if flag == "Development only" and "developmentonly" not in entry.flags:
                continue
            if flag == "Client module" and "client" not in entry.modules:
                continue
            if flag == "Server module" and "server" not in entry.modules:
                continue
            if flag == "Has description" and not entry.description:
                continue
            if change != "All changes" and state != change:
                continue
            haystack = " ".join((entry.name, entry.description, *entry.flags, *entry.modules)).casefold()
            if not all(term in haystack for term in query):
                continue
            self.rows[key] = entry
            self.table.insert("", "end", iid=key, values=(entry.name, entry.kind, self._default_label(entry), state), tags=("even" if len(self.rows) % 2 else "odd", state))
        counts = {name: sum(state == name for state in self.change_states.values()) for name in ("Added", "Changed", "Removed")}
        self.count_value.set(f"{len(self.rows):,} results  /  {len(self.entries):,} in catalog")
        self.comparison_value.set((f"+{counts['Added']} added  ·  {counts['Changed']} changed  ·  {counts['Removed']} removed" if sum(counts.values()) else "No changes since previous scan") if self.previous else "")
        if selected and selected[0] in self.rows:
            self.table.selection_set(selected[0])
        elif self.rows:
            self.table.selection_set(next(iter(self.rows)))
        else:
            self.detail_title.configure(text="No matching entries")
            self.detail_kind.configure(text="")
            self._detail_text("Try a different search or filter.")

    @staticmethod
    def _default_label(entry):
        return "—" if entry.default is None else '""' if entry.default == "" else entry.default

    def _sort(self, column):
        reverse = getattr(self, "sort_state", (None, True)) == (column, False)
        self.sort_state = (column, reverse)
        children = list(self.table.get_children())
        children.sort(key=lambda key: self.table.set(key, column).casefold(), reverse=reverse)
        for index, key in enumerate(children):
            self.table.move(key, "", index)

    def _selected(self):
        selected = self.table.selection()
        return self.rows.get(selected[0]) if selected else None

    def _detail_text(self, text):
        self.detail.configure(state="normal")
        self.detail.delete("1.0", "end")
        self.detail.insert("1.0", text)
        self.detail.configure(state="disabled")

    def _show_detail(self, _=None):
        entry = self._selected()
        if entry is None:
            return
        self.detail_title.configure(text=entry.name)
        self.detail_kind.configure(text=f"{entry.kind.upper()}" + (f"  /  {entry.value_type}" if entry.value_type else ""))
        description = entry.description or "No description provided by the game."
        fields = [description, ""]
        if entry.kind == "Variable":
            fields.extend(("BUILT-IN DEFAULT", self._default_label(entry)))
            if entry.minimum is not None or entry.maximum is not None:
                fields.extend(("RANGE", f"{entry.minimum if entry.minimum is not None else 'Not supplied'}  to  {entry.maximum if entry.maximum is not None else 'Not supplied'}"))
        fields.extend(("FLAGS", "  ·  ".join(entry.flags) or "None supplied"))
        fields.extend(("MODULES", ", ".join(entry.modules) or "None supplied"))
        if entry.enum:
            fields.append(f"Enum: {entry.enum}")
        old = next((item for item in self.previous if item.key == entry.key), None)
        if self.change_states.get(entry.key) == "Changed" and old is not None:
            fields.extend(("", "Changed since the comparison scan:"))
            for name, value in asdict(entry).items():
                if asdict(old)[name] != value:
                    fields.append(f"  {name}: {asdict(old)[name]} → {value}")
        if self.change_states.get(entry.key) == "Removed":
            fields.extend(("", "Removed from the current scan. This row comes from the comparison snapshot."))
        self._detail_text("\n".join(fields))
        self.detail.configure(state="normal")
        for label in ("BUILT-IN DEFAULT", "RANGE", "FLAGS", "MODULES"):
            position = self.detail.search(label, "1.0", stopindex="end", exact=True)
            if position:
                self.detail.tag_add("label", position, position+" lineend")
                self.detail.tag_add("value", position+" +1line linestart", position+" +1line lineend")
        self.detail.configure(state="disabled")

    def _copy_name(self):
        entry = self._selected()
        if entry:
            self.clipboard_clear()
            self.clipboard_append(entry.name)
            self.status_value.set(f"Copied {entry.name}.")

    def _copy_default(self):
        entry = self._selected()
        if not entry:
            return
        if entry.default is None:
            self.status_value.set("This entry does not supply a default value.")
            return
        value = json.dumps(entry.default, ensure_ascii=False) if entry.value_type.lower() == "string" else entry.default
        self.clipboard_clear()
        self.clipboard_append(f"{entry.name} {value}")
        self.status_value.set("Copied the built-in default command. Nothing was applied to your game.")

    def _export_items(self, scope="results"):
        if scope == "all":
            items = self.entries
        elif scope == "changes":
            combined = {entry.key: entry for entry in self.previous}
            combined.update({entry.key: entry for entry in self.entries})
            items = [entry for key, entry in combined.items() if self.change_states.get(key) in ("Added", "Changed", "Removed")]
        else:
            items = list(self.rows.values())
        return sorted(items, key=lambda entry: (entry.name.casefold(), entry.kind))

    def _export(self, scope="results", grouped=False):
        if not self.entries:
            messagebox.showinfo("No catalog loaded", "Refresh from game files first.", parent=self)
            return
        ExportDialog(self, scope, grouped)

    def _export_menu(self):
        menu = tk.Menu(self, tearoff=False, background="#202731", foreground="#e9edf4",
                       activebackground="#3b3328", activeforeground="#ffdaaa", borderwidth=0,
                       font=("Segoe UI", 11))
        menu.add_command(label=f"Export results…  ({len(self.rows):,})", command=lambda: self._export("results"))
        menu.add_command(label=f"Export all…  ({len(self.entries):,})", command=lambda: self._export("all"))
        menu.add_command(label="Export all by alphabetical groups…", command=lambda: self._export("all", True))
        menu.add_separator()
        menu.add_command(label="Export changes…", command=lambda: self._export("changes"),
                         state="normal" if self._export_items("changes") else "disabled")
        menu.update_idletasks()
        menu.tk_popup(self.export_button.winfo_rootx()+self.export_button.winfo_width()-menu.winfo_reqwidth(), self.export_button.winfo_rooty()+self.export_button.winfo_height()+5)

    def _tools_menu(self):
        menu = tk.Menu(self, tearoff=False, background="#202731", foreground="#e9edf4",
                       activebackground="#3b3328", activeforeground="#ffdaaa", borderwidth=0, font=("Segoe UI", 11))
        for label, callback in (("Compare scan…", self._compare_file), ("Check config…", self._check_config),
                                ("Open results folder", self._open_results), ("About this app", self._about)):
            menu.add_command(label=label, command=callback)
        menu.tk_popup(self.tools_button.winfo_rootx()+self.tools_button.winfo_width()+5, self.tools_button.winfo_rooty())

    def _compare_file(self):
        if not self.entries:
            messagebox.showinfo("No current scan", "Refresh from game files first.", parent=self)
            return
        path = filedialog.askopenfilename(parent=self, title="Choose an earlier snapshot.json", initialdir=self.storage / "snapshots", filetypes=(("Snapshot", "*.json"),))
        if path:
            try:
                meta, self.previous = load_snapshot(Path(path))
                self._filter()
                self.status_value.set(f"Comparing current results with build {meta.get('version', {}).get('ClientVersion', '?')} from {meta.get('scanned_at', '?')}.")
            except (OSError, ValueError, KeyError, TypeError, ScanError) as exc:
                messagebox.showerror("Could not compare", str(exc), parent=self)

    def _check_config(self):
        if not self.entries:
            messagebox.showinfo("No scan loaded", "Refresh from game files first.", parent=self)
            return
        path = filedialog.askopenfilename(parent=self, title="Choose a config to review", filetypes=(("CS2 configs", "*.cfg"), ("All files", "*.*")))
        if not path:
            return
        try:
            findings = check_config(Path(path).read_text(encoding="utf-8-sig"), self.entries)
        except (OSError, UnicodeError) as exc:
            messagebox.showerror("Could not read config", str(exc), parent=self)
            return
        window = tk.Toplevel(self)
        window.title("Config review — " + Path(path).name)
        window.geometry("920x550")
        window.configure(background="#111820")
        frame = ttk.Frame(window, padding=18)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="Direct settings review", font=("Segoe UI Semibold", 18)).pack(anchor="w")
        ttk.Label(frame, text="Read-only check. Bind/alias contents and values are not validated. Unlisted runtime commands are not automatically errors.", wraplength=870, style="Muted.TLabel").pack(anchor="w", pady=(6, 12))
        box = tk.Text(frame, wrap="word", background="#161f29", foreground="#e2eaf4", padx=12, pady=12, relief="flat")
        box.pack(fill="both", expand=True)
        box.insert("1.0", "\n\n".join(f"Line {item['line']} · {item['command']} · {item['status']}\n{item['detail']}" for item in findings) or "No flagged direct settings found. This does not certify the complete config.")
        box.configure(state="disabled")

    def _open_results(self):
        self.storage.mkdir(parents=True, exist_ok=True)
        os.startfile(self.storage)

    def _about(self):
        messagebox.showinfo("About CS2 Command Browser", "CS2 Command Browser 1.1\n\nExtracts data locally using DumpSource2 by ValveResourceFormat contributors (GPL-3.0). No game process, console, or online command list is used.\n\nGame DLLs are loaded in a separate offline extractor process from private copies. Missing descriptions stay empty. Runtime-registered actions may not be included. Future CS2 builds may require a new extractor.\n\nSource code, license, and build instructions accompany this app.", parent=self)

    def _close(self):
        if self.busy:
            messagebox.showinfo("Scan in progress", "Please wait for the scan to finish before closing.", parent=self)
            return
        self.destroy()


def main():
    parser = argparse.ArgumentParser(description="Browse console commands extracted offline from your CS2 files.")
    parser.add_argument("--scan", metavar="GAME_FOLDER", help="Scan a manually supplied game folder without opening the interface")
    parser.add_argument("--data-dir", type=Path, help="Override the local results folder")
    parser.add_argument("--smoke-test", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.scan:
        try:
            result = run_scan(args.scan, resource_root() / "tools/DumpSource2-CS2.exe", args.data_dir,
                              progress=lambda message: print(message, flush=True))
            print(result)
            return 0
        except ScanError as exc:
            storage = args.data_dir or app_data()
            storage.mkdir(parents=True, exist_ok=True)
            (storage / "command-line-error.txt").write_text(str(exc), encoding="utf-8")
            if sys.stderr is not None:
                print(str(exc), file=sys.stderr)
            return 1
    if os.name == "nt":
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except (AttributeError, OSError):
            pass
    app = Browser(args.data_dir)
    if args.smoke_test:
        smoke_error = []
        def test():
            try:
                import tempfile
                import zipfile
                from unittest.mock import patch
                app.query_value.set("cl_draw_only_deathnotices")
                app._filter()
                app.update_idletasks()
                entry = app._selected()
                assert entry and entry.name == "cl_draw_only_deathnotices"
                app._show_detail()
                assert "crosshair" in app.detail.get("1.0", "end").lower()
                assert len(app._export_items("results")) == 1
                assert len(app._export_items("all")) == len(app.entries)
                app.letter_value.set("Z")
                app._filter()
                assert not app.rows
                app._reset_filters()
                app._filter()
                app.update_idletasks()
                assert len(app.rows) >= len(app.entries)
                app.query_value.set("cl_draw_only_deathnotices")
                app._filter()
                dialog = ExportDialog(app, "all", True)
                dialog.file_format.set("JSON (.json)")
                assert f"{len(app.entries):,} entries" in dialog.preview.get()
                with tempfile.TemporaryDirectory() as folder:
                    destination = Path(folder) / "all-A-Z.zip"
                    with patch("ui.filedialog.asksaveasfilename", return_value=str(destination)):
                        dialog.save()
                    with zipfile.ZipFile(destination) as archive:
                        manifest = json.loads(archive.read("manifest.json"))
                        assert manifest["entry_count"] == len(app.entries)
                        assert sum(group["count"] for group in manifest["groups"]) == len(app.entries)
                app.geometry("1160x720")
                app.update_idletasks()
                assert app.status_label.winfo_height() > 5
                assert app.inspector.winfo_width() >= 260
                atomic_json(app.storage / "ui-smoke-test.json", {"passed": True, "entry": entry.name,
                    "all_export_count": len(app.entries), "grouped_export_verified": True, "minimum_window_checked": True,
                    "window_size": app.geometry()})
            except Exception as exc:
                smoke_error.append(str(exc))
                atomic_json(app.storage / "ui-smoke-test.json", {"passed": False, "error": repr(exc)})
            finally:
                app.destroy()
        app.after(500, test)
    app.mainloop()
    if args.smoke_test and smoke_error:
        return 1


if __name__ == "__main__":
    raise SystemExit(main() or 0)
