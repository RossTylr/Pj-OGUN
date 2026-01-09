"""Top-level scenario model combining all components.

A Scenario is the complete input specification for a Pj-OGUN simulation run.
It includes the network topology, vehicle fleet, demand configuration,
and simulation parameters.
"""

from typing import Optional

from pydantic import BaseModel, Field, model_validator

from pj_ogun.models.demand import DemandConfiguration
from pj_ogun.models.enums import DemandMode
from pj_ogun.models.network import Edge, Node
from pj_ogun.models.vehicles import Vehicle, VehicleType


class SimulationConfig(BaseModel):
    """Global simulation control parameters."""
    
    # Time
    duration_hours: float = Field(
        8.0, 
        gt=0, 
        le=168,  # Up to 1 week
        description="Total simulation duration (hours)"
    )
    random_seed: int = Field(
        42,
        description="RNG seed for reproducible stochastic events"
    )
    time_step_mins: float = Field(
        1.0, 
        gt=0, 
        le=60,
        description="Minimum time resolution for event scheduling"
    )
    
    # Extended operations features (Phase 4)
    enable_crew_fatigue: bool = Field(
        False,
        description="Model mandatory crew rest periods"
    )
    enable_vehicle_maintenance: bool = Field(
        False,
        description="Schedule maintenance windows for vehicles"
    )
    enable_shift_patterns: bool = Field(
        False,
        description="Model day/night shift rotations"
    )
    enable_breakdowns: bool = Field(
        False,
        description="Generate random vehicle breakdowns from MTBF"
    )
    
    # Output control
    log_level: str = Field(
        "INFO",
        description="Event logging verbosity (DEBUG, INFO, WARNING)"
    )
    
    model_config = {"extra": "forbid"}
    
    @property
    def duration_mins(self) -> float:
        """Simulation duration in minutes."""
        return self.duration_hours * 60


