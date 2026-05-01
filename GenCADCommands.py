# GenCADCommands.py
# Defines the commands for the GenCAD workbench

import time
import uuid
import FreeCAD
import FreeCADGui
from PySide import QtCore, QtGui, QtWidgets
import os
import sys
import Part
import Sketcher
import PartDesign
from FreeCAD import Vector
import traceback

# Add the CADomatic project path to sys.path so we can import modules
cadomatic_path = os.path.join(FreeCAD.getUserAppDataDir(), "Mod", "freecad.gencad", "cadomatic")
sys.path.insert(0, cadomatic_path)

# Import dialogs
from GenCADDialog import show_genCAD_dialog_with_mode
from GenCADProgressDialog import run_generation_with_gui

# Define paths for generated files
GUI_SNIPPET = """
import FreeCADGui as Gui
import time
time.sleep(0.1)  # allow GUI to load
Gui.activeDocument().activeView().viewAxometric()
Gui.SendMsgToActiveView("ViewFit")
"""


def _get_gen_dir() -> str:
    """Get the generated files directory path."""
    return os.path.join(FreeCAD.getUserAppDataDir(), "Mod", "freecad.gencad", "cadomatic", "generated")


def _get_gen_script_path() -> str:
    """Get the path to the generated result script."""
    return os.path.join(_get_gen_dir(), "result_script.py")


def _get_log_file_path() -> str:
    """Get the path to the last run log file."""
    return os.path.join(_get_gen_dir(), "last_run_log.txt")


def _ensure_gen_dir() -> str:
    """Ensure the generated directory exists and return its path."""
    gen_dir = _get_gen_dir()
    os.makedirs(gen_dir, exist_ok=True)
    return gen_dir


screenshot_code = f"""
import FreeCADGui as Gui
import time
import os
time.sleep(3)  # allow GUI to load
screenshot_path = os.path.join("{_get_gen_dir()}", "screenshot.png")
view = Gui.ActiveDocument.ActiveView
view.saveImage(screenshot_path, 720, 480, 'White')
print("📸 Screenshot saved at " + screenshot_path)
"""


def _clean_code_fences(code: str) -> str:
    """Remove markdown code fences and language prefix."""
    if code.startswith("```"):
        code = code.strip("`\n ")
        if code.lower().startswith("python"):
            code = code[len("python"):].lstrip()
    return code


def _make_result(stdout: str = "", stderr: str = "", returncode: int = 0):
    """Create a simple result object."""
    class Result:
        def __init__(self):
            self.stdout = stdout
            self.stderr = stderr
            self.returncode = returncode
    return Result()


def _get_model_name(llm_backend: str) -> str:
    """Get the model name from config based on LLM backend."""
    from GenCADConfig import config
    model_map = {
        "Ollama": ('ollama_model', 'gemini-3-flash-preview:cloud'),
        "OpenRouter": ('openrouter_model', 'google/gemini-3-flash-preview'),
        "RouterAIru": ('routerairu_model', 'google/gemini-3-flash-preview'),
    }
    key, default = model_map.get(llm_backend, (None, 'Unknown'))
    return config.get_setting(key, default) if key else 'Unknown'


def _set_llm_backend_env(llm_backend: str):
    """Set environment variable for the selected LLM backend."""
    backends = {"OpenRouter": "USE_OPENROUTER", "Ollama": "USE_OLLAMA", "RouterAIru": "USE_ROUTERAIRU"}
    active = backends.get(llm_backend, "USE_OPENROUTER")
    for key in backends.values():
        os.environ.pop(key, None)
    os.environ[active] = "True"


def _make_log_fn(log_callback=None):
    """Create a log function that uses the callback or FreeCAD console."""
    def log(msg):
        if log_callback:
            log_callback(msg)
        else:
            FreeCAD.Console.PrintMessage(msg + "\n")
    return log


def get_selected_objects_python():
    """Export selected objects to Python code using ObjectsToPython module.

    Returns:
        str: Python code representing the selected objects, or None if no objects selected
    """
    import FreeCADGui
    import sys
    
    try:
        # Get selected objects
        selection = FreeCADGui.Selection.getSelection()
        if not selection:
            return None

        # Import the objects_to_python module from utils
        utils_path = os.path.join(FreeCAD.getUserAppDataDir(), "Mod", "freecad.gencad", "utils")
        if not os.path.exists(utils_path):
            FreeCAD.Console.PrintError(f"Utils path not found: {utils_path}\n")
            return None
        
        sys.path.insert(0, utils_path)
        
        try:
            import objects_to_python as o2p
            import FreeCAD as app
            
            # Create a temporary document for export
            temp_doc = app.newDocument("TempExport")
            temp_doc_name = temp_doc.Name
            
            # Copy selected objects to temp document
            copied_objects = []
            for obj in selection:
                try:
                    # Copy the object
                    app.setActiveDocument(temp_doc_name)
                    copied_obj = app.activeDocument().copyObject(obj, True)
                    copied_objects.append(copied_obj)
                except Exception as e:
                    FreeCAD.Console.PrintWarning(f"Could not copy object {obj.Name}: {str(e)}\n")
            
            if not copied_objects:
                app.closeDocument(temp_doc_name)
                return None
            
            # Capture the output from exportObjectsToPython
            # We need to mock the dialog's textEdit to capture the output
            class MockTextEdit:
                def __init__(self):
                    self.lines = []
                def append(self, line):
                    self.lines.append(line)
            
            class MockForm:
                def __init__(self):
                    self.textEdit = MockTextEdit()
            
            class MockDialog:
                def __init__(self):
                    self.form = MockForm()
            
            # Save original dialog
            original_dialog = getattr(o2p, 'dialog', None)
            
            # Create and set mock dialog
            mock_dialog = MockDialog()
            o2p.dialog = mock_dialog
            
            # Export to Python - this will populate mock_dialog.form.textEdit.lines
            o2p.exportObjectsToPython(temp_doc, create_doc_in_result_script=True)
            
            # Get the generated code
            python_code = '\n'.join(mock_dialog.form.textEdit.lines)
            
            # Restore original dialog
            if original_dialog:
                o2p.dialog = original_dialog
            else:
                if hasattr(o2p, 'dialog'):
                    delattr(o2p, 'dialog')
            
            # Clean up temp document
            app.closeDocument(temp_doc_name)
            
            # Remove utils from path
            sys.path.remove(utils_path)
            
            return python_code
            
        except ImportError as e:
            FreeCAD.Console.PrintError(f"Could not import objects_to_python: {str(e)}\n")
            return None

    except Exception as e:
        FreeCAD.Console.PrintError(f"Error exporting selected objects: {str(e)}\n")
        return None
    

