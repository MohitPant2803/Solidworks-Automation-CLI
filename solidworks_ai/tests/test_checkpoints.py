import pytest
import tempfile
import json
from pathlib import Path
from typing import Any, Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from solidworks_ai.memory.models import Base, Project, Feature, Checkpoint
from solidworks_ai.memory.checkpoints import CheckpointManager
from solidworks_ai.memory.context_manager import ContextManager

@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionClass = sessionmaker(bind=engine)
    session = SessionClass()
    try:
        yield session
    finally:
        session.close()

def test_checkpoint_creation_and_restore(db_session: Session) -> None:
    context_mgr = ContextManager(db_session)
    cp_mgr = CheckpointManager(db_session)
    
    # Create project and feature
    project = context_mgr.get_or_create_project("CheckpointTest")
    context_mgr.add_feature(
        project_id=project.id,
        sw_feature_name="Boss-Extrude1",
        user_name="base plate",
        feature_type="extrude",
        metadata={"length": 200}
    )
    
    # Create temp CAD file and update project file path
    with tempfile.TemporaryDirectory() as tmpdir:
        fake_cad_file = Path(tmpdir) / "part.sldprt"
        fake_cad_file.write_text("dummy cad data")
        
        context_mgr.update_project_file_path(project.id, str(fake_cad_file))
        
        # 1. Create Checkpoint
        cp = cp_mgr.create_checkpoint(project.id, "CP_1")
        assert cp is not None
        assert cp.name == "CP_1"
        assert cp.file_backup_path != ""
        assert Path(cp.file_backup_path).exists()
        
        # Modify DB state
        context_mgr.add_feature(
            project_id=project.id,
            sw_feature_name="Cut-Extrude1",
            user_name="center hole",
            feature_type="hole",
            metadata={"diameter": 10}
        )
        
        features_pre_restore = context_mgr.get_features(project.id)
        assert len(features_pre_restore) == 2
        
        # 2. Restore Checkpoint
        success, backup_file_to_restore, restored_features = cp_mgr.restore_checkpoint(project.id, cp.id)
        assert success is True
        assert backup_file_to_restore == cp.file_backup_path
        
        # Check that DB features reverted back to only 1 (reverted Cut-Extrude1)
        features_post_restore = context_mgr.get_features(project.id)
        assert len(features_post_restore) == 1
        assert features_post_restore[0]["sw_feature_name"] == "Boss-Extrude1"
        
        # Check backup file exists
        assert Path(backup_file_to_restore).read_text() == "dummy cad data"
        
        # Clean up backup file
        if Path(cp.file_backup_path).exists():
            Path(cp.file_backup_path).unlink()
