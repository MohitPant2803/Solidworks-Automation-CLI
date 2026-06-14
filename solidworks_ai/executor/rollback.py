import logging
import shutil
from pathlib import Path
from typing import Optional, Any
from sqlalchemy.orm import Session
from solidworks_ai.cad.solidworks import SolidWorksConnection, SolidWorksError
from solidworks_ai.memory.checkpoints import CheckpointManager
from solidworks_ai.memory.context_manager import ContextManager
from solidworks_ai.memory.models import Project

logger = logging.getLogger(__name__)

class RollbackHandler:
    def __init__(self, db_session: Session, sw_conn: SolidWorksConnection) -> None:
        self.db = db_session
        self.sw_conn = sw_conn
        self.cp_mgr = CheckpointManager(db_session)
        self.context_mgr = ContextManager(db_session)

    def rollback_to_checkpoint(self, project_id: int, checkpoint_id: int) -> bool:
        """
        Rolls back the database state and the active SolidWorks model
        to the specified checkpoint.
        """
        logger.info(f"Initiating rollback to checkpoint ID: {checkpoint_id}...")
        
        # 1. Fetch project path info
        project = self.db.query(Project).filter(Project.id == project_id).first()
        if not project:
            logger.error(f"Project ID {project_id} not found.")
            return False

        # 2. Restore DB state
        success, backup_file, restored_features = self.cp_mgr.restore_checkpoint(project_id, checkpoint_id)
        if not success:
            logger.error("Failed to restore database checkpoint.")
            return False

        try:
            # 3. Handle CAD file restoration
            if backup_file and Path(backup_file).exists():
                logger.info(f"Restoring physical CAD file from backup: {backup_file}")
                
                # Close active doc without saving
                self.sw_conn.close_active_document(save_changes=False)
                
                # Copy backup over target file
                target_path = Path(project.file_path)
                shutil.copy2(backup_file, target_path)
                
                # Open restored document in SW
                self.sw_conn.open_document(str(target_path))
                
            else:
                # If there's no backup file, we revert to an empty clean part
                logger.info("No physical backup file in checkpoint. Reverting to a clean part.")
                self.sw_conn.close_active_document(save_changes=False)
                self.sw_conn.create_new_part()
                
                # If we had a file path, clear it or reset
                self.context_mgr.update_project_file_path(project_id, "")

            # 4. Rebuild the restored model
            self.sw_conn.rebuild()
            logger.info("Rollback completed successfully.")
            return True

        except Exception as e:
            logger.error(f"Error during physical CAD rollback: {e}")
            return False

    def undo_last_operation(self, project_id: int) -> bool:
        """
        Rolls back to the second-to-last checkpoint (undoes the last action).
        """
        checkpoints = self.cp_mgr.get_checkpoints(project_id)
        if len(checkpoints) < 2:
            # Revert to start
            if len(checkpoints) == 1:
                # Reset to checkpoint 1
                return self.rollback_to_checkpoint(project_id, checkpoints[0].id)
            logger.warning("No checkpoints available to undo.")
            return False
            
        # Roll back to the second to last checkpoint
        target_cp = checkpoints[-2]
        logger.info(f"Undoing last operation. Reverting to checkpoint '{target_cp.name}' (ID: {target_cp.id})")
        return self.rollback_to_checkpoint(project_id, target_cp.id)
