# Testing workflow

How to test Palette Pilot manually and (if present) with automated tests.

## In-QGIS testing

1. Open a test QGIS project with **vector layers** using **graduated**, **categorized**, or **single symbol** symbology.
2. Enable the Palette Pilot plugin (toolbar or menu).
3. Select the layer in the Layers panel so it is the **current layer**.
4. Open the dialog and exercise the Home tab:
   - **Graduated / categorized:** Change the ramp combo or **Intent palette**; confirm the map and legend update. Try **Invert ramp** and **Apply**.
   - **Single symbol:** Confirm the ramp section stays available as **Colour ramp preview (for swatches)** — edit the ramp or pick **Intent palette** / **Saved styles** and confirm **quick swatches** update; click swatches or use the colour picker and confirm the symbol colour updates (the ramp itself does not replace single-symbol symbology).
5. Confirm:
   - The map canvas updates when applying ramps or single-symbol colours.
   - The legend (e.g. in Layer Properties → Symbology) matches expectations.
6. **Edge cases** to try:
   - No layer selected → expect a clear message.
   - Graduated/categorized layer but symbology not supported by the ramp applier → expect the existing warning when Apply cannot change the renderer.
   - Layer with many classes → confirm rendering and performance are acceptable.

## Automated tests

### Qt/QGIS compatibility tests

The `qt_compat` module has dedicated unit tests in `tests/test_qt_compat.py`. These mock both Qt5/QGIS 3 and Qt6/QGIS 4 environments to verify that all enum constants resolve correctly on both platforms — no QGIS installation required.

Run from the repo root (install dev deps once with `uv sync --extra dev`):

```bash
uv run python -m unittest tests.test_qt_compat -v
```

### Theme engine tests

The `theme_engine` module has unit tests in `tests/test_theme_engine.py`. These mock QGIS APIs and exercise theme CRUD (save/load/list/delete), style discovery, regex matching with geometry type enforcement, and theme application — no QGIS installation required.

```bash
uv run python -m unittest tests.test_theme_engine -v
```

### Palette presets (data sanity)

`tests/test_palette_presets.py` checks named preset hex lists and display order without importing QGIS.

```bash
uv run python -m unittest tests.test_palette_presets -v
```

### Run all tests at once

```bash
uv run python -m unittest discover tests -v
```

Equivalent using pytest:

```bash
uv run pytest -v
```

### Other unit tests

- **Unit tests** for pure logic (e.g. preset hex data in `palette_presets`, theme engine, `qt_compat`) run in the **project venv**. They do not require QGIS.
- **Integration tests** that need PyQGIS (e.g. applying a ramp to a mock or real layer) require running under QGIS’s Python (e.g. `qgis_testrunner.py` or a small runner that loads QGIS then runs tests). Document the exact command (e.g. in this file or in README) so others can run them.

## Regression

After code changes, re-run the same manual checklist above and any automated tests. Keep the checklist in this document or in a `TESTING_CHECKLIST.md` so anyone can verify before release.
