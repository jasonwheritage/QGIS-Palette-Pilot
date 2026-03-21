# Tests

## Running tests

From the repo root:

```bash
uv run python -m unittest discover tests -v
```

Or without uv:

```bash
python3 -m unittest discover tests -v
```

## Test modules

- **`test_qt_compat.py`** — Verifies the `qt_compat` compatibility shim resolves Qt enum constants correctly for both Qt5 (unscoped enums) and Qt6 (scoped enums), and QGIS 3 vs QGIS 4 API constants (`QgsWkbTypes` vs `Qgis.GeometryType`, `Qgis.Info` vs `Qgis.MessageLevel.Info`, etc.). Uses mocked `qgis` modules so no QGIS installation is needed.- **`test_theme_engine.py`** — Tests the theme engine: theme CRUD (save/load/list/delete), `.qml` style discovery by geometry type, regex matching against project layers with geometry type enforcement, and applying themes to single layers and bulk project layers. Uses mocked QGIS modules so no QGIS installation is needed.- **Additional unit tests** for pure logic (e.g. ramp building, colour list handling) go here and run from the project venv (no QGIS required).
- **Integration tests** that need PyQGIS require running under QGIS’s Python; see [docs/testing.md](../docs/testing.md).
