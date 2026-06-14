import logging
from typing import Dict, Any, List, Optional
from solidworks_ai.cad.solidworks import SolidWorksConnection, SolidWorksError

logger = logging.getLogger(__name__)

def read_active_model_summary(model: Any) -> Dict[str, Any]:
    """
    Inspects the active SolidWorks document, traverses all features,
    and generates a compact summary.
    """
    if not model:
        return {"features": []}

    features_list: List[Dict[str, Any]] = []
    
    try:
        # Get the first feature in the tree
        feat = model.FirstFeature()
        
        while feat:
            name = feat.Name
            type_name = feat.GetTypeName2()  # e.g., "ProfileFeature" (Sketch), "Extrusion" (Boss-Extrude)
            
            # Map native SolidWorks type names to clean friendly types
            friendly_type = type_name
            if type_name == "ProfileFeature":
                friendly_type = "sketch"
            elif type_name == "Extrusion":
                friendly_type = "extrude"
            elif type_name == "Cut":
                friendly_type = "cut"
            elif type_name == "Fillet":
                friendly_type = "fillet"
            elif type_name == "Chamfer":
                friendly_type = "chamfer"
            
            # Sub-features or dimensions if available
            # Note: We can attempt to read values of dimensions belonging to the feature.
            # E.g., if it's a sketch or extrusion, we look up D1@name.
            dimensions = {}
            if friendly_type in ["sketch", "extrude", "cut"]:
                for d_index in [1, 2, 3]:
                    dim_name = f"D{d_index}@{name}"
                    try:
                        param = model.Parameter(dim_name)
                        if param:
                            # Convert back to millimeters from meters
                            dimensions[f"D{d_index}"] = param.SystemValue * 1000.0
                    except Exception:
                        pass

            features_list.append({
                "name": name,
                "type": friendly_type,
                "raw_type": type_name,
                "dimensions": dimensions
            })
            
            # Move to next feature
            feat = feat.GetNextFeature()
            
    except Exception as e:
        logger.error(f"Error traversing features: {e}")
        # Return whatever we gathered or empty
        
    return {
        "document_name": model.GetTitle(),
        "document_type": "Part" if model.GetType() == 1 else "Assembly" if model.GetType() == 2 else "Drawing",
        "features": features_list
    }
