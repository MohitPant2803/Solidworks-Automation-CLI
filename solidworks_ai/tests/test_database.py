import pytest
from typing import Any
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from solidworks_ai.memory.models import Base
from solidworks_ai.memory.context_manager import ContextManager

@pytest.fixture
def db_session() -> Any:
    # Use SQLite memory database for fully isolated tests
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()

def test_project_creation_and_retrieval(db_session) -> None:
    context_mgr = ContextManager(db_session)
    project = context_mgr.get_or_create_project("TestProj")
    assert project.id is not None
    assert project.name == "TestProj"

    # Fetching again should return the same project
    project_again = context_mgr.get_or_create_project("TestProj")
    assert project_again.id == project.id

def test_conversation_history(db_session) -> None:
    context_mgr = ContextManager(db_session)
    project = context_mgr.get_or_create_project("TestProj")
    
    context_mgr.add_message(project.id, "user", "Create a plate.")
    context_mgr.add_message(project.id, "model", "I will do that.")
    
    history = context_mgr.get_history(project.id)
    assert len(history) == 2
    assert history[0]["role"] == "user"
    assert history[0]["content"] == "Create a plate."
    assert history[1]["role"] == "model"
    assert history[1]["content"] == "I will do that."

def test_feature_mapping_and_resolution(db_session) -> None:
    context_mgr = ContextManager(db_session)
    project = context_mgr.get_or_create_project("TestProj")
    
    context_mgr.add_feature(
        project_id=project.id,
        sw_feature_name="Boss-Extrude1",
        user_name="base plate",
        feature_type="extrude",
        metadata={"length": 200, "width": 100}
    )
    
    # Resolve exact match
    resolved = context_mgr.resolve_user_feature(project.id, "base plate")
    assert resolved is not None
    assert resolved["sw_feature_name"] == "Boss-Extrude1"
    assert resolved["metadata"]["length"] == 200

    # Resolve partial match
    resolved_partial = context_mgr.resolve_user_feature(project.id, "plate")
    assert resolved_partial is not None
    assert resolved_partial["sw_feature_name"] == "Boss-Extrude1"
    
    # Non-existing
    resolved_none = context_mgr.resolve_user_feature(project.id, "shaft")
    assert resolved_none is None
