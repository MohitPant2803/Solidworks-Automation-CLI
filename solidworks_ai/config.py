import os
import sys
import json
from pathlib import Path
from typing import Dict, Any

# Determine if we are running as a packaged PyInstaller executable
if getattr(sys, 'frozen', False):
    # Path where the SolidWorksAI.exe is located
    EXE_DIR = Path(sys.executable).parent
else:
    # Path of the script's root workspace
    EXE_DIR = Path(__file__).resolve().parent.parent

# Project Specific Paths relative to EXE_DIR
CONFIG_FILE = EXE_DIR / "config.json"
DB_PATH = EXE_DIR / "database.db"
LOG_DIR = EXE_DIR / "logs"
PROJECTS_DIR = EXE_DIR / "projects"

# Ensure folders exist
LOG_DIR.mkdir(parents=True, exist_ok=True)
PROJECTS_DIR.mkdir(parents=True, exist_ok=True)

# Default configuration template
DEFAULT_CONFIG = {
    "gemini_api_key": "",
    "gemini_model_name": "gemini-2.5-flash"
}

def load_config() -> Dict[str, str]:
    """Loads configuration from config.json. Creates it with default template if missing."""
    if not CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "w") as f:
                json.dump(DEFAULT_CONFIG, f, indent=4)
        except Exception as e:
            print(f"Warning: Could not create default config.json: {e}")
        return DEFAULT_CONFIG

    try:
        with open(CONFIG_FILE, "r") as f:
            config_data = json.load(f)
            # Ensure required keys exist
            for k, v in DEFAULT_CONFIG.items():
                if k not in config_data:
                    config_data[k] = v
            return config_data
    except Exception as e:
        print(f"Warning: Failed to load config.json ({e}). Using default settings.")
        return DEFAULT_CONFIG

def save_config(api_key: str, model_name: str = "gemini-2.5-flash") -> None:
    """Saves updated configuration parameters to config.json."""
    config_data = {
        "gemini_api_key": api_key,
        "gemini_model_name": model_name
    }
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(config_data, f, indent=4)
    except Exception as e:
        print(f"Error: Could not save config.json: {e}")

# Load initial configuration parameters
_config = load_config()

# Database URL
DATABASE_URL = f"sqlite:///{DB_PATH}"

# Gemini API configuration loaded from config.json or environment fallback
GEMINI_API_KEY = _config.get("gemini_api_key") or os.getenv("GEMINI_API_KEY", "")
MODEL_NAME = _config.get("gemini_model_name") or os.getenv("GEMINI_MODEL_NAME", "gemini-2.5-flash")

# Update os.environ so other modules reading via os.getenv work consistently
os.environ["GEMINI_API_KEY"] = GEMINI_API_KEY
os.environ["GEMINI_MODEL_NAME"] = MODEL_NAME

# SolidWorks Constants (COM Enum mapping helpers)
class SWConstants:
    # Document Types
    swDocPART = 1
    swDocASSEMBLY = 2
    swDocDRAWING = 3
    
    # End conditions
    swEndCondBlind = 0
    swEndCondThroughAll = 1
    swEndCondThroughNext = 2
    swEndCondUpToNext = 3
    swEndCondUpToLast = 4
    swEndCondUpToSelected = 5
    swEndCondMidPlane = 6
    
    # Selection Types
    swSelEVERYTHING = 0
    
    # Save options
    swSaveAsOptions_Silent = 1
    swSaveAsOptions_Copy = 2
    
    # Export types
    swExportStep = "STEP"
    swExportStl = "STL"
