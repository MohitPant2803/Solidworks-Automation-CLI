import json
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from solidworks_ai.memory.models import Project, Feature, Conversation

class ContextManager:
    def __init__(self, db_session: Session):
        self.db = db_session

    def get_or_create_project(self, project_name: str) -> Project:
        """Fetch an existing project or create a new one."""
        project = self.db.query(Project).filter(Project.name == project_name).first()
        if not project:
            project = Project(name=project_name)
            self.db.add(project)
            self.db.commit()
            self.db.refresh(project)
        return project

    def update_project_file_path(self, project_id: int, file_path: str) -> None:
        """Update the file path for the active project."""
        project = self.db.query(Project).filter(Project.id == project_id).first()
        if project:
            project.file_path = file_path
            self.db.commit()

    def add_message(self, project_id: int, role: str, content: str) -> None:
        """Add a conversation message to history."""
        msg = Conversation(project_id=project_id, role=role, content=content)
        self.db.add(msg)
        self.db.commit()

    def get_history(self, project_id: int) -> List[Dict[str, str]]:
        """Get the full message history for the project."""
        messages = (
            self.db.query(Conversation)
            .filter(Conversation.project_id == project_id)
            .order_by(Conversation.created_at.asc())
            .all()
        )
        return [{"role": msg.role, "content": msg.content} for msg in messages]

    def clear_history(self, project_id: int) -> None:
        """Clear message history for the project."""
        self.db.query(Conversation).filter(Conversation.project_id == project_id).delete()
        self.db.commit()

    def add_feature(
        self,
        project_id: int,
        sw_feature_name: str,
        user_name: str,
        feature_type: str,
        metadata: Dict[str, Any]
    ) -> Feature:
        """Record a newly created feature in the database."""
        feature = Feature(
            project_id=project_id,
            sw_feature_name=sw_feature_name,
            user_name=user_name,
            feature_type=feature_type,
            metadata_json=json.dumps(metadata)
        )
        self.db.add(feature)
        self.db.commit()
        self.db.refresh(feature)
        return feature

    def get_features(self, project_id: int) -> List[Dict[str, Any]]:
        """Get all database feature mappings for a project."""
        features = (
            self.db.query(Feature)
            .filter(Feature.project_id == project_id)
            .order_by(Feature.created_at.asc())
            .all()
        )
        return [
            {
                "id": feat.id,
                "sw_feature_name": feat.sw_feature_name,
                "user_name": feat.user_name,
                "feature_type": feat.feature_type,
                "metadata": json.loads(feat.metadata_json) if feat.metadata_json else {}
            }
            for feat in features
        ]

    def remove_feature(self, project_id: int, sw_feature_name: str) -> bool:
        """Delete a feature mapping from the project database."""
        feat = (
            self.db.query(Feature)
            .filter(Feature.project_id == project_id, Feature.sw_feature_name == sw_feature_name)
            .first()
        )
        if feat:
            self.db.delete(feat)
            self.db.commit()
            return True
        return False

    def resolve_user_feature(self, project_id: int, user_query: str) -> Optional[Dict[str, Any]]:
        """
        Attempt to resolve a user friendly name (like 'base plate' or 'holes')
        to its DB entry containing the SolidWorks feature name.
        """
        features = self.get_features(project_id)
        # Exact match
        for f in features:
            if f["user_name"].lower() == user_query.lower():
                return f
        # Substring match
        for f in features:
            if user_query.lower() in f["user_name"].lower():
                return f
        return None
