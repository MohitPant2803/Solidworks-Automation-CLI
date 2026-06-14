import pytest
from pydantic import ValidationError
from solidworks_ai.schemas.commands import (
    CreatePlateCommand,
    CreateHoleCommand,
    ModifyDimensionCommand,
    ApplyFilletCommand
)

def test_create_plate_validation() -> None:
    # Valid Command
    cmd = CreatePlateCommand(
        length=200.0,
        width=100.0,
        thickness=10.0,
        plane_name="Front Plane",
        user_name="base plate"
    )
    assert cmd.tool == "create_plate"
    assert cmd.length == 200.0
    assert cmd.width == 100.0
    assert cmd.thickness == 10.0

    # Invalid Command (missing required fields)
    with pytest.raises(ValidationError):
        CreatePlateCommand(length=200.0)  # type: ignore

def test_create_hole_validation() -> None:
    cmd = CreateHoleCommand(
        diameter=8.0,
        depth=-1.0,
        x=20.0,
        y=20.0,
        plane_or_face_name="Boss-Extrude1",
        user_name="M8 hole"
    )
    assert cmd.diameter == 8.0
    assert cmd.depth == -1.0
    assert cmd.x == 20.0

def test_modify_dimension_validation() -> None:
    cmd = ModifyDimensionCommand(
        feature_name="base plate",
        parameter_name="width",
        value=300.0
    )
    assert cmd.value == 300.0
    assert cmd.parameter_name == "width"

def test_apply_fillet_validation() -> None:
    cmd = ApplyFilletCommand(
        target_name="base plate",
        radius=5.0
    )
    assert cmd.radius == 5.0