def get_selected_objects_python_without_tmp_doc():
    """Export selected objects to Python code using ObjectsToPython module.

    Returns:
        str: Python code representing the selected objects, or None if no objects selected
    """
    import FreeCADGui
    import sys
    
    try:
        # Get selected objects
        selection = FreeCADGui.Selection.getSelection()
        if not selection:
            return None

        # Import the objects_to_python module from utils
        utils_path = os.path.join(FreeCAD.getUserAppDataDir(), "Mod", "freecad.gencad", "utils")
        if not os.path.exists(utils_path):
            FreeCAD.Console.PrintError(f"Utils path not found: {utils_path}\n")
            return None
        
        sys.path.insert(0, utils_path)
        
        try:
            import objects_to_python as o2p
            import FreeCAD as app
            
            # # Create a temporary document for export
            # temp_doc = app.newDocument("TempExport")
            # temp_doc_name = temp_doc.Name
            
            # # Copy selected objects to temp document
            # copied_objects = []
            # for obj in selection:
            #     try:
            #         # Copy the object
            #         app.setActiveDocument(temp_doc_name)
            #         copied_obj = app.activeDocument().copyObject(obj, True)
            #         copied_objects.append(copied_obj)
            #     except Exception as e:
            #         FreeCAD.Console.PrintWarning(f"Could not copy object {obj.Name}: {str(e)}\n")
            
            # if not copied_objects:
            #     app.closeDocument(temp_doc_name)
            #     return None
            
            # Capture the output from exportObjectsToPython
            # We need to mock the dialog's textEdit to capture the output
            class MockTextEdit:
                def __init__(self):
                    self.lines = []
                def append(self, line):
                    self.lines.append(line)
            
            class MockForm:
                def __init__(self):
                    self.textEdit = MockTextEdit()
            
            class MockDialog:
                def __init__(self):
                    self.form = MockForm()
            
            # Save original dialog
            original_dialog = getattr(o2p, 'dialog', None)
            
            # Create and set mock dialog
            mock_dialog = MockDialog()
            o2p.dialog = mock_dialog
            
            # Export to Python - this will populate mock_dialog.form.textEdit.lines
            o2p.exportObjectsToPython(app.activeDocument(), create_doc_in_result_script=True)
            
            # Get the generated code
            python_code = '\n'.join(mock_dialog.form.textEdit.lines)
            
            # Restore original dialog
            if original_dialog:
                o2p.dialog = original_dialog
            else:
                if hasattr(o2p, 'dialog'):
                    delattr(o2p, 'dialog')
            
            # Clean up temp document
            # app.closeDocument(app.activeDocument().Name)
            
            # Remove utils from path
            sys.path.remove(utils_path)
            
            return python_code
            
        except ImportError as e:
            FreeCAD.Console.PrintError(f"Could not import objects_to_python: {str(e)}\n")
            return None

    except Exception as e:
        FreeCAD.Console.PrintError(f"Error exporting selected objects: {str(e)}\n")
        return None


class FixLoopSignaler(QtCore.QObject):
    """Helper QObject with signal for thread-safe main thread invocation."""
    continue_signal = QtCore.Signal()
    verification_success_signal = QtCore.Signal()
    verification_failed_signal = QtCore.Signal()


