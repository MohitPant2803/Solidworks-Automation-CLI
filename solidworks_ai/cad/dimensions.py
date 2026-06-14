import logging
from typing import Any
from solidworks_ai.cad.solidworks import SolidWorksError

logger = logging.getLogger(__name__)

def modify_dimension(
    model: Any,
    dimension_name: str,  # e.g., "D1@Sketch1" or "D1@Boss-Extrude1"
    new_value_mm: float
) -> None:
    """
    Modifies a specific dimension value in the active model.
    dimension_name: The parameter name in SolidWorks, e.g. "D1@Sketch1".
    new_value_mm: The new value in millimeters.
    """
    logger.info(f"Modifying dimension '{dimension_name}' to {new_value_mm} mm")
    
    # Convert mm to meters
    value_m = new_value_mm / 1000.0
    
    try:
        # Access the Parameter object
        param = model.Parameter(dimension_name)
        if not param:
            raise SolidWorksError(f"Dimension '{dimension_name}' not found in the model.")
            
        # Set value in meters
        param.SystemValue = value_m
        
        # Rebuild to apply
        model.EditRebuild3()
        logger.info(f"Successfully updated dimension '{dimension_name}' to {new_value_mm} mm")
    except Exception as e:
        raise SolidWorksError(f"Failed to modify dimension '{dimension_name}': {e}")
