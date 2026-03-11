#!/usr/bin/env python3
"""
Create a zip of the Palette Pilot plugin for release or "Install from ZIP".
The zip contains the palette_pilot folder at the top level (no extra parent).
Run from the repository root.

Usage:
  python3 scripts/create_release_zip.py
  python3 scripts/create_release_zip.py -o palette_pilot_v1.0.0.zip
"""
from __future__ import annotations

import argparse
import os
import zipfile
from pathlib import Path

# Paths and names to exclude from the plugin zip (same idea as .gitignore for the plugin dir)
EXCLUDE_DIRS = {"__pycache__", ".git", ".venv", "venv", ".mypy_cache", ".ruff_cache"}
EXCLUDE_SUFFIXES = (".pyc", ".pyo", ".pycod", ".pycz", ".DS_Store")


def should_exclude(path: Path, base: Path) -> bool:
    rel = path.relative_to(base)
    parts = rel.parts
    if any(part in EXCLUDE_DIRS for part in parts):
        return True
    if path.suffix in EXCLUDE_SUFFIXES or path.name.endswith(EXCLUDE_SUFFIXES):
        return True
    return False


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create a release zip of the Palette Pilot plugin (palette_pilot) for Install from ZIP or QGIS plugin server."
    )
    parser.add_argument(
        "-o", "--output",
        default="palette_pilot.zip",
        help="Output zip path (default: palette_pilot.zip)",
    )
    args = parser.parse_args()

    script_dir = Path(__file__).resolve().parent
    repo_root = script_dir.parent
    plugin_dir = repo_root / "palette_pilot"

    if not plugin_dir.is_dir():
        print(f"Error: plugin directory not found: {plugin_dir}", file=__import__("sys").stderr)
        return 1

    out_path = Path(args.output)
    if not out_path.is_absolute():
        out_path = repo_root / out_path

    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(plugin_dir):
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
            root_path = Path(root)
            for name in files:
                file_path = root_path / name
                if should_exclude(file_path, plugin_dir):
                    continue
                arcname = file_path.relative_to(repo_root)
                zf.write(file_path, arcname)

    print(f"Created {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