class GenCAD_CreateModel:
    """Create a CAD model from text description"""

    def GetResources(self):
        return {
            'Pixmap': ':/icons/Std_DlgParameter.svg',
            'MenuText': 'Create Model from Text',
            'ToolTip': 'Generate or modify a CAD model from a text description'
        }

    def Activated(self):
        """Do something here"""
        # Show a dialog to get the user's description (non-modal)
        def on_dialog_complete(description, mode):
            if not description:
                FreeCAD.Console.PrintMessage("Model generation cancelled.\n")
                return

            # Use the active provider from settings instead of asking the user
            from GenCADConfig import config
            active_provider = config.get_setting('provider', 'OpenRouter')

            # For modify mode, get selected objects code
            selected_objects_code = None
            if mode == "modify":
                selected_objects_code = get_selected_objects_python()
                if not selected_objects_code:
                    FreeCAD.Console.PrintMessage("No objects selected for modification. Please select objects first.\n")
                    return

            # Show progress dialog with generation
            self.show_generation_dialog(description, active_provider, mode, selected_objects_code)

        show_genCAD_dialog_with_mode(on_dialog_complete)

    def show_generation_dialog(self, description, llm_backend, mode="new", selected_objects_code=None):
        """Show the progress dialog and start generation"""
        # Get FreeCAD main window as parent
        mw = FreeCADGui.getMainWindow()

        # Store dialog reference to prevent garbage collection
        self.generation_dialog = run_generation_with_gui(
            mw,
            description,
            lambda user_input, log_callback, dialog_ref: self.generate_model_with_log(user_input, llm_backend, log_callback, mode, selected_objects_code, dialog_ref),
            on_complete=self.on_generation_complete
        )

        # Store mode for later use
        self.operation_mode = mode

        # Show dialog modally
        self.generation_dialog.exec_()

    def generate_model_with_log(self, description, llm_backend, log_callback, mode="new", selected_objects_code=None, dialog_ref=None):
        """Generate model with logging callback.
        
        NOTE: This runs in a worker thread. Only LLM calls and file I/O should happen here.
        FreeCAD GUI operations must be deferred to the main thread.
        
        Args:
            dialog_ref: Reference to the progress dialog for cancellation checking
        """
        try:
            _set_llm_backend_env(llm_backend)

            mode_label = "Modify selected objects" if mode == "modify" else "Generate new model"
            log_callback(f"Mode: {mode_label}")

            result = self._generate_code(
                description=description,
                llm_backend=llm_backend,
                log_callback=log_callback,
                dialog_ref=dialog_ref,
                mode=mode,
                selected_objects_code=selected_objects_code,
            )

            if dialog_ref and not dialog_ref.is_running:
                log_callback("⚠ Generation cancelled by user")
                dialog_ref.set_status("Cancelled")
                return None

            if result:
                log_callback("Code generation completed!")
                log_callback("Executing script in main thread...")
                return result
            else:
                log_callback("Failed to generate model.")
                return False

        except Exception as e:
            log_callback(f"Error: {str(e)}")
            raise

    def on_generation_complete(self, result, error):
        """Called when generation completes. Executes the script in the main thread."""
        if result:
            # Get the log callback from the generation dialog
            log_callback = None
            if hasattr(self, 'generation_dialog') and self.generation_dialog:
                log_callback = self.generation_dialog.log
            
            # Execute the script in the main thread (GUI-safe) with fix loop
            self.execute_script_with_fix_loop(result, log_callback)
        elif error:
            FreeCAD.Console.PrintError(f"Model generation failed: {error}\n")

    def generate_model(self, description, llm_backend, log_callback=None, dialog_ref=None):
        """Generate CAD code. Kept for backward compatibility."""
        return self._generate_code(description, llm_backend, log_callback, dialog_ref, mode="new")

    def modify_model(self, description, llm_backend, log_callback=None, selected_objects_code=None, dialog_ref=None):
        """Modify existing selected objects. Kept for backward compatibility."""
        return self._generate_code(
            description, llm_backend, log_callback, dialog_ref,
            mode="modify", selected_objects_code=selected_objects_code,
        )

    def _generate_code(self, description, llm_backend, log_callback=None, dialog_ref=None, mode="new", selected_objects_code=None):
        """Unified code generation method. Runs in a worker thread.

        Args:
            description: User description (for new) or modification request (for modify)
            llm_backend: LLM backend to use
            log_callback: Optional callback for logging
            dialog_ref: Progress dialog reference for cancellation
            mode: "new" for generation, "modify" for modification
            selected_objects_code: Python code of selected objects (modify mode only)

        Returns:
            str: Path to generated script, or False if failed
        """
        log = _make_log_fn(log_callback)

        try:
            self._current_description = description
            action = "Generating" if mode == "new" else "Modifying"
            log(f"{action} model for: {description}")
            log(f"Using LLM backend: {llm_backend}")
            log(f"Using LLM model: {_get_model_name(llm_backend)}")

            if mode == "modify":
                if not selected_objects_code:
                    log("No objects code provided for modification.")
                    return False
                log(f"Processing {len(selected_objects_code)} characters of selected objects code")

            if dialog_ref and not dialog_ref.is_running:
                return False

            if mode == "modify":
                log("Requesting modification code from LLM...")
                result = self.modify_with_cadomatic(description, selected_objects_code, llm_backend, dialog_ref)
            else:
                log("Requesting code from LLM...")
                result = self.generate_with_default_cadomatic(description, dialog_ref)

            if dialog_ref and not dialog_ref.is_running:
                return False

            if result.returncode != 0:
                label = "initial" if mode == "new" else "modification"
                log(f"Failed to generate {label} code. Error: " + result.stderr)
                return False

            generated_code = _clean_code_fences(result.stdout)

            gen_script_path = _get_gen_script_path()
            with open(gen_script_path, 'w') as f:
                f.write(generated_code)

            label = "Initial" if mode == "new" else "Modification"
            log(f"{label} code written to {gen_script_path}")
            return gen_script_path

        except Exception as e:
            log(f"Error {'generating' if mode == 'new' else 'modifying'} model: {str(e)}")
            import traceback
            log(f"Traceback: {traceback.format_exc()}")
            return False

    def generate_with_default_cadomatic(self, description, dialog_ref=None, reset_conversation=True):
        """Generate CAD code using the default CADomatic approach - calls LLM directly
        
        Args:
            dialog_ref: Reference to the progress dialog for cancellation checking
            reset_conversation: Whether to reset conversation history (default True for new generations)
        """
        global cadomatic_path
        
        # Add cadomatic to path
        sys.path.insert(0, cadomatic_path)
        
        try:
            from src.llm_client import prompt_llm, reset_memory
            
            # Reset conversation history only for new generation (not fix loop iterations)
            if reset_conversation:
                reset_memory()
            
            # Generate the CAD script
            generated_code = prompt_llm(description)
            
            return _make_result(stdout=generated_code)
            
        except Exception as e:
            error_msg = f"Generation failed with exception: {str(e)}"
            FreeCAD.Console.PrintError(f"{error_msg}\n")
            return _make_result(stderr=error_msg, returncode=1)

    def modify_with_cadomatic(self, description, existing_code, llm_backend, dialog_ref=None):
        """Generate modification code using CADomatic with modify prompt - calls LLM directly.
        
        Args:
            dialog_ref: Reference to the progress dialog for cancellation checking
        """
        global cadomatic_path
        
        # Add cadomatic to path
        sys.path.insert(0, cadomatic_path)
        
        try:
            from src.llm_client import prompt_llm_with_context, reset_memory
            
            # Reset conversation history for new modification session
            reset_memory()
            
            # Load the modify instruction prompt
            prompt_path = os.path.join(cadomatic_path, "prompts", "modify_instruction.txt")
            with open(prompt_path, 'r') as f:
                base_prompt = f.read()
            
            # Build the full prompt
            full_prompt = f"""{base_prompt}

Current FreeCAD Python code (exported via ObjectsToPython):
{existing_code}

User modification request:
{description}

Respond with the modified FreeCAD Python code only.
"""
            
            # Generate the modified CAD script
            generated_code = prompt_llm_with_context(full_prompt, description)
            
            return _make_result(stdout=generated_code)
            
        except Exception as e:
            error_msg = f"Modification failed with exception: {str(e)}"
            FreeCAD.Console.PrintError(f"{error_msg}\n")
            return _make_result(stderr=error_msg, returncode=1)

    def execute_script(self, script_path, mode="new"):
        """Execute the generated FreeCAD script in the main thread.
        
        This method MUST be called from the main thread as it interacts with FreeCAD GUI.
        
        Args:
            script_path: Path to the script to execute
            mode: Operation mode - "new" for new model, "modify" for modification
        
        Returns:
            tuple: (success: bool, console_output: str)
        """
        # Capture console messages before execution
        captured_before = self._get_console_messages()
        try:
            # Run the script using FreeCAD's exec function
            with open(script_path, 'r') as f:
                script_content = f.read()

            # script_content += GUI_SNIPPET # focus to object

            # Create a new document for execution
            doc_name = "GenCAD_" + str(uuid.uuid4())[:8]
            doc = FreeCAD.newDocument(doc_name)
            FreeCAD.setActiveDocument(doc.Name)

            # Execute the script in the FreeCAD namespace
            exec_namespace = {
                'App': FreeCAD,
                'Gui': FreeCADGui,
                'FreeCAD': FreeCAD,
                'FreeCADGui': FreeCADGui,
                'Part': Part,
                'Sketcher': Sketcher,
                'PartDesign': PartDesign,
                'Vector': FreeCAD.Vector,
                'Rotation': FreeCAD.Rotation,
                'Placement': FreeCAD.Placement,
                'doc': doc,
                'math': __import__('math'),
            }
            
            exec(script_content, exec_namespace)

            # Recompute the document
            doc.recompute()
            QtWidgets.QApplication.processEvents() # important or some error will not catched

            # Capture console messages after execution and extract new ones
            captured_after = self._get_console_messages()
            new_messages = self._extract_new_messages(captured_before, captured_after)
            
            if new_messages:
                raise Exception(new_messages)

            FreeCAD.closeDocument(doc.Name)

            return True, new_messages

        except Exception as e:
            error_details = traceback.format_exc()
            # exc_info returns a tuple (type, value, traceback)
            exc_type, exc_value, exc_tb = sys.exc_info()
            # Extract information about the last error location
            tb_last = traceback.extract_tb(exc_tb)[-1]  # last element - error location
            filename = tb_last.filename
            line_no = tb_last.lineno
            function_name = tb_last.name
            code_line = tb_last.line  # the code fragment itself
            # 2. Full call stack (Python 3.11+ will automatically add ^^^^^)
            tb_str = traceback.format_exc()
            # 3. Format the output
            # Note: standard Python writes "TypeError:", but in your example "<class 'TypeError'>:"
            # Replace only if exact match is needed:
            exc_type = type(sys.exc_info()[1])
            tb_str = tb_str.replace(f"{exc_type.__name__}:", f"<class '{exc_type.__name__}'>:")
                  
            # error_msg = f"Error executing script: {str(e)}"
            # FreeCAD.Console.PrintError(f"{error_msg}\n")
            
            # Capture console messages after execution and extract new ones
            captured_after = self._get_console_messages()
            new_messages = self._extract_new_messages(captured_before, captured_after)
            new_messages = new_messages + '\n' + error_details
            
            # Close the temporary document
            try:
                FreeCAD.closeDocument(doc.Name)
            except Exception:
                pass  # Document might not exist if creation failed
            
            return False, new_messages

    def _get_console_messages(self):
        """Get all console messages currently in the FreeCAD report view."""
        try:
            # Try to get messages from the report view if available
            mw = FreeCADGui.getMainWindow()
            report_view = mw.findChild(QtWidgets.QTextEdit, "Report view")
            if report_view:
                return report_view.toPlainText()
        except Exception:
            pass
        return ""

    def _extract_new_messages(self, before, after):
        """Extract new messages that appeared after execution."""
        if not before:
            return after
        # Get the part of 'after' that's not in 'before'
        if after.startswith(before):
            return after[len(before):]
        return after

    def execute_script_with_fix_loop(self, script_path, log_callback=None):
        """Execute the script and run the fix loop if there are errors.
        
        This method runs on the main thread for execution, but triggers
        background thread for LLM fix calls.
        
        Args:
            script_path: Path to the script to execute
            log_callback: Optional callback for logging messages to the generation dialog
        """
        from GenCADConfig import config
        
        MAX_RETRIES = config.get_setting('max_retries_of_fix_script', 5)
        
        # Store state for the fix loop
        self._fix_loop_state = {
            'script_path': script_path,
            'attempt': 0,
            'max_retries': MAX_RETRIES,
            'generated_code': '',
            'log_callback': log_callback,
            'cancelled': False,  # Flag for cancellation
        }
        
        # Create signaler for thread-safe main thread invocation
        self._fix_loop_signaler = FixLoopSignaler()
        self._fix_loop_signaler.continue_signal.connect(self._run_fix_loop_iteration)
        self._fix_loop_signaler.verification_success_signal.connect(self._on_verification_success)
        self._fix_loop_signaler.verification_failed_signal.connect(self._on_verification_failed)
        
        # Read the initial script
        with open(script_path, 'r') as f:
            self._fix_loop_state['generated_code'] = f.read()
        
        # Connect cancel signal from progress dialog
        if hasattr(self, 'generation_dialog') and self.generation_dialog is not None:
            self.generation_dialog.continue_spinner()
            # Connect cancel signal (Qt handles duplicate connections gracefully)
            self.generation_dialog.cancel_requested_signal.connect(self._on_cancel_requested)
        
        # Start the fix loop
        self._run_fix_loop_iteration()

    def _on_cancel_requested(self):
        """Handle cancel request from the progress dialog."""
        state = self._fix_loop_state
        state['cancelled'] = True

    def _on_verification_success(self):
        """Handle successful LLM verification (called from main thread via signal)."""
        self._stop_fix_loop_progress(success=True)
        exec(GUI_SNIPPET)

    def _on_verification_failed(self):
        """Handle failed LLM verification (called from main thread via signal)."""
        self._stop_fix_loop_progress(success=False)

    def _run_fix_loop_iteration(self):
        """Run one iteration of the fix loop."""
        # Process pending Qt events to allow Cancel button signal to be received
        QtWidgets.QApplication.processEvents()
        
        state = self._fix_loop_state
        log_callback = state.get('log_callback')
        
        # Check if cancel was requested
        if state.get('cancelled'):
            msg = "⚠ Fix loop cancelled by user"
            if log_callback:
                log_callback(msg)
            FreeCAD.Console.PrintMessage(f"{msg}\n")
            # Update status to Cancelled
            if hasattr(self, 'generation_dialog') and self.generation_dialog:
                self.generation_dialog.set_status("Cancelled")
            self._stop_fix_loop_progress(success=False)
            return
        
        state['attempt'] += 1
        attempt_num = state['attempt']
        
        # Log attempt to the generation dialog
        if log_callback:
            log_callback(f"▶ Attempt {attempt_num} executing script...")
        
        # Save the list of open document names before execution (excluding GenCAD_ ones)
        self._pre_execution_docs = self._get_open_document_names()
        
        # Execute the script (main thread), pass mode to keep doc open for modifications
        success, console_output = self.execute_script(state['script_path'], mode=getattr(self, 'operation_mode', 'new'))
        
        # Check for errors in console output
        has_errors = self._has_console_errors(console_output)
        
        if success and not has_errors:
            msg = f"✓ Attempt {attempt_num}: Script executed successfully!"
            if log_callback:
                log_callback(msg)
            FreeCAD.Console.PrintMessage(f"{msg}\n")

            # Check if any verification is enabled (optional feature)
            from GenCADConfig import config
            use_visual_verification = config.get_setting('use_part_visual_verification', False)
            use_code_verification = config.get_setting('use_part_verification', False)

            if use_visual_verification or use_code_verification:
                msg = "🔍 Launching part verification..."
                if log_callback:
                    log_callback(msg)
                FreeCAD.Console.PrintMessage(f"{msg}\n")
                self._verify_code_in_background()
                return
            else:
                # No verification needed - stop the spinner on successful execution
                self._stop_fix_loop_progress(success=True)
                exec(GUI_SNIPPET)
                return
        
        # There are errors - log them
        # Extract just the error lines for brevity using the same indicators as _has_console_errors
        error_indicators = [
            'Error', 'error', 'Exception', 'exception', 'Failed', 'failed',
            'Traceback', 'NameError', 'AttributeError', 'TypeError',
            'ValueError', 'SyntaxError', 'RuntimeError'
        ]
        error_lines = [line for line in console_output.split('\n') if any(indicator in line for indicator in error_indicators)]
        error_summary = '\n'.join(error_lines[-5:]) if error_lines else console_output[:300]
        
        # Ensure we always show some error information
        if not error_summary.strip():
            error_summary = "Check the Report View for details."
        
        msg = f"✗ Attempt {attempt_num}: Failed with errors:\n{error_summary}"
        if log_callback:
            log_callback(msg)
        FreeCAD.Console.PrintWarning(f"✗ Script test failed with errors:\n{console_output[:500]}...\n")
        
        # Close any remaining GenCAD documents from the failed attempt
        self._close_gencad_documents()
        
        # Close any new non-GenCAD documents that appeared during execution
        self._close_new_documents()
        
        if state['attempt'] >= state['max_retries']:
            msg = f"✗ Max retries ({state['max_retries']}) reached. Giving up."
            if log_callback:
                log_callback(msg)
            FreeCAD.Console.PrintError(f"{msg}\n")
            # Stop the spinner when max retries reached
            self._stop_fix_loop_progress(success=False)
            return
        
        # Need to fix the script - run LLM in background thread
        self._fix_script_in_background(console_output)

    def _stop_fix_loop_progress(self, success=True):
        """Stop the progress spinner when the fix loop completes (success or max retries).
        
        Args:
            success: If True, show success status; if False, show failure status.
        """
        if hasattr(self, 'generation_dialog') and self.generation_dialog:
            self.generation_dialog.stop_progress(success=success)

    def _has_console_errors(self, console_output):
        """Check if console output contains error messages."""
        error_indicators = [
            'Error', 'error', 'Exception', 'exception', 'Failed', 'failed',
            'Traceback', 'NameError', 'AttributeError', 'TypeError',
            'ValueError', 'SyntaxError', 'RuntimeError'
        ]
        for indicator in error_indicators:
            if indicator in console_output:
                return True
        return False

    def _check_cancel_and_stop(self, log_callback=None):
        """Check if cancel was requested and stop the fix loop.
        
        Returns:
            bool: True if cancelled, False otherwise.
        """
        state = self._fix_loop_state
        if state.get('cancelled'):
            msg = "⚠ Fix loop cancelled by user"
            if log_callback:
                log_callback(msg)
            FreeCAD.Console.PrintMessage(f"{msg}\n")
            # Update status to Cancelled
            if hasattr(self, 'generation_dialog') and self.generation_dialog:
                self.generation_dialog.set_status("Cancelled")
            return True
        return False
    
    def _close_gencad_documents(self):
        """Close any remaining GenCAD temporary documents after a failed attempt."""
        try:
            for doc in FreeCAD.listDocuments().values():
                if doc.Name.startswith("GenCAD_"):
                    FreeCAD.closeDocument(doc.Name)
        except Exception:
            pass

    def _get_open_document_names(self):
        """Get names of all open documents excluding GenCAD_ ones."""
        try:
            return {doc.Name for doc in FreeCAD.listDocuments().values() if not doc.Name.startswith("GenCAD_")}
        except Exception:
            return set()

    def _close_new_documents(self):
        """Close any new documents that appeared after execution (excluding GenCAD_ ones)."""
        try:
            current_docs = self._get_open_document_names()
            pre_execution_docs = getattr(self, '_pre_execution_docs', set())
            new_docs = current_docs - pre_execution_docs
            for doc_name in new_docs:
                FreeCAD.closeDocument(doc_name)
                break
        except Exception:
            pass

    def _fix_script_in_background(self, error_logs):
        """Call LLM to fix the script in a background thread."""
        import threading
        
        state = self._fix_loop_state
        description = getattr(self, '_current_description', '')
        generated_code = state['generated_code']
        log_callback = state.get('log_callback')
        
        # Build fix prompt
        fix_prompt = f"""
I want to make the following part using FreeCAD 1.0.1 python scripting

{description}

The following FreeCAD script was created but it failed during execution:

{generated_code}

Here is the error log:
{error_logs}

Please provide a corrected FreeCAD script. Keep the logic same, just correct the given error. Respond with valid FreeCAD 1.0.1 Python code only, no extra comments.
"""
        
        def worker():
            try:
                # Check if cancel was requested before starting
                if self._check_cancel_and_stop(log_callback):
                    return
                
                next_attempt = state['attempt'] + 1
                msg = f"⟳ Requesting LLM to code fix (attempt {next_attempt})..."
                if log_callback:
                    log_callback('')
                    log_callback("=" * 60)
                    log_callback(msg)
                    log_callback("=" * 60)
                FreeCAD.Console.PrintMessage("\n")
                FreeCAD.Console.PrintMessage(f"{msg}\n")
                
                # Call LLM directly
                result = self.generate_with_default_cadomatic(fix_prompt, reset_conversation=False)
                
                # Check if cancel was requested after LLM call
                if self._check_cancel_and_stop(log_callback):
                    return
                
                if result.returncode != 0:
                    msg = f"Failed to generate fixed code. Error: {result.stderr}"
                    if log_callback:
                        log_callback(msg)
                    FreeCAD.Console.PrintError(f"{msg}\n")
                    return
                
                fixed_code = _clean_code_fences(result.stdout)
                
                # Check if cancel was requested before saving
                if self._check_cancel_and_stop(log_callback):
                    return
                
                # Save fixed code
                state['generated_code'] = fixed_code
                with open(state['script_path'], 'w') as f:
                    f.write(fixed_code)
                
                msg = f"Fixed code written."
                if log_callback:
                    log_callback(msg)
                FreeCAD.Console.PrintMessage(f"{msg}\n")
                
                # Signal to run next iteration on main thread
                self._fix_loop_signaler.continue_signal.emit()
                
            except Exception as e:
                msg = f"Error in fix loop: {str(e)}"
                if log_callback:
                    log_callback(msg)
                FreeCAD.Console.PrintError(f"{msg}\n")
        
        thread = threading.Thread(target=worker, daemon=True)
        thread.start()

    def _capture_screenshots(self):
        """Capture screenshots from 7 standard views and return list of paths.
        
        Views: isometric, top, front, right, bottom, rear, left
        """
        import time
        gen_dir = _get_gen_dir()
        screenshot_paths = []
        
        # View directions for FreeCAD: (x, y, z) camera position relative to origin
        view_directions = {
            "isometric": (1, 1, 1),
            "top": (0, 0, 1),
            "front": (0, -1, 0),
            "right": (1, 0, 0),
            "bottom": (0, 0, -1),
            "rear": (0, 1, 0),
            "left": (-1, 0, 0),
        }
        
        try:
            
            view = FreeCADGui.ActiveDocument.ActiveView
            view.setAnimationEnabled(False)
            
            for view_name, direction in view_directions.items():
                # Set camera view direction
                view.setViewDirection(direction)
                # Small delay to allow view to update
                time.sleep(0.1)
                FreeCADGui.SendMsgToActiveView("ViewFit")
                time.sleep(0.1)
                screenshot_path = os.path.join(gen_dir, f"screenshot_{view_name}.png")
                view.saveImage(screenshot_path, 720, 480, 'White')
                screenshot_paths.append(screenshot_path)
                FreeCAD.Console.PrintMessage(f"📸 Screenshot saved at {screenshot_path}\n")
            return screenshot_paths
        except Exception as e:
            FreeCAD.Console.PrintError(f"Failed to capture screenshots: {str(e)}\n")
            return []
        finally:
            view.setAnimationEnabled(True)

    def _verify_code_in_background(self):
        """Run LLM verification on successfully executed code in a background thread.
        
        First runs visual verification (if enabled), then code verification (if enabled).
        """
        import threading

        state = self._fix_loop_state
        description = getattr(self, '_current_description', '')
        generated_code = state['generated_code']
        log_callback = state.get('log_callback')

        def worker():
            try:
                # Check if cancel was requested before starting
                if self._check_cancel_and_stop(log_callback):
                    return

                from GenCADConfig import config
                use_visual_verification = config.get_setting('use_part_visual_verification', False)
                use_code_verification = config.get_setting('use_part_verification', False)

                current_code = generated_code
                screenshot_path = None

                # Step 1: Visual verification (if enabled)
                if use_visual_verification:
                    msg = "=" * 60 + '\n' + "⟳ Running visual part verification..." + '\n' + "=" * 60
                    if log_callback:
                        log_callback(msg)
                    FreeCAD.Console.PrintMessage(f"{msg}\n")

                    # Capture screenshots from 4 views in main thread (GUI operation)
                    screenshot_paths = self._capture_screenshots()

                    if screenshot_paths:
                        from cadomatic.src.part_verify import verify_part_visual
                        visual_result = verify_part_visual(screenshot_paths, description, current_code)

                        # Check if cancel was requested after verification
                        if self._check_cancel_and_stop(log_callback):
                            return

                        if not visual_result['verified']:
                            msg = "⚠ Visual verification failed: geometry needs corrections."
                            if log_callback:
                                log_callback(msg)
                            FreeCAD.Console.PrintMessage(f"{msg}\n")

                            corrected_code = visual_result['corrected_code']
                            if corrected_code:
                                current_code = corrected_code
                                state['generated_code'] = corrected_code
                                with open(state['script_path'], 'w') as f:
                                    f.write(corrected_code)

                                msg = "Corrected code written by visual verification."
                                if log_callback:
                                    log_callback(msg)
                                FreeCAD.Console.PrintMessage(f"{msg}\n")

                                # Signal to run next iteration on main thread (test the corrected code)
                                self._fix_loop_signaler.continue_signal.emit()
                                return
                            else:
                                msg = "⚠ Visual verification returned no corrected code."
                                if log_callback:
                                    log_callback(msg)
                                FreeCAD.Console.PrintMessage(f"{msg}\n")
                        else:
                            msg = "✓ Visual verification passed: geometry matches request."
                            if log_callback:
                                log_callback(msg)
                            FreeCAD.Console.PrintMessage(f"{msg}\n")
                    else:
                        msg = "⚠ Visual verification skipped: could not capture screenshot."
                        if log_callback:
                            log_callback(msg)
                        FreeCAD.Console.PrintMessage(f"{msg}\n")

                # Step 2: Code verification (if enabled)
                if use_code_verification:
                    msg = "=" * 60 + '\n' + "⟳ Running part code verification..." + '\n' + "=" * 60
                    if log_callback:
                        log_callback(msg)
                    FreeCAD.Console.PrintMessage(f"{msg}\n")

                    from cadomatic.src.part_verify import verify_generated_code
                    code_result = verify_generated_code(description, current_code)

                    # Check if cancel was requested after verification
                    if self._check_cancel_and_stop(log_callback):
                        return

                    if code_result['verified']:
                        msg = "✓ LLM code verification passed: code matches request."
                        if log_callback:
                            log_callback(msg)
                        FreeCAD.Console.PrintMessage(f"{msg}\n")
                        # Stop the spinner and show result in main thread via signal
                        self._fix_loop_signaler.verification_success_signal.emit()
                    else:
                        msg = "⚠ LLM code verification failed: code needs corrections."
                        if log_callback:
                            log_callback(msg)
                        FreeCAD.Console.PrintMessage(f"{msg}\n")

                        # Save corrected code
                        corrected_code = code_result['corrected_code']
                        if corrected_code:
                            state['generated_code'] = corrected_code
                            with open(state['script_path'], 'w') as f:
                                f.write(corrected_code)

                            msg = "Corrected code written by LLM code verification."
                            if log_callback:
                                log_callback(msg)
                            FreeCAD.Console.PrintMessage(f"{msg}\n")

                            # Signal to run next iteration on main thread (test the corrected code)
                            self._fix_loop_signaler.continue_signal.emit()
                        else:
                            msg = "⚠ Code verification returned no corrected code. Stopping."
                            if log_callback:
                                log_callback(msg)
                            FreeCAD.Console.PrintError(f"{msg}\n")
                            self._fix_loop_signaler.verification_failed_signal.emit()
                else:
                    # No verification needed - stop the spinner on successful execution
                    self._fix_loop_signaler.verification_success_signal.emit()

            except Exception as e:
                msg = f"Error in verification: {str(e)}"
                if log_callback:
                    log_callback(msg)
                FreeCAD.Console.PrintError(f"{msg}\n")
                import traceback
                FreeCAD.Console.PrintError(f"{traceback.format_exc()}\n")
                # On error, stop the spinner (assume success to not block user)
                self._fix_loop_signaler.verification_success_signal.emit()

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()


