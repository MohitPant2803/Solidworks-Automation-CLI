import logging
from typing import Any
from solidworks_ai.cad.sketches import create_circle
from solidworks_ai.cad.extrude import cut_extrude

logger = logging.getLogger(__name__)

def create_hole(
    model: Any,
    plane_or_face_name: str,
    diameter_mm: float,
    depth_mm: float,  # -1 for Through All
    x_mm: float,
    y_mm: float
) -> str:
    """
    Creates a standard circular hole at (x, y) coordinates relative to a plane or face
    by sketching a circle and then applying a cut extrusion.
    """
    logger.info(f"Creating hole of dia {diameter_mm} mm, depth {depth_mm} mm at ({x_mm}, {y_mm}) on {plane_or_face_name}")
    
    # 1. Create a circle sketch
    sketch_name = create_circle(
        model=model,
        plane_name=plane_or_face_name,
        diameter_mm=diameter_mm,
        xc_mm=x_mm,
        yc_mm=y_mm
    )
    
    # 2. Perform cut extrusion
    feature_name = cut_extrude(
        model=model,
        sketch_name=sketch_name,
        depth_mm=depth_mm
    )
    
    logger.info(f"Hole created successfully: feature {feature_name} using sketch {sketch_name}")
    return feature_name
