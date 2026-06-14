import logging
from typing import List, Dict, Any, Union
from pydantic import ValidationError
from solidworks_ai.schemas.commands import (
    CreatePlateCommand,
    CreateHoleCommand,
    ModifyDimensionCommand,
    ApplyFilletCommand,
    AssignMaterialCommand,
    SaveCommand,
    ExportStlCommand,
    ExportStepCommand,
    UndoCommand,
    RollbackCommand,
    CreateAssemblyCommand,
    AddAssemblyComponentCommand,
    AddMateCommand,
    CreateDrawingCommand
)

logger = logging.getLogger(__name__)

CommandType = Union[
    CreatePlateCommand,
    CreateHoleCommand,
    ModifyDimensionCommand,
    ApplyFilletCommand,
    AssignMaterialCommand,
    SaveCommand,
    ExportStlCommand,
    ExportStepCommand,
    UndoCommand,
    RollbackCommand,
    CreateAssemblyCommand,
    AddAssemblyComponentCommand,
    AddMateCommand,
    CreateDrawingCommand
]

def parse_command(cmd_dict: Dict[str, Any]) -> CommandType:
    """Parses and validates a single command dictionary into a Pydantic model."""
    tool = cmd_dict.get("tool")
    if not tool:
        raise ValueError("Command dictionary missing 'tool' field.")

    try:
        if tool == "create_plate":
            return CreatePlateCommand(**cmd_dict)
        elif tool == "create_hole":
            return CreateHoleCommand(**cmd_dict)
        elif tool == "modify_dimension":
            return ModifyDimensionCommand(**cmd_dict)
        elif tool == "apply_fillet":
            return ApplyFilletCommand(**cmd_dict)
        elif tool == "assign_material":
            return AssignMaterialCommand(**cmd_dict)
        elif tool == "save":
            return SaveCommand(**cmd_dict)
        elif tool == "export_stl":
            return ExportStlCommand(**cmd_dict)
        elif tool == "export_step":
            return ExportStepCommand(**cmd_dict)
        elif tool == "undo":
            return UndoCommand(**cmd_dict)
        elif tool == "rollback":
            return RollbackCommand(**cmd_dict)
        elif tool == "create_assembly":
            return CreateAssemblyCommand(**cmd_dict)
        elif tool == "add_assembly_component":
            return AddAssemblyComponentCommand(**cmd_dict)
        elif tool == "add_mate":
            return AddMateCommand(**cmd_dict)
        elif tool == "create_drawing":
            return CreateDrawingCommand(**cmd_dict)
        else:
            raise ValueError(f"Unsupported tool command type: '{tool}'")
    except ValidationError as e:
        logger.error(f"Validation error parsing command for tool '{tool}': {e}")
        raise ValueError(f"Invalid parameters for command '{tool}': {e.errors()}")

def parse_commands_list(commands: List[Dict[str, Any]]) -> List[CommandType]:
    """Parses and validates a list of commands."""
    parsed: List[CommandType] = []
    for cmd in commands:
        parsed.append(parse_command(cmd))
    return parsed
