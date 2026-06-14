import logging
from typing import List, Dict, Any, Optional
import win32com.client
import pythoncom
from sqlalchemy.orm import Session

from solidworks_ai.cad.solidworks import SolidWorksConnection, SolidWorksError
from solidworks_ai.cad.sketches import create_rectangle, create_circle
from solidworks_ai.cad.extrude import boss_extrude, cut_extrude
from solidworks_ai.cad.holes import create_hole
from solidworks_ai.cad.fillets import apply_fillet
from solidworks_ai.cad.materials import assign_material
from solidworks_ai.cad.dimensions import modify_dimension
from solidworks_ai.memory.context_manager import ContextManager
from solidworks_ai.memory.checkpoints import CheckpointManager
from solidworks_ai.executor.rollback import RollbackHandler
from solidworks_ai.ai.parser import CommandType

logger = logging.getLogger(__name__)

class CommandExecutor:
    def __init__(self, db_session: Session, sw_conn: SolidWorksConnection) -> None:
        self.db = db_session
        self.sw_conn = sw_conn
        self.context_mgr = ContextManager(db_session)
        self.cp_mgr = CheckpointManager(db_session)
        self.rollback_handler = RollbackHandler(db_session, sw_conn)

    def execute_plan(
        self,
        project_id: int,
        commands: List[CommandType],
        checkpoint_name: str = "Pre-Execution Backup"
    ) -> List[str]:
        """
        Executes a plan of validated commands in SolidWorks.
        Creates a checkpoint first. If any command fails, performs an automatic rollback.
        Returns the list of features created/modified.
        """
        # 1. Create a pre-execution checkpoint
        logger.info(f"Creating pre-execution checkpoint '{checkpoint_name}'")
        cp = self.cp_mgr.create_checkpoint(project_id, checkpoint_name)
        cp_id = cp.id if cp else 0

        # Get active model doc (connect if not connected)
        try:
            model = self.sw_conn.get_active_document()
        except SolidWorksError:
            # If no doc active, create a new part!
            model = self.sw_conn.create_new_part()

        # Update project file path if it isn't set yet (for file backups)
        from solidworks_ai.memory.models import Project as ProjectModel
        project = self.db.query(ProjectModel).filter(ProjectModel.id == project_id).first()
        
        if project and not project.file_path:
            # Generate default path in project directory
            from solidworks_ai.config import PROJECTS_DIR
            default_path = PROJECTS_DIR / project.name / f"{project.name}.sldprt"
            default_path.parent.mkdir(parents=True, exist_ok=True)
            self.sw_conn.save_document(str(default_path))
            self.context_mgr.update_project_file_path(project_id, str(default_path))

        executed_features: List[str] = []

        try:
            for idx, cmd in enumerate(commands):
                tool = cmd.tool
                logger.info(f"Executing step {idx + 1}/{len(commands)}: {tool}")

                if tool == "create_plate":
                    # Create sketch rectangle + extrude
                    sketch_name = create_rectangle(
                        model=model,
                        plane_name=cmd.plane_name,
                        width_mm=cmd.length,  # length is along horizontal (width)
                        height_mm=cmd.width,  # width is along vertical (height)
                        xc_mm=0.0,
                        yc_mm=0.0
                    )
                    feature_name = boss_extrude(
                        model=model,
                        sketch_name=sketch_name,
                        depth_mm=cmd.thickness
                    )
                    # Register mapping in DB
                    meta = {
                        "length": cmd.length,
                        "width": cmd.width,
                        "thickness": cmd.thickness,
                        "sketch_name": sketch_name,
                        "feature_name": feature_name,
                        "plane_name": cmd.plane_name
                    }
                    self.context_mgr.add_feature(
                        project_id=project_id,
                        sw_feature_name=feature_name,
                        user_name=cmd.user_name,
                        feature_type="extrude",
                        metadata=meta
                    )
                    executed_features.append(feature_name)

                elif tool == "create_hole":
                    # Resolve face/plane selection name
                    target_plane = cmd.plane_or_face_name
                    resolved = self.context_mgr.resolve_user_feature(project_id, target_plane)
                    if resolved:
                        # If resolved, we want to sketch on a face of this feature
                        sw_feat_name = resolved["sw_feature_name"]
                        logger.info(f"Hole target resolved from '{target_plane}' to native feature '{sw_feat_name}'")
                        
                        # Get first face of feature
                        sw_feat = model.FeatureByName(sw_feat_name)
                        if not sw_feat:
                            raise SolidWorksError(f"Could not find native feature '{sw_feat_name}' in model.")
                        
                        faces = sw_feat.GetFaces()
                        if not faces or len(faces) == 0:
                            raise SolidWorksError(f"Native feature '{sw_feat_name}' has no faces to sketch on.")
                        
                        # Select the first face
                        null_sel = win32com.client.VARIANT(pythoncom.VT_DISPATCH, None)
                        faces[0].Select4(False, null_sel)
                        # We use the selected face as the plane_or_face_name for create_hole
                        # Passing empty string or letting create_hole know that face is already selected
                        # Let's modify select_plane_or_face to accept the selection or handle empty string
                        target_plane = sw_feat_name  # SelectByID2 can select feature face or we sketch on active selection
                    
                    feature_name = create_hole(
                        model=model,
                        plane_or_face_name=target_plane,
                        diameter_mm=cmd.diameter,
                        depth_mm=cmd.depth,
                        x_mm=cmd.x,
                        y_mm=cmd.y
                    )
                    # Register feature in DB
                    meta = {
                        "diameter": cmd.diameter,
                        "depth": cmd.depth,
                        "x": cmd.x,
                        "y": cmd.y,
                        "target_plane": cmd.plane_or_face_name,
                        "feature_name": feature_name
                    }
                    self.context_mgr.add_feature(
                        project_id=project_id,
                        sw_feature_name=feature_name,
                        user_name=cmd.user_name,
                        feature_type="hole",
                        metadata=meta
                    )
                    executed_features.append(feature_name)

                elif tool == "modify_dimension":
                    # Resolve feature name
                    resolved = self.context_mgr.resolve_user_feature(project_id, cmd.feature_name)
                    sw_feature_name = resolved["sw_feature_name"] if resolved else cmd.feature_name
                    metadata = resolved["metadata"] if resolved else {}
                    
                    # Resolve dimension parameter name
                    dim_param = self._resolve_dimension_param(
                        model=model,
                        feature_name=sw_feature_name,
                        parameter_name=cmd.parameter_name,
                        metadata=metadata
                    )
                    
                    modify_dimension(
                        model=model,
                        dimension_name=dim_param,
                        new_value_mm=cmd.value
                    )
                    # Update feature metadata in DB
                    if resolved:
                        meta = resolved["metadata"]
                        param_name_lower = cmd.parameter_name.lower()
                        if param_name_lower in ["width", "length", "thickness", "depth", "radius", "diameter"]:
                            meta[param_name_lower] = cmd.value
                        
                        # Save updated metadata
                        self.context_mgr.remove_feature(project_id, sw_feature_name)
                        self.context_mgr.add_feature(
                            project_id=project_id,
                            sw_feature_name=sw_feature_name,
                            user_name=resolved["user_name"],
                            feature_type=resolved["feature_type"],
                            metadata=meta
                        )
                    executed_features.append(sw_feature_name)

                elif tool == "apply_fillet":
                    # Resolve feature name
                    resolved = self.context_mgr.resolve_user_feature(project_id, cmd.target_name)
                    sw_target = resolved["sw_feature_name"] if resolved else cmd.target_name
                    
                    feature_name = apply_fillet(
                        model=model,
                        target_name=sw_target,
                        radius_mm=cmd.radius
                    )
                    # Register mapping in DB
                    meta = {
                        "radius": cmd.radius,
                        "target_name": cmd.target_name,
                        "feature_name": feature_name
                    }
                    self.context_mgr.add_feature(
                        project_id=project_id,
                        sw_feature_name=feature_name,
                        user_name=cmd.user_name,
                        feature_type="fillet",
                        metadata=meta
                    )
                    executed_features.append(feature_name)

                elif tool == "assign_material":
                    assign_material(model=model, material_name=cmd.material_name)
                    executed_features.append(cmd.material_name)

                elif tool == "save":
                    save_path = cmd.file_path if cmd.file_path else project.file_path
                    self.sw_conn.save_document(save_path)
                    if cmd.file_path:
                        self.context_mgr.update_project_file_path(project_id, cmd.file_path)

                elif tool == "export_stl":
                    self.sw_conn.export_stl(cmd.file_path)

                elif tool == "export_step":
                    self.sw_conn.export_step(cmd.file_path)

                elif tool == "undo":
                    self.rollback_handler.undo_last_operation(project_id)

                elif tool == "rollback":
                    self.rollback_handler.rollback_to_checkpoint(project_id, cmd.checkpoint_id)

                elif tool == "create_assembly":
                    from solidworks_ai.cad.assemblies import create_assembly as cad_create_assembly
                    sw_app = self.sw_conn.get_app()
                    model = cad_create_assembly(sw_app)
                    meta = {
                        "document_type": "assembly"
                    }
                    self.context_mgr.add_feature(
                        project_id=project_id,
                        sw_feature_name=model.GetTitle(),
                        user_name=cmd.user_name,
                        feature_type="assembly",
                        metadata=meta
                    )
                    from solidworks_ai.config import PROJECTS_DIR
                    default_path = PROJECTS_DIR / project.name / f"{cmd.user_name}.sldasm"
                    default_path.parent.mkdir(parents=True, exist_ok=True)
                    self.sw_conn.save_document(str(default_path))
                    self.context_mgr.update_project_file_path(project_id, str(default_path))
                    executed_features.append(model.GetTitle())

                elif tool == "add_assembly_component":
                    from solidworks_ai.cad.assemblies import add_component as cad_add_component
                    comp = cad_add_component(
                        model=model,
                        component_path=cmd.component_path,
                        x_mm=cmd.x,
                        y_mm=cmd.y,
                        z_mm=cmd.z,
                        friendly_name=cmd.user_name
                    )
                    meta = {
                        "component_path": cmd.component_path,
                        "x": cmd.x,
                        "y": cmd.y,
                        "z": cmd.z,
                        "comp_name": comp.Name2
                    }
                    self.context_mgr.add_feature(
                        project_id=project_id,
                        sw_feature_name=comp.Name2,
                        user_name=cmd.user_name,
                        feature_type="assembly_component",
                        metadata=meta
                    )
                    executed_features.append(comp.Name2)

                elif tool == "add_mate":
                    from solidworks_ai.cad.assemblies import add_assembly_mate
                    mate = add_assembly_mate(
                        model=model,
                        comp1_name=cmd.comp1_name,
                        comp2_name=cmd.comp2_name,
                        mate_type=cmd.mate_type,
                        align=cmd.align
                    )
                    meta = {
                        "comp1_name": cmd.comp1_name,
                        "comp2_name": cmd.comp2_name,
                        "mate_type": cmd.mate_type,
                        "align": cmd.align,
                        "mate_name": mate.Name
                    }
                    self.context_mgr.add_feature(
                        project_id=project_id,
                        sw_feature_name=mate.Name,
                        user_name=f"mate_{cmd.comp1_name}_{cmd.comp2_name}",
                        feature_type="assembly_mate",
                        metadata=meta
                    )
                    executed_features.append(mate.Name)

                elif tool == "create_drawing":
                    from solidworks_ai.cad.drawings import create_drawing as cad_create_drawing, create_drawing_views
                    sw_app = self.sw_conn.get_app()
                    model = cad_create_drawing(sw_app)
                    created_views = create_drawing_views(
                        drawing_doc=model,
                        model_path=cmd.model_path
                    )
                    meta = {
                        "model_path": cmd.model_path,
                        "created_views": created_views
                    }
                    self.context_mgr.add_feature(
                        project_id=project_id,
                        sw_feature_name=model.GetTitle(),
                        user_name=cmd.user_name,
                        feature_type="drawing",
                        metadata=meta
                    )
                    if cmd.drawing_path:
                        self.sw_conn.save_document(cmd.drawing_path)
                        self.context_mgr.update_project_file_path(project_id, cmd.drawing_path)
                    else:
                        from solidworks_ai.config import PROJECTS_DIR
                        default_path = PROJECTS_DIR / project.name / f"{cmd.user_name}.slddrw"
                        default_path.parent.mkdir(parents=True, exist_ok=True)
                        self.sw_conn.save_document(str(default_path))
                        self.context_mgr.update_project_file_path(project_id, str(default_path))
                    executed_features.append(model.GetTitle())

            # Rebuild model and save active file at end of success
            if project and project.file_path:
                self.sw_conn.rebuild()
                self.sw_conn.save_document(project.file_path)
                
            return executed_features

        except Exception as e:
            logger.error(f"Execution failed during operation '{tool}': {e}. Triggering rollback to checkpoint ID {cp_id}...")
            # Revert CAD and DB states
            if cp_id > 0:
                self.rollback_handler.rollback_to_checkpoint(project_id, cp_id)
            raise SolidWorksError(f"Execution failed at step '{tool}': {e}. Model rolled back to pre-execution state.") from e

    def _resolve_dimension_param(
        self,
        model: Any,
        feature_name: str,
        parameter_name: str,
        metadata: Dict[str, Any]
    ) -> str:
        """
        Maps friendly parameter names like 'width' or 'depth'
        to their native SolidWorks parameter strings (e.g. 'D1@Sketch1').
        """
        sketch_name = metadata.get("sketch_name", "Sketch1")
        param_lower = parameter_name.lower()
        
        # Format can be width, length, thickness, depth, diameter, radius
        if param_lower in ["width", "length", "height"]:
            # width is D1, height/length is D2
            if param_lower == "width":
                return f"D1@{sketch_name}"
            else:
                return f"D2@{sketch_name}"
        elif param_lower in ["thickness", "depth"]:
            # Extrusion depth is D1 of the Boss-Extrude feature
            return f"D1@{feature_name}"
        elif param_lower in ["diameter", "radius"]:
            # Circle sketch diameter is D1 of the sketch
            return f"D1@{sketch_name}"
            
        # Fallback to direct parameter string if it's already in the correct format
        return parameter_name
