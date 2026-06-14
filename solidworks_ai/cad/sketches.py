import logging
from typing import Any, Tuple, Optional
import win32com.client
from solidworks_ai.cad.solidworks import SolidWorksError

logger = logging.getLogger(__name__)

def select_plane_or_face(model: Any, name: str) -> bool:
    """
    Selects a plane or face by its name.
    Common plane names: 'Front Plane', 'Top Plane', 'Right Plane'.
    """
    model.ClearSelection2(True)
    # SelectByID2(Name, Type, X, Y, Z, Append, Mark, Callout, SelectOption)
    
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
        
    success = model.Extension.SelectByID2(search_name, obj_type, 0, 0, 0, False, 0, None, 0)
    if not success and obj_type == "FACE":
        # Fallback to general select
        success = model.Extension.SelectByID2(search_name, "EXTRUDESURF", 0, 0, 0, False, 0, None, 0)
        
    if not success:
        logger.warning(f"Could not select plane/face named '{name}'. attempting default Front Plane.")
        success = model.Extension.SelectByID2("Front Plane", "PLANE", 0, 0, 0, False, 0, None, 0)
        if not success:
            raise SolidWorksError(f"Failed to select plane or face: {name}")
            
    return success

def start_sketch(model: Any, plane_or_face_name: str) -> None:
    """Selects the plane/face and enters sketch mode."""
    select_plane_or_face(model, plane_or_face_name)
    # InsertSketch2(UpdateDoc) -> enters sketch mode if not already in it
    model.InsertSketch2(True)
    logger.info(f"Entered sketch mode on '{plane_or_face_name}'")

def close_sketch(model: Any, save_changes: bool = True) -> None:
    """Exits sketch mode."""
    # InsertSketch2(UpdateDoc) -> toggles/exits sketch mode
    model.InsertSketch2(save_changes)
    logger.info("Exited sketch mode.")

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
    
    # Convert mm to meters
    xc = xc_mm / 1000.0
    yc = yc_mm / 1000.0
    w = width_mm / 1000.0
    h = height_mm / 1000.0
    
    # Center rectangle: Center point and one Corner point
    # CreateCenterRectangle(xc, yc, zc, x_corner, y_corner, z_corner)
    rect_segments = sketch_mgr.CreateCenterRectangle(xc, yc, 0.0, xc + (w / 2.0), yc + (h / 2.0), 0.0)
    if not rect_segments:
        raise SolidWorksError("Failed to draw center rectangle sketch.")

    # Add dimensions to fully define the sketch
    # Select horizontal segment to dimension width
    # In center rectangle, segment 0 or 2 is horizontal
    try:
        rect_segments[0].Select4(False, None)
        model.AddDimension2(xc, yc + (h / 2.0) + 0.01, 0.0)
        
        # Select vertical segment to dimension height
        rect_segments[1].Select4(False, None)
        model.AddDimension2(xc + (w / 2.0) + 0.01, yc, 0.0)
    except Exception as e:
        logger.warning(f"Could not fully add dimensions to sketch segments: {e}")

    # Get active sketch name
    active_sketch = model.GetActiveSketch2()
    sketch_name = active_sketch.Name if active_sketch else "Sketch1"
    
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
    xc = xc_mm / 1000.0
    yc = yc_mm / 1000.0
    r = (diameter_mm / 2.0) / 1000.0
    
    # CreateCircle(xc, yc, zc, xp, yp, zp)
    circle = sketch_mgr.CreateCircle(xc, yc, 0.0, xc + r, yc, 0.0)
    if not circle:
        raise SolidWorksError("Failed to draw circle sketch.")
        
    try:
        # Select circle to add dimension
        circle.Select4(False, None)
        model.AddDimension2(xc + r + 0.01, yc + 0.01, 0.0)
    except Exception as e:
        logger.warning(f"Could not dimension circle sketch: {e}")

    active_sketch = model.GetActiveSketch2()
    sketch_name = active_sketch.Name if active_sketch else "Sketch1"
    
    close_sketch(model, True)
    return sketch_name
