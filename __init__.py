"""
KiCad Schematic Bring-Up Assistant Plugin
Automated PCB bring-up checklist generation
Version 1.0.0
"""

__version__ = "1.0.0"
__author__ = "name" #change later

try:
    from .bringup_plugin import SchematicBringUpPlugin
    

    def register():
        """Register the plugin with KiCad"""
        try:
            plugin = SchematicBringUpPlugin()
            plugin.register()
            return plugin
        except Exception as e:
            print(f"Error registering Bring-Up Assistant: {e}")
            return None
    
    _plugin_instance = register()
    
except ImportError as e:
    print(f"Failed to load Bring-Up Assistant plugin: {e}")
    _plugin_instance = None

__all__ = ['SchematicBringUpPlugin', 'register']