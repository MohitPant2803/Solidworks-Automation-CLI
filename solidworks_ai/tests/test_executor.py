import pytest
from unittest.mock import MagicMock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from solidworks_ai.memory.models import Base
from solidworks_ai.cad.solidworks import SolidWorksConnection
from solidworks_ai.executor.executor import CommandExecutor
from solidworks_ai.ai.parser import parse_commands_list

@pytest.fixture
def db_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionClass = sessionmaker(bind=engine)
    session = SessionClass()
    return session

@patch("solidworks_ai.executor.executor.create_rectangle")
@patch("solidworks_ai.executor.executor.boss_extrude")
def test_executor_execute_plate(
    mock_boss_extrude: MagicMock,
    mock_create_rectangle: MagicMock,
    db_session: Session
) -> None:
    # 1. Setup mocks
    mock_sw_conn = MagicMock(spec=SolidWorksConnection)
    mock_model = MagicMock()
    mock_sw_conn.get_active_document.return_value = mock_model
    
    mock_create_rectangle.return_value = "Sketch1"
    mock_boss_extrude.return_value = "Boss-Extrude1"

    executor = CommandExecutor(db_session, mock_sw_conn)
    
    # 2. Prepare mock commands
    commands = [{
        "tool": "create_plate",
        "length": 200.0,
        "width": 100.0,
        "thickness": 10.0,
        "plane_name": "Front Plane",
        "user_name": "base plate"
    }]
    parsed_cmds = parse_commands_list(commands)

    # Create dummy project
    from solidworks_ai.memory.context_manager import ContextManager
    context_mgr = ContextManager(db_session)
    project = context_mgr.get_or_create_project("ExecTest")

    # 3. Execute
    executed_features = executor.execute_plan(project.id, parsed_cmds)

    # 4. Assertions
    assert "Boss-Extrude1" in executed_features
    mock_create_rectangle.assert_called_once_with(
        model=mock_model,
        plane_name="Front Plane",
        width_mm=200.0,
        height_mm=100.0,
        xc_mm=0.0,
        yc_mm=0.0
    )
    mock_boss_extrude.assert_called_once_with(
        model=mock_model,
        sketch_name="Sketch1",
        depth_mm=10.0
    )

    # Verify features updated in DB
    db_features = context_mgr.get_features(project.id)
    assert len(db_features) == 1
    assert db_features[0]["user_name"] == "base plate"
    assert db_features[0]["sw_feature_name"] == "Boss-Extrude1"

@patch("solidworks_ai.cad.assemblies.create_assembly")
@patch("solidworks_ai.cad.assemblies.add_component")
@patch("solidworks_ai.cad.assemblies.add_assembly_mate")
@patch("solidworks_ai.cad.drawings.create_drawing")
@patch("solidworks_ai.cad.drawings.create_drawing_views")
def test_executor_execute_assembly_and_drawings(
    mock_create_drawing_views: MagicMock,
    mock_create_drawing: MagicMock,
    mock_add_assembly_mate: MagicMock,
    mock_add_component: MagicMock,
    mock_create_assembly: MagicMock,
    db_session: Session
) -> None:
    # Setup mocks
    mock_sw_conn = MagicMock(spec=SolidWorksConnection)
    mock_model = MagicMock()
    mock_model.GetTitle.return_value = "ViseAssembly"
    mock_sw_conn.get_active_document.return_value = mock_model
    
    mock_create_assembly.return_value = mock_model
    
    mock_comp = MagicMock()
    mock_comp.Name2 = "base_plate-1"
    mock_add_component.return_value = mock_comp
    
    mock_mate = MagicMock()
    mock_mate.Name = "ConcentricMate1"
    mock_add_assembly_mate.return_value = mock_mate
    
    mock_drawing = MagicMock()
    mock_drawing.GetTitle.return_value = "ViseDrawing"
    mock_create_drawing.return_value = mock_drawing
    mock_create_drawing_views.return_value = ["FrontView", "TopView"]

    executor = CommandExecutor(db_session, mock_sw_conn)
    
    # Create project
    from solidworks_ai.memory.context_manager import ContextManager
    context_mgr = ContextManager(db_session)
    project = context_mgr.get_or_create_project("AssemblyTest")

    # Commands list
    commands = [
        {
            "tool": "create_assembly",
            "user_name": "vise_assembly"
        },
        {
            "tool": "add_assembly_component",
            "component_path": "C:\\CAD\\base.sldprt",
            "x": 10.0,
            "y": 0.0,
            "z": 0.0,
            "user_name": "base_part"
        },
        {
            "tool": "add_mate",
            "comp1_name": "base_part",
            "comp2_name": "jaw_part",
            "mate_type": "concentric",
            "align": 1
        },
        {
            "tool": "create_drawing",
            "model_path": "C:\\CAD\\base.sldprt",
            "drawing_path": "C:\\CAD\\base.slddrw",
            "user_name": "base_drawing"
        }
    ]
    parsed_cmds = parse_commands_list(commands)

    # Execute
    executed_features = executor.execute_plan(project.id, parsed_cmds)

    # Assertions
    assert "ViseAssembly" in executed_features
    assert "base_plate-1" in executed_features
    assert "ConcentricMate1" in executed_features
    assert "ViseDrawing" in executed_features

    # Verify features updated in DB
    db_features = context_mgr.get_features(project.id)
    assert len(db_features) == 4
    feature_types = [f["feature_type"] for f in db_features]
    assert "assembly" in feature_types
    assert "assembly_component" in feature_types
    assert "assembly_mate" in feature_types
    assert "drawing" in feature_types

