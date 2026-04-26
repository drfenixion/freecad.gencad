import importlib.util
import subprocess
import sys
import re
import os
import site
from pathlib import Path
from PySide import QtWidgets, QtCore, QtGui
import importlib.metadata
import importlib.util

try:
    from addonmanager_utilities import get_python_exe
except (ModuleNotFoundError, ImportError, AttributeError):
    from freecad.utils import get_python_exe


class DependencyInstallDialog(QtWidgets.QDialog):
    def __init__(self, parent, dependencies):
        super().__init__(parent)
        self.setWindowTitle("Installing Dependencies")
        self.resize(400, 300)
        # Make dialog modal within FreeCAD (stays on top of FreeCAD, minimizes with FreeCAD)
        self.setWindowModality(QtCore.Qt.WindowModal)
        self.dependencies = dependencies
        self.setup_ui()

    def setup_ui(self):
        layout = QtWidgets.QVBoxLayout()
        self.list_widget = QtWidgets.QListWidget()
        for dep in self.dependencies:
            item = QtWidgets.QListWidgetItem(dep)
            self.list_widget.addItem(item)
        layout.addWidget(self.list_widget)
        self.progress_bar = QtWidgets.QProgressBar()
        self.progress_bar.setRange(0, len(self.dependencies))
        layout.addWidget(self.progress_bar)
        self.setLayout(layout)

    def update_status(self, index, status):
        item = self.list_widget.item(index)
        if status == "installing":
            item.setText(f"{self.dependencies[index]} (installing...)")
            item.setForeground(QtGui.QColor("blue"))
        elif status == "installed":
            item.setText(f"{self.dependencies[index]} - installed")
            item.setForeground(QtGui.QColor("green"))
            self.progress_bar.setValue(index + 1)

def get_dependencies_from_pyproject(pyproject_path, dep_category="dependencies = ["):
    deps = []
    in_dependencies = False
    with open(pyproject_path, "r") as f:
        for line in f:
            if line.strip() == dep_category:
                in_dependencies = True
                continue
            if in_dependencies:
                if line.strip() == "]":
                    break
                match = re.search(r'"([^">=<~]+)', line)
                if match:
                    deps.append(match.group(1))
    return deps

def add_freecad_python_paths():
    major = sys.version_info.major
    minor = sys.version_info.minor
    
    pythonPackagesPath = f'~/.local/share/FreeCAD/AdditionalPythonPackages/py{major}{minor}'
    pythonPackagesPath = Path(pythonPackagesPath).expanduser().absolute()
    if not os.path.exists(pythonPackagesPath):
        os.makedirs(pythonPackagesPath)    
    if pythonPackagesPath.exists() and (str(pythonPackagesPath) not in sys.path):
        sys.path.append(str(pythonPackagesPath))

    return pythonPackagesPath

def check_dependencies(dependencies):
    add_freecad_python_paths()
    return get_missing_dependencies(dependencies)

def get_missing_dependencies(dependencies):
    missing = []
    for dep in dependencies:
        try:
            dist = importlib.metadata.distribution(dep)
            
            top_level = dist.read_text('top_level.txt')
            
            if not top_level:
                continue
                
            module_names = [name.strip() for name in top_level.splitlines() if name.strip()]
            
            found = False
            for mod_name in module_names:
                if importlib.util.find_spec(mod_name) is not None:
                    found = True
                    break
            
            if not found:
                missing.append(dep)
                
        except importlib.metadata.PackageNotFoundError:
            missing.append(dep)
            
    return missing

