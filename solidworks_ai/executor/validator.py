import logging
from typing import List
from solidworks_ai.ai.parser import CommandType

logger = logging.getLogger(__name__)

def validate_commands(commands: List[CommandType]) -> None:
    """
    Performs safety, sanity, and logical validation on a list of commands
    before they are executed in SolidWorks.
    Raises ValueError on validation failure.
    """
    logger.info(f"Validating {len(commands)} commands before execution...")
    
    for i, cmd in enumerate(commands):
        tool = cmd.tool
        
        if tool == "create_plate":
            # Length, Width, Thickness must be positive
            if cmd.length <= 0 or cmd.width <= 0 or cmd.thickness <= 0:
                raise ValueError(
                    f"Command {i} (create_plate) failed validation: "
                    f"Dimensions must be positive. Received length={cmd.length}, width={cmd.width}, thickness={cmd.thickness}"
                )
            # Limit plate size to 5 meters to prevent massive CAD crashes
            if cmd.length > 5000.0 or cmd.width > 5000.0 or cmd.thickness > 2000.0:
                raise ValueError(
                    f"Command {i} (create_plate) exceeds workspace limits of 5m x 5m x 2m. "
                    f"Received {cmd.length}x{cmd.width}x{cmd.thickness} mm"
                )

        elif tool == "create_hole":
            if cmd.diameter <= 0:
                raise ValueError(
                    f"Command {i} (create_hole) failed: Diameter must be positive. Received {cmd.diameter} mm"
                )
            if cmd.depth <= 0 and cmd.depth != -1:
                raise ValueError(
                    f"Command {i} (create_hole) failed: Depth must be positive or -1 (Through All). Received {cmd.depth} mm"
                )
            # Sanity check: diameter shouldn't be larger than a regular workspace
            if cmd.diameter > 1000.0:
                raise ValueError(
                    f"Command {i} (create_hole) diameter '{cmd.diameter} mm' exceeds maximum hole size threshold (1m)."
                )

        elif tool == "apply_fillet":
            if cmd.radius <= 0:
                raise ValueError(
                    f"Command {i} (apply_fillet) failed: Radius must be positive. Received {cmd.radius} mm"
                )
            if cmd.radius > 500.0:
                raise ValueError(
                    f"Command {i} (apply_fillet) radius '{cmd.radius} mm' is suspiciously large."
                )

        elif tool == "modify_dimension":
            if cmd.value <= 0:
                raise ValueError(
                    f"Command {i} (modify_dimension) failed: New dimension value must be positive. Received {cmd.value} mm"
                )

        elif tool == "assign_material":
            if not cmd.material_name.strip():
                raise ValueError(f"Command {i} (assign_material) failed: Material name cannot be empty.")

        elif tool == "create_assembly":
            if not cmd.user_name.strip():
                raise ValueError(f"Command {i} (create_assembly) failed: User name cannot be empty.")

        elif tool == "add_assembly_component":
            if not cmd.component_path.strip():
                raise ValueError(f"Command {i} (add_assembly_component) failed: Component path cannot be empty.")
            if not cmd.user_name.strip():
                raise ValueError(f"Command {i} (add_assembly_component) failed: User name cannot be empty.")

        elif tool == "add_mate":
            if not cmd.comp1_name.strip() or not cmd.comp2_name.strip():
                raise ValueError(f"Command {i} (add_mate) failed: Component names cannot be empty.")
            if cmd.mate_type not in ["concentric", "coincident", "parallel", "perpendicular"]:
                raise ValueError(f"Command {i} (add_mate) failed: Unsupported mate type '{cmd.mate_type}'.")

        elif tool == "create_drawing":
            if not cmd.model_path.strip():
                raise ValueError(f"Command {i} (create_drawing) failed: Model path cannot be empty.")
            if not cmd.user_name.strip():
                raise ValueError(f"Command {i} (create_drawing) failed: User name cannot be empty.")
                
    logger.info("All commands successfully passed pre-execution validation.")
