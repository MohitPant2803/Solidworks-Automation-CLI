from typing import Literal, Optional, Dict, Any, List
from pydantic import BaseModel, Field, root_validator

class CreatePlateCommand(BaseModel):
    tool: Literal["create_plate"] = "create_plate"
    length: float = Field(..., description="Length of the plate in mm (along X/horizontal axis)")
    width: float = Field(..., description="Width of the plate in mm (along Y/vertical axis)")
    thickness: float = Field(..., description="Thickness of extrusion in mm (along Z axis)")
    plane_name: str = Field("Front Plane", description="Plane to draw the sketch on")
    user_name: str = Field("base plate", description="Friendly user name for the plate feature")

class CreateHoleCommand(BaseModel):
    tool: Literal["create_hole"] = "create_hole"
    diameter: float = Field(..., description="Hole diameter in mm")
    depth: float = Field(..., description="Hole depth in mm. Use -1 for through-all")
    x: float = Field(..., description="X coordinate of hole center in mm relative to face center")
    y: float = Field(..., description="Y coordinate of hole center in mm relative to face center")
    plane_or_face_name: str = Field(..., description="Face name (e.g. Boss-Extrude1) or plane name to drill on")
    user_name: str = Field("hole", description="Friendly name for the hole feature")

class ModifyDimensionCommand(BaseModel):
    tool: Literal["modify_dimension"] = "modify_dimension"
    feature_name: str = Field(..., description="Friendly user name (e.g. 'base plate') or native feature name")
    parameter_name: str = Field(..., description="Parameter dimension, e.g. 'width', 'length', 'thickness', or 'D1'")
    value: float = Field(..., description="New value in millimeters")

class ApplyFilletCommand(BaseModel):
    tool: Literal["apply_fillet"] = "apply_fillet"
    target_name: str = Field(..., description="Feature name (e.g. 'base plate') or native name to apply fillet to")
    radius: float = Field(..., description="Fillet radius in mm")
    user_name: str = Field("fillet", description="Friendly name for the fillet feature")

class AssignMaterialCommand(BaseModel):
    tool: Literal["assign_material"] = "assign_material"
    material_name: str = Field(..., description="Name of the material, e.g. 'Alloy Steel', 'Copper', 'Brass', 'AISI 304'")

class SaveCommand(BaseModel):
    tool: Literal["save"] = "save"
    file_path: Optional[str] = Field(None, description="Absolute file path to save. If null, saves to current path.")

class ExportStlCommand(BaseModel):
    tool: Literal["export_stl"] = "export_stl"
    file_path: str = Field(..., description="Absolute file path to export (.stl)")

class ExportStepCommand(BaseModel):
    tool: Literal["export_step"] = "export_step"
    file_path: str = Field(..., description="Absolute file path to export (.step)")

class UndoCommand(BaseModel):
    tool: Literal["undo"] = "undo"

class RollbackCommand(BaseModel):
    tool: Literal["rollback"] = "rollback"
    checkpoint_id: int = Field(..., description="The ID of the checkpoint to roll back to")

class CreateAssemblyCommand(BaseModel):
    tool: Literal["create_assembly"] = "create_assembly"
    user_name: str = Field("assembly", description="Friendly name for the assembly document")

class AddAssemblyComponentCommand(BaseModel):
    tool: Literal["add_assembly_component"] = "add_assembly_component"
    component_path: str = Field(..., description="Absolute file path of the .sldprt or .sldasm file to add")
    x: float = Field(0.0, description="X offset coordinate in millimeters")
    y: float = Field(0.0, description="Y offset coordinate in millimeters")
    z: float = Field(0.0, description="Z offset coordinate in millimeters")
    user_name: str = Field(..., description="Friendly name for the component in the assembly")

class AddMateCommand(BaseModel):
    tool: Literal["add_mate"] = "add_mate"
    comp1_name: str = Field(..., description="Friendly name of the first component")
    comp2_name: str = Field(..., description="Friendly name of the second component")
    mate_type: Literal["concentric", "coincident", "parallel", "perpendicular"] = Field(..., description="Standard mate type")
    align: int = Field(1, description="Alignment condition (1 = Aligned, 2 = Anti-Aligned)")
    entity1_type: str = Field("face", description="Selection entity type for component 1 (e.g. 'face', 'axis', 'plane')")
    entity2_type: str = Field("face", description="Selection entity type for component 2")

class CreateDrawingCommand(BaseModel):
    tool: Literal["create_drawing"] = "create_drawing"
    model_path: str = Field(..., description="Absolute path of the 3D model (part or assembly) to document")
    drawing_path: Optional[str] = Field(None, description="Absolute path where the drawing document should be saved")
    user_name: str = Field("drawing sheet", description="Friendly name for the drawing sheet")

# Define a container for execution plan
class ExecutionPlan(BaseModel):
    commands: List[Dict[str, Any]] = Field(default_factory=list, description="List of raw commands to execute")
