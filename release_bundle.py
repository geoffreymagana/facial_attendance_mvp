"""Create a portable zip release containing the built AttendanceSystem exe and a data folder.

The bundle can include a different data folder than the repository's current `data/`,
so you can package a release with a pretrained model and captured face samples.
"""

from __future__ import annotations

import argparse
import sys
import zipfile
from pathlib import Path

DEFAULT_NOTE = '''Facial Recognition Class Attendance System

1. Unzip anywhere, then double-click AttendanceSystem.exe.
2. Windows SmartScreen may warn because the exe is unsigned:
   click "More info" → "Run anyway".
3. First launch takes a few seconds while the app unpacks.
4. The app loads runtime data from the data/ folder next to the EXE.
5. Do not move the EXE away from the data/ folder if you want to keep
   existing students and attendance history.
'''


def add_file_to_zip(zf: zipfile.ZipFile, path: Path, arcname: str) -> None:
    zf.write(path, arcname=arcname)


def add_directory_to_zip(zf: zipfile.ZipFile, root_dir: Path, base_dir: Path) -> None:
    for path in sorted(base_dir.rglob('*')):
        if path.is_file():
            arcname = str(path.relative_to(root_dir))
            zf.write(path, arcname=arcname)


def build_bundle(exe_path: Path, data_dir: Path | None, output_path: Path, note_text: str | None) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output_path, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
        add_file_to_zip(zf, exe_path, 'AttendanceSystem.exe')

        if data_dir is not None and data_dir.exists():
            if not data_dir.is_dir():
                raise ValueError(f"Data path is not a directory: {data_dir}")
            add_directory_to_zip(zf, data_dir.parent, data_dir)
        elif data_dir is not None:
            print(f"Warning: data directory does not exist: {data_dir}")

        if note_text is not None:
            zf.writestr('README-FIRST.txt', note_text)

    print(f"Created bundle: {output_path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='Create a ZIP bundle containing AttendanceSystem.exe and a data folder.'
    )
    parser.add_argument(
        '--exe',
        default='dist/AttendanceSystem.exe',
        help='Path to the built AttendanceSystem.exe (default: dist/AttendanceSystem.exe)'
    )
    parser.add_argument(
        '--data',
        default='data',
        help='Path to the data folder to include in the bundle (default: data)'
    )
    parser.add_argument(
        '--output',
        default='AttendanceSystem-bundle.zip',
        help='Output zip file path (default: AttendanceSystem-bundle.zip)'
    )
    parser.add_argument(
        '--no-note',
        action='store_true',
        help='Do not include the default README-FIRST.txt note in the bundle.'
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    exe_path = Path(args.exe)
    data_dir = Path(args.data) if args.data else None
    output_path = Path(args.output)

    if not exe_path.exists():
        print(f"Error: exe not found: {exe_path}", file=sys.stderr)
        return 1

    note_text = None if args.no_note else DEFAULT_NOTE
    if data_dir is None:
        print('No data folder specified; bundling only the exe.')
    else:
        if not data_dir.exists():
            print(f"Warning: data folder does not exist: {data_dir}")

    build_bundle(exe_path, data_dir, output_path, note_text)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
