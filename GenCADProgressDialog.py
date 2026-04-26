"""
GenCAD Progress Dialog - Dialog with progress indicator and logging for CAD generation.
"""
from PySide import QtCore, QtGui, QtWidgets
import threading


class GenCADProgressDialog(QtWidgets.QDialog):
    """
    Dialog window with spinning progress indicator and process logging
    for CAD script generation in GenCAD workbench.
    
    All GUI updates are performed in the main thread via signals/slots
    to avoid Qt errors when working with different threads.
    """

    # Signals for safe GUI updates from other threads
    log_signal = QtCore.Signal(str)
    status_signal = QtCore.Signal(str)
    generation_complete = QtCore.Signal(object, object)  # (result, error)
    cancel_requested_signal = QtCore.Signal()  # Signal for cancel request from fix loop

    def __init__(self, parent=None, title="CAD Script Generation"):
        super(GenCADProgressDialog, self).__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.resize(600, 500)

        self.is_running = False
        self.result = None
        self.error = None
        self.on_complete_callback = None
        self.cancel_requested = False  # Flag for fix loop cancellation

        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        """Set up the dialog interface."""
        layout = QtWidgets.QVBoxLayout()
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        # Title
        title_label = QtWidgets.QLabel("<h2>CAD Script Generation</h2>")
        title_label.setAlignment(QtCore.Qt.AlignCenter)
        layout.addWidget(title_label)

        # Progress indicator (spinner)
        progress_layout = QtWidgets.QVBoxLayout()

        self.spinner = QtWidgets.QProgressBar()
        self.spinner.setRange(0, 0)  # Indeterminate mode (infinite animation)
        self.spinner.setMinimumHeight(24)
        self.spinner.setMaximumHeight(30)
        progress_layout.addWidget(self.spinner)

        layout.addLayout(progress_layout)

        # Status
        self.status_label = QtWidgets.QLabel("Initializing...")
        self.status_label.setAlignment(QtCore.Qt.AlignCenter)
        self.status_label.setStyleSheet("font-weight: bold; color: #555; font-size: 11px;")
        layout.addWidget(self.status_label)

        # Log
        log_group = QtWidgets.QGroupBox("Process Log")
        log_layout = QtWidgets.QVBoxLayout()
        log_layout.setContentsMargins(8, 8, 8, 8)

        self.log_text = QtWidgets.QPlainTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QtGui.QFont("Consolas", 9))
        self.log_text.setMinimumHeight(250)
        self.log_text.setStyleSheet("background-color: #f5f5f5;")
        log_layout.addWidget(self.log_text)

        log_group.setLayout(log_layout)
        layout.addWidget(log_group)

        # Buttons
        button_layout = QtWidgets.QHBoxLayout()
        button_layout.addStretch()

        self.cancel_button = QtWidgets.QPushButton("Cancel")
        self.cancel_button.setEnabled(False)
        self.cancel_button.setMinimumWidth(100)
        self.cancel_button.clicked.connect(self.cancel_generation)
        button_layout.addWidget(self.cancel_button)

        self.close_button = QtWidgets.QPushButton("Close")
        self.close_button.setEnabled(False)
        self.close_button.setMinimumWidth(100)
        self.close_button.clicked.connect(self.close_dialog)
        button_layout.addWidget(self.close_button)

        layout.addLayout(button_layout)

        self.setLayout(layout)

    def _connect_signals(self):
        """Connect signals to slots for safe GUI updates."""
        self.log_signal.connect(self._append_log)
        self.status_signal.connect(self.status_label.setText)
        self.generation_complete.connect(self._on_generation_complete)

    def _append_log(self, message):
        """Append a message to the log (called in the main thread)."""
        self.log_text.appendPlainText(message)
        # Auto-scroll to bottom
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def log(self, message):
        """Append a message to the log (safe via signal)."""
        self.log_signal.emit(message)

    def set_status(self, message):
        """Set the status text (safe via signal)."""
        self.status_signal.emit(message)

    def start_generation(self, generation_func, on_complete_callback=None):
        """
        Start the generation process in a separate thread.

        Args:
            generation_func: Function to execute (must accept log_callback)
            on_complete_callback: Опциональный callback function(result, error)
        """
        self.is_running = True
        self.result = None
        self.error = None
        self.on_complete_callback = on_complete_callback

        # GUI update (in the main thread)
        self.spinner.show()
        self.cancel_button.setEnabled(True)
        self.close_button.setEnabled(False)
        self.set_status("Generating code...")
        self.log_text.clear()

        def worker():
            """Worker thread function."""
            cancelled = False
            try:
                self.log("=" * 60)
                self.log("Starting CAD script generation")
                self.log("=" * 60)

                # Execute generation function with is_running check
                result = generation_func(self.log, self)
                self.result = result

                # Check for cancellation after generation
                if not self.is_running:
                    cancelled = True
                    return

                if result:
                    self.log("=" * 60)
                    self.log("✓ LLM Generation completed successfully!")
                    self.log("=" * 60)
                    self.set_status("LLM Generation completed successfully")
                else:
                    self.log("=" * 60)
                    self.log("✗ Generation returned no result")
                    self.log("=" * 60)
                    self.set_status("Error: No result")

            except Exception as e:
                self.error = str(e)
                self.log("=" * 60)
                self.log(f"✗ Error: {str(e)}")
                self.log("=" * 60)
                self.set_status(f"Error: {str(e)}")
            finally:
                self.is_running = False
                # Signal completion to main thread (only if not cancelled)
                if not cancelled:
                    self.generation_complete.emit(self.result, self.error)

        # Start worker thread
        self.thread = threading.Thread(target=worker, daemon=True)
        self.thread.start()

    def _on_generation_complete(self, result, error):
        """Called when generation completes (in the main thread)."""
        # Не останавливаем спиннер здесь - он будет остановлен после цикла исправлений
        # через метод stop_progress()
        # Cancel button stays enabled during fix loop
        # Only disable close button if generation wasn't cancelled
        if not self.cancel_requested:
            self.close_button.setEnabled(False)

        if self.on_complete_callback:
            self.on_complete_callback(result, error)

    def continue_spinner(self):
        """Continue spinner animation after generation completes (for fix loop)."""
        self.spinner.setRange(0, 0)  # Indeterminate mode
        self.spinner.show()
        self.set_status("Fixing script...")

    def stop_progress(self, success=True):
        """Stop progress after all operations complete (generation + fix loop).
        
        Args:
            success: If True, show success status; if False, show failure status.
        """
        self.spinner.setValue(100)
        self.spinner.hide()
        self.cancel_button.setEnabled(False)
        self.close_button.setEnabled(True)
        if success:
            self.set_status("Generation completed successfully")
        else:
            self.set_status("Generation failed")

    def cancel_generation(self):
        """Cancel the generation or fix loop process."""
        self.set_status("Cancelling...")
        self.is_running = False
        self.cancel_requested = True  # Set flag for fix loop to check
        self.cancel_button.setEnabled(False)
        self.close_button.setEnabled(True)
        self.spinner.setValue(0)
        self.spinner.hide()
        # Emit signal to stop fix loop if it's running
        self.cancel_requested_signal.emit()

    def close_dialog(self):
        """Close the dialog and stop the progress indicator."""
        self.spinner.setValue(0)
        self.spinner.hide()
        self.accept()

    def reject(self):
        """Handle dialog rejection."""
        if self.is_running:
            reply = QtWidgets.QMessageBox.question(
                self,
                "Confirm Cancel",
                "Generation is still in progress. Are you sure you want to cancel?",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
            )
            if reply == QtWidgets.QMessageBox.No:
                return

        super(GenCADProgressDialog, self).reject()


def run_generation_with_gui(parent, user_input, generation_func, on_complete=None):
    """
    Show the generation dialog and start the process.

    Args:
        parent: Parent widget (FreeCAD main window)
        user_input: CAD model description from user
        generation_func: Function to call with (user_input, log_callback, dialog)
        on_complete: Optional callback(result, error)

    Returns:
        GenCADProgressDialog instance
    """
    dialog = GenCADProgressDialog(parent, "CAD Script Generation")

    def wrapped_func(log_callback, dialog_ref):
        return generation_func(user_input, log_callback, dialog_ref)

    dialog.start_generation(wrapped_func, on_complete)

    return dialog
