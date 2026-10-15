"""Offline CS2 extraction, snapshots and exports. Python standard library only."""
from __future__ import annotations

import csv
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from typing import Callable


class ScanError(Exception):
    pass


@dataclass(frozen=True)
class Entry:
    name: str
    kind: str
    description: str = ""
    default: str | None = None
    value_type: str = ""
    minimum: str | None = None
    maximum: str | None = None
    flags: tuple[str, ...] = ()
    modules: tuple[str, ...] = ()
    enum: str = ""

    @property
    def key(self) -> str:
        return f"{self.kind}:{self.name}"


def app_data() -> Path:
    return Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "CS2CommandBrowser"


def atomic_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temp = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as output:
            json.dump(data, output, indent=2, ensure_ascii=False)
        os.replace(temp, path)
    finally:
        Path(temp).unlink(missing_ok=True)


def resolve_game(path: str | Path) -> Path:
    """Only normalize the user's chosen folder. Never search drives or Steam."""
    supplied = Path(str(path).strip().strip('"')).expanduser()
    if not str(path).strip():
        raise ScanError("Choose your CS2 installation folder first.")
    candidates = (supplied, supplied / "game", supplied.parent.parent if supplied.name.lower() == "win64" else supplied)
    for candidate in candidates:
        candidate = candidate.resolve()
        if (candidate / "bin/win64/tier0.dll").is_file() and (candidate / "csgo/bin/win64/client.dll").is_file():
            return candidate
    raise ScanError("That folder does not contain the CS2 game files. Choose Counter-Strike Global Offensive, its game folder, or game/bin/win64.")


def read_version(game: Path) -> dict[str, str]:
    info = game / "csgo/steam.inf"
    if not info.is_file():
        raise ScanError("csgo/steam.inf is missing. Check the selected installation folder.")
    values = {}
    for line in info.read_text(encoding="utf-8-sig").splitlines():
        key, separator, value = line.partition("=")
        if separator:
            values[key.strip()] = value.strip()
    if not values.get("ClientVersion"):
        raise ScanError("The game version could not be read from csgo/steam.inf.")
    return values


def entries_from_schema(data: dict) -> list[Entry]:
    results = []
    for section, kind in (("convars", "Variable"), ("commands", "Command")):
        items = data.get(section)
        if not isinstance(items, list) or not items:
            raise ScanError(f"The extractor did not produce a complete {section} list. An extractor update may be needed.")
        for item in items:
            if not isinstance(item, dict) or not isinstance(item.get("name"), str) or not item["name"]:
                raise ScanError(f"Invalid {section} entry in the extractor output.")
            def optional(name):
                value = item.get(name)
                return None if value is None else str(value)
            results.append(Entry(
                name=item["name"], kind=kind, description=item.get("help", "").strip(),
                default=optional("default"), value_type=item.get("type", ""),
                minimum=optional("min"), maximum=optional("max"),
                flags=tuple(sorted(set(item.get("flags", [])))),
                modules=tuple(sorted(set(item.get("modules", [])))), enum=item.get("enum", ""),
            ))
    if len({entry.key for entry in results}) != len(results):
        raise ScanError("The extractor output contains duplicate entries.")
    return sorted(results, key=lambda entry: (entry.name.casefold(), entry.kind))


