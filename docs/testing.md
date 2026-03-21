# Testing workflow

How to test Palette Pilot manually and (if present) with automated tests.

## In-QGIS testing

1. Open a test QGIS project that has **vector layers** with **graduated** or **categorized** symbology.
2. Enable the Palette Pilot plugin (toolbar or menu).
3. Select the layer in the Layers panel so it is the **current layer**.
4. Run the plugin action (e.g. “Apply palette” or open the dialog and click Apply).
5. Confirm:
   - The map canvas updates with the new colours.
   - The legend (e.g. in Layer Properties → Symbology) shows the applied ramp/palette.
6. **Edge cases** to try:
   - No layer selected → expect a clear message.
   - Layer with a different renderer (e.g. single symbol) → expect a message that only graduated/categorized are supported.
   - Layer with many classes → confirm rendering and performance are acceptable.

## Automated tests

### Qt/QGIS compatibility tests

The `qt_compat` module has dedicated unit tests in `tests/test_qt_compat.py`. These mock both Qt5/QGIS 3 and Qt6/QGIS 4 environments to verify that all enum constants resolve correctly on both platforms — no QGIS installation required.

Run from the repo root:

```bash
uv run python -m unittest tests.test_qt_compat -v
```

### Theme engine tests

The `theme_engine` module has unit tests in `tests/test_theme_engine.py`. These mock QGIS APIs and exercise theme CRUD (save/load/list/delete), style discovery, regex matching with geometry type enforcement, and theme application — no QGIS installation required.

```bash
uv run python -m unittest tests.test_theme_engine -v
```

### Run all tests at once

```bash
uv run python -m unittest discover tests -v
```

Or without uv:

```bash
python3 -m unittest tests.test_qt_compat -v
```

### Other unit tests

- **Unit tests** for pure logic (e.g. building a ramp from a colour list, mapping ramp to category list) run in the **project venv**. They do not require QGIS.
- **Integration tests** that need PyQGIS (e.g. applying a ramp to a mock or real layer) require running under QGIS’s Python (e.g. `qgis_testrunner.py` or a small runner that loads QGIS then runs tests). Document the exact command (e.g. in this file or in README) so others can run them.

## Regression

After code changes, re-run the same manual checklist above and any automated tests. Keep the checklist in this document or in a `TESTING_CHECKLIST.md` so anyone can verify before release.
