import os
import sys
from dotenv import load_dotenv
from pathlib import Path
import json

class LoadEnv:
    def __init__(self):
        """
        To add a new API key, add a self.yourkey = os.getenv("yourkey")
        """
        self._load_env_file()
        self.GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
        self.GEMINI_API_KEY_IMAGE = os.getenv("GEMINI_API_KEY_IMAGE")
        self.HF_TOKEN = os.getenv("HF_TOKEN")
        self.USE_OLLAMA = os.getenv("USE_OLLAMA", "False").lower() == "true"
        self.USE_OPENROUTER = os.getenv("USE_OPENROUTER", "False").lower() == "true"
        self.USE_ROUTERAIRU = os.getenv("USE_ROUTERAIRU", "False").lower() == "true"
        self.OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
        self.OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "google/gemini-3-flash-preview")
        self.OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemini-3-flash-preview:cloud")
        self.ROUTERAIRU_API_KEY = os.getenv("ROUTERAIRU_API_KEY")
        self.ROUTERAIRU_MODEL = os.getenv("ROUTERAIRU_MODEL", "google/gemini-3-flash-preview")
        # VLM models for visual verification
        self.OLLAMA_VLM_MODEL = os.getenv("OLLAMA_VLM_MODEL", "qwen3.6")
        self.OPENROUTER_VLM_MODEL = os.getenv("OPENROUTER_VLM_MODEL", "qwen/qwen3.6-plus")
        self.ROUTERAIRU_VLM_MODEL = os.getenv("ROUTERAIRU_VLM_MODEL", "qwen/qwen3.6-plus")

        # Load GenCAD configuration if available
        self._load_gencad_config()

        # Override environment variables with GenCAD config if available
        self._apply_gencad_config()


    def _load_env_file(self):
        # Look for .env files in the current directory and parent directories
        current_dir = Path(__file__).parent.parent.resolve()
        env_local_path = current_dir / ".env.local"
        env_path = current_dir / ".env"
        
        if env_local_path.exists():
            load_dotenv(env_local_path)
            print("local env loaded", file=sys.stderr)  # Print to stderr instead of stdout
        elif env_path.exists():
            load_dotenv(env_path)
    
    def _load_gencad_config(self):
        """Load GenCAD configuration from file"""
        self.gencad_config = {}
        
        # Define config file path
        config_dir = Path.home() / '.freecad' / 'GenCAD'
        config_file = config_dir / 'config.json'
        
        if config_file.exists():
            try:
                with open(config_file, 'r') as f:
                    self.gencad_config = json.load(f)
            except (json.JSONDecodeError, IOError):
                print("Could not load GenCAD config file")
    
    def _apply_gencad_config(self):
        """Apply GenCAD configuration to override environment variables"""
        if self.gencad_config:
            # Override based on selected provider
            provider = self.gencad_config.get('provider', 'OpenRouter')

            if provider == 'Ollama':
                self.USE_OLLAMA = True
                self.USE_OPENROUTER = False
                self.USE_ROUTERAIRU = False
                self.OLLAMA_MODEL = self.gencad_config.get('ollama_model', getattr(self, 'OLLAMA_MODEL', 'gemini-3-flash-preview:cloud'))
                self.OLLAMA_VLM_MODEL = self.gencad_config.get('ollama_vlm_model', getattr(self, 'OLLAMA_VLM_MODEL', 'qwen3.6'))
            elif provider == 'OpenRouter':
                self.USE_OLLAMA = False
                self.USE_OPENROUTER = True
                self.USE_ROUTERAIRU = False
                self.OPENROUTER_API_KEY = self.gencad_config.get('openrouter_api_key', self.OPENROUTER_API_KEY)
                self.OPENROUTER_MODEL = self.gencad_config.get('openrouter_model', self.OPENROUTER_MODEL)
                self.OPENROUTER_VLM_MODEL = self.gencad_config.get('openrouter_vlm_model', getattr(self, 'OPENROUTER_VLM_MODEL', 'qwen/qwen3.6-plus'))
            elif provider == 'RouterAIru':
                self.USE_OLLAMA = False
                self.USE_OPENROUTER = False
                self.USE_ROUTERAIRU = True
                self.ROUTERAIRU_API_KEY = self.gencad_config.get('routerairu_api_key', getattr(self, 'ROUTERAIRU_API_KEY', ''))
                self.ROUTERAIRU_MODEL = self.gencad_config.get('routerairu_model', getattr(self, 'ROUTERAIRU_MODEL', 'google/gemini-3-flash-preview'))
                self.ROUTERAIRU_VLM_MODEL = self.gencad_config.get('routerairu_vlm_model', getattr(self, 'ROUTERAIRU_VLM_MODEL', 'qwen/qwen3.6-plus'))

load_env = LoadEnv()