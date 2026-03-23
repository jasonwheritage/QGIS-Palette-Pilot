# Release checklist

Use this when preparing a release (e.g. v1.0.0 or later).

## Done (v1.0.0 prep)

- [x] **License** — GPL-2.0-or-later in repo root and `palette_pilot/`.
- [x] **Plugin icon** — `palette_pilot/img/icon.png` and set in plugin code (OS-agnostic path).
- [x] **Metadata** — `version=1.0.0`, `experimental=False`, repository, tracker, homepage, icon in `palette_pilot/metadata.txt`.
- [x] **Translations (i18n)** — `palette_pilot/i18n/` with `palette_pilot.pro`, `palette_pilot_en.ts`; strings use `QCoreApplication.translate()`; README and docs describe pylupdate5/lrelease.
- [x] **.gitignore** — `PLAN.md` excluded; `.ts`/`.qm` not ignored.
- [x] **Directory name** — Plugin folder renamed from `colour_palette_tool` to `palette_pilot` for consistency.
- [x] **Docs** — README: Install and use (all platforms), Using the plugin (single/graduated/categorized, field requirement), Lightweight approach, Translations, Development; installation.md and development.md updated; release zip and QGIS server publish steps documented.
- [x] **Scripts** — `scripts/create_release_zip.py` (zip for release); `scripts/install_plugin_for_dev.py` (python3, creates plugin dir if missing, palette_pilot).
- [x] **OS-agnostic** — Paths use `os.path.join()` and plugin dir from `__file__`; scripts work on Windows, macOS, Linux.

## Animated demo

The README **Using the plugin** section includes a placeholder for an animated demo. To add or update it:

1. **Record a short screen capture** of someone using the plugin:
   - Open QGIS with a project that has at least one vector layer (graduated or categorized).
   - Run **Plugins → Palette Pilot** (or click the toolbar icon).
   - Select a layer, choose a colour ramp from the list, and click **Apply** so the map updates.
   - Keep the clip short (e.g. 5–15 seconds).

2. **Tools you can use** (OS-agnostic options):

   **Linux (recommended):**
   - **`slop` + `ffmpeg`** — `slop` lets you click-drag to select a precise screen region, then `ffmpeg` records that region. This gives you pixel-perfect control over the capture area without recording your entire screen or guessing coordinates.
   - **Kdenlive** — full-featured open-source video editor for trimming, adding titles/annotations, and exporting to MP4 or GIF. Useful when the raw recording needs post-production (e.g. trimming dead time, adding a brief intro).

   **macOS:**
   - QuickTime or built-in screenshot (Cmd+Shift+5), then convert to GIF if needed.

   **Windows:**
   - Xbox Game Bar (Win+G), or a tool like **ScreenToGif** for direct GIF output.

3. **Export as GIF** (e.g. 800×600 or similar, not too large for the repo). Save as **`docs/demo.gif`**.

4. **Commit** `docs/demo.gif`. The README already references it as `![Palette Pilot demo](docs/demo.gif)`.

If you prefer not to ship a GIF (e.g. to keep the repo small), you can host the demo on a wiki or external page and replace the image in the README with a link to the video or GIF URL.

## Creating a release (automated)

Use the **Create Release** GitHub Actions workflow to publish a new release:

1. Go to **Actions → Create Release → Run workflow**.
2. Choose the version bump type: **major**, **minor**, or **patch**.
3. Click **Run workflow**. The workflow will:
   - Read the current version from `palette_pilot/metadata.txt`.
   - Compute the new version number.
   - Update `metadata.txt` with the new version.
   - Build the release ZIP using `scripts/create_release_zip.py`.
   - Commit the version bump and create a git tag (e.g. `v1.1.0`).
   - Create a **draft** GitHub release with the ZIP attached.
4. Review the draft release on the **Releases** page, edit the notes if needed, then publish.

## Other release steps (manual)

- Bump `version` in `palette_pilot/metadata.txt`.
- Update changelog in `metadata.txt` or README if desired.
- Create the release zip: from the repo root run `uv run python scripts/create_release_zip.py` (output: `palette_pilot.zip`). Use `-o name.zip` to set the output path.
- Tag the release in git (e.g. `v1.0.0`).

## Publish on the public QGIS plugin server

To make the plugin installable via **Plugins → Manage and Install Plugins** in QGIS:

1. **Get an OSGeo ID** (if you don’t have one): [OSGeo user ID](https://www.osgeo.org/community/getting-started-osgeo/osgeo_userid/).

2. **Prepare the plugin zip** so it validates:
   - Zip contains only the **plugin folder** `palette_pilot/` at the top level (no extra parent folder, no `__MACOSX`, `.git`, `__pycache__`).
   - Package under 25 MB, no binaries; `metadata.txt`, `__init__.py`, and **LICENSE** (no extension) inside the folder.
   - `metadata.txt` has valid **repository**, **tracker** (issues URL), **homepage**, and **license** compatible with GPLv2 or later. See [plugins.qgis.org/docs/publish](https://plugins.qgis.org/docs/publish/).

3. **Upload:** Go to [QGIS plugin repo → Upload a plugin](https://plugins.qgis.org/plugins/add/), sign in with your OSGeo ID, and upload the zip.

4. **Review:** A staff member will approve the plugin; you’ll be notified. New uploads may be unapproved until reviewed. Ensure the zip matches the code in the “repository” URL in metadata so reviewers can verify.
