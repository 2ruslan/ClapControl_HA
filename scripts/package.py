"""Build a source archive that extracts directly into HA's addons directory."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

root = Path(__file__).resolve().parents[1]
files = [root / name for name in (
    'config.yaml', 'repository.yaml', 'Dockerfile', 'run.sh', 'requirements.txt',
    'README.md', 'DOCS.md', 'CHANGELOG.md', 'VALIDATION.md',
    '.dockerignore', '.gitignore', '.gitattributes')]
for directory in ('clap_control', 'tests', 'scripts', '.github'):
    files.extend(p for p in (root / directory).rglob('*')
                 if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc')
version = next(line.split(':', 1)[1].strip().strip('"')
               for line in (root / 'config.yaml').read_text().splitlines()
               if line.startswith('version:'))
output = root / f'clap-control-{version}.zip'
with ZipFile(output, 'w', ZIP_DEFLATED) as archive:
    for path in sorted(files):
        archive.write(path, 'clap_control/' + path.relative_to(root).as_posix())
with ZipFile(output) as archive:
    assert archive.testzip() is None
    assert 'clap_control/config.yaml' in archive.namelist()
print(f'{output}: {len(files)} files, {output.stat().st_size} bytes')
