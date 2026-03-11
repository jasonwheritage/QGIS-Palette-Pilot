# Palette Pilot - QGIS plugin
def classFactory(iface):
    from .palette_pilot import ColourPaletteToolPlugin

    return ColourPaletteToolPlugin(iface)
