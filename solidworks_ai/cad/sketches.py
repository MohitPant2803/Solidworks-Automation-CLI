import logging
from typing import Any, Tuple, Optional
import win32com.client
import pythoncom
from solidworks_ai.cad.solidworks import SolidWorksError

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# COM helpers – explicit VARIANT wrapping avoids every "Type mismatch" /
# "Member not found" error that pywin32 late-binding can cause.
# ---------------------------------------------------------------------------
def _null_dispatch():
    """Returns a properly typed NULL IDispatch VARIANT for Callout params."""
    return win32com.client.VARIANT(pythoncom.VT_DISPATCH, None)

def _safe_select(model: Any, name: str, sel_type: str,
                 x: float = 0.0, y: float = 0.0, z: float = 0.0,
                 append: bool = False, mark: int = 0) -> bool:
    """
    Wrapper around ModelDocExtension.SelectByID2 with fully typed params.
    Every argument is explicitly cast to the COM-expected type.
    """
    try:
        return model.Extension.SelectByID2(
            str(name),            # BSTR  Name
            str(sel_type),        # BSTR  Type
            float(x),             # Double X
            float(y),             # Double Y
            float(z),             # Double Z
            bool(append),         # VARIANT_BOOL Append
            int(mark),            # Long  Mark
            _null_dispatch(),     # IDispatch Callout  (NULL)
            int(0)                # Long  SelectOption
        )
    except Exception as e:
        logger.warning(f"SelectByID2('{name}', '{sel_type}') failed: {e}")
        return False


def select_plane_or_face(model: Any, name: str) -> bool:
    """
    Selects a plane or face by its name.
    Common plane names: 'Front Plane', 'Top Plane', 'Right Plane'.
    """
    model.ClearSelection2(True)

    # Check common planes first, format properly
    search_name = name.strip()
    if search_name.lower() in ["front", "front plane"]:
        search_name = "Front Plane"
    elif search_name.lower() in ["top", "top plane"]:
        search_name = "Top Plane"
    elif search_name.lower() in ["right", "right plane"]:
        search_name = "Right Plane"

    obj_type = "PLANE"
    if "plane" not in search_name.lower():
        obj_type = "FACE"

    success = _safe_select(model, search_name, obj_type)

    if not success and obj_type == "FACE":
        # Fallback to general select
        success = _safe_select(model, search_name, "EXTRUDESURF")

    if not success:
        logger.warning(f"Could not select plane/face named '{name}'. Attempting default Front Plane.")
        success = _safe_select(model, "Front Plane", "PLANE")
        if not success:
            raise SolidWorksError(f"Failed to select plane or face: {name}")

    return success


def start_sketch(model: Any, plane_or_face_name: str) -> None:
    """Selects the plane/face and enters sketch mode."""
    select_plane_or_face(model, plane_or_face_name)
    try:
        model.InsertSketch2(True)
    except Exception as e:
        raise SolidWorksError(f"InsertSketch2 failed when opening sketch on '{plane_or_face_name}': {e}")
    logger.info(f"Entered sketch mode on '{plane_or_face_name}'")


def close_sketch(model: Any, save_changes: bool = True) -> None:
    """Exits sketch mode."""
    try:
        model.InsertSketch2(save_changes)
    except Exception as e:
        raise SolidWorksError(f"InsertSketch2 failed when closing sketch: {e}")
    logger.info("Exited sketch mode.")


def _get_sketch_name(model: Any) -> str:
    """
    Safely retrieves the active sketch's feature name.
    The ISketch COM object does NOT have a .Name property — we must go
    through ISketch.GetFeature() -> IFeature.Name.
    """
    try:
        active_sketch = model.ActiveSketch
        if active_sketch:
            sketch_feat = active_sketch.GetFeature()
            if sketch_feat:
                return sketch_feat.Name
    except Exception as e:
        logger.warning(f"Could not read active sketch name: {e}")
    return "Sketch1"


def create_rectangle(
    model: Any,
    plane_name: str,
    width_mm: float,
    height_mm: float,
    xc_mm: float = 0.0,
    yc_mm: float = 0.0
) -> str:
    """
    Creates a center rectangle sketch on the specified plane.
    Returns the sketch name (e.g. 'Sketch1').
    """
    start_sketch(model, plane_name)

    sketch_mgr = model.SketchManager

    # Convert mm to meters (SolidWorks COM API works in meters)
    xc = float(xc_mm) / 1000.0
    yc = float(yc_mm) / 1000.0
    w  = float(width_mm) / 1000.0
    h  = float(height_mm) / 1000.0

    # Center rectangle: Center point and one Corner point
    # CreateCenterRectangle(xc, yc, zc, x_corner, y_corner, z_corner)
    try:
        rect_segments = sketch_mgr.CreateCenterRectangle(
            float(xc), float(yc), float(0.0),
            float(xc + w / 2.0), float(yc + h / 2.0), float(0.0)
        )
    except Exception as e:
        close_sketch(model, False)
        raise SolidWorksError(f"CreateCenterRectangle failed: {e}")

    if not rect_segments:
        close_sketch(model, False)
        raise SolidWorksError("CreateCenterRectangle returned no segments.")

    # Add dimensions to fully define the sketch
    try:
        null_sel = _null_dispatch()
        rect_segments[0].Select4(False, null_sel)
        model.AddDimension2(float(xc), float(yc + h / 2.0 + 0.01), float(0.0))

        rect_segments[1].Select4(False, null_sel)
        model.AddDimension2(float(xc + w / 2.0 + 0.01), float(yc), float(0.0))
    except Exception as e:
        logger.warning(f"Could not fully add dimensions to sketch segments: {e}")

    sketch_name = _get_sketch_name(model)

    close_sketch(model, True)
    return sketch_name


def create_circle(
    model: Any,
    plane_name: str,
    diameter_mm: float,
    xc_mm: float = 0.0,
    yc_mm: float = 0.0
) -> str:
    """
    Creates a circle sketch on the specified plane/face.
    Returns the sketch name.
    """
    start_sketch(model, plane_name)

    sketch_mgr = model.SketchManager

    # Convert mm to meters
    xc = float(xc_mm) / 1000.0
    yc = float(yc_mm) / 1000.0
    r  = float(diameter_mm) / 2.0 / 1000.0

    # CreateCircle(xc, yc, zc, xp, yp, zp)
    try:
        circle = sketch_mgr.CreateCircle(
            float(xc), float(yc), float(0.0),
            float(xc + r), float(yc), float(0.0)
        )
    except Exception as e:
        close_sketch(model, False)
        raise SolidWorksError(f"CreateCircle failed: {e}")

    if not circle:
        close_sketch(model, False)
        raise SolidWorksError("CreateCircle returned None.")

    try:
        null_sel = _null_dispatch()
        circle.Select4(False, null_sel)
        model.AddDimension2(float(xc + r + 0.01), float(yc + 0.01), float(0.0))
    except Exception as e:
        logger.warning(f"Could not dimension circle sketch: {e}")

    sketch_name = _get_sketch_name(model)

    close_sketch(model, True)
    return sketch_name
