import logging
from typing import Any
from solidworks_ai.cad.solidworks import SolidWorksError

logger = logging.getLogger(__name__)

def assign_material(model: Any, material_name: str) -> None:
    """
    Assigns a material to the active part document.
    material_name: e.g. "Alloy Steel", "Copper", "Brass", "AISI 304", "1060 Alloy".
    """
    # Verify it is a Part document (type 1)
    doc_type = model.GetType()
    if doc_type != 1:  # swDocPART
        raise SolidWorksError("Material assignment is only supported for Part (.sldprt) documents.")

    logger.info(f"Assigning material '{material_name}' to part")
    
    # Cast to PartDoc and set material
    # Arguments: ConfigName (empty for active), Database (empty for default), MaterialName
    try:
        model.SetMaterialPropertyName2("", "", material_name)
        model.EditRebuild3()
        logger.info(f"Material '{material_name}' assigned successfully.")
    except Exception as e:
        raise SolidWorksError(f"Failed to assign material '{material_name}': {e}")
