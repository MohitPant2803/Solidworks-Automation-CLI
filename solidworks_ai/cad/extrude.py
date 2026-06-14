import logging
from typing import Any
from solidworks_ai.cad.solidworks import SolidWorksError
from solidworks_ai.config import SWConstants

logger = logging.getLogger(__name__)

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
    model.ClearSelection2(True)
    success = model.Extension.SelectByID2(sketch_name, "SKETCH", 0, 0, 0, False, 0, None, 0)
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
    feat = feat_mgr.FeatureExtrusion3(
        True,                                # Sd (Single direction)
        False,                               # Flip (draft/cut side)
        flip,                                # Dir (True to reverse direction)
        SWConstants.swEndCondBlind,          # T1
        SWConstants.swEndCondBlind,          # T2
        depth,                               # D1
        0.0,                                 # D2
        False,                               # Dchk1 (Draft)
        False,                               # Dchk2 (Draft)
        False,                               # Ddir1
        False,                               # Ddir2
        0.0,                                 # Dang1
        0.0,                                 # Dang2
        False,                               # OffsetReverse1
        False,                               # OffsetReverse2
        False,                               # TranslateSurface1
        False,                               # TranslateSurface2
        True,                                # Merge
        True,                                # UseFeatScope
        True,                                # UseAutoSelect
        0,                                   # T0 (StartCondition = Sketch Plane)
        0.0,                                 # StartOffset
        False                                # FlipStartOffset
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
    model.ClearSelection2(True)
    success = model.Extension.SelectByID2(sketch_name, "SKETCH", 0, 0, 0, False, 0, None, 0)
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
    feat = feat_mgr.FeatureCut4(
        True,                                # Sd (Single direction)
        False,                               # Flip
        flip_dir,                            # Dir
        end_condition,                       # T1
        SWConstants.swEndCondBlind,          # T2
        depth,                               # D1
        0.0,                                 # D2
        False,                               # Dchk1 (Draft)
        False,                               # Dchk2 (Draft)
        False,                               # Ddir1
        False,                               # Ddir2
        0.0,                                 # Dang1
        0.0,                                 # Dang2
        False,                               # OffsetReverse1
        False,                               # OffsetReverse2
        False,                               # TranslateSurface1
        False,                               # TranslateSurface2
        False,                               # NormalCut
        True,                                # UseFeatScope
        True,                                # UseAutoSelect
        True,                                # AssemblyFeatureScope
        True,                                # ConPropagate
        True,                                # ModelPropagate
        True,                                # PropagateToParts
        0,                                   # T0 (StartCondition = Sketch Plane)
        0.0,                                 # StartOffset
        False                                # FlipStartOffset
    )

    if not feat:
        raise SolidWorksError(f"FeatureCut4 returned null for sketch '{sketch_name}'. Check cut geometry.")

    logger.info(f"Created Cut Extrude feature: {feat.Name}")
    return feat.Name
