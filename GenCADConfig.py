# GenCADConfig.py
# Configuration management for GenCAD workbench

import os
import json
from pathlib import Path

class GenCADConfig:
    """Configuration manager for GenCAD workbench"""
    
    def __init__(self):
        # Define config file path
        self.config_dir = Path.home() / '.freecad' / 'GenCAD'
        self.config_file = self.config_dir / 'config.json'
        
        # Create config directory if it doesn't exist
        self.config_dir.mkdir(parents=True, exist_ok=True)
        
        # Load existing config or set defaults
        self.settings = self.load_config()
    
    def load_config(self):
        """Load configuration from file"""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass

        # Return default settings
        return {
            # Modeling options
            'build_tree': 'Build Tree of Part',
            'modeling_approach': 'Use Sketches',
            'workbench': 'Use PartDesign WB',
            'circular_placement': 'Use PartDesign_PolarPattern',
            'use_rag': False,  # RAG enabled by default
            'use_fasteners_wb': False,  # Fasteners WB disabled by default
            'use_part_verification': False,  # LLM part verification disabled by default
            'use_part_visual_verification': False,  # Visual part verification disabled by default
            'max_retries_of_fix_script': 5,  # Max retries for fixing script
            # LLM settings
            'provider': 'OpenRouter',  # Default provider
            'openrouter_api_key': '',
            'routerairu_api_key': '',
            'ollama_model': 'gemini-3-flash-preview:cloud',
            'openrouter_model': 'google/gemini-3-flash-preview',
            'routerairu_model': 'google/gemini-3-flash-preview',
            # UI preferences
            'api_keys_hidden': False  # UI state for API keys visibility
        }
    
    def save_config(self, settings):
        """Save configuration to file"""
        self.settings.update(settings)
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.settings, f, indent=2)
            return True
        except IOError:
            return False
    
    def get_setting(self, key, default=None):
        """Get a specific setting value"""
        return self.settings.get(key, default)
    
    def set_setting(self, key, value):
        """Set a specific setting value"""
        self.settings[key] = value
        self.save_config(self.settings)


# Global instance
config = GenCADConfig()