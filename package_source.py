"""Bundle corresponding sources and notices, excluding local game data and builds."""
from pathlib import Path
import shutil
import sys
import zipfile

root = Path(__file__).resolve().parent
destination = root / 'portable-v1.1' / 'CS2 Command Browser'
destination.mkdir(parents=True, exist_ok=True)
for filename in ('README.md', 'LICENSE', 'THIRD-PARTY-NOTICES.md'):
    shutil.copy2(root / filename, destination / filename)
licenses = destination / 'licenses'
licenses.mkdir(exist_ok=True)
upstream = root / 'vendor' / 'DumpSource2'
for folder, label in ((upstream, 'DumpSource2'), (upstream / 'vendor' / 'fmt', 'fmt'),
                      (upstream / 'vendor' / 'spdlog', 'spdlog'), (upstream / 'vendor' / 'json', 'json'),
                      (upstream / 'vendor' / 'hl2sdk-cs2', 's2sdk')):
    for source in folder.iterdir():
        if source.is_file() and source.name.lower().startswith(('license', 'copying', 'notice')):
            shutil.copy2(source, licenses / f'{label}-{source.name}')
# Python and Tcl/Tk ship their own notices with the installed runtime.
base = Path(sys.base_prefix)
for source in (base / 'LICENSE.txt', *base.glob('tcl/*/license.terms')):
    if source.is_file():
        shutil.copy2(source, licenses / f'{source.parent.name}-{source.name}')
for source in (root / '.buildenv' / 'Lib' / 'site-packages').glob('pyinstaller-*.dist-info/licenses/*'):
    if source.is_file():
        shutil.copy2(source, licenses / f'PyInstaller-{source.name}')

included = ['app.py', 'ui.py', 'core.py', 'test_core.py', 'build.ps1', 'package_source.py', 'record_build.py', 'README.md', 'LICENSE', 'THIRD-PARTY-NOTICES.md', 'tools/extractor-build.json']
with zipfile.ZipFile(destination / 'Source.zip', 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
    for filename in included:
        archive.write(root / filename, filename)
    for source in upstream.rglob('*'):
        relative = source.relative_to(root)
        if not source.is_file() or any(part in ('.git', '__pycache__', '.vs', 'build', 'node_modules') for part in relative.parts):
            continue
        # The extractor builds the SDK as headers only; prebuilt SDK utilities
        # and import libraries are not part of its corresponding source.
        if source.suffix.lower() in ('.exe', '.dll', '.so', '.dylib', '.lib', '.a', '.obj', '.o', '.pdb'):
            continue
        archive.write(source, relative.as_posix())
print('Packaged source and third-party notices.')
