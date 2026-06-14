import json
import shutil
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
from sqlalchemy.orm import Session
from solidworks_ai.config import PROJECTS_DIR
from solidworks_ai.memory.models import Checkpoint, Feature, Project

class CheckpointManager:
    def __init__(self, db_session: Session):
        self.db = db_session

    def create_checkpoint(self, project_id: int, checkpoint_name: str) -> Optional[Checkpoint]:
        """
        Creates a checkpoint by:
        1. Backing up the active CAD .sldprt file (if saved).
        2. Serializing current database features.
        3. Storing it in the checkpoints table.
        """
        project = self.db.query(Project).filter(Project.id == project_id).first()
        if not project:
            return None

        # 1. Serialize features
        features = (
            self.db.query(Feature)
            .filter(Feature.project_id == project_id)
            .order_by(Feature.created_at.asc())
            .all()
        )
        features_data = [
            {
                "sw_feature_name": f.sw_feature_name,
                "user_name": f.user_name,
                "feature_type": f.feature_type,
                "metadata_json": f.metadata_json
            }
            for f in features
        ]
        db_state_json = json.dumps(features_data)

        # 2. Handle file backup
        backup_path_str = ""
        if project.file_path and Path(project.file_path).exists():
            orig_path = Path(project.file_path)
            checkpoint_dir = PROJECTS_DIR / project.name / "checkpoints"
            checkpoint_dir.mkdir(parents=True, exist_ok=True)
            
            # Count current checkpoints to make unique name
            cp_count = self.db.query(Checkpoint).filter(Checkpoint.project_id == project_id).count()
            backup_filename = f"{orig_path.stem}_cp{cp_count + 1}{orig_path.suffix}"
            backup_path = checkpoint_dir / backup_filename
            
            # Copy file
            shutil.copy2(orig_path, backup_path)
            backup_path_str = str(backup_path)

        # 3. Create DB record
        cp = Checkpoint(
            project_id=project_id,
            name=checkpoint_name,
            db_state_json=db_state_json,
            file_backup_path=backup_path_str
        )
        self.db.add(cp)
        self.db.commit()
        self.db.refresh(cp)
        return cp

    def get_checkpoints(self, project_id: int) -> List[Checkpoint]:
        """Retrieve all checkpoints for a project."""
        return (
            self.db.query(Checkpoint)
            .filter(Checkpoint.project_id == project_id)
            .order_by(Checkpoint.created_at.asc())
            .all()
        )

    def restore_checkpoint(
        self,
        project_id: int,
        checkpoint_id: int
    ) -> Tuple[bool, Optional[str], List[Dict[str, Any]]]:
        """
        Restores database state to a checkpoint. Returns:
        (success, backup_file_path_to_restore_manually, list_of_features_restored)
        The CAD wrapper will handle closing/reopening files.
        """
        project = self.db.query(Project).filter(Project.id == project_id).first()
        cp = self.db.query(Checkpoint).filter(Checkpoint.id == checkpoint_id).first()
        if not project or not cp or cp.project_id != project_id:
            return False, None, []

        # Delete current features in DB for this project
        self.db.query(Feature).filter(Feature.project_id == project_id).delete()

        # Restore from checkpoint state
        features_data = json.loads(cp.db_state_json)
        restored_features = []
        for f_dict in features_data:
            new_feat = Feature(
                project_id=project_id,
                sw_feature_name=f_dict["sw_feature_name"],
                user_name=f_dict["user_name"],
                feature_type=f_dict["feature_type"],
                metadata_json=f_dict["metadata_json"]
            )
            self.db.add(new_feat)
            restored_features.append(f_dict)
        
        # Clean up any checkpoints created AFTER this restored checkpoint
        post_checkpoints = (
            self.db.query(Checkpoint)
            .filter(Checkpoint.project_id == project_id, Checkpoint.id > checkpoint_id)
            .all()
        )
        for old_cp in post_checkpoints:
            # Delete physical backup files
            if old_cp.file_backup_path and Path(old_cp.file_backup_path).exists():
                try:
                    Path(old_cp.file_backup_path).unlink()
                except Exception:
                    pass
            self.db.delete(old_cp)
            
        self.db.commit()

        # Return info to trigger CAD-side restore
        file_to_restore = cp.file_backup_path if cp.file_backup_path else None
        return True, file_to_restore, restored_features
