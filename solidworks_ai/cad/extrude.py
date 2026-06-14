import logging
from typing import Any
import win32com.client
import pythoncom
from solidworks_ai.cad.solidworks import SolidWorksError
from solidworks_ai.config import SWConstants

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers for COM VARIANT wrapping
# ---------------------------------------------------------------------------
def _bool(val: bool):
    """Wrap a Python bool as a COM VARIANT_BOOL."""
    return win32com.client.VARIANT(pythoncom.VT_BOOL, bool(val))

def _long(val: int):
    """Wrap a Python int as a COM VT_I4 (Long)."""
    return win32com.client.VARIANT(pythoncom.VT_I4, int(val))

def _double(val: float):
    """Wrap a Python float as a COM VT_R8 (Double)."""
    return win32com.client.VARIANT(pythoncom.VT_R8, float(val))

def _dispatch_none():
    """Return a COM VT_DISPATCH variant set to None (null pointer)."""
    return win32com.client.VARIANT(pythoncom.VT_DISPATCH, None)


def boss_extrude(
    model: Any,
    sketch_name: str,
    depth_mm: float,
    flip: bool = False
) -> str:
    """
    Extrudes a sketch to a blind depth in millimeters.
    Returns the feature name (e.g. 'Boss-Extrude1').
    """
    # 1. Select the sketch
    # SelectByID2(Name, Type, X, Y, Z, Append, Mark, Callout, SelectOption)
    try:
        model.ClearSelection2(True)
    except Exception as e:
        raise SolidWorksError(f"ClearSelection2 failed before boss_extrude: {e}")

    null_callout = _dispatch_none()
    try:
        success = model.Extension.SelectByID2(
            sketch_name,       # Name
            "SKETCH",          # Type
            _double(0.0),      # X
            _double(0.0),      # Y
            _double(0.0),      # Z
            _bool(False),      # Append
            _long(0),          # Mark
            null_callout,      # Callout
            _long(0)           # SelectOption
        )
    except Exception as e:
        raise SolidWorksError(
            f"Extension.SelectByID2 failed for sketch '{sketch_name}' "
            f"in boss_extrude: {e}"
        )

    if not success:
        raise SolidWorksError(f"Failed to select sketch '{sketch_name}' for extrusion.")

    # Convert mm to meters
    depth = depth_mm / 1000.0

    # 2. Call FeatureExtrusion3
    # Parameters:
    # Sd (Single direction), Flip (flip side to cut / direction), Dir (flip direction of extrusion), 
    # T1 (Type of end condition for Dir1), T2 (Type of end condition for Dir2), 
    # D1 (Depth Dir1), D2 (Depth Dir2), Dchk1 (Draft Dir1), Dchk2 (Draft Dir2), 
    # Ddir1 (Draft Dir1 direction), Ddir2 (Draft Dir2 direction), 
    # Dang1 (Draft angle Dir1), Dang2 (Draft angle Dir2), 
    # OffsetReverse1, OffsetReverse2, TranslateSurface1, TranslateSurface2, 
    # Merge (Merge results), UseFeatScope, UseAutoSelect, T0 (StartCondition), 
    # StartOffset, FlipStartOffset
    feat_mgr = model.FeatureManager
    try:
        feat = feat_mgr.FeatureExtrusion3(
            _bool(True),                                 # Sd (Single direction)
            _bool(False),                                # Flip (draft/cut side)
            _bool(flip),                                 # Dir (True to reverse direction)
            _long(SWConstants.swEndCondBlind),            # T1
            _long(SWConstants.swEndCondBlind),            # T2
            _double(depth),                              # D1
            _double(0.0),                                # D2
            _bool(False),                                # Dchk1 (Draft)
            _bool(False),                                # Dchk2 (Draft)
            _bool(False),                                # Ddir1
            _bool(False),                                # Ddir2
            _double(0.0),                                # Dang1
            _double(0.0),                                # Dang2
            _bool(False),                                # OffsetReverse1
            _bool(False),                                # OffsetReverse2
            _bool(False),                                # TranslateSurface1
            _bool(False),                                # TranslateSurface2
            _bool(True),                                 # Merge
            _bool(True),                                 # UseFeatScope
            _bool(True),                                 # UseAutoSelect
            _long(0),                                    # T0 (StartCondition = Sketch Plane)
            _double(0.0),                                # StartOffset
            _bool(False)                                 # FlipStartOffset
        )
    except Exception as e:
        raise SolidWorksError(
            f"FeatureManager.FeatureExtrusion3 failed for sketch '{sketch_name}' "
            f"(depth={depth_mm}mm, flip={flip}): {e}"
        )

    if not feat:
        raise SolidWorksError(f"FeatureExtrusion3 returned null for sketch '{sketch_name}'. Check geometry.")

    logger.info(f"Created Boss Extrude feature: {feat.Name} with depth {depth_mm} mm")
    return feat.Name

