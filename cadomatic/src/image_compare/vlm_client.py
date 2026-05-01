from src.load_environment import load_env
from langchain.schema import HumanMessage
from pathlib import Path
import os
import FreeCAD

# Determine the generated directory based on context
if "FreeCAD" in globals() or hasattr(os, 'path') and os.path.exists(os.path.join(FreeCAD.getUserAppDataDir(), "Mod", "freecad.gencad")):
