# Installation

How to install the Palette Pilot plugin and how to find your QGIS plugin directory.

**Quick path (default profile):** Windows `%APPDATA%\QGIS\QGIS3\profiles\default\python\plugins\` · macOS `~/Library/Application Support/QGIS/QGIS3/profiles/default/python/plugins/` · Linux `~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/`

## Finding your plugin directory

QGIS loads Python plugins from a **plugin directory** inside the active **profile**. You need the path to that folder (e.g. to copy the plugin into it or to run the dev install script).

### Method 1: From QGIS (most reliable)

1. Open QGIS.
2. Go to **Plugins → Manage and Install Plugins**.
3. Click **Installed** (or **Settings** in some versions).
4. Look for an option such as **Open plugin directory** / **Show plugin folder** (if available in your QGIS version). That opens your plugin directory in the file manager.

If your QGIS build does not show that button:

### Method 2: Python Console

1. In QGIS: **Plugins → Python Console**.
2. Run:

   ```python
   import os
   from qgis.core import QgsApplication
   # Path to the active profile folder
   profile_path = QgsApplication.qgisSettingsDirPath()
   # Plugin directory is: <profile_path>/python/plugins
   plugin_dir = os.path.join(profile_path, "python", "plugins")
   print(plugin_dir)
   ```

3. Copy the printed path. That is where you must place the `palette_pilot` folder (or run the dev script with this path).

### Method 3: Standard paths by OS and profile

If you use the **default** profile and have not moved QGIS data:

| OS      | Plugin directory (default profile) |
|---------|-------------------------------------|
| Windows | `%APPDATA%\QGIS\QGIS3\profiles\default\python\plugins\` |
| macOS   | `~/Library/Application Support/QGIS/QGIS3/profiles/default/python/plugins/` |
| Linux   | `~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/` |

- **Windows:** Press `Win + R`, type `%APPDATA%\QGIS\QGIS3\profiles\default\python\plugins`, press Enter to open that folder.
- **macOS / Linux:** Replace `~` with your home directory. If you use a **named profile** (e.g. “testing”), replace `default` with that profile name (e.g. `profiles/testing/python/plugins/`).

### Multiple profiles

If you use **Settings → User Profiles** and a profile other than “default”, use that profile name in the path:  
`.../profiles/<your_profile_name>/python/plugins/`.

---

## Install from folder (manual copy)

1. Locate your plugin directory (see above).
2. Copy the **entire** `palette_pilot` folder (the one that contains `__init__.py` and `metadata.txt`) into the plugin directory. You should end up with:
   - `.../plugins/palette_pilot/__init__.py`
   - `.../plugins/palette_pilot/metadata.txt`
   - etc.
3. In QGIS: **Plugins → Manage and Install Plugins → Installed** → enable **Palette Pilot**.

---

## Install from zip

Useful for distributing the plugin or installing from a release.

1. Obtain a **zip of the plugin** that contains the `palette_pilot` folder at the top level (e.g. the repo zipped, or a release asset). The zip must **not** add an extra parent folder (e.g. `colour_exploration-master`) unless that folder itself contains `palette_pilot`.
2. In QGIS: **Plugins → Manage and Install Plugins**.
3. Switch to **Install from ZIP** (or **Not installed** and use the “Install from ZIP” button).
4. Choose the zip file. QGIS will unpack it into your plugin directory. If the zip contains only the contents of `palette_pilot` (no wrapper folder), you may need to rename the extracted folder to `palette_pilot` so the folder name matches what QGIS expects.
5. **Recommended:** Zip the **contents** of the repo so that the zip has a single top-level entry `palette_pilot/` (with `__init__.py`, `metadata.txt`, etc. inside it). Then “Install from ZIP” will create `.../plugins/palette_pilot/` correctly.
6. Go to **Installed** and enable **Palette Pilot**.

---

## Development: install via script (copy or symlink)

For development you can **copy** or **symlink** the plugin from the repo into the QGIS plugin directory so that:
- **Copy:** You run the script after pulling changes to refresh the plugin in QGIS (or use “Reload” in Plugin Manager if your QGIS supports it).
- **Symlink:** Edits in the repo are used immediately by QGIS (no copy step); reload the plugin in QGIS after code changes.

A small script is provided so you don’t have to locate the plugin path or copy files by hand each time.

- **Script:** [../scripts/install_plugin_for_dev.py](../scripts/install_plugin_for_dev.py)
- **Usage:** See [Development workflow → Installing the plugin for development](development.md#installing-the-plugin-for-development) in the development doc.

You can run the script from the repo root, optionally setting the plugin directory (e.g. from Method 2 above):

```bash
# Use default plugin path for your OS (default profile)
python3 scripts/install_plugin_for_dev.py

# Use a specific plugin directory (e.g. from Python Console output)
set QGIS_PLUGINS_PATH=C:\Users\You\AppData\Roaming\QGIS\QGIS3\profiles\default\python\plugins
python3 scripts/install_plugin_for_dev.py

# Prefer symlink (Unix; on Windows may require admin)
python3 scripts/install_plugin_for_dev.py --symlink
```

Details and options are in [development.md](development.md#installing-the-plugin-for-development).
