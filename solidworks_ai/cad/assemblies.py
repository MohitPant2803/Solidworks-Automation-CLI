import logging
from typing import Any, Optional
from solidworks_ai.cad.solidworks import SolidWorksError

logger = logging.getLogger(__name__)

def create_assembly(sw: Any) -> Any:
    """Creates a new assembly document in SolidWorks using the default template."""
    logger.info("Creating new Assembly document...")
    # NewAssembly is a shortcut method that returns the active doc
    sw.NewAssembly()
    model = sw.ActiveDoc
    if not model:
        raise SolidWorksError("Failed to create a new assembly document.")
    logger.info("Assembly document created successfully.")
    return model

def add_component(
    model: Any,
    component_path: str,
    x_mm: float = 0.0,
    y_mm: float = 0.0,
    z_mm: float = 0.0,
    friendly_name: str = ""
) -> Any:
    """
    Inserts a Part (.sldprt) or sub-assembly into the active assembly document.
    Coordinates are translated from mm to meters for COM.
    """
    doc_type = model.GetType()
    if doc_type != 2:  # swDocASSEMBLY
        raise SolidWorksError("Component insertion is only supported inside Assembly (.sldasm) documents.")

    logger.info(f"Adding component from path: '{component_path}' at ({x_mm}, {y_mm}, {z_mm}) mm")

    # Convert coordinates to meters
    x = x_mm / 1000.0
    y = y_mm / 1000.0
    z = z_mm / 1000.0

    # Cast model to AssemblyDoc
    # AddComponent5(CompName, ConfigOption, ConfigName, DispStateOption, DispStateName, X, Y, Z)
    # ConfigOption: 0 = uses default configuration
    assembly = model
    comp = assembly.AddComponent5(component_path, 0, "", 0, "", x, y, z)
    if not comp:
        raise SolidWorksError(f"Failed to add component '{component_path}' to assembly.")

    # Rebuild to apply
    model.EditRebuild3()
    logger.info(f"Added component: {comp.Name2}")
    return comp

def add_assembly_mate(
    model: Any,
    comp1_name: str,
    comp2_name: str,
    mate_type: str,  # "concentric", "coincident", "parallel", "perpendicular"
    align: int = 1   # 1 = aligned, 2 = anti-aligned
) -> Any:
    """
    Programmatically mates two components by:
    1. Finding target components by friendly name match.
    2. Finding matching face geometry (planar for coincident/parallel, cylindrical for concentric).
    3. Selecting the entities.
    4. Executing AssemblyDoc.AddMate5.
    """
    doc_type = model.GetType()
    if doc_type != 2:  # swDocASSEMBLY
        raise SolidWorksError("Mates can only be created inside Assembly (.sldasm) documents.")

    assembly = model
    
    # 1. Resolve components
    components = assembly.GetComponents(False)
    comp1 = None
    comp2 = None
    
    for c in components:
        # Match component names (substring match)
        c_name = c.Name2.lower()
        if comp1_name.lower() in c_name:
            comp1 = c
        if comp2_name.lower() in c_name:
            comp2 = c

    if not comp1:
        raise SolidWorksError(f"Could not find component matching name: '{comp1_name}' in assembly.")
    if not comp2:
        raise SolidWorksError(f"Could not find component matching name: '{comp2_name}' in assembly.")

    # 2. Clear selections
    model.ClearSelection2(True)

    # 3. Find suitable faces to mate based on mate type
    ent1 = None
    ent2 = None
    
    if mate_type.lower() == "concentric":
        ent1 = _find_cylindrical_face(comp1)
        ent2 = _find_cylindrical_face(comp2)
        sw_mate_type = 1  # swMateCONCENTRIC
    elif mate_type.lower() in ["coincident", "parallel", "perpendicular"]:
        ent1 = _find_planar_face(comp1)
        ent2 = _find_planar_face(comp2)
        if mate_type.lower() == "coincident":
            sw_mate_type = 0  # swMateCOINCIDENT
        elif mate_type.lower() == "parallel":
            sw_mate_type = 2  # swMatePARALLEL
        else:
            sw_mate_type = 3  # swMatePERPENDICULAR
    else:
        raise SolidWorksError(f"Unsupported mate type: '{mate_type}'")

    if not ent1 or not ent2:
        raise SolidWorksError(f"Could not find matching geometry (faces) to create '{mate_type}' mate between '{comp1_name}' and '{comp2_name}'.")

    # 4. Select both faces (using Select4 to append)
    ent1.Select4(True, None)
    ent2.Select4(True, None)

    # 5. Call AddMate5
    # AddMate5(MateType, Align, Flip, Distance, Angle, WidthMax, WidthMin, AddMicroRoute, ...
    # Align: 0 = Aligned, 1 = Anti-Aligned, 2 = Closest
    align_val = 0 if align == 1 else 1
    
    errors = 0
    # AddMate5 returns Mate2 object on success
    mate = assembly.AddMate5(sw_mate_type, align_val, False, 0.0, 0.0, 0.0, 0.0, False, False, 0, errors)
    
    if not mate:
        raise SolidWorksError(f"AddMate5 failed to create '{mate_type}' mate. COM error code: {errors}")

    model.EditRebuild3()
    logger.info(f"Successfully created '{mate_type}' mate: {mate.Name}")
    return mate

def _find_cylindrical_face(component: Any) -> Optional[Any]:
    """Helper to return the first cylindrical face found in component bodies."""
    # GetBodies3(1) -> 1 = solid bodies
    bodies = component.GetBodies3(1)
    if not bodies:
        return None
    for body in bodies:
        faces = body.GetFaces()
        for face in faces:
            surf = face.GetSurface()
            if surf.IsCylinder():
                return face
    return None

def _find_planar_face(component: Any) -> Optional[Any]:
    """Helper to return the first planar face found in component bodies."""
    bodies = component.GetBodies3(1)
    if not bodies:
        return None
    for body in bodies:
        faces = body.GetFaces()
        for face in faces:
            surf = face.GetSurface()
            if surf.IsPlane():
                return face
    return None
