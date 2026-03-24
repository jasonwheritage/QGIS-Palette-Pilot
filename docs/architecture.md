# Architecture: considerations, strengths, weaknesses, future recommendations

See [PLAN.md](../PLAN.md) for full context. This document summarises the architecture for the Palette Pilot plugin.

## Architecture considerations

- **In-process, single runtime:** The plugin runs inside the QGIS process, using QGIS’s bundled Python and PyQGIS. There is no separate server, backend, or web layer; all logic and UI execute in one process.

- **UI and API surface:** UI is Qt/PyQt (dialog or dock widget), following standard QGIS plugin layout (toolbar action, menu entry, `initGui` / `unload`). Styling is applied by mutating layer renderers in place (`setSourceColorRamp()`, `updateColorRamp()`, category colours) and calling `triggerRepaint()`.

- **Style ownership:** Applied palettes become part of the layer’s style and project; persistence and sharing are handled by QGIS (layer style, project, style manager). The plugin avoids duplicating style data in its own storage.
- **Theme system:** Themes are JSON files stored in `palette_pilot_themes/` under the QGIS settings directory.  Each theme contains an ordered list of *rules*; a rule pairs a `.qml` style file (from `palette_pilot_full_styles/<geometry>/`) with a regex pattern that matches layer names.  The theme engine (`theme_engine.py`) handles theme CRUD, style discovery, regex matching against project layers, and applying `.qml` styles via `layer.loadNamedStyle()`.  Geometry type enforcement ensures point styles only apply to point layers, etc.  A theme editor dialog (`theme_editor_dialog.py`) provides the UI for building rules with live match previews and a preview-before-save workflow.
- **Dependencies:** The plugin depends on a specific QGIS/PyQGIS version (e.g. 3.44) for API stability. It does not ship a separate Python or Qt; it uses what QGIS provides.
- **Qt5/Qt6 and QGIS 3/4 compatibility:** The plugin uses a `qt_compat` shim module (`palette_pilot/qt_compat.py`) that resolves enum constants at import time for both Qt5 (unscoped enums like `Qt.NoFocus`) and Qt6 (scoped enums like `Qt.FocusPolicy.NoFocus`), as well as QGIS 3 APIs (`QgsWkbTypes`, `Qgis.Info`, `QgsMapLayer.VectorLayer`) and their QGIS 4 equivalents (`Qgis.GeometryType`, `Qgis.MessageLevel`, `Qgis.LayerType`). Plugin code imports constants from `qt_compat` instead of using Qt/QGIS enums directly, avoiding scattered `try/except` blocks.
- **Scope of logic:** Palette “application” is a thin adapter: map user choice (ramp or colour list) onto existing graduated/categorized renderer structures. Classification method and class breaks are left to QGIS; the plugin only changes colours.

- **Home tab palette UX:** Named intent palettes and swatch helpers live in `palette_pilot/palette_presets.py` (hex lists, sampling a ramp for display, building a `QgsGradientColorRamp`). On the Home tab, **Intent palette** builds a gradient from a preset and applies it to **graduated/categorized** layers; on **single-symbol** layers it only updates the ramp preview (the group title switches to “preview for swatches”) so users can still edit the ramp that drives **quick swatches**. **Preset swatches** show colours from a chosen named palette; **quick swatches from ramp** sample the current ramp preview. Single-symbol colour apply reuses the existing colour-button path.

## Strengths

- **Simple deployment:** No server, no extra runtime; users install QGIS and the plugin. Updates are a matter of updating the plugin in the plugin directory or via Plugin Manager.

- **Native integration:** Direct access to project, layers, and styling APIs; no serialisation or sync layer. The map and legend update immediately.

- **Single source of truth:** Styles live in QGIS. No plugin-specific config that can drift from what the user sees in the Layer Properties or Style Manager.

- **Familiar model:** Standard QGIS plugin pattern; existing docs and examples (toolbar, dialogs, PyQGIS) apply.

## Weaknesses

- **Tied to QGIS and PyQGIS version:** API changes or removals in newer QGIS can break the plugin; version compatibility must be tracked and tested. The `qt_compat` shim mitigates this for known Qt5→Qt6 and QGIS 3→4 enum changes, but new API removals may still require updates.

- **Debugging and testing:** Full execution is inside QGIS; debugging requires attaching to the QGIS process or using the Python Console. Automated integration tests need a QGIS environment (e.g. headless or test runner that loads QGIS).

- **Limited to PyQGIS surface:** Cannot do anything that PyQGIS does not expose. Raster and other renderer types are out of scope for the current design.

- **No headless “apply” for CI:** End-to-end “apply palette” cannot be run in a normal CI job without launching QGIS or a QGIS Python runtime.

## Future recommendations

The list below is ordered for development: **lower effort and localized changes first**, then **theme-editor improvements in a sensible sequence** (behaviour before heavy layout restructuring), then **deeper symbology controls** that touch many renderer and symbol code paths. **Home tab palette UX** (items 6–7 below) is implemented; see “Home tab palette UX” under considerations.

1. **Support rule reordering** — *Assessment: low effort, high leverage.* Precedence is already defined by rule order; exposing up/down (or drag) in `ThemeEditorDialog` only reorders the in-memory list before save, with no schema migration. Do this first so users can fix overlaps without delete-and-recreate.

2. **Support rule toggling** — *Assessment: low–medium effort.* Add an optional per-rule `enabled` flag (default `true` for backward compatibility), skip disabled rules in `theme_engine` when applying, and add a checkbox on each rule widget. Builds naturally on stable ordering.

3. **Compact the Theme tab layout** — *Assessment: medium effort (iteration).* Tighten margins, scroll areas, and rule widget density in the main dialog and theme editor **after** reorder/toggle controls exist, so the final control set drives layout.

4. **Group rules by geometry type** — *Assessment: medium effort.* Segment the editor UI (sections, collapsible groups, or tabs) by point/line/polygon while keeping a clear, documented apply order (for example preserve a single linear rule list in JSON, or define how grouped UI maps to order). Easier to design once reorder and toggle are in place.

5. **Delete user-created ramps and themes** — *Assessment: low effort for ramps; theme file deletion is already implemented in the Theme tab.* Remaining work is chiefly removing user-saved colour ramps from `QgsStyle` and pruning the plugin’s saved-name list in `QSettings`, plus confirmation and any polish for “in use” cases. Goal: users can drop obsolete ramps and themes without manual profile edits, with clear behaviour when a definition is still referenced.

6. **Quick colour palette for single symbol layers** — **Done.** Home tab: quick swatches (sampled from ramp preview) and preset swatches (named palettes), applied via the single-symbol colour path.

7. **Expand palette controls from the Home tab** — **Done.** Intent palette combo, preset integration with ramp apply for classed layers and ramp-preview updates for single-symbol layers; see `palette_presets.py`.

8. **Improve styling quality-of-life controls** — *Assessment: high effort.* Line colour, line weight, and separate fill/line transparency require navigating `QgsSymbol` / sub-symbols across single, graduated, and categorized renderers, with many edge cases. Defer until core palette and theme flows are stable. Scope: line colour and weight plus separate fill/line alpha for faster cartographic tuning.
