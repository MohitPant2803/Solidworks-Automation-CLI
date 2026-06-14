import logging
from typing import Any, List
import win32com.client
import pythoncom
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
    radius = float(radius_mm) / 1000.0
    
    # Pre-build VARIANT-wrapped null dispatch for SelectByID2 Callout parameter
    null_callout = win32com.client.VARIANT(pythoncom.VT_DISPATCH, None)
    # Pre-build VARIANT-wrapped null dispatch for Select4 SelectionData parameter
    null_sel_data = win32com.client.VARIANT(pythoncom.VT_DISPATCH, None)
    
    # 1. Clear selection
    try:
        model.ClearSelection2(True)
    except Exception as e:
        raise SolidWorksError(f"ClearSelection2 failed: {e}")
    
    # 2. Try to get as feature first
    try:
        feature = model.FeatureByName(target_name)
    except Exception as e:
        raise SolidWorksError(f"FeatureByName('{target_name}') failed: {e}")
    
    selection_made = False
    
    if feature:
        # If it's a feature, select all its faces. SolidWorks will fillet all edges of these faces.
        logger.info(f"Target '{target_name}' is a feature. Selecting its faces to apply fillet.")
        try:
            faces = feature.GetFaces()
        except Exception as e:
            raise SolidWorksError(f"GetFaces() on feature '{target_name}' failed: {e}")
        
        if faces:
            # We must select all faces to fillet all edges.
            # Using Select4 to append (True)
            for i, face in enumerate(faces):
                # face.Select4(Append, SelectionData)
                # First one clear selection, subsequent append
                try:
                    face.Select4(
                        win32com.client.VARIANT(pythoncom.VT_BOOL, True),   # Append
                        null_sel_data                                        # SelectionData (IDispatch, None)
                    )
                except Exception as e:
                    raise SolidWorksError(f"Select4 failed on face index {i} of feature '{target_name}': {e}")
            selection_made = True
        else:
            # Fallback to feature selection
            try:
                selection_made = model.Extension.SelectByID2(
                    str(target_name),                                        # Name
                    str("BODYFEATURE"),                                       # Type
                    float(0.0),                                              # X
                    float(0.0),                                              # Y
                    float(0.0),                                              # Z
                    win32com.client.VARIANT(pythoncom.VT_BOOL, False),       # Append
                    int(0),                                                  # Mark
                    null_callout,                                            # Callout (IDispatch, None)
                    int(0)                                                   # SelectOption
                )
            except Exception as e:
                raise SolidWorksError(
                    f"SelectByID2('{target_name}', 'BODYFEATURE') failed: {e}"
                )
    else:
        # If not a feature, try to select by ID directly (e.g. FACE or EDGE)
        logger.info(f"Target '{target_name}' not found as feature. Attempting general selection as FACE/EDGE.")
        try:
            selection_made = model.Extension.SelectByID2(
                str(target_name),                                            # Name
                str("FACE"),                                                 # Type
                float(0.0),                                                  # X
                float(0.0),                                                  # Y
                float(0.0),                                                  # Z
                win32com.client.VARIANT(pythoncom.VT_BOOL, False),           # Append
                int(0),                                                      # Mark
                null_callout,                                                # Callout (IDispatch, None)
                int(0)                                                       # SelectOption
            )
        except Exception as e:
            raise SolidWorksError(
                f"SelectByID2('{target_name}', 'FACE') failed: {e}"
            )
        
        if not selection_made:
            try:
                selection_made = model.Extension.SelectByID2(
                    str(target_name),                                        # Name
                    str("EDGE"),                                             # Type
                    float(0.0),                                              # X
                    float(0.0),                                              # Y
                    float(0.0),                                              # Z
                    win32com.client.VARIANT(pythoncom.VT_BOOL, False),       # Append
                    int(0),                                                  # Mark
                    null_callout,                                            # Callout (IDispatch, None)
                    int(0)                                                   # SelectOption
                )
            except Exception as e:
                raise SolidWorksError(
                    f"SelectByID2('{target_name}', 'EDGE') failed: {e}"
                )
             
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
    try:
        feat_mgr = model.FeatureManager
    except Exception as e:
        raise SolidWorksError(f"Failed to access FeatureManager: {e}")
    
    try:
        fillet_feat = feat_mgr.FeatureFillet3(
            win32com.client.VARIANT(pythoncom.VT_I4, int(0)),                # Options (constant radius)
            win32com.client.VARIANT(pythoncom.VT_R8, float(radius)),         # Radius (meters)
            win32com.client.VARIANT(pythoncom.VT_BOOL, True),                # Propagate (tangent propagation)
            win32com.client.VARIANT(pythoncom.VT_BOOL, False),               # Help
            win32com.client.VARIANT(pythoncom.VT_I4, int(0)),                # CornerType
            win32com.client.VARIANT(pythoncom.VT_R8, float(0.0)),            # SetbackValue
            win32com.client.VARIANT(pythoncom.VT_I4, int(0))                 # SetbackEdgeCount
        )
    except Exception as e:
        raise SolidWorksError(
            f"FeatureFillet3 COM call failed for target '{target_name}' "
            f"with radius={radius} m: {e}"
        )

    if not fillet_feat:
        raise SolidWorksError(f"FeatureFillet3 failed for target '{target_name}'. Validate radius and geometry.")

    logger.info(f"Created Fillet feature: {fillet_feat.Name}")
    return fillet_feat.Name
