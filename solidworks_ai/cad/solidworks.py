import os
import sys
import logging
from pathlib import Path
from typing import Optional, Any
import win32com.client
import pythoncom
from solidworks_ai.config import SWConstants

logger = logging.getLogger(__name__)

class SolidWorksError(Exception):
    """Custom exception for SolidWorks API errors."""
    pass

class SolidWorksConnection:
    def __init__(self) -> None:
        self.sw_app: Optional[Any] = None

    def connect(self) -> Any:
        """Connects to a running SolidWorks instance or launches one if not open."""
        # Initialize COM library
        pythoncom.CoInitialize()
        try:
            # First, try to get active running instance
            logger.info("Attempting to connect to active SolidWorks instance...")
            self.sw_app = win32com.client.GetActiveObject("SldWorks.Application")
        except Exception:
            try:
                # If not running, start it
                logger.info("SolidWorks is not running. Launching new SolidWorks instance...")
                self.sw_app = win32com.client.Dispatch("SldWorks.Application")
            except Exception as e:
                raise SolidWorksError(
                    f"Failed to connect to or start SolidWorks. Make sure it is installed. Error: {e}"
                )

        if self.sw_app:
            self.sw_app.Visible = True
            logger.info("Connected to SolidWorks successfully.")
            return self.sw_app
        else:
            raise SolidWorksError("Unable to reference SldWorks.Application object.")

    def get_app(self) -> Any:
        """Get the SldWorks application instance, connecting if necessary."""
        if not self.sw_app:
            return self.connect()
        return self.sw_app

    def get_active_document(self) -> Any:
        """Returns the active model document."""
        app = self.get_app()
        model = app.ActiveDoc
        if not model:
            raise SolidWorksError("No active document found in SolidWorks. Please open or create a part.")
        return model

    def create_new_part(self) -> Any:
        """Creates a new part document using the default template."""
        app = self.get_app()
        # Create a new part. NewPart is a shortcut that uses the default template.
        app.NewPart()
        model = app.ActiveDoc
        if not model:
            raise SolidWorksError("Failed to create a new part document.")
        logger.info("Created new Part document successfully.")
        return model

    def open_document(self, file_path: str) -> Any:
        """Opens a SolidWorks document from file_path."""
        app = self.get_app()
        path = Path(file_path).resolve()
        if not path.exists():
            raise SolidWorksError(f"File to open does not exist: {path}")

        file_type = SWConstants.swDocPART  # Default to part for now
        if path.suffix.lower() == ".sldasm":
            file_type = SWConstants.swDocASSEMBLY
        elif path.suffix.lower() == ".slddrw":
            file_type = SWConstants.swDocDRAWING

        errors = win32com.client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
        warnings = win32com.client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
        
        # OpenDoc6 (FileName, Type, Options, ConfigurationName, Errors, Warnings)
        model = app.OpenDoc6(str(path), file_type, 1, "", errors, warnings)
        if not model:
            raise SolidWorksError(f"Failed to open document: {path}. COM Error Code: {errors.value}")
        
        app.ActivateDoc3(model.GetTitle(), True, 2, errors)
        logger.info(f"Opened document: {path}")
        return model

    def close_active_document(self, save_changes: bool = False) -> None:
        """Closes the active document, optionally discarding changes."""
        app = self.get_app()
        try:
            model = app.ActiveDoc
            if not model:
                return
            
            title = model.GetTitle()
            if not save_changes:
                # To close without saving, mark it as saved to prevent dialog box prompt
                model.SetSaveFlag()
            
            app.CloseDoc(title)
            logger.info(f"Closed document '{title}' (Save changes: {save_changes})")
        except Exception as e:
            logger.warning(f"Error while closing active document: {e}")

    def save_document(self, file_path: str) -> None:
        """Saves the active document to file_path."""
        model = self.get_active_document()
        path = Path(file_path).resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        
        # SaveAs options (silent)
        errors = win32com.client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
        warnings = win32com.client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
        
        success = model.SaveAs4(str(path), 0, SWConstants.swSaveAsOptions_Silent, errors, warnings)
        if not success:
            raise SolidWorksError(f"Failed to save document to {path}. Error code: {errors.value}")
        logger.info(f"Saved document successfully to {path}")

    def rebuild(self) -> bool:
        """Forces a rebuild/regen of the active model geometry."""
        model = self.get_active_document()
        # EditRebuild3 returns True if successful
        success = model.EditRebuild3()
        if not success:
            logger.warning("Model rebuild completed with warnings or failed.")
        else:
            logger.info("Model rebuilt successfully.")
        return success

    def export_stl(self, file_path: str) -> None:
        """Exports the active model as STL."""
        self.export_file(file_path, "STL")

    def export_step(self, file_path: str) -> None:
        """Exports the active model as STEP."""
        self.export_file(file_path, "STEP")

    def export_file(self, file_path: str, format_type: str) -> None:
        """Helper to export active document to step/stl."""
        model = self.get_active_document()
        path = Path(file_path).resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        
        errors = win32com.client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
        warnings = win32com.client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
        
        # SaveAs4 handles export based on file extension automatically
        success = model.SaveAs4(str(path), 0, SWConstants.swSaveAsOptions_Silent, errors, warnings)
        if not success:
            raise SolidWorksError(f"Failed to export model to {format_type} at {path}. Error: {errors.value}")
        logger.info(f"Exported model to {format_type} at {path}")
