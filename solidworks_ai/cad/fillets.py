import logging
from typing import Any, List
from solidworks_ai.cad.solidworks import SolidWorksError

logger = logging.getLogger(__name__)

def apply_fillet(
    model: Any,
    target_name: str,  # Can be a feature name (e.g. "Boss-Extrude1") or specific face/edge selection ID
    radius_mm: float
) -> str:
    """
    Applies a constant-radius fillet to the specified feature's edges, face, or edge.
    Returns the fillet feature name.
    """
    logger.info(f"Applying fillet of radius {radius_mm} mm to '{target_name}'")
    
    # Convert mm to meters
    radius = radius_mm / 1000.0
    
    # 1. Clear selection
    model.ClearSelection2(True)
    
    # 2. Try to get as feature first
    feature = model.FeatureByName(target_name)
    selection_made = False
    
    if feature:
        # If it's a feature, select all its faces. SolidWorks will fillet all edges of these faces.
        logger.info(f"Target '{target_name}' is a feature. Selecting its faces to apply fillet.")
        faces = feature.GetFaces()
        if faces:
            # We must select all faces to fillet all edges.
            # Using Select4 to append (True)
            for i, face in enumerate(faces):
                # face.Select4(Append, SelectionData)
                # First one clear selection, subsequent append
                face.Select4(True, None)
            selection_made = True
        else:
            # Fallback to feature selection
            selection_made = model.Extension.SelectByID2(target_name, "BODYFEATURE", 0, 0, 0, False, 0, None, 0)
    else:
        # If not a feature, try to select by ID directly (e.g. FACE or EDGE)
        logger.info(f"Target '{target_name}' not found as feature. Attempting general selection as FACE/EDGE.")
        selection_made = model.Extension.SelectByID2(target_name, "FACE", 0, 0, 0, False, 0, None, 0)
        if not selection_made:
            selection_made = model.Extension.SelectByID2(target_name, "EDGE", 0, 0, 0, False, 0, None, 0)
            
    if not selection_made:
        raise SolidWorksError(f"Could not select target '{target_name}' for fillet operation.")

    # 3. Call FeatureFillet3
    # FeatureFillet3(Options, Radius, Propagate, Help, CornerType, SetbackValue, SetbackEdgeCount)
    # Options: 0 = Constant radius, 1 = Variable radius, etc.
    # Propagate: True (tangent propagation)
    # Help: False
    # CornerType: 0
    # SetbackValue: 0.0
    # SetbackEdgeCount: 0
    feat_mgr = model.FeatureManager
    fillet_feat = feat_mgr.FeatureFillet3(
        0,                                   # Options (constant radius)
        radius,                              # Radius (meters)
        True,                                # Propagate (tangent propagation)
        False,                               # Help
        0,                                   # CornerType
        0.0,                                 # SetbackValue
        0                                    # SetbackEdgeCount
    )

    if not fillet_feat:
        raise SolidWorksError(f"FeatureFillet3 failed for target '{target_name}'. Validate radius and geometry.")

    logger.info(f"Created Fillet feature: {fillet_feat.Name}")
    return fillet_feat.Name
