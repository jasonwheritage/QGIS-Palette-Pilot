# Changelog

All notable changes to Palette Pilot will be documented in this file.

## [Unreleased]

### Added
- **Auto/Manual apply mode** — new toggle on the Home tab lets users choose
  between Auto (live-apply on every selection change, existing behaviour) and
  Manual (changes are staged until the user clicks Apply). The setting persists
  across sessions.
- **Swatch selection** section — dedicated group between "Colour ramp selection"
  and "Colour selection" for clickable colour swatches derived from the active
  ramp.
- **Category-aware Apply button** — on categorized/graduated layers the Apply
  button now checks for selected legend nodes: if categories are selected it
  applies the single colour to those categories; otherwise it applies the ramp
  to the whole layer.
- **Legend selection preservation** — applying a single colour to selected
  categories no longer deselects the layer or jumps the selection back to the
  layer title.

### Changed
- Renamed "Colour ramp for classes" section to **Colour ramp selection**.
- Renamed "Colour picker" section to **Colour selection**.
- Saved-ramp and saved-colour changes now sync the colour/ramp button
  immediately (even in Manual mode) so the staged value is always visible.
- `qgisMaximumVersion` bumped from `3.99` to `4.00` in metadata.

### Removed
- **Intent palette** — the preset ramp-for-classes combo and its handler have
  been removed (was buggy).
- **Preset swatches** — the preset swatch combo, grid, and rebuild logic have
  been removed; swatches now derive exclusively from the active ramp.

### Fixed
- Single colour applied to all categories instead of only the selected ones on
  categorized/graduated layers.
- Saved ramps did not update the swatch grid when selected.

## [1.3.1] - 2025-01-01

- Bump version to 1.3.1.

## [1.3.0] - 2024-12-01

- Home tab: preset ramps, single-symbol swatches, ramp preview for single symbol.
- Delete saved single colours and user-saved colour ramps.
- Theme: rule reorder/toggle, compact UI, scroll-safe combos.
