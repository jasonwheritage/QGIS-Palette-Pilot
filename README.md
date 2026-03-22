# Palette Pilot

A **QGIS plugin** to style vector layers in a snap: colour ramps, saved colours, full layer styles (point, line, polygon), and reusable themes.

- **Vector layers** only: apply colours to **single-symbol** layers, or apply built-in or saved ramps to **graduated** or **categorized** symbology; save/load full .qml styles by geometry type and apply them through saved theme rules.
- Runs inside QGIS as an installable Python plugin.

<video src="docs/assets/QGIS-Palette-Pilot-Demo-01.mp4" controls width="100%"></video>

## Installation

Palette Pilot runs in [QGIS](https://qgis.org/) 3.28 or later (including Qt6 builds and QGIS 4.x). One flow for every OS:

1. **Install the plugin** (pick one):
  - **From ZIP (easiest):** In QGIS go to **Plugins → Manage and Install Plugins → Install from ZIP**, choose a release zip that contains the `palette_pilot` folder at the top level.
  - **From folder:** Copy the `palette_pilot` folder into your QGIS plugin directory. Default profile paths:
    - **Windows:** `%APPDATA%\QGIS\QGIS3\profiles\default\python\plugins\`
    - **macOS:** `~/Library/Application Support/QGIS/QGIS3/profiles/default/python/plugins/`
    - **Linux:** `~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/`  
    Different or named profile? Get the path from **Plugins → Python Console** → [docs/installation.md](docs/installation.md#finding-your-plugin-directory).
2. **Enable:** **Plugins → Manage and Install Plugins → Installed** → tick **Palette Pilot**.
3. **Use:** Open a project with vector layers → **Plugins → Palette Pilot** (or toolbar icon) → select layer(s), pick a ramp or colour, click **Apply**.

Troubleshooting: **View → Panels → Log Messages** → Palette Pilot tab.

## Using the plugin

Changing layer colours in QGIS usually means opening **Layer Properties → Symbology**, picking a renderer, choosing a field, then hunting for colour ramps and applying them step by step. Palette Pilot gives you one place to pick a ramp or colour and apply it to one or more layers, so you can try different palettes quickly without reopening dialogs.

**Supported layer types:**

- **Single symbol** — One colour for the whole layer. Open Palette Pilot, pick a colour (or a saved colour), and apply. Ideal for boundaries, background layers, or any layer that uses a single symbol.
- **Graduated** — Colours by a numeric field (e.g. population, elevation). The **field to classify on must already be set** in Layer Properties → Symbology (e.g. “Value” = your numeric field). Palette Pilot then applies a colour ramp to those classes without you re-opening Symbology.
- **Categorized** — Colours by a category field (e.g. type, region). The **field to classify on must already be set** in Layer Properties → Symbology (e.g. “Value” = your category field). Palette Pilot applies a ramp across the categories.
- **Themes (full style rules)** — Save a theme made of ordered rules that match layer names (regex) and apply `.qml` styles by geometry type. Use this to quickly re-apply a consistent full-style setup across projects.

**Steps:**

1. Set your layer’s symbology in **QGIS Layer Properties → Symbology** (Single symbol, Graduated, or Categorized; for graduated/categorized, select the **field** to ramp on).
2. Open **Plugins → Palette Pilot** (or the toolbar icon), select one or more layers, then choose a ramp or colour and it will be applied automatically, otherwise click **Apply**.

Quick concept diagrams are in [docs/development.md](docs/development.md#quick-concept-diagrams).



## Lightweight approach: built on QGIS

Palette Pilot is designed to stay small and reliable by relying on QGIS’s own functionality instead of reimplementing it:

- **No extra dependencies** — The plugin uses only PyQGIS and Qt, which QGIS already provides. There is no separate server, database, or external service. A built-in compatibility shim (`qt_compat.py`) handles Qt5/Qt6 and QGIS 3/4 API differences automatically.
- **QGIS owns the data** — Colour ramps come from QGIS’s built-in style (and your saved ramps in the style manager). Saved colours and full layer styles (.qml) are stored where QGIS normally keeps them. The plugin does not duplicate style data in its own config, so what you see in Layer Properties or the Style Manager is the same as what Palette Pilot uses.
- **Thin layer over existing symbology** — The plugin does not create or manage classification (fields, class breaks, or categories). It only applies a chosen ramp or colour to layers that already use single-symbol, graduated, or categorized renderers. You set up the renderer and field in Layer Properties; Palette Pilot is a fast way to try different palettes on that setup.
- **Fits the QGIS model** — Applied styles become part of your layer and project. Saving the project, exporting a layer style, or sharing a .qml file works as usual; the plugin does not add its own file format or sync layer.

For more on design and trade-offs, see [docs/architecture.md](docs/architecture.md).

## How this project was developed

This plugin was developed with AI-assisted coding using **Cursor** and **GitHub Copilot (Claude Opus 4.6)**. Design, implementation, docs, and release prep were done in collaboration with these tools—iterating on the codebase, QGIS plugin conventions, and documentation from within the editor.

## Development

- **Setup:** Use **uv** (`uv venv`, then `uv sync` or `uv pip install -e ".[dev]"`) or the **pip** fallback (`python -m venv .venv`, `pip install -r requirements-dev.txt`). See [docs/development.md](docs/development.md#installing-the-plugin-for-development).
- **Installing the plugin for dev:** Copy or symlink the plugin into your QGIS plugin directory. From the repo root: `./scripts/install_plugin_for_dev.py` (copy) or `./scripts/install_plugin_for_dev.py --symlink` (or `python3 scripts/...`). Set `QGIS_PLUGINS_PATH` if your plugin dir is different. See [docs/installation.md](docs/installation.md#development-install-via-script-copy-or-symlink) and [docs/development.md](docs/development.md).
- **Docs:** [docs/development.md](docs/development.md), [docs/installation.md](docs/installation.md), [docs/testing.md](docs/testing.md), [docs/debugging.md](docs/debugging.md), [docs/architecture.md](docs/architecture.md).

## Translations

The plugin uses Qt Linguist (`.ts` / `.qm`) for translations. Source files live in `palette_pilot/i18n/`. To add or update translations:

1. Install Qt Linguist tools (e.g. on Debian: `sudo apt install qttools5-dev-tools`).
2. From `palette_pilot/i18n/` run `pylupdate5 palette_pilot.pro` to update `.ts` files from the Python sources.
3. Open the `.ts` file(s) in Qt Linguist, translate, and save.
4. Run `lrelease palette_pilot_en.ts` (and each locale) to compile `.qm` files. QGIS loads translations when the user changes language in **Settings → Options → General** and restarts.

The `.ts` files are included in the repo so contributors can add new languages.
