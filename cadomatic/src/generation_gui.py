"""
GUI module for CAD script generation with progress indicator and logging.
Designed for FreeCAD GenCAD workbench integration.
"""
import os
import sys
import threading
import queue
from PySide import QtCore, QtGui, QtWidgets


class GenerationDialog(QtWidgets.QDialog):
    """
    Dialog window with loading indicator and process logging for CAD generation.
    """
    
    generation_complete = QtCore.Signal(object, object)  # (result, error)
    
    def __init__(self, parent=None, title="CAD Script Generation"):
        super(GenerationDialog, self).__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.resize(550, 450)
        
        self.log_queue = queue.Queue()
        self.is_running = False
        self.result = None
        self.error = None
        
        self._setup_ui()
        
    def _setup_ui(self):
        """Setup the dialog UI."""
        layout = QtWidgets.QVBoxLayout()
        layout.setSpacing(10)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Title
        title_label = QtWidgets.QLabel("<h2>CAD Script Generation</h2>")
        title_label.setAlignment(QtCore.Qt.AlignCenter)
        layout.addWidget(title_label)
        
        # Progress indicator (spinner)
        progress_layout = QtWidgets.QHBoxLayout()
        
        self.spinner = QtWidgets.QProgressBar()
        self.spinner.setRange(0, 0)  # Indeterminate mode (infinite animation)
        self.spinner.setMinimumHeight(20)
        progress_layout.addWidget(self.spinner)
        
        layout.addLayout(progress_layout)
        
        # Status label
        self.status_var = QtWidgets.QLabel("Initializing...")
        self.status_var.setAlignment(QtCore.Qt.AlignCenter)
        self.status_var.setStyleSheet("font-weight: bold; color: #555;")
        layout.addWidget(self.status_var)
        
        # Log section
        log_group = QtWidgets.QGroupBox("Process Log")
        log_layout = QtWidgets.QVBoxLayout()
        log_layout.setContentsMargins(5, 5, 5, 5)
        
        self.log_text = QtWidgets.QPlainTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QtGui.QFont("Consolas", 9))
        self.log_text.setMinimumHeight(200)
        log_layout.addWidget(self.log_text)
        
        log_group.setLayout(log_layout)
        layout.addWidget(log_group)
        
        # Buttons
        button_layout = QtWidgets.QHBoxLayout()
        button_layout.addStretch()
        
        self.cancel_button = QtWidgets.QPushButton("Cancel")
        self.cancel_button.setEnabled(False)
        self.cancel_button.clicked.connect(self.cancel_generation)
        button_layout.addWidget(self.cancel_button)
        
        self.close_button = QtWidgets.QPushButton("Close")
        self.close_button.setEnabled(False)
        self.close_button.clicked.connect(self.accept)
        button_layout.addWidget(self.close_button)
        
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
        
        # Connect signal for thread-safe UI updates
        self.generation_complete.connect(self._on_generation_complete)
        
    def log(self, message):
        """Add a message to the log (thread-safe)."""
        self.log_queue.put(message)
        # Schedule UI update in main thread
        QtWidgets.QApplication.postEvent(
            self.log_text.viewport(),
            QtCore.QEvent(QtCore.QEvent.User)
        )
        
    def event(self, event):
        """Handle custom events for log updates."""
        if event.type() == QtCore.QEvent.User:
            self._update_log()
            return True
        return super(GenerationDialog, self).event(event)
    
    def _update_log(self):
        """Update the log text from queue."""
        try:
            while True:
                message = self.log_queue.get_nowait()
                self.log_text.appendPlainText(message)
                # Auto-scroll to bottom
                scrollbar = self.log_text.verticalScrollBar()
                scrollbar.setValue(scrollbar.maximum())
        except queue.Empty:
            pass
    
    def start_generation(self, generation_func, on_complete_callback=None):
        """
        Start the generation process in a separate thread.
        
        Args:
            generation_func: Function to execute (should accept log_callback)
            on_complete_callback: Optional callback function(result, error)
        """
        self.is_running = True
        self.result = None
        self.error = None
        self.on_complete_callback = on_complete_callback
        
        # Update UI
        self.spinner.show()
        self.cancel_button.setEnabled(True)
        self.close_button.setEnabled(False)
        self.status_var.setText("Generating code...")
        self.log_text.clear()
        
        def worker():
            """Worker thread function."""
            try:
                self.log("=" * 60)
                self.log("Starting CAD script generation")
                self.log("=" * 60)
                
                # Execute generation function
                result = generation_func(self.log)
                self.result = result
                
                if result:
                    self.log("=" * 60)
                    self.log("✓ Generation completed successfully!")
                    self.log("=" * 60)
                    self.status_var.setText("Generation completed successfully")
                else:
                    self.log("=" * 60)
                    self.log("✗ Generation returned no result")
                    self.log("=" * 60)
                    self.status_var.setText("Error: No result")
                    
            except Exception as e:
                self.error = str(e)
                self.log("=" * 60)
                self.log(f"✗ Error: {str(e)}")
                self.log("=" * 60)
                self.status_var.setText(f"Error: {str(e)}")
            finally:
                self.is_running = False
                # Signal completion in main thread
                self.generation_complete.emit(self.result, self.error)
        
        # Start worker thread
        self.thread = threading.Thread(target=worker, daemon=True)
        self.thread.start()
    
    def _on_generation_complete(self, result, error):
        """Called when generation completes (in main thread)."""
        self.spinner.hide()
        self.cancel_button.setEnabled(False)
        self.close_button.setEnabled(True)
        
        if self.on_complete_callback:
            self.on_complete_callback(result, error)
    
    def cancel_generation(self):
        """Cancel the generation process."""
        self.log("⚠ Cancelled by user...")
        self.status_var.setText("Cancelled")
        self.is_running = False
        self.cancel_button.setEnabled(False)
        self.close_button.setEnabled(True)
    
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
        
        super(GenerationDialog, self).reject()


def run_generation_with_gui(parent, user_input, generation_func, on_complete=None):
    """
    Show the generation dialog and run the generation process.
    
    Args:
        parent: Parent widget (FreeCAD main window)
        user_input: User's CAD description
        generation_func: Function to call with (user_input, log_callback)
        on_complete: Optional callback(result, error)
    
    Returns:
        GenerationDialog instance for further interaction
    """
    dialog = GenerationDialog(parent, "CAD Script Generation")
    
    def wrapped_func(log_callback):
        return generation_func(user_input, log_callback)
    
    dialog.start_generation(wrapped_func, on_complete)
    
    return dialog