def pip_install(pkg_name):
    python_exe = get_python_exe()

    pythonPackagesPath = add_freecad_python_paths()

    if pythonPackagesPath.exists() and (str(pythonPackagesPath) not in sys.path):
        sys.path.append(str(pythonPackagesPath))
        
    p = subprocess.Popen(
        [python_exe, "-m", "pip", "install", "--disable-pip-version-check", "--target", pythonPackagesPath, pkg_name],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    
    for line in iter(p.stdout.readline, b''):
        if line:
            print(line.decode("utf-8"), end="")
    print()

    for err in iter(p.stderr.readline, b''):
        if err:
            print(err.decode("utf-8"), end="")
    print()

    p.stdout.close()
    p.stderr.close()
    p.wait(timeout=1200)

def ask_and_install_dependencies(parent, dependencies, title = "Missing Dependencies", description="GenCAD workbench is missing the following dependencies"):
    if not dependencies:
        return True
    
    msg = f"{description}:\n{', '.join(dependencies)}\n\nDo you want to install them now?"
    reply = QtWidgets.QMessageBox.question(
        parent,
        title,
        msg,
        QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
    )
    
    if reply == QtWidgets.QMessageBox.Yes:
        dialog = DependencyInstallDialog(parent, dependencies)
        dialog.show()
        
        # Use QThread to perform installation without blocking GUI
        from PySide.QtCore import QThread, Signal
        
        class InstallThread(QThread):
            progress = Signal(int, str)
            finished = Signal(bool, str)
            
            def __init__(self, dependencies):
                super().__init__()
                self.dependencies = dependencies
                
            def run(self):
                try:
                    for i, dep in enumerate(self.dependencies):
                        self.progress.emit(i, "installing")
                        pip_install(dep)
                        self.progress.emit(i, "installed")
                    self.finished.emit(True, "Success")
                except Exception as e:
                    self.finished.emit(False, str(e))
        
        thread = InstallThread(dependencies)
        thread.progress.connect(dialog.update_status)
        thread.finished.connect(lambda success, msg: (
            dialog.accept() if success else QtWidgets.QMessageBox.critical(parent, "Error", f"Failed: {msg}"),
            QtWidgets.QMessageBox.information(parent, "Success", "Dependencies installed successfully.") if success else None
        ))
        thread.start()
        
        # Start dialog event loop
        return dialog.exec_() == QtWidgets.QDialog.Accepted
    
    QtWidgets.QMessageBox.information(parent, "Canceled", "Dependencies installation was canceled by user.")
    return False

def deps_check_and_install(FreeCAD, FreeCADGui, notice_if_already_installed=False):
        # Check dependencies
        import sys
        import os
        from PySide import QtWidgets
        # Add path to project root to import cadomatic
        base_path = os.path.join(FreeCAD.getUserAppDataDir(), "Mod", "GenCAD")
        sys.path.append(base_path)
        
        try:
           
            # dynamically add module to sys.path
            add_freecad_python_paths()

            pyproject_path = os.path.join(base_path, "cadomatic", "pyproject.toml")
            main_deps = get_dependencies_from_pyproject(pyproject_path)
            missing = check_dependencies(main_deps)
            
            all_installed = True
            
            if missing:
                all_installed = False
                if not ask_and_install_dependencies(FreeCADGui.getMainWindow(), missing):
                    FreeCAD.Console.PrintWarning("GenCAD: Some dependencies are not installed.\n")

            rag_deps = get_dependencies_from_pyproject(pyproject_path, dep_category='rag = [')
            missing = check_dependencies(rag_deps)
            
            if missing:
                all_installed = False
                if not ask_and_install_dependencies(FreeCADGui.getMainWindow(), missing,
                                                    title='OPTIONAL: RAG missing dependencies.',
                                                    description="GenCAD workbench is missing the following dependencies (optional but to big (~2.8Gb), required only for RAG)"):
                    FreeCAD.Console.PrintWarning("GenCAD: Some dependencies are not installed.\n")
            
            if notice_if_already_installed and all_installed:
                QtWidgets.QMessageBox.information(FreeCADGui.getMainWindow(), "Dependencies", "All dependencies are already installed.")
        except Exception as e:
            FreeCAD.Console.PrintError(f"GenCAD: Error checking dependencies: {str(e)}\n")