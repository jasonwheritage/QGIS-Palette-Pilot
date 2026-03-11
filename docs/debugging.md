# Debugging the plugin

The plugin runs inside QGIS, so debugging is done against the QGIS process. See also [development.md](development.md#debugging).

## Requirement

The plugin must be **debuggable**: breakpoints, step-through, and inspection of plugin code when it runs in QGIS. At least one supported workflow should be documented and validated.

## Recommended: attach to QGIS

1. Start QGIS (with a test project if useful).
2. **Get QGIS’s Python path:** In QGIS, **Plugins → Python Console**, run:
   ```python
   import sys
   print(sys.executable)
   ```
3. **Install debugpy into that Python** (from a terminal):
   ```bash
   "<QGIS_PYTHON_PATH>" -m pip install debugpy
   ```
   Replace `<QGIS_PYTHON_PATH>` with the path from step 2 (e.g. on Windows something like `C:\Program Files\QGIS 3.44\bin\python3.exe`).
4. In the plugin code, at the point where you want to stop (e.g. start of `run()` or inside the apply function), add:
   ```python
   import debugpy
   debugpy.listen(5678)
   debugpy.wait_for_client()
   ```
5. Restart QGIS (or reload the plugin), then trigger the code path (e.g. click the plugin toolbar button). Execution will pause at `wait_for_client()`.
6. In your IDE (VS Code / Cursor): create a **Python: Attach** launch configuration that attaches to `localhost:5678`. Start the debugger in attach mode. Once attached, execution continues and you can set breakpoints and step.
7. **Document your environment:** Note your OS, QGIS version (e.g. 3.44.x), and any path differences so others can reproduce.

## Alternative: QGIS Python Console

For quick checks without a full attach setup:

- **Plugins → Python Console**
- Import the plugin module or run snippets that call into the plugin.
- Use `print()` or logging to inspect state.

Not full breakpoint debugging but sufficient for many issues.

## Logging

The plugin logs via `QgsMessageLog` or Python `logging`. To view logs:

- **View → Panels → Log Messages** (ensure the panel is open).
- Select the appropriate log level (e.g. Info, Warning, Debug) and the plugin’s log channel if applicable.

For user-reported issues, document how to enable **debug** level so users can share detailed logs.
