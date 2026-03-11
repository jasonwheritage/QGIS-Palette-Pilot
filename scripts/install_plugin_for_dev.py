#!/usr/bin/env python3
"""
Copy or symlink the Palette Pilot plugin (palette_pilot) into the QGIS plugin directory
for development. Run from the repository root.

Usage (from repo root):
  ./scripts/install_plugin_for_dev.py                    # copy (default)
  ./scripts/install_plugin_for_dev.py --symlink          # symlink if possible
  python3 scripts/install_plugin_for_dev.py             # or call via python3
  set QGIS_PLUGINS_PATH=... && ./scripts/install_plugin_for_dev.py

Environment:
  QGIS_PLUGINS_PATH  Optional. Plugin directory (e.g. from QGIS Python Console).
                     If unset, uses default per-OS path for the "default" profile.
"""
from __future__ import annotations

import argparse
import os
import platform
import shutil
import sys


def _default_plugin_dir() -> str:
    """Default QGIS plugin directory for the default profile."""
    system = platform.system()
    home = os.path.expanduser("~")
    if system == "Windows":
        appdata = os.environ.get("APPDATA", os.path.join(home, "AppData", "Roaming"))
        return os.path.join(appdata, "QGIS", "QGIS3", "profiles", "default", "python", "plugins")
    if system == "Darwin":
        base = os.path.join(home, "Library", "Application Support", "QGIS", "QGIS3")
    else:
        base = os.path.join(home, ".local", "share", "QGIS", "QGIS3")
    return os.path.join(base, "profiles", "default", "python", "plugins")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Install Palette Pilot (palette_pilot) into QGIS plugin directory for development.",
    )
    parser.add_argument(
        "--symlink",
        action="store_true",
        help="Create a symlink instead of copying (edits in repo apply immediately; may need admin on Windows).",
    )
    parser.add_argument(
        "--plugins-dir",
        metavar="PATH",
        default=os.environ.get("QGIS_PLUGINS_PATH", "").strip() or None,
        help="QGIS plugin directory (default: QGIS_PLUGINS_PATH or OS default).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only print what would be done.",
    )
    args = parser.parse_args()

    # Repo root: parent of directory containing this script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.dirname(script_dir)
    source = os.path.join(repo_root, "palette_pilot")

    if not os.path.isdir(source):
        print(f"Source not found: {source}", file=sys.stderr)
        return 1

    dest_dir = args.plugins_dir or _default_plugin_dir()
    dest = os.path.join(dest_dir, "palette_pilot")

    if args.dry_run:
        print(f"Source:      {source}")
        print(f"Destination: {dest}")
        print(f"Mode:        {'symlink' if args.symlink else 'copy'}")
        return 0

    if not os.path.isdir(dest_dir):
        try:
            os.makedirs(dest_dir, exist_ok=True)
            print(f"Created plugin directory: {dest_dir}")
        except OSError as e:
            print(f"Plugin directory does not exist and could not be created: {dest_dir}", file=sys.stderr)
            print(f"Error: {e}", file=sys.stderr)
            print("Create it manually or set QGIS_PLUGINS_PATH to your QGIS plugin path (see docs/installation.md).", file=sys.stderr)
            return 1

    if os.path.exists(dest):
        if os.path.islink(dest):
            os.unlink(dest)
        else:
            shutil.rmtree(dest)

    try:
        if args.symlink:
            os.symlink(source, dest, target_is_directory=True)
            print(f"Symlinked: {dest} -> {source}")
        else:
            shutil.copytree(source, dest)
            print(f"Copied: {source} -> {dest}")
    except OSError as e:
        print(f"Failed: {e}", file=sys.stderr)
        if args.symlink and platform.system() == "Windows":
            print("On Windows, symlinks often require elevated privileges. Try without --symlink to copy.", file=sys.stderr)
        return 1

    print("Done. In QGIS: Plugins → Manage and Install Plugins → Installed → enable Palette Pilot (or reload).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
