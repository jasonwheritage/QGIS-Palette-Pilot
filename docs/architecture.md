# Architecture: considerations, strengths, weaknesses, future recommendations

See [PLAN.md](../PLAN.md) for full context. This document summarises the architecture for the Palette Pilot plugin.

## Architecture considerations

- **In-process, single runtime:** The plugin runs inside the QGIS process, using QGIS’s bundled Python and PyQGIS. There is no separate server, backend, or web layer; all logic and UI execute in one process.

- **UI and API surface:** UI is Qt/PyQt (dialog or dock widget), following standard QGIS plugin layout (toolbar action, menu entry, `initGui` / `unload`). Styling is applied by mutating layer renderers in place (`setSourceColorRamp()`, `updateColorRamp()`, category colours) and calling `triggerRepaint()`.

- **Style ownership:** Applied palettes become part of the layer’s style and project; persistence and sharing are handled by QGIS (layer style, project, style manager). The plugin avoids duplicating style data in its own storage.

- **Dependencies:** The plugin depends on a specific QGIS/PyQGIS version (e.g. 3.44) for API stability. It does not ship a separate Python or Qt; it uses what QGIS provides.

- **Scope of logic:** Palette “application” is a thin adapter: map user choice (ramp or colour list) onto existing graduated/categorized renderer structures. Classification method and class breaks are left to QGIS; the plugin only changes colours.

## Strengths

- **Simple deployment:** No server, no extra runtime; users install QGIS and the plugin. Updates are a matter of updating the plugin in the plugin directory or via Plugin Manager.

- **Native integration:** Direct access to project, layers, and styling APIs; no serialisation or sync layer. The map and legend update immediately.

- **Single source of truth:** Styles live in QGIS. No plugin-specific config that can drift from what the user sees in the Layer Properties or Style Manager.

- **Familiar model:** Standard QGIS plugin pattern; existing docs and examples (toolbar, dialogs, PyQGIS) apply.

## Weaknesses

- **Tied to QGIS and PyQGIS version:** API changes or removals in newer QGIS can break the plugin; version compatibility must be tracked and tested.

- **Debugging and testing:** Full execution is inside QGIS; debugging requires attaching to the QGIS process or using the Python Console. Automated integration tests need a QGIS environment (e.g. headless or test runner that loads QGIS).

- **Limited to PyQGIS surface:** Cannot do anything that PyQGIS does not expose. Raster and other renderer types are out of scope for the current design.

- **No headless “apply” for CI:** End-to-end “apply palette” cannot be run in a normal CI job without launching QGIS or a QGIS Python runtime.

## Future recommendations

- **Compatibility and metadata:** Publish a compatibility matrix (e.g. plugin version ↔ QGIS 3.28 LTR, 3.34, 3.44) and set `qgisMinimumVersion` / `qgisMaximumVersion` in `metadata.txt` so users get clear install constraints.

- **Extend renderer/layer support only if needed:** Consider raster or other vector renderers only if there is user demand and a clear path with `QgsStyle` / existing APIs; avoid scope creep.

- **Plugin repository:** Once stable, consider publishing to the official QGIS plugin repository for discoverability and one-click install.

- **Keep logic testable:** Isolate pure logic (e.g. building a ramp from a colour list, mapping ramp to categories) in small functions or modules that can be unit-tested in the project venv without QGIS; reserve QGIS for integration and UI.

- **Document architecture decisions:** When making larger changes (e.g. where to store user palettes, how to handle reclassification), record the rationale in this file or in ADRs so future work stays consistent.