def load_snapshot(path: Path) -> tuple[dict, list[Entry]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("format_version") != 1:
        raise ScanError("This snapshot uses an unsupported format.")
    entries = []
    for item in data["entries"]:
        item = dict(item)
        item["flags"] = tuple(item.get("flags", []))
        item["modules"] = tuple(item.get("modules", []))
        entries.append(Entry(**item))
    return data, entries


def compare(before: list[Entry], after: list[Entry]) -> dict[str, str]:
    old = {entry.key: entry for entry in before}
    new = {entry.key: entry for entry in after}
    return {key: "Added" if key not in old else "Removed" if key not in new else "Changed" if old[key] != new[key] else "Unchanged"
            for key in sorted(old.keys() | new.keys())}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def stage_modules(game: Path, stage: Path, progress: Callable[[str], None]) -> dict:
    """Load only copies, keeping any library-created logs away from the install."""
    progress("Preparing local copies of the game libraries…")
    files = []
    for folder in (game / "bin/win64", game / "csgo/bin/win64"):
        files.extend(sorted(folder.rglob("*.dll")))
    files.append(game / "csgo/steam.inf")
    manifest = {}
    for source in files:
        relative = source.relative_to(game)
        destination = stage / relative
        initial = source.stat()
        signature = (initial.st_size, initial.st_mtime_ns)
        manifest[relative.as_posix()] = {"size": signature[0], "mtime_ns": signature[1]}
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.is_file() or (destination.stat().st_size, destination.stat().st_mtime_ns) != signature:
            shutil.copy2(source, destination)
        if (source.stat().st_size, source.stat().st_mtime_ns) != signature:
            raise ScanError("CS2 files changed while copying. Wait for the game update to finish, then refresh again.")
    # An update may remove a library. Remove only stale DLL copies in our private stage.
    expected = set(manifest)
    for folder in (stage / "bin/win64", stage / "csgo/bin/win64"):
        for cached in folder.rglob("*.dll"):
            if cached.relative_to(stage).as_posix() not in expected:
                cached.unlink()
    return manifest


@contextmanager
def extractor_environment():
    """Do not pass the packaged Python runtime's DLL search path to the game."""
    environment = os.environ.copy()
    bundled = getattr(sys, "_MEIPASS", None)
    if not bundled or os.name != "nt":
        yield environment
        return
    import ctypes
    root = Path(bundled).resolve()
    environment["PATH"] = os.pathsep.join(part for part in environment.get("PATH", "").split(os.pathsep)
        if part and not Path(part).resolve().is_relative_to(root))
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.SetDllDirectoryW.argtypes = [ctypes.c_wchar_p]
    kernel.SetDllDirectoryW.restype = ctypes.c_int
    if not kernel.SetDllDirectoryW(None):
        raise OSError(ctypes.get_last_error(), "Could not prepare the extractor's library search path")
    try:
        yield environment
    finally:
        kernel.SetDllDirectoryW(str(root))


def run_scan(game_input: str, extractor: Path, storage: Path | None = None,
             progress: Callable[[str], None] = lambda _: None, timeout: float = 180) -> Path:
    game = resolve_game(game_input)
    if not extractor.is_file():
        raise ScanError("The offline extractor is missing. Keep the tools folder beside the app.")
    storage = (storage or app_data()).resolve()
    # Never put copied modules or output in the selected game installation.
    if storage == game or game in storage.parents:
        raise ScanError("The results folder must be outside the game installation.")
    storage.mkdir(parents=True, exist_ok=True)
    lock = storage / "scan.lock"
    lock_handle = os.open(lock, os.O_CREAT | os.O_RDWR)
    try:
        if os.name == "nt":
            import msvcrt
            if os.fstat(lock_handle).st_size == 0:
                os.write(lock_handle, b"0")
            os.lseek(lock_handle, 0, os.SEEK_SET)
            msvcrt.locking(lock_handle, msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(lock_handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as exc:
        os.close(lock_handle)
        raise ScanError("Another scan is already running. Wait for it to finish, then try again.") from exc
    try:
        version = read_version(game)
        # Separate caches by selected installation, including two same-version installs.
        install_key = hashlib.sha256(str(game).casefold().encode()).hexdigest()[:16]
        stage = storage / "cache" / install_key / "game"
        manifest = stage_modules(game, stage, progress)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        scan_dir = storage / "snapshots" / f"{stamp}-{version['ClientVersion']}"
        scan_dir.mkdir(parents=True)
        log_path = scan_dir / "extractor.log"
        with tempfile.TemporaryDirectory(prefix="extract-", dir=storage) as work:
            work_path = Path(work)
            progress("Reading commands and descriptions from the copied libraries…")
            try:
                with log_path.open("w", encoding="utf-8") as log, extractor_environment() as environment:
                    result = subprocess.run(
                        [str(extractor.resolve()), str(work_path.resolve())],
                        cwd=stage / "bin/win64", stdout=log, stderr=subprocess.STDOUT,
                        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                        timeout=timeout, check=False, env=environment,
                    )
            except subprocess.TimeoutExpired as exc:
                raise ScanError(f"Extraction timed out. Your previous results are unchanged. Details: {log_path}") from exc
            if result.returncode != 0 or not (work_path / "schemas.json").is_file():
                raise ScanError(f"The extractor could not complete this game build (code {result.returncode}). Your previous results are unchanged. Details: {log_path}")
            entries = entries_from_schema(json.loads((work_path / "schemas.json").read_text(encoding="utf-8")))
            if read_version(game) != version:
                raise ScanError("The installed game updated during extraction. Refresh again after the update finishes.")
            for relative, fingerprint in manifest.items():
                stat = (game / relative).stat()
                if (stat.st_size, stat.st_mtime_ns) != (fingerprint["size"], fingerprint["mtime_ns"]):
                    raise ScanError("A game library changed during extraction. Refresh again after the update finishes.")
            progress("Saving the command list…")
            key_hashes = {relative: sha256(stage / relative) for relative in (
                "bin/win64/tier0.dll", "bin/win64/engine2.dll", "bin/win64/schemasystem.dll",
                "csgo/bin/win64/client.dll", "csgo/bin/win64/server.dll") if (stage / relative).is_file()}
            snapshot = {"format_version": 1, "source": "installed_game", "scanned_at": datetime.now(timezone.utc).isoformat(),
                        "game_path": str(game), "version": version, "module_hashes": key_hashes,
                        "extractor_sha256": sha256(extractor), "entries": [asdict(entry) for entry in entries]}
            for filename in ("convars.txt", "commands.txt"):
                shutil.copy2(work_path / filename, scan_dir / filename)
            atomic_json(scan_dir / "snapshot.json", snapshot)
            atomic_json(storage / "latest.json", {"snapshot": str(scan_dir / "snapshot.json")})
        return scan_dir / "snapshot.json"
    except ScanError:
        raise
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise ScanError(f"The scan could not finish: {exc}") from exc
    finally:
        # Closing the handle releases the OS lock, even after a crashed scan.
        os.close(lock_handle)


def export_entries(path: Path, entries: list[Entry], metadata: dict | None = None, changes: dict[str, str] | None = None) -> None:
    changes = changes or {}
    if path.suffix.lower() == ".json":
        atomic_json(path, {"metadata": metadata or {}, "entries": [{**asdict(entry), "change": changes.get(entry.key, "")} for entry in entries]})
    elif path.suffix.lower() == ".csv":
        with path.open("w", encoding="utf-8-sig", newline="") as target:
            writer = csv.writer(target)
            writer.writerow(("Name", "Kind", "Description", "Default", "Type", "Minimum", "Maximum", "Flags", "Modules", "Enum", "Change"))
            for entry in entries:
                # Keep arbitrary game strings literal when opened in spreadsheet apps.
                def cell(value):
                    value = "" if value is None else str(value)
                    return "'" + value if value.startswith(("=", "+", "-", "@")) else value
                writer.writerow([cell(value) for value in (entry.name, entry.kind, entry.description, entry.default,
                    entry.value_type, entry.minimum, entry.maximum, " ".join(entry.flags), " ".join(entry.modules), entry.enum, changes.get(entry.key, ""))])
    elif path.suffix.lower() == ".md":
        with path.open("w", encoding="utf-8") as target:
            target.write("# CS2 commands and variables\n\nBuilt-in defaults, not active settings.\n\n")
            for entry in entries:
                name = entry.name.replace("`", "\\`")
                target.write(f"## `{name}`\n\n{entry.description or 'No description provided by the game.'}\n\n")
                for label, value in (("Kind", entry.kind), ("Default", '""' if entry.default == "" else entry.default), ("Type", entry.value_type),
                                     ("Minimum", entry.minimum), ("Maximum", entry.maximum),
                                     ("Flags", " ".join(entry.flags)), ("Modules", ", ".join(entry.modules)),
                                     ("Change", changes.get(entry.key))):
                    if value is not None and value != "":
                        target.write(f"- **{label}:** {value}\n")
                target.write("\n")
    else:
        with path.open("w", encoding="utf-8") as target:
            target.write("CS2 commands and variables — built-in defaults, not active settings\n\n")
            for entry in entries:
                default_text = '""' if entry.default == "" else entry.default
                value = "" if default_text is None else f" = {default_text}"
                change = f"; {changes[entry.key]}" if entry.key in changes else ""
                target.write(f"{entry.name}{value} [{entry.kind}; {' '.join(entry.flags)}{change}]\n  {entry.description or 'No description provided by the game.'}\n")
                if entry.value_type:
                    target.write(f"  Type: {entry.value_type}\n")
                if entry.minimum is not None or entry.maximum is not None:
                    target.write(f"  Range: {entry.minimum if entry.minimum is not None else 'not supplied'} to {entry.maximum if entry.maximum is not None else 'not supplied'}\n")
                if entry.modules:
                    target.write(f"  Modules: {', '.join(entry.modules)}\n")
                target.write("\n")


def alphabetical_group(name: str) -> str:
    """Button prefixes (+/-) and leading underscores do not create extra groups."""
    name = name.lstrip("+-_")
    initial = name[:1].upper()
    return initial if initial in "ABCDEFGHIJKLMNOPQRSTUVWXYZ" and initial else "#"


def group_alphabetically(entries: list[Entry]) -> dict[str, list[Entry]]:
    groups = {}
    for entry in sorted(entries, key=lambda item: (item.name.casefold(), item.kind)):
        groups.setdefault(alphabetical_group(entry.name), []).append(entry)
    return dict(sorted(groups.items(), key=lambda pair: (pair[0] == "#", pair[0])))


def export_grouped(path: Path, entries: list[Entry], file_format: str = "txt",
                   metadata: dict | None = None, changes: dict[str, str] | None = None) -> None:
    """Write one file per nonempty letter to a single ZIP, published atomically."""
    if file_format not in ("txt", "csv", "json", "md"):
        raise ValueError("Choose TXT, CSV, JSON, or Markdown for grouped exports.")
    groups = group_alphabetically(entries)
    if not groups:
        raise ValueError("There are no entries to export.")
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    os.close(handle)
    try:
        with tempfile.TemporaryDirectory(prefix="cs2-export-", dir=path.parent) as workspace:
            with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                index = ["# CS2 command export — alphabetical groups", "", f"{len(entries):,} entries in {len(groups)} groups.",
                         "", "Built-in defaults, not active settings. Leading +, - and _ are ignored for grouping; other symbols and digits go in Other.", ""]
                version = (metadata or {}).get("version", {})
                if version.get("ClientVersion"):
                    index.extend((f"Installed build: {version['ClientVersion']}", ""))
                manifest = {"format_version": 1, "entry_count": len(entries), "file_format": file_format,
                            "metadata": metadata or {}, "groups": []}
                for letter, items in groups.items():
                    filename = f"{'Other' if letter == '#' else letter}.{file_format}"
                    output = Path(workspace) / filename
                    export_entries(output, items, {**(metadata or {}), "alphabetical_group": letter}, changes)
                    archive.write(output, filename)
                    index.append(f"- [{letter if letter != '#' else 'Other'}]({filename}) — {len(items):,} entries")
                    manifest["groups"].append({"group": letter, "file": filename, "count": len(items)})
                archive.writestr("INDEX.md", "\n".join(index) + "\n")
                archive.writestr("manifest.json", json.dumps(manifest, indent=2, ensure_ascii=False))
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def check_config(text: str, entries: list[Entry]) -> list[dict]:
    """Review direct settings without pretending runtime actions/aliases are absent."""
    known = {entry.name.casefold(): entry for entry in entries}
    aliases = {match.group(1).casefold() for match in re.finditer(r'^\s*alias\s+"?([^"\s]+)', text, re.M | re.I)}
    findings = []
    for number, line in enumerate(text.splitlines(), 1):
        match = re.match(r'^\s*(?:"([^"\n]+)"|(\S+))', line)
        if not match or line.lstrip().startswith("//"):
            continue
        name = (match.group(1) or match.group(2)).casefold()
        entry = known.get(name)
        if entry and "cheat" in entry.flags:
            findings.append({"line": number, "command": name, "status": "Cheat-protected", "detail": "Requires cheats to change; a direct setting is unsuitable for official matches."})
        elif name not in known and name not in aliases:
            findings.append({"line": number, "command": name, "status": "Not in extracted registry", "detail": "May be a runtime action or another alias; absence does not prove removal."})
    return findings
