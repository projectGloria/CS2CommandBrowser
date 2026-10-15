# CS2 Command Browser

A local Windows app for extracting CS2 console variables and commands from the game files you select. It does not start CS2 or require console commands, copy/paste, an account, or an online command database.

## Open the app

Open **portable-v1.1/CS2 Command Browser/CS2 Command Browser.exe** (or **CS2 Command Browser.exe** beside this README in the packaged folder). Keep the accompanying `_internal` folder beside the executable. Python is not required for this packaged version. Close v1.1 before rebuilding its package.

1. Paste your installation path or choose **Browse**. Accepted folders are `Counter-Strike Global Offensive`, its `game` subfolder, or `game/bin/win64`.
2. Select **Refresh catalog**. The first scan copies the required libraries to a private cache; later scans reuse unchanged files.
3. Search names and descriptions, select an entry to see its details, or filter by kind and flags.

The app remembers the path you enter. It does not search your computer for CS2.

## What you can do

- View game-supplied descriptions, built-in defaults, value types, ranges, flags, and declaring modules.
- Copy an entry's name or its default-value command. This never applies a setting to CS2.
- Use the **Export** menu for **Export results**, **Export all**, **Export all by alphabetical groups**, or **Export changes**. The export dialog lets you choose scope, single-file/A–Z organization, and TXT, CSV, JSON, or Markdown.
- Alphabetical exports produce a ZIP containing one file per nonempty letter, `INDEX.md`, and `manifest.json` with group counts and build information. Leading `+`, `-`, and `_` are ignored for grouping; other symbols and digits are placed in `Other`. Every exported entry retains its change status. **All current entries** ignores search and filters and excludes removed entries from old scans.
- CSV values beginning with spreadsheet formula characters are prefixed with an apostrophe to keep them literal.
- Compare successive scans of the same installation automatically. Added, removed, and changed rows have distinct colors. **Compare scan** also accepts an earlier `snapshot.json` manually.
- Check a `.cfg` file for cheat-protected direct settings and commands absent from the extracted registry. This is a limited, read-only check: it does not expand binds/aliases, validate values, or prove that an unlisted runtime command was removed.

Removed rows come from the older snapshot; they are clearly marked and may be included when exporting comparison results.

## Where results are saved

Use **Tools → Open results folder** to open `%LOCALAPPDATA%/CS2CommandBrowser`.

- `settings.json` — the folder you supplied.
- `snapshots/` — successful structured snapshots, raw `convars.txt` / `commands.txt`, and extraction logs. Failed attempts retain a diagnostic log without replacing the last good scan.
- `cache/` — private copies of installed game libraries. These may take several hundred MB or more. They can be deleted while the app is closed; the next scan recreates them.
- `latest.json` — a pointer to your latest successful scan.

The app uses your Windows time zone when displaying scan times. Snapshot timestamps are stored in UTC.

## How extraction works

The bundled [DumpSource2](https://github.com/ValveResourceFormat/DumpSource2) tool loads the copied game modules in a separate offline process and reads their registered data. It does not attach to a running game or launch `cs2.exe`. It is not a simple string search. Your selected installation and personal configs are not modified.

Results describe **your installed build**, not a website's latest snapshot. They contain **built-in defaults**, not the settings currently active in your game. Some entries have no help text, and dynamically registered actions such as movement/button commands may not appear. A missing entry alone is not evidence that a command was removed. The app never invents missing Valve descriptions.

The tool also performs upstream schema extraction internally; only console data and the extraction log are retained. If the extractor fails, the app does not promote partial output. If CS2 changes its engine layout, a new compatible extractor build may be needed. The error dialog points to the diagnostic log.

## Source and rebuilding

The Python app uses only the standard library. Source files are `app.py`, `ui.py`, `core.py`, and `test_core.py`. A full source archive accompanies the packaged executable, including the pinned upstream extractor and its build dependencies. No Valve game binaries are distributed with this app.

To run the source directly on Windows with Python/Tkinter installed:

```powershell
python app.py
```

To scan from a terminal with an explicitly supplied path:

```powershell
python app.py --scan 'D:\SteamLibrary\steamapps\common\Counter-Strike Global Offensive'
```

To rebuild the extractor and package the desktop app, run `build.ps1`. This needs Visual Studio 2022 with the C++ desktop build tools and a Windows SDK, Python with pip, and internet access for Python build dependencies. It installs build tools into a project-local `.buildenv`; it does not install them globally. The normal packaged app runs offline.

The pinned extractor checkout is under `vendor/DumpSource2`. The provided source archive includes the CS2 SDK, fmt, spdlog, and nlohmann/json submodule contents needed to build the CS2 target. Other game targets are not built. Build provenance is recorded in `tools/extractor-build.json`.

## License and credits

CS2 Command Browser is provided under GNU GPL version 3; see `LICENSE`. The offline extraction engine is DumpSource2 by ValveResourceFormat contributors, also GPL-3.0. Dependency notices are in `THIRD-PARTY-NOTICES.md` and the supplied source archive. There is no warranty. CS2 and Valve names identify the game; this is an independent tool.