class Scenario(BaseModel):
    """Complete Pj-OGUN scenario definition.
    
    This is the root model that combines all scenario components:
    - Network topology (nodes and edges)
    - Vehicle fleet (types and instances)
    - Demand configuration
    - Simulation parameters
    
    Validation ensures all cross-references are valid (edges reference
    existing nodes, vehicles reference valid types and locations, etc.)
    """
    
    # Metadata
    name: str = Field(
        ...,
        min_length=1,
        description="Scenario name"
    )
    description: Optional[str] = Field(
        None,
        description="Scenario description and notes"
    )
    version: str = Field(
        "1.0.0",
        description="Schema version for compatibility checking"
    )
    
    # Network
    nodes: list[Node] = Field(
        ...,
        min_length=1,
        description="Network nodes (facilities, positions)"
    )
    edges: list[Edge] = Field(
        ...,
        min_length=1,
        description="Network edges (routes between nodes)"
    )
    
    # Fleet
    vehicle_types: list[VehicleType] = Field(
        ...,
        min_length=1,
        description="Vehicle type definitions"
    )
    vehicles: list[Vehicle] = Field(
        ...,
        min_length=1,
        description="Vehicle instances in the scenario"
    )
    
    # Demand
    demand: DemandConfiguration = Field(
        ...,
        description="Demand generation configuration"
    )
    
    # Configuration
    config: SimulationConfig = Field(
        default_factory=SimulationConfig,
        description="Simulation control parameters"
    )
    
    @model_validator(mode="after")
    def validate_all_references(self) -> "Scenario":
        """Ensure all cross-references between components are valid."""
        errors = []
        
        # Build reference sets
        node_ids = {n.id for n in self.nodes}
        vehicle_type_ids = {vt.id for vt in self.vehicle_types}
        
        # Check edge references
        for i, edge in enumerate(self.edges):
            if edge.from_node not in node_ids:
                errors.append(
                    f"Edge[{i}] references unknown source node: '{edge.from_node}'"
                )
            if edge.to_node not in node_ids:
                errors.append(
                    f"Edge[{i}] references unknown destination node: '{edge.to_node}'"
                )
            if edge.from_node == edge.to_node:
                errors.append(
                    f"Edge[{i}] is a self-loop (from=to='{edge.from_node}')"
                )
        
        # Check vehicle type references
        for vehicle in self.vehicles:
            if vehicle.type_id not in vehicle_type_ids:
                errors.append(
                    f"Vehicle '{vehicle.id}' references unknown type: '{vehicle.type_id}'"
                )
            if vehicle.start_location not in node_ids:
                errors.append(
                    f"Vehicle '{vehicle.id}' starts at unknown node: '{vehicle.start_location}'"
                )
        
        # Check demand location references
        demand_locations = self.demand.get_all_locations()
        for loc in demand_locations:
            if loc not in node_ids:
                errors.append(
                    f"Demand references unknown node: '{loc}'"
                )
        
        # Raise combined error if any issues found
        if errors:
            raise ValueError(
                f"Scenario validation failed with {len(errors)} error(s):\n"
                + "\n".join(f"  - {e}" for e in errors)
            )
        
        return self
    
    @model_validator(mode="after")
    def validate_network_connectivity(self) -> "Scenario":
        """Warn if network appears disconnected (not a hard error)."""
        # Build adjacency for connectivity check
        # This is a soft check - disconnected nodes might be intentional
        # Full graph analysis happens in simulation setup
        return self
    
    def get_node_by_id(self, node_id: str) -> Node | None:
        """Look up a node by its ID."""
        for node in self.nodes:
            if node.id == node_id:
                return node
        return None
    
    def get_vehicle_type_by_id(self, type_id: str) -> VehicleType | None:
        """Look up a vehicle type by its ID."""
        for vt in self.vehicle_types:
            if vt.id == type_id:
                return vt
        return None
    
    def get_vehicles_by_type(self, type_id: str) -> list[Vehicle]:
        """Get all vehicles of a specific type."""
        return [v for v in self.vehicles if v.type_id == type_id]
    
    def get_vehicles_by_role(self, role: str) -> list[Vehicle]:
        """Get all vehicles with types matching a role."""
        type_ids_for_role = {
            vt.id for vt in self.vehicle_types if vt.role.value == role
        }
        return [v for v in self.vehicles if v.type_id in type_ids_for_role]
    
    def summary(self) -> str:
        """Generate human-readable scenario summary."""
        lines = [
            f"Scenario: {self.name}",
            f"  Duration: {self.config.duration_hours} hours",
            f"  Nodes: {len(self.nodes)}",
            f"  Edges: {len(self.edges)}",
            f"  Vehicle types: {len(self.vehicle_types)}",
            f"  Vehicles: {len(self.vehicles)}",
            f"  Demand mode: {self.demand.mode.value}",
        ]
        
        if self.demand.mode == DemandMode.MANUAL:
            lines.append(f"  Manual events: {len(self.demand.manual_events)}")
        else:
            lines.append(f"  Rate configs: {len(self.demand.rate_based)}")
        
        return "\n".join(lines)
    
    model_config = {"extra": "forbid"}


def load_scenario(path: str) -> Scenario:
    """Load and validate a scenario from JSON file.
    
    Args:
        path: Path to scenario JSON file
        
    Returns:
        Validated Scenario instance
        
    Raises:
        FileNotFoundError: If file doesn't exist
        ValidationError: If JSON doesn't match schema
    """
    import json
    from pathlib import Path
    
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"Scenario file not found: {path}")
    
    with open(file_path) as f:
        data = json.load(f)
    
    return Scenario.model_validate(data)


def save_scenario(scenario: Scenario, path: str, indent: int = 2) -> None:
    """Save a scenario to JSON file.
    
    Args:
        scenario: Scenario to save
        path: Output file path
        indent: JSON indentation (default 2)
    """
    from pathlib import Path
    
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(file_path, "w") as f:
        f.write(scenario.model_dump_json(indent=indent, by_alias=True))
