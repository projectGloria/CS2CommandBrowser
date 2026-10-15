from datetime import datetime, timezone
from importlib.metadata import version
import json
from pathlib import Path
import subprocess

from core import atomic_json, sha256

root = Path(__file__).resolve().parent
path = root / 'tools' / 'extractor-build.json'
provenance = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
upstream = root / 'vendor' / 'DumpSource2'
if (upstream / '.git').exists():
    provenance['upstream_commit'] = subprocess.check_output(['git', '-C', str(upstream), 'rev-parse', 'HEAD'], text=True).strip()
    provenance['submodule_commits'] = subprocess.check_output(['git', '-C', str(upstream), 'submodule', 'status'], text=True).splitlines()
provenance.update({'upstream': 'https://github.com/ValveResourceFormat/DumpSource2',
                   'modified_upstream_source': False,
                   'built_at': datetime.now(timezone.utc).isoformat(),
                   'extractor_sha256': sha256(root / 'tools' / 'DumpSource2-CS2.exe'),
                   'pyinstaller': version('pyinstaller'), 'cmake': version('cmake')})
atomic_json(path, provenance)
print('Recorded extractor build provenance.')
