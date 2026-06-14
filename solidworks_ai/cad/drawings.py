import os
import logging
from typing import Any, List, Optional
from pathlib import Path
from solidworks_ai.cad.solidworks import SolidWorksError

logger = logging.getLogger(__name__)

def create_drawing(sw: Any) -> Any:
    """
    Creates a new drawing document in SolidWorks using the default template.
    Returns the drawing document (ModelDoc2) object.
    """
    logger.info("Creating new drawing document...")
    
    # 1. Attempt to get default drawing template path
    template_path = ""
    try:
        # 8 is swUserPreferenceStringValue_e.swDefaultTemplateDrawing
        template_path = sw.GetUserPreferenceStringValue(8)
        logger.info(f"Default drawing template path: '{template_path}'")
    except Exception as e:
        logger.warning(f"Could not retrieve default drawing template path: {e}")
    
    drawing_doc = None
    
    # Try different ways to instantiate a drawing document
    try:
        # Paper size: 2 = swDwgPaperAsize
        drawing_doc = sw.NewDocument(template_path, 2, 0.2794, 0.2159)
    except Exception as e:
        logger.warning(f"Failed to create drawing doc with template: {e}. Trying standard empty template...")
    
    if not drawing_doc:
        try:
            drawing_doc = sw.NewDocument("", 2, 0.2794, 0.2159)
        except Exception as e:
            logger.warning(f"Failed with empty template name: {e}. Trying NewDrawing2...")
    
    if not drawing_doc:
        try:
            # NewDrawing2(PaperSize, TemplateName, Width, Height)
            drawing_doc = sw.NewDrawing2(2, "", 0.2794, 0.2159)
        except Exception as e:
            logger.warning(f"Failed to create new drawing document via NewDrawing2: {e}")
            
    if not drawing_doc:
        # Final fallback: NewDocument("", 0, 0, 0)
        try:
            drawing_doc = sw.NewDocument("", 0, 0, 0)
        except Exception as e:
            raise SolidWorksError(f"Failed to create drawing: {e}")

    if not drawing_doc:
        raise SolidWorksError("Failed to create new drawing document. No document active.")
        
    logger.info("Drawing document created successfully.")
    return drawing_doc

def create_drawing_views(drawing_doc: Any, model_path: str) -> List[str]:
    """
    Creates standard views (Front, Top, Right, Isometric) for the given 3D model path.
    """
    resolved_path = str(Path(model_path).resolve())
    if not os.path.exists(resolved_path):
        raise SolidWorksError(f"Cannot create drawing views: model path does not exist '{resolved_path}'")
    
    # Cast drawing_doc to DrawingDoc
    # CreateDrawViewFromModelView3(ModelName, ViewName, X, Y, Z)
    # ViewName values: "*Front", "*Top", "*Right", "*Isometric"
    # Positions are in meters
    views_to_create = [
        {"name": "*Front", "x": 0.08, "y": 0.08},
        {"name": "*Top", "x": 0.08, "y": 0.16},
        {"name": "*Right", "x": 0.18, "y": 0.08},
        {"name": "*Isometric", "x": 0.18, "y": 0.16}
    ]
    
    created_views = []
    for view_info in views_to_create:
        view_name = view_info["name"]
        x = view_info["x"]
        y = view_info["y"]
        logger.info(f"Creating view '{view_name}' at X={x}m, Y={y}m for model '{resolved_path}'")
        
        view_obj = drawing_doc.CreateDrawViewFromModelView3(
            resolved_path,
            view_name,
            x,
            y,
            0.0
        )
        if not view_obj:
            logger.warning(f"Failed to create view '{view_name}'.")
        else:
            logger.info(f"View '{view_name}' created successfully: {view_obj.Name}")
            created_views.append(view_obj.Name)
            
    if not created_views:
        raise SolidWorksError(f"Failed to create any drawing views for model: '{resolved_path}'")
        
    # Rebuild sheet
    drawing_doc.EditRebuild3()
    return created_views
