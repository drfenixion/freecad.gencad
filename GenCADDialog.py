# GenCADDialog.py
# Defines the dialog for the GenCAD workbench

import FreeCAD
import FreeCADGui
from PySide import QtCore, QtGui, QtWidgets
import os
import sys
import tempfile
import subprocess

# Add the CADomatic project path to sys.path so we can import modules
import FreeCAD
mod_path = os.path.join(FreeCAD.getUserAppDataDir(), "Mod", "freecad.gencad", "cadomatic")
sys.path.insert(0, mod_path)

from cadomatic.src.dependency_checker import deps_check_and_install


class GenCADDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super(GenCADDialog, self).__init__(parent)
        self.setWindowTitle("GenCAD: Create Model from Text")
        self.setModal(False)  # Non-modal to allow object selection in FreeCAD
        self.resize(500, 400)

        layout = QtWidgets.QVBoxLayout()

        # Mode selector - Generate new or Modify selected
        self.mode_group = QtWidgets.QGroupBox("Operation Mode")
        mode_layout = QtWidgets.QVBoxLayout()
        
        self.new_model_radio = QtWidgets.QRadioButton("Generate new model")
        self.new_model_radio.setChecked(True)
        self.new_model_radio.setToolTip("Generate a completely new model from description")
        
        self.modify_model_radio = QtWidgets.QRadioButton("Modify selected objects")
        self.modify_model_radio.setToolTip("Modify currently selected objects in the document")
        
        mode_layout.addWidget(self.new_model_radio)
        mode_layout.addWidget(self.modify_model_radio)
        self.mode_group.setLayout(mode_layout)
        layout.addWidget(self.mode_group)

        # Description label
        label = QtWidgets.QLabel("Describe your CAD model:")
        layout.addWidget(label)

        # Text input area
        self.text_edit = QtWidgets.QTextEdit()
        self.text_edit.setPlaceholderText("Example: Create a 10mm cube with a 2mm hole through the center...")
        layout.addWidget(self.text_edit)

        # Buttons
        button_layout = QtWidgets.QHBoxLayout()

        self.ok_button = QtWidgets.QPushButton("Generate")
        self.cancel_button = QtWidgets.QPushButton("Cancel")

        button_layout.addWidget(self.ok_button)
        button_layout.addWidget(self.cancel_button)

        layout.addLayout(button_layout)

        self.setLayout(layout)

        # Connect signals
        self.ok_button.clicked.connect(self.accept)
        self.cancel_button.clicked.connect(self.reject)

    def get_description(self):
        return self.text_edit.toPlainText()
    
    def get_mode(self):
        """Return the selected operation mode: 'new' or 'modify'"""
        if self.new_model_radio.isChecked():
            return "new"
        else:
            return "modify"


class GenCADSettingsDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super(GenCADSettingsDialog, self).__init__(parent)
        self.setWindowTitle("GenCAD Settings")
        self.setModal(True)
        self.resize(550, 550)

        layout = QtWidgets.QVBoxLayout()

        # === Modeling Options Group (top, grouped together) ===
        modeling_options_group = QtWidgets.QGroupBox("Modeling Options")
        modeling_options_layout = QtWidgets.QFormLayout()
        modeling_options_layout.setFieldGrowthPolicy(QtWidgets.QFormLayout.AllNonFixedFieldsGrow)
        modeling_options_layout.setSpacing(8)

        # 1) Build Tree / Bake Part
        self.build_tree_combo = QtWidgets.QComboBox()
        self.build_tree_combo.addItems(["Build Tree of Part", "Bake Part"])
        self.build_tree_combo.setToolTip("Choose between parametric feature tree or simple baked geometry")
        modeling_options_layout.addRow("Part Structure:", self.build_tree_combo)

        # 2) Use Sketches / Use Primitives / Auto
        self.modeling_approach_combo = QtWidgets.QComboBox()
        self.modeling_approach_combo.addItems(["Auto", "Use Sketches", "Use Primitives"])
        self.modeling_approach_combo.setToolTip("Choose between auto (both), sketch-based, or primitive-based modeling")
        modeling_options_layout.addRow("Modeling Approach:", self.modeling_approach_combo)

        # 3) PartDesign WB / Part WB
        self.workbench_combo = QtWidgets.QComboBox()
        self.workbench_combo.addItems(["Use PartDesign WB", "Use Part WB"])
        self.workbench_combo.setToolTip("Choose the primary workbench for modeling")
        modeling_options_layout.addRow("Workbench:", self.workbench_combo)

        # 4) PolarPattern / Placement for circular placement
        self.circular_placement_combo = QtWidgets.QComboBox()
        self.circular_placement_combo.addItems(["Use PartDesign_PolarPattern", "Use Placement for Circle"])
        self.circular_placement_combo.setToolTip("Choose method for placing objects in a circle")
        modeling_options_layout.addRow("Circular Placement:", self.circular_placement_combo)

        # 5) Use RAG context
        self.use_rag_checkbox = QtWidgets.QCheckBox()
        self.use_rag_checkbox.setChecked(False)
        self.use_rag_checkbox.setToolTip("Use RAG (Retrieval-Augmented Generation) to include FreeCAD documentation context")
        modeling_options_layout.addRow("Use RAG Context:", self.use_rag_checkbox)

        # 6) Use LLM part verification
        self.use_part_verification_checkbox = QtWidgets.QCheckBox()
        self.use_part_verification_checkbox.setChecked(False)
        self.use_part_verification_checkbox.setToolTip("Enable LLM verification of generated code parameters against user request after successful test execution")
        modeling_options_layout.addRow("Use Part Code Verification:", self.use_part_verification_checkbox)

        # 7) Use LLM visual part verification
        self.use_part_visual_verification_checkbox = QtWidgets.QCheckBox()
        self.use_part_visual_verification_checkbox.setChecked(False)
        self.use_part_visual_verification_checkbox.setToolTip("Enable visual verification of generated part screenshot against user request after successful test execution")
        modeling_options_layout.addRow("Use Visual Part Verification:", self.use_part_visual_verification_checkbox)

        # 8) Max retries for fixing script
        self.max_retries_spinbox = QtWidgets.QSpinBox()
        self.max_retries_spinbox.setRange(1, 10)
        self.max_retries_spinbox.setValue(5)
        self.max_retries_spinbox.setToolTip("Maximum number of retries for fixing failed FreeCAD scripts")
        modeling_options_layout.addRow("Max Retries for Fix:", self.max_retries_spinbox)

        # 9) Use Fasteners WB
        self.use_fasteners_wb_checkbox = QtWidgets.QCheckBox()
        self.use_fasteners_wb_checkbox.setChecked(False)
        self.use_fasteners_wb_checkbox.setToolTip("Use Fasteners workbench for attaching fasteners to circular edges")
        modeling_options_layout.addRow("Use Fasteners WB:", self.use_fasteners_wb_checkbox)

        modeling_options_group.setLayout(modeling_options_layout)
        layout.addWidget(modeling_options_group)

        # === LLM Provider Settings ===
        provider_group = QtWidgets.QGroupBox("LLM Provider")
        provider_layout = QtWidgets.QVBoxLayout()

        self.provider_combo = QtWidgets.QComboBox()
        self.provider_combo.addItems(["Ollama", "OpenRouter", "RouterAIru"])
        provider_layout.addWidget(self.provider_combo)

        provider_group.setLayout(provider_layout)
        layout.addWidget(provider_group)

        # === API Key inputs ===
        api_keys_group = QtWidgets.QGroupBox("API Keys")
        api_keys_layout = QtWidgets.QFormLayout()

        self.openrouter_api_key = QtWidgets.QLineEdit()
        self.routerairu_api_key = QtWidgets.QLineEdit()

        # Store original values for toggle functionality
        self._api_key_values = {
            'openrouter': '',
            'routerairu': ''
        }
        self._api_keys_hidden = False

        api_keys_layout.addRow("OpenRouter API Key:", self.openrouter_api_key)
        api_keys_layout.addRow("RouterAIru API Key:", self.routerairu_api_key)

        # Toggle button for hiding/showing API keys
        self.toggle_api_keys_btn = QtWidgets.QPushButton("Hide Keys")
        self.toggle_api_keys_btn.setToolTip("Hide or show API keys (masked with asterisks)")
        self.toggle_api_keys_btn.clicked.connect(self._toggle_api_keys)
        api_keys_layout.addRow(self.toggle_api_keys_btn)

        api_keys_group.setLayout(api_keys_layout)
        layout.addWidget(api_keys_group)

        # === Model inputs with defaults and reset buttons ===
        models_group = QtWidgets.QGroupBox("Model (use top tier models)")
        models_layout = QtWidgets.QFormLayout()

        # Ollama model
        ollama_model_layout = QtWidgets.QHBoxLayout()
        self.ollama_model = QtWidgets.QLineEdit()
        self.ollama_model.setText("gemini-3-flash-preview:cloud")  # Default
        self.reset_ollama_model = QtWidgets.QPushButton("Reset")
        ollama_model_layout.addWidget(self.ollama_model)
        ollama_model_layout.addWidget(self.reset_ollama_model)
        models_layout.addRow("Ollama Model:", ollama_model_layout)

        # OpenRouter model
        openrouter_model_layout = QtWidgets.QHBoxLayout()
        self.openrouter_model = QtWidgets.QLineEdit()
        self.openrouter_model.setText("google/gemini-3-flash-preview")  # Default
        self.reset_openrouter_model = QtWidgets.QPushButton("Reset")
        openrouter_model_layout.addWidget(self.openrouter_model)
        openrouter_model_layout.addWidget(self.reset_openrouter_model)
        models_layout.addRow("OpenRouter Model:", openrouter_model_layout)

        # ROUTERAIRU model
        routerairu_model_layout = QtWidgets.QHBoxLayout()
        self.routerairu_model = QtWidgets.QLineEdit()
        self.routerairu_model.setText("google/gemini-3-flash-preview")  # Default
        self.reset_routerairu_model = QtWidgets.QPushButton("Reset")
        routerairu_model_layout.addWidget(self.routerairu_model)
        routerairu_model_layout.addWidget(self.reset_routerairu_model)
        models_layout.addRow("RouterAIru Model:", routerairu_model_layout)

        models_group.setLayout(models_layout)
        layout.addWidget(models_group)

        # === VLM Models for Visual Verification ===
        vlm_models_group = QtWidgets.QGroupBox("VLM Models (for visual verification)")
        vlm_models_layout = QtWidgets.QFormLayout()

        # Ollama VLM model
        ollama_vlm_model_layout = QtWidgets.QHBoxLayout()
        self.ollama_vlm_model = QtWidgets.QLineEdit()
        self.ollama_vlm_model.setText("gemini-3-flash-preview:cloud")  # Default
        self.reset_ollama_vlm_model = QtWidgets.QPushButton("Reset")
        ollama_vlm_model_layout.addWidget(self.ollama_vlm_model)
        ollama_vlm_model_layout.addWidget(self.reset_ollama_vlm_model)
        vlm_models_layout.addRow("Ollama VLM Model:", ollama_vlm_model_layout)

        # OpenRouter VLM model
        openrouter_vlm_model_layout = QtWidgets.QHBoxLayout()
        self.openrouter_vlm_model = QtWidgets.QLineEdit()
        self.openrouter_vlm_model.setText("google/gemini-3-flash-preview")  # Default
        self.reset_openrouter_vlm_model = QtWidgets.QPushButton("Reset")
        openrouter_vlm_model_layout.addWidget(self.openrouter_vlm_model)
        openrouter_vlm_model_layout.addWidget(self.reset_openrouter_vlm_model)
        vlm_models_layout.addRow("OpenRouter VLM Model:", openrouter_vlm_model_layout)

        # ROUTERAIRU VLM model
        routerairu_vlm_model_layout = QtWidgets.QHBoxLayout()
        self.routerairu_vlm_model = QtWidgets.QLineEdit()
        self.routerairu_vlm_model.setText("google/gemini-3-flash-preview")  # Default
        self.reset_routerairu_vlm_model = QtWidgets.QPushButton("Reset")
        routerairu_vlm_model_layout.addWidget(self.routerairu_vlm_model)
        routerairu_vlm_model_layout.addWidget(self.reset_routerairu_vlm_model)
        vlm_models_layout.addRow("RouterAIru VLM Model:", routerairu_vlm_model_layout)

        vlm_models_group.setLayout(vlm_models_layout)
        layout.addWidget(vlm_models_group)

        # === Dependencies ===
        deps_group = QtWidgets.QGroupBox("Dependencies")
        deps_layout = QtWidgets.QVBoxLayout()

        deps_check_btn = QtWidgets.QPushButton("Check and install dependencies")
        deps_check_btn.setToolTip("Check for missing dependencies and install them")
        deps_check_btn.clicked.connect(lambda: deps_check_and_install(FreeCAD, FreeCADGui, notice_if_already_installed=True))
        deps_layout.addWidget(deps_check_btn)

        deps_group.setLayout(deps_layout)
        layout.addWidget(deps_group)

        # # === Ollama usage (Linux) ===
        # ollama_group = QtWidgets.QGroupBox("Ollama usage on Linux (can be free quota for cloud models)")
        # ollama_layout = QtWidgets.QVBoxLayout()

        # ollama_instructions = QtWidgets.QPlainTextEdit()
        # ollama_instructions.setReadOnly(True)
        # ollama_instructions.setMaximumHeight(150)
        # ollama_instructions.setPlainText(
        #     "# Install ollama\n"
        #     "curl -fsSL https://ollama.com/install.sh | sh\n\n"
        #     "# Register Ollama account on official site.\n\n"
        #     "# Do device signin and follow it instruction.\n"
        #     "ollama signin\n\n"
        #     "# Pull cloud model.\n"
        #     "ollama pull gemini-3-flash-preview:cloud\n\n"
        #     "# Select Ollama Provider in these Setting and fill that model (gemini-3-flash-preview:cloud) to Ollama Model field."
        # )
        # ollama_layout.addWidget(ollama_instructions)

        # # Download link for Windows
        # ollama_link_label = QtWidgets.QLabel()
        # ollama_link_label.setText('Ollama usage on Win look likes above way but GUI: <a href="https://ollama.com/download/windows">https://ollama.com/download/windows</a>')
        # ollama_link_label.setOpenExternalLinks(True)
        # ollama_link_label.setTextInteractionFlags(QtCore.Qt.TextBrowserInteraction)
        # ollama_layout.addWidget(ollama_link_label)

        # ollama_group.setLayout(ollama_layout)
        # layout.addWidget(ollama_group)

        # === Disclaimer ===
        disclaimer_group = QtWidgets.QGroupBox("Disclaimer")
        disclaimer_layout = QtWidgets.QVBoxLayout()

        disclaimer_btn = QtWidgets.QPushButton("Disclaimer")
        disclaimer_btn.setToolTip("View important information about GenCAD usage")
        disclaimer_btn.clicked.connect(self._show_disclaimer)
        disclaimer_layout.addWidget(disclaimer_btn)

        disclaimer_group.setLayout(disclaimer_layout)
        layout.addWidget(disclaimer_group)

        # === Sponsorship Widget ===
        vertical_spacer = QtWidgets.QSpacerItem(20, 15, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Fixed)
        layout.addItem(vertical_spacer)

        sponsorship_group = QtWidgets.QGroupBox("GenCAD is sponsored by:")
        sponsorship_layout = QtWidgets.QVBoxLayout()
        sponsorship_layout.setContentsMargins(9, 9, 9, 9)

        sponsorship_description = QtWidgets.QLabel("Here can be your sponsorship or ads")
        sponsorship_description.setFont(QtGui.QFont("", 20, QtGui.QFont.Bold))
        sponsorship_layout.addWidget(sponsorship_description)

        sponsorship_email = QtWidgets.QLabel('Write to <a href="mailto:it.project.devel@gmail.com">it.project.devel@gmail.com</a>')
        sponsorship_email.setFont(QtGui.QFont("", 10, QtGui.QFont.Bold))
        sponsorship_email.setTextFormat(QtCore.Qt.RichText)
        sponsorship_email.setTextInteractionFlags(QtCore.Qt.TextBrowserInteraction)
        sponsorship_email.setOpenExternalLinks(True)
        sponsorship_layout.addWidget(sponsorship_email)

        sponsorship_group.setLayout(sponsorship_layout)
        layout.addWidget(sponsorship_group)
        layout.addItem(vertical_spacer)

        # === Buttons ===
        button_layout = QtWidgets.QHBoxLayout()

        self.ok_button = QtWidgets.QPushButton("Save")
        self.cancel_button = QtWidgets.QPushButton("Cancel")

        button_layout.addWidget(self.ok_button)
        button_layout.addWidget(self.cancel_button)

        layout.addLayout(button_layout)

        self.setLayout(layout)

        # Connect signals
        self.ok_button.clicked.connect(self.accept)
        self.cancel_button.clicked.connect(self.reject)

        # Connect reset buttons
        self.reset_ollama_model.clicked.connect(lambda: self.ollama_model.setText("gemini-3-flash-preview:cloud"))
        self.reset_openrouter_model.clicked.connect(lambda: self.openrouter_model.setText("google/gemini-3-flash-preview"))
        self.reset_routerairu_model.clicked.connect(lambda: self.routerairu_model.setText("google/gemini-3-flash-preview"))
        self.reset_ollama_vlm_model.clicked.connect(lambda: self.ollama_vlm_model.setText("gemini-3-flash-preview:cloud"))
        self.reset_openrouter_vlm_model.clicked.connect(lambda: self.openrouter_vlm_model.setText("google/gemini-3-flash-preview"))
        self.reset_routerairu_vlm_model.clicked.connect(lambda: self.routerairu_vlm_model.setText("google/gemini-3-flash-preview"))

        # Connect workbench change to update circular placement
        self.workbench_combo.currentTextChanged.connect(self._on_workbench_changed)

        # Load current settings
        self.load_settings()

    def _apply_api_keys_hidden_state(self):
        """Apply the hidden state to API key fields (used on load)."""
        api_key_fields = {
            'openrouter': self.openrouter_api_key,
            'routerairu': self.routerairu_api_key
        }

        for key_name, field in api_key_fields.items():
            original_value = field.text()
            self._api_key_values[key_name] = original_value
            if original_value:
                field.setText('*' * len(original_value))
                field.setReadOnly(True)
        
        self.toggle_api_keys_btn.setText("Show Keys")
        self.toggle_api_keys_btn.setToolTip("Show hidden API keys")

    def _toggle_api_keys(self):
        """Toggle between hiding and showing API keys."""
        api_key_fields = {
            'openrouter': self.openrouter_api_key,
            'routerairu': self.routerairu_api_key
        }

        if self._api_keys_hidden:
            # Show keys
            for key_name, field in api_key_fields.items():
                field.setText(self._api_key_values[key_name])
                field.setReadOnly(False)
            self.toggle_api_keys_btn.setText("Hide Keys")
            self.toggle_api_keys_btn.setToolTip("Hide or show API keys (masked with asterisks)")
            self._api_keys_hidden = False
        else:
            # Hide keys with asterisks - use stored values, not current field text
            for key_name, field in api_key_fields.items():
                original_value = self._api_key_values[key_name]
                if original_value:
                    field.setText('*' * len(original_value))
                    field.setReadOnly(True)
            self.toggle_api_keys_btn.setText("Show Keys")
            self.toggle_api_keys_btn.setToolTip("Show hidden API keys")
            self._api_keys_hidden = True

        # Save state to config
        from GenCADConfig import config
        config.set_setting('api_keys_hidden', self._api_keys_hidden)

    def _on_workbench_changed(self, workbench):
        """Automatically switch circular placement when workbench changes."""
        if workbench == "Use Part WB":
            self.circular_placement_combo.setCurrentText("Use Placement for Circle")
            self.circular_placement_combo.setEnabled(False)
        elif workbench == "Use PartDesign WB":
            self.circular_placement_combo.setCurrentText("Use PartDesign_PolarPattern")
            self.circular_placement_combo.setEnabled(True)

    def _show_disclaimer(self):
        """Show the disclaimer message dialog."""
        disclaimer_text = (
            "GenCAD automatically tests the LLM-generated code directly in FreeCAD using its Python interpreter.\n\n"
            "By using GenCAD, you should understand that the generated code could theoretically cause harm to your files. "
            "In practice, during all my testing time, there has not been a single case of problems caused by the generated code. "
            "Nevertheless, remember that the generation depends on your request, model and has a randomness factor. "
            "'Generation depends on your request' means - Do not ask GenCAD for anything that could harm your system.\n\n"
            "IMPORTANT: You use GenCAD at your own risk and under your own responsibility. "
            "If you want more safety, use an isolated environment for FreeCAD.\n\n"
            "The generated model may be inaccurate or incorrect. Always verify the result.\n\n"
            "IMPORTANT: Use top-tier models from well-known providers (e.g., Google, Anthropic, OpenAI). "
            "Weak or small models may be unsuitable for use and produce incorrect or unusable CAD code.\n\n"
            "GenCAD internal workflow:\n"
            "user_input + system_instruction -> (LLM -> generated code -> test execution in FreeCAD) loop of code fixing."
        )
        msg_box = QtWidgets.QMessageBox()
        msg_box.setIcon(QtWidgets.QMessageBox.Warning)
        msg_box.setWindowTitle("GenCAD Disclaimer")
        msg_box.setText(disclaimer_text)
        msg_box.setStandardButtons(QtWidgets.QMessageBox.Ok)
        msg_box.exec_()

    def load_settings(self):
        """Load current settings from config"""
        from GenCADConfig import config

        # Load modeling options
        self.build_tree_combo.setCurrentText(config.get_setting('build_tree', 'Build Tree of Part'))
        self.modeling_approach_combo.setCurrentText(config.get_setting('modeling_approach', 'Use Sketches'))
        self.workbench_combo.setCurrentText(config.get_setting('workbench', 'Use PartDesign WB'))
        self.circular_placement_combo.setCurrentText(config.get_setting('circular_placement', 'Use PartDesign_PolarPattern'))
        self.use_rag_checkbox.setChecked(config.get_setting('use_rag', False))
        self.use_fasteners_wb_checkbox.setChecked(config.get_setting('use_fasteners_wb', False))
        self.use_part_verification_checkbox.setChecked(config.get_setting('use_part_verification', False))
        self.use_part_visual_verification_checkbox.setChecked(config.get_setting('use_part_visual_verification', False))
        self.max_retries_spinbox.setValue(config.get_setting('max_retries_of_fix_script', 5))

        # Apply workbench-dependent circular placement locking
        self._on_workbench_changed(self.workbench_combo.currentText())

        # Load provider
        provider = config.get_setting('provider', 'OpenRouter')
        index = self.provider_combo.findText(provider)
        if index >= 0:
            self.provider_combo.setCurrentIndex(index)

        # Load API keys
        openrouter_key = config.get_setting('openrouter_api_key', '')
        routerairu_key = config.get_setting('routerairu_api_key', '')
        self.openrouter_api_key.setText(openrouter_key)
        self.routerairu_api_key.setText(routerairu_key)

        # Always store original values for toggle functionality
        self._api_key_values['openrouter'] = openrouter_key
        self._api_key_values['routerairu'] = routerairu_key

        # Load API keys visibility state
        api_keys_hidden = config.get_setting('api_keys_hidden', False)
        if api_keys_hidden:
            self._api_keys_hidden = True
            self._apply_api_keys_hidden_state()  # Apply hidden state without saving

        # Load model names
        self.ollama_model.setText(config.get_setting('ollama_model', 'gemini-3-flash-preview:cloud'))
        self.openrouter_model.setText(config.get_setting('openrouter_model', 'google/gemini-3-flash-preview'))
        self.routerairu_model.setText(config.get_setting('routerairu_model', 'google/gemini-3-flash-preview'))
        # Load VLM model names
        self.ollama_vlm_model.setText(config.get_setting('ollama_vlm_model', 'gemini-3-flash-preview:cloud'))
        self.openrouter_vlm_model.setText(config.get_setting('openrouter_vlm_model', 'google/gemini-3-flash-preview'))
        self.routerairu_vlm_model.setText(config.get_setting('routerairu_vlm_model', 'google/gemini-3-flash-preview'))

    def get_settings(self):
        """Return the current settings"""
        # Read from text fields; if field is masked (all asterisks), use stored value
        openrouter_text = self.openrouter_api_key.text()
        if openrouter_text and all(c == '*' for c in openrouter_text):
            openrouter_key = self._api_key_values['openrouter']
        else:
            openrouter_key = openrouter_text

        routerairu_text = self.routerairu_api_key.text()
        if routerairu_text and all(c == '*' for c in routerairu_text):
            routerairu_key = self._api_key_values['routerairu']
        else:
            routerairu_key = routerairu_text

        return {
            # Modeling options
            'build_tree': self.build_tree_combo.currentText(),
            'modeling_approach': self.modeling_approach_combo.currentText(),
            'workbench': self.workbench_combo.currentText(),
            'circular_placement': self.circular_placement_combo.currentText(),
            'use_rag': self.use_rag_checkbox.isChecked(),
            'use_fasteners_wb': self.use_fasteners_wb_checkbox.isChecked(),
            'use_part_verification': self.use_part_verification_checkbox.isChecked(),
            'use_part_visual_verification': self.use_part_visual_verification_checkbox.isChecked(),
            'max_retries_of_fix_script': self.max_retries_spinbox.value(),
            # LLM settings
            'provider': self.provider_combo.currentText(),
            'openrouter_api_key': openrouter_key,
            'routerairu_api_key': routerairu_key,
            'ollama_model': self.ollama_model.text(),
            'openrouter_model': self.openrouter_model.text(),
            'routerairu_model': self.routerairu_model.text(),
            # VLM models
            'ollama_vlm_model': self.ollama_vlm_model.text(),
            'openrouter_vlm_model': self.openrouter_vlm_model.text(),
            'routerairu_vlm_model': self.routerairu_vlm_model.text(),
        }


def show_genCAD_dialog_with_mode(callback):
    """Show the GenCAD dialog and call callback with (description, mode) when Generate is clicked.
    
    Dialog is non-modal, so user can select objects in FreeCAD while dialog is open.
    
    Args:
        callback: Function to call with (description, mode) when Generate is clicked
    """
    dialog = GenCADDialog(FreeCADGui.getMainWindow())
    
    # Store original accept method
    original_accept = dialog.accept
    
    def on_generate():
        description = dialog.get_description()
        mode = dialog.get_mode()
        dialog.close()
        if callback:
            callback(description, mode)
    
    # Override accept to call our callback
    dialog.accept = on_generate
    dialog.show()


def show_genCAD_settings_dialog():
    """Show the GenCAD settings dialog and return the settings"""
    dialog = GenCADSettingsDialog(FreeCADGui.getMainWindow())
    if dialog.exec_() == QtWidgets.QDialog.Accepted:
        return dialog.get_settings()
    return None
