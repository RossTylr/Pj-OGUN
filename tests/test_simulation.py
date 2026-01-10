"""Tests for Pj-OGUN simulation engine."""

import json
import pytest
from pathlib import Path

from pj_ogun.models.scenario import load_scenario
from pj_ogun.models.enums import EventType
from pj_ogun.simulation.engine import SimulationEngine


class TestSimulationEngine:
    @pytest.fixture
    def example_scenario(self):
        """Load the example MEDEVAC scenario."""
        scenario_path = Path(__file__).parent.parent / "scenarios" / "example_medevac.json"
        if not scenario_path.exists():
            pytest.skip("Example scenario not found")
        return load_scenario(str(scenario_path))
    
    def test_engine_initialisation(self, example_scenario):
        """Test that engine initialises without error."""
        engine = SimulationEngine(example_scenario)
        assert engine.scenario == example_scenario
        assert engine.event_log is not None
    
    def test_simulation_runs(self, example_scenario):
        """Test that simulation runs to completion."""
        engine = SimulationEngine(example_scenario)
        event_log = engine.run()
        
        # Should have some events
        assert len(event_log) > 0
        
        # Should have start and end events
        event_types = [e.event_type for e in event_log.events]
        assert EventType.SIMULATION_STARTED in event_types
        assert EventType.SIMULATION_ENDED in event_types
    
    def test_casualties_generated(self, example_scenario):
        """Test that casualties are generated from demand config."""
        engine = SimulationEngine(example_scenario)
        event_log = engine.run()
        
        # Example scenario has 10 casualties total (sum of quantities)
        casualties = event_log.casualties
        assert len(casualties) == 10  # 1+1+2+1+1+2+1+1 = 10
    
    def test_casualties_evacuated(self, example_scenario):
        """Test that casualties are collected and delivered."""
        engine = SimulationEngine(example_scenario)
        event_log = engine.run()
        
        # Check that at least some casualties were collected
        collected_events = event_log.filter_by_type(EventType.CASUALTY_COLLECTED)
        assert len(collected_events) > 0
        
        # Check that at least some casualties were delivered
        delivered_events = event_log.filter_by_type(EventType.CASUALTY_DELIVERED)
        assert len(delivered_events) > 0
    
    def test_vehicles_dispatched(self, example_scenario):
        """Test that vehicles are dispatched for casualties."""
        engine = SimulationEngine(example_scenario)
        event_log = engine.run()
        
        dispatch_events = event_log.filter_by_type(EventType.VEHICLE_DISPATCHED)
        assert len(dispatch_events) > 0
    
    def test_deterministic_results(self, example_scenario):
        """Test that same seed produces same results."""
        # Run twice with same seed
        engine1 = SimulationEngine(example_scenario)
        log1 = engine1.run()
        
        engine2 = SimulationEngine(example_scenario)
        log2 = engine2.run()
        
        # Same number of events
        assert len(log1) == len(log2)
        
        # Same casualty count
        assert len(log1.casualties) == len(log2.casualties)
        
        # Same event types in same order
        types1 = [e.event_type for e in log1.events]
        types2 = [e.event_type for e in log2.events]
        assert types1 == types2
    
    def test_casualty_timestamps(self, example_scenario):
        """Test that casualty timestamps are populated correctly."""
        engine = SimulationEngine(example_scenario)
        event_log = engine.run()
        
        for casualty in event_log.casualties:
            # All casualties should have generation time
            assert casualty.time_generated >= 0
            
            # Collected casualties should have collection time after generation
            if casualty.time_collected is not None:
                assert casualty.time_collected >= casualty.time_generated
            
            # Delivered casualties should have delivery time after collection
            if casualty.time_delivered is not None:
                assert casualty.time_delivered >= casualty.time_collected
    
    def test_event_log_export(self, example_scenario):
        """Test that event log can be exported to DataFrame."""
        engine = SimulationEngine(example_scenario)
        event_log = engine.run()
        
        # Export to DataFrame
        df = event_log.to_dataframe()
        assert len(df) == len(event_log)
        assert "time_mins" in df.columns
        assert "event_type" in df.columns
        
        # Export casualties to DataFrame
        cas_df = event_log.casualties_to_dataframe()
        assert len(cas_df) == len(event_log.casualties)


class TestNetworkRouting:
    @pytest.fixture
    def example_scenario(self):
        scenario_path = Path(__file__).parent.parent / "scenarios" / "example_medevac.json"
        if not scenario_path.exists():
            pytest.skip("Example scenario not found")
        return load_scenario(str(scenario_path))
    
    def test_graph_construction(self, example_scenario):
        """Test that network graph is built correctly."""
        engine = SimulationEngine(example_scenario)
        engine._setup()
        
        # Graph should have correct number of nodes and edges
        assert engine.graph.number_of_nodes() == 4
        assert engine.graph.number_of_edges() == 4
    
    def test_travel_time_calculation(self, example_scenario):
        """Test travel time between nodes."""
        engine = SimulationEngine(example_scenario)
        engine._setup()
        
        # Calculate travel time from combat_alpha to role1_aid
        # Distance is 8 km, terrain factor 1.2 -> effective 9.6 km
        # At 60 km/h -> 9.6 minutes
        travel_time = engine._calculate_travel_time(
            "combat_alpha", "role1_aid", 60
        )
        assert travel_time > 0
        assert travel_time < 20  # Should be reasonable
    
    def test_find_nearest_medical(self, example_scenario):
        """Test finding nearest medical facility."""
        engine = SimulationEngine(example_scenario)
        engine._setup()
        
        # From combat_alpha, nearest should be role1_aid
        nearest = engine._find_nearest_medical("combat_alpha")
        assert nearest == "role1_aid"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
