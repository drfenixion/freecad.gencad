# GenCAD Workbench - GUI initialization
# Defines the toolbar, menus and commands

import os
import FreeCAD
import FreeCADGui
from PySide import QtGui
from FreeCADGui import Workbench

# def attach_debugger():
#     try:
#         # For v0.21:
#         from addonmanager_utilities import get_python_exe
#     except (ModuleNotFoundError, ImportError, AttributeError):
#         # For v0.22/v1.0:
#         from freecad.utils import get_python_exe    
#     import debugpy
#     debugpy.configure(python=get_python_exe())
#     debugpy.listen(("0.0.0.0", 5678))
#     debugpy.wait_for_client()
#     debugpy.trace_this_thread(True)
#     debugpy.debug_this_thread()
#     print('DEBUG attached.')

# try:
#     attach_debugger()
# except:
#     from cadomatic.src.dependency_checker import pip_install
#     pip_install('debugpy')
#     try:
#         attach_debugger()
#     except:
#         pass

class GenCADWorkbench(Workbench):
    """
    GenCAD workbench object
    """
    Icon = os.path.join(FreeCAD.getUserAppDataDir(), "Mod", "freecad.gencad", "gencad_icon.svg")
    # Icon = """
    # /* XPM */
    # static char * genCAD_xpm[] = {
    # "16 16 3 1",
    # " 	c None",
    # ".	c #000000",
    # "+	c #00AA00",
    # "                ",
    # "    ........    ",
    # "  ..+++++++..   ",
    # " .++++...+++.   ",
    # " .++..  .....   ",
    # " .++.           ",
    # " .++.           ",
    # " .++.           ",
    # " .++.  ......   ",
    # " .++.  .++++.   ",
    # " .++.  .++++.   ",
    # " .++.    .++.   ",
    # " .++++...+++.   ",
    # "  ..++++++++.   ",
    # "    ........    ",
    # "                "};
    # """

    MenuText = "GenCAD"
    ToolTip = "GenCAD workbench: Generate CAD models from text descriptions"

    def Initialize(self):
        """This function is executed when FreeCAD starts"""
        from cadomatic.src.dependency_checker import deps_check_and_install
        deps_check_and_install(FreeCAD, FreeCADGui)

        # Import commands
        import GenCADCommands
        self.list = ["GenCAD_CreateModel", "GenCAD_ExportToMacro", "GenCAD_Settings"]  # A list of command names created in the line above
        self.appendToolbar("GenCAD Commands", self.list)  # creates a new toolbar with your commands
        self.appendMenu("GenCAD", self.list)  # creates a new menu

        FreeCAD.Console.PrintMessage("GenCAD workbench loaded\n")

    def Activated(self):
        """This function is executed when the workbench is activated"""
        return

    def Deactivated(self):
        """This function is executed when the workbench is deactivated"""
        return

    def ContextMenu(self, recipient):
        """This function is executed whenever the user right-clicks on screen"""
        # "recipient" will be either "view" or "tree"
        self.appendContextMenu("GenCAD", self.list)  # add commands to the context menu

    def GetClassName(self):
        # This function is mandatory if this is a full Python workbench
        # This is not a template, the returned string should be exactly "Gui::PythonWorkbench"
        return "Gui::PythonWorkbench"


# Create and register the workbench
wb = GenCADWorkbench()
FreeCADGui.addWorkbench(wb)
