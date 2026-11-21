# GloriaSetup rollout

Tagging `vX.Y.Z` now builds the app and attaches `CS2CommandBrowser_X.Y.Z_x64-setup.exe` to that release.
Nothing was built, pushed, tagged or released locally.

## Please

- **Check the version.** No project file holds a version number. `gloria.toml` uses `1.1.0` because the build is named `portable-v1.1`. The catalog says 0.1.3. A pushed tag overrides it, so only manual runs use this value.
- **Check the build in CI.** It copies `build.ps1` and has not been run. `vendor/DumpSource2` is not in the repo, so the workflow clones ValveResourceFormat/DumpSource2 at the commit in `tools/extractor-build.json`. It then initialises the same four submodules as `build.ps1`. If you patched the extractor locally, CI will not have the patch. The provenance file says it is unmodified.
- **Check the exe icon.** `build.ps1` passes no `--icon`, so the app exe had the default PyInstaller icon. The workflow adds `--icon assets/icon.ico`. The installer's shortcuts take their icon from the exe, so this gives them the app icon. `build.ps1` itself is unchanged.
- **Set the secrets** `WINDOWS_PFX_BASE64` and `WINDOWS_PFX_PASSWORD`, or the setup is built unsigned.
- **Data folder.** The app stores settings and scan snapshots in `%LOCALAPPDATA%\CS2CommandBrowser` (`core.py` `app_data()`), which is the only entry in `data_folders`.
- **No `legacy_names`.** The app only shipped as a portable folder, never with an installer.
- **`package_source.py` is not run in CI.** It needs the vendored source tree and only produces the source archive, not runtime files.
- **Release creation.** If the release is missing, the workflow creates it with generated notes. For a manual `workflow_dispatch` run on a branch, it builds and packs but does not upload.
