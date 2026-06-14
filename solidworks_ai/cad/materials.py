import logging
from typing import Any
import win32com.client
import pythoncom
from solidworks_ai.cad.solidworks import SolidWorksError

logger = logging.getLogger(__name__)

def assign_material(model: Any, material_name: str) -> None:
    """
    Assigns a material to the active part document.
    material_name: e.g. "Alloy Steel", "Copper", "Brass", "AISI 304", "1060 Alloy".
    """
    # Verify it is a Part document (type 1)
    try:
        doc_type = model.GetType()
    except Exception as e:
        raise SolidWorksError(f"GetType() COM call failed: {e}")
    
    if doc_type != 1:  # swDocPART
        raise SolidWorksError("Material assignment is only supported for Part (.sldprt) documents.")

    logger.info(f"Assigning material '{material_name}' to part")
    
    # Cast to PartDoc and set material
    # Arguments: ConfigName (empty for active), Database (empty for default), MaterialName
    try:
        model.SetMaterialPropertyName2(
            str(""),                    # ConfigName — empty string for active config
            str(""),                    # Database — empty string for default database
            str(material_name)          # MaterialName
        )
    except Exception as e:
        raise SolidWorksError(
            f"SetMaterialPropertyName2('', '', '{material_name}') COM call failed: {e}"
        )
    
    try:
        model.EditRebuild3()
    except Exception as e:
        raise SolidWorksError(
            f"EditRebuild3() COM call failed after assigning material '{material_name}': {e}"
        )
    
    logger.info(f"Material '{material_name}' assigned successfully.")
