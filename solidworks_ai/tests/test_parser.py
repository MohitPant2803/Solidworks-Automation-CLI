import pytest
from solidworks_ai.ai.parser import parse_command, parse_commands_list
from solidworks_ai.executor.validator import validate_commands
from solidworks_ai.schemas.commands import CreatePlateCommand

def test_parse_valid_command() -> None:
    raw_cmd = {
        "tool": "create_plate",
        "length": 200,
        "width": 100,
        "thickness": 10,
        "plane_name": "Front Plane",
        "user_name": "plate"
    }
    parsed = parse_command(raw_cmd)
    assert isinstance(parsed, CreatePlateCommand)
    assert parsed.length == 200.0

def test_parse_invalid_command() -> None:
    raw_cmd = {
        "tool": "create_plate",
        # missing length, width, thickness
        "user_name": "plate"
    }
    with pytest.raises(ValueError) as exc:
        parse_command(raw_cmd)
    assert "Invalid parameters" in str(exc.value)

def test_validation_rules() -> None:
    # Valid
    parsed_valid = parse_commands_list([{
        "tool": "create_plate",
        "length": 200,
        "width": 100,
        "thickness": 10
    }])
    # Should not raise exception
    validate_commands(parsed_valid)

    # Invalid (negative length)
    parsed_invalid_neg = parse_commands_list([{
        "tool": "create_plate",
        "length": -50,
        "width": 100,
        "thickness": 10
    }])
    with pytest.raises(ValueError) as exc:
        validate_commands(parsed_invalid_neg)
    assert "Dimensions must be positive" in str(exc.value)

    # Invalid (oversized dimensions)
    parsed_invalid_size = parse_commands_list([{
        "tool": "create_plate",
        "length": 6000,
        "width": 100,
        "thickness": 10
    }])
    with pytest.raises(ValueError) as exc:
        validate_commands(parsed_invalid_size)
    assert "exceeds workspace limits" in str(exc.value)

def test_parse_assembly_and_drawing_commands() -> None:
    raw_cmds = [
        {
            "tool": "create_assembly",
            "user_name": "vise_assembly"
        },
        {
            "tool": "add_assembly_component",
            "component_path": "C:\\CAD\\base.sldprt",
            "x": 10.0,
            "y": 20.0,
            "z": 30.0,
            "user_name": "base_plate"
        },
        {
            "tool": "add_mate",
            "comp1_name": "base_plate",
            "comp2_name": "movable_jaw",
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
    
    parsed = parse_commands_list(raw_cmds)
    assert len(parsed) == 4
    
    # Run validation
    validate_commands(parsed)