class GenCAD_ExportToMacro:
    """Export selected objects to a new macro"""

    def GetResources(self):
        return {
            'Pixmap': ':/icons/accessories-text-editor.svg',
            'MenuText': 'Export Objects to Macro',
            'ToolTip': 'Convert selected objects to Python code and open in a new macro'
        }

    def Activated(self):
        """Convert selected objects to Python code and open in macro editor"""
        import FreeCADGui
        import time
        import re

        # Get selected objects
        selection = FreeCADGui.Selection.getSelection()
        if not selection:
            FreeCAD.Console.PrintMessage("No objects selected for export. Please select objects first.\n")
            return

        # Get first selected object name for filename
        first_obj_name = selection[0].Name
        # Sanitize name: replace spaces with underscores, remove special characters
        sanitized_name = re.sub(r'[^a-zA-Z0-9_]', '', first_obj_name.replace(' ', '_'))

        # Get timestamp
        timestamp = time.strftime("%Y%m%d_%H%M%S")

        # Build macro filename: gencad_name_of_first_selected_obj_timestamp.FCMacro
        macro_dir = FreeCAD.getUserMacroDir(True)
        os.makedirs(macro_dir, exist_ok=True)
        macro_filename = os.path.join(macro_dir, f"gencad_{sanitized_name}_{timestamp}.FCMacro")

        # Get selected objects code using the existing function
        selected_objects_code = get_selected_objects_python_without_tmp_doc()
        if not selected_objects_code:
            FreeCAD.Console.PrintError("Failed to export selected objects to Python code.\n")
            return

        # Write the code to the macro file
        with open(macro_filename, 'w') as f:
            f.write(selected_objects_code)

        # Open the macro in the editor
        FreeCADGui.open(macro_filename)

        FreeCAD.Console.PrintMessage(f"Exported objects to macro: {macro_filename}\n")


class GenCAD_Settings:
    """Configure GenCAD settings"""

    def GetResources(self):
        return {
            'Pixmap': ':/icons/preferences-general.svg',
            'MenuText': 'GenCAD Settings',
            'ToolTip': 'Configure GenCAD LLM providers and models'
        }

    def Activated(self):
        """Open the settings dialog"""
        from GenCADDialog import show_genCAD_settings_dialog
        from GenCADConfig import config

        settings = show_genCAD_settings_dialog()

        if settings:
            # Save settings to config file
            success = config.save_config(settings)

            if success:
                FreeCAD.Console.PrintMessage("GenCAD settings saved successfully.\n")
            else:
                FreeCAD.Console.PrintError("Failed to save GenCAD settings.\n")


# Register the commands
FreeCADGui.addCommand('GenCAD_CreateModel', GenCAD_CreateModel())
FreeCADGui.addCommand('GenCAD_ExportToMacro', GenCAD_ExportToMacro())
FreeCADGui.addCommand('GenCAD_Settings', GenCAD_Settings())
