"""Tests for Pj-OGUN schema models."""

import json
import pytest
from pathlib import Path

from pydantic import ValidationError

from pj_ogun.models import (
    Coordinates,
    DemandConfiguration,
    DemandMode,
    Edge,
    ManualDemandEvent,
    Node,
    NodeCapacity,
    NodeType,
    Scenario,
    SimulationConfig,
    SpeedProfile,
    Vehicle,
    VehicleClass,
    VehicleRole,
    VehicleType,
)
from pj_ogun.models.enums import DemandType, Priority


class TestCoordinates:
    def test_basic_coordinates(self):
        coords = Coordinates(x=10.5, y=20.3)
        assert coords.x == 10.5
        assert coords.y == 20.3
    
    def test_distance_calculation(self):
        c1 = Coordinates(x=0, y=0)
        c2 = Coordinates(x=3, y=4)
        assert c1.distance_to(c2) == 5.0


class TestNode:
    def test_basic_node(self):
        node = Node(
            id="test_node",
            name="Test Node",
            type=NodeType.COMBAT,
            coordinates=Coordinates(x=10, y=20),
        )
        assert node.id == "test_node"
        assert node.type == NodeType.COMBAT
    
    def test_node_id_cleanup(self):
        node = Node(
            id="  test node  ",
            name="Test",
            type=NodeType.COMBAT,
            coordinates=Coordinates(x=0, y=0),
        )
        assert node.id == "test_node"
    
    def test_medical_node_with_capacity(self):
        node = Node(
            id="aid_station",
            name="Aid Station",
            type=NodeType.MEDICAL_ROLE1,
            coordinates=Coordinates(x=50, y=50),
            capacity=NodeCapacity(treatment_slots=2, holding_casualties=6),
        )
        assert node.capacity.treatment_slots == 2


class TestEdge:
    def test_basic_edge(self):
        edge = Edge(
            **{"from": "node_a", "to": "node_b", "distance_km": 10.0}
        )
        assert edge.from_node == "node_a"
        assert edge.to_node == "node_b"
        assert edge.distance_km == 10.0
        assert edge.bidirectional is True
    
    def test_travel_time_calculation(self):
        edge = Edge(
            **{"from": "a", "to": "b", "distance_km": 60.0}
        )
        # 60 km at 60 km/h = 1 hour = 60 minutes
        assert edge.travel_time_mins(60.0) == 60.0
    
    def test_travel_time_with_terrain(self):
        from pj_ogun.models.network import EdgeProperties
        edge = Edge(
            **{
                "from": "a",
                "to": "b",
                "distance_km": 60.0,
                "properties": EdgeProperties(terrain_factor=1.5),
            }
        )
        # 60 km at 60 km/h with 1.5x terrain = 90 minutes
        assert edge.travel_time_mins(60.0) == 90.0


class TestSpeedProfile:
    def test_valid_speed_profile(self):
        sp = SpeedProfile(unladen_kmh=60, laden_kmh=45)
        assert sp.get_speed(is_laden=False) == 60
        assert sp.get_speed(is_laden=True) == 45
    
    def test_laden_faster_than_unladen_fails(self):
        with pytest.raises(ValidationError):
            SpeedProfile(unladen_kmh=50, laden_kmh=60)


class TestVehicleType:
    def test_ambulance_requires_casualty_capacity(self):
        with pytest.raises(ValidationError):
            VehicleType(
                id="bad_amb",
                name="Bad Ambulance",
                role=VehicleRole.AMBULANCE,
                vehicle_class=VehicleClass.LIGHT,
                casualty_capacity=0,  # Invalid
                speed=SpeedProfile(unladen_kmh=60, laden_kmh=45),
                service_times={"load_time_mins": 5, "unload_time_mins": 5},
            )
    
    def test_valid_ambulance(self):
        from pj_ogun.models.vehicles import ServiceTimes
        vt = VehicleType(
            id="amb_test",
            name="Test Ambulance",
            role=VehicleRole.AMBULANCE,
            vehicle_class=VehicleClass.LIGHT,
            casualty_capacity=2,
            speed=SpeedProfile(unladen_kmh=60, laden_kmh=45),
            service_times=ServiceTimes(load_time_mins=5, unload_time_mins=5),
        )
        assert vt.casualty_capacity == 2


class TestDemandConfiguration:
    def test_manual_mode_requires_events(self):
        with pytest.raises(ValidationError):
            DemandConfiguration(
                mode=DemandMode.MANUAL,
                manual_events=[],  # Empty - invalid
            )
    
    def test_valid_manual_demand(self):
        config = DemandConfiguration(
            mode=DemandMode.MANUAL,
            manual_events=[
                ManualDemandEvent(
                    time_mins=30,
                    type=DemandType.CASUALTY,
                    location="combat_a",
                    priority=Priority.PRIORITY,
                )
            ],
        )
        assert len(config.manual_events) == 1


class TestScenario:
    def test_load_example_scenario(self):
        """Test loading the example MEDEVAC scenario."""
        scenario_path = Path(__file__).parent.parent / "scenarios" / "example_medevac.json"
        
        if not scenario_path.exists():
            pytest.skip("Example scenario not found")
        
        with open(scenario_path) as f:
            data = json.load(f)
        
        scenario = Scenario.model_validate(data)
        
        assert scenario.name == "Basic MEDEVAC Exercise"
        assert len(scenario.nodes) == 4
        assert len(scenario.edges) == 4
        assert len(scenario.vehicles) == 3
    
    def test_invalid_edge_reference(self):
        """Test that edges referencing non-existent nodes fail."""
        with pytest.raises(ValidationError) as exc_info:
            Scenario(
                name="Bad Scenario",
                nodes=[
                    Node(
                        id="only_node",
                        name="Only Node",
                        type=NodeType.COMBAT,
                        coordinates=Coordinates(x=0, y=0),
                    )
                ],
                edges=[
                    Edge(**{"from": "only_node", "to": "missing_node", "distance_km": 10})
                ],
                vehicle_types=[
                    VehicleType(
                        id="amb",
                        name="Ambulance",
                        role=VehicleRole.AMBULANCE,
                        vehicle_class=VehicleClass.LIGHT,
                        casualty_capacity=2,
                        speed=SpeedProfile(unladen_kmh=60, laden_kmh=45),
                        service_times={"load_time_mins": 5, "unload_time_mins": 5},
                    )
                ],
                vehicles=[
                    Vehicle(id="v1", type_id="amb", start_location="only_node")
                ],
                demand=DemandConfiguration(
                    mode=DemandMode.MANUAL,
                    manual_events=[
                        ManualDemandEvent(
                            time_mins=30,
                            type=DemandType.CASUALTY,
                            location="only_node",
                        )
                    ],
                ),
            )
        
        assert "missing_node" in str(exc_info.value)
    
    def test_scenario_summary(self):
        """Test scenario summary generation."""
        from pj_ogun.models.scenario import load_scenario
        
        scenario_path = Path(__file__).parent.parent / "scenarios" / "example_medevac.json"
        if not scenario_path.exists():
            pytest.skip("Example scenario not found")
        
        scenario = load_scenario(str(scenario_path))
        summary = scenario.summary()
        
        assert "Basic MEDEVAC Exercise" in summary
        assert "8 hours" in summary or "8.0 hours" in summary


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