def cut_extrude(
    model: Any,
    sketch_name: str,
    depth_mm: float,
    flip_dir: bool = False
) -> str:
    """
    Cuts a sketch to a blind depth or through-all.
    If depth_mm is -1, it performs a through-all cut.
    Returns the cut feature name.
    """
    try:
        model.ClearSelection2(True)
    except Exception as e:
        raise SolidWorksError(f"ClearSelection2 failed before cut_extrude: {e}")

    null_callout = _dispatch_none()
    try:
        success = model.Extension.SelectByID2(
            sketch_name,       # Name
            "SKETCH",          # Type
            _double(0.0),      # X
            _double(0.0),      # Y
            _double(0.0),      # Z
            _bool(False),      # Append
            _long(0),          # Mark
            null_callout,      # Callout
            _long(0)           # SelectOption
        )
    except Exception as e:
        raise SolidWorksError(
            f"Extension.SelectByID2 failed for sketch '{sketch_name}' "
            f"in cut_extrude: {e}"
        )

    if not success:
        raise SolidWorksError(f"Failed to select sketch '{sketch_name}' for cut extrusion.")

    # Convert mm to meters
    depth = depth_mm / 1000.0 if depth_mm > 0 else 0.0
    end_condition = SWConstants.swEndCondBlind if depth_mm > 0 else SWConstants.swEndCondThroughAll

    # 27 Parameters for FeatureCut4:
    # Sd (Single direction), Flip (flip side to cut), Dir (flip direction of cut),
    # T1 (End Condition), T2 (End Condition), D1 (Depth), D2 (Depth),
    # Dchk1 (Draft), Dchk2 (Draft), Ddir1 (Draft direction), Ddir2 (Draft direction),
    # Dang1 (Draft angle), Dang2 (Draft angle), OffsetReverse1, OffsetReverse2,
    # TranslateSurface1, TranslateSurface2, NormalCut, UseFeatScope, UseAutoSelect,
    # AssemblyFeatureScope, ConPropagate, ModelPropagate, PropagateToParts, T0 (StartCondition),
    # StartOffset, FlipStartOffset
    feat_mgr = model.FeatureManager
    try:
        feat = feat_mgr.FeatureCut4(
            _bool(True),                                 # Sd (Single direction)
            _bool(False),                                # Flip
            _bool(flip_dir),                             # Dir
            _long(end_condition),                        # T1
            _long(SWConstants.swEndCondBlind),            # T2
            _double(depth),                              # D1
            _double(0.0),                                # D2
            _bool(False),                                # Dchk1 (Draft)
            _bool(False),                                # Dchk2 (Draft)
            _bool(False),                                # Ddir1
            _bool(False),                                # Ddir2
            _double(0.0),                                # Dang1
            _double(0.0),                                # Dang2
            _bool(False),                                # OffsetReverse1
            _bool(False),                                # OffsetReverse2
            _bool(False),                                # TranslateSurface1
            _bool(False),                                # TranslateSurface2
            _bool(False),                                # NormalCut
            _bool(True),                                 # UseFeatScope
            _bool(True),                                 # UseAutoSelect
            _bool(True),                                 # AssemblyFeatureScope
            _bool(True),                                 # ConPropagate
            _bool(True),                                 # ModelPropagate
            _bool(True),                                 # PropagateToParts
            _long(0),                                    # T0 (StartCondition = Sketch Plane)
            _double(0.0),                                # StartOffset
            _bool(False)                                 # FlipStartOffset
        )
    except Exception as e:
        raise SolidWorksError(
            f"FeatureManager.FeatureCut4 failed for sketch '{sketch_name}' "
            f"(depth={depth_mm}mm, flip_dir={flip_dir}): {e}"
        )

    if not feat:
        raise SolidWorksError(f"FeatureCut4 returned null for sketch '{sketch_name}'. Check cut geometry.")

    logger.info(f"Created Cut Extrude feature: {feat.Name}")
    return feat.Name
