"""Top-level scenario model for Pj-OGUN simulations."""

from typing import Optional

from pydantic import BaseModel, Field, model_validator

from pj_ogun.schema.demand import DemandConfiguration
from pj_ogun.schema.edges import Edge
from pj_ogun.schema.nodes import Node
from pj_ogun.schema.vehicles import Vehicle, VehicleType


class SimulationConfig(BaseModel):
    """Global simulation parameters.
    
    Controls simulation duration, randomness, and
    optional realism features for extended runs.
    """
    
    # ===== Core Parameters =====
    duration_hours: float = Field(
        8.0,
        gt=0,
        le=72,
        description="Simulation length in hours (max 72)"
    )
    random_seed: int = Field(
        42,
        description="Seed for reproducible random number generation"
    )
    time_step_mins: float = Field(
        1.0,
        gt=0,
        description="Minimum time resolution for event scheduling"
    )
    
    # ===== 72-Hour Realism Features =====
    enable_crew_fatigue: bool = Field(
        False,
        description="Model crew rest requirements after continuous ops"
    )
    enable_vehicle_maintenance: bool = Field(
        False,
        description="Schedule vehicle maintenance windows"
    )
    enable_shift_patterns: bool = Field(
        False,
        description="Model day/night shift changes at facilities"
    )
    enable_resupply_cycles: bool = Field(
        False,
        description="Model periodic depot resupply"
    )
    
    # ===== Performance =====
    max_events: int = Field(
        100000,
        gt=0,
        description="Maximum events before simulation terminates (safety limit)"
    )
    
    @property
    def duration_mins(self) -> float:
        """Get duration in minutes for internal calculations."""
        return self.duration_hours * 60


class Scenario(BaseModel):
    """Complete Pj-OGUN scenario definition.
    
    A scenario contains everything needed to run a simulation:
    - Network topology (nodes and edges)
    - Vehicle fleet (types and instances)
    - Demand configuration
    - Simulation parameters
    
    The scenario can be serialised to/from JSON for storage
    and sharing.
    """
    
    # ===== Metadata =====
    name: str = Field(
        ...,
        min_length=1,
        description="Scenario name"
    )
    description: Optional[str] = Field(
        None,
        description="Detailed scenario description"
    )
    version: str = Field(
        "1.0.0",
        description="Schema version for compatibility tracking"
    )
    author: Optional[str] = Field(
        None,
        description="Scenario author"
    )
    
    # ===== Network =====
    nodes: list[Node] = Field(
        ...,
        min_length=1,
        description="Network nodes (facilities, positions)"
    )
    edges: list[Edge] = Field(
        default_factory=list,
        description="Routes between nodes"
    )
    
    # ===== Fleet =====
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
    
    # ===== Demand =====
    demand: DemandConfiguration = Field(
        ...,
        description="Demand generation configuration"
    )
    
    # ===== Configuration =====
    config: SimulationConfig = Field(
        default_factory=SimulationConfig,
        description="Simulation parameters"
    )
    
    @model_validator(mode="after")
    def validate_all_references(self) -> "Scenario":
        """Ensure all cross-references are valid.
        
        Validates that:
        - Edges reference existing nodes
        - Vehicles reference existing vehicle types
        - Vehicle start locations are valid nodes
        - Demand events reference valid nodes
        """
        # Build lookup sets
        node_ids = {n.id for n in self.nodes}
        vehicle_type_ids = {vt.id for vt in self.vehicle_types}
        
        errors = []
        
        # Validate edges reference valid nodes
        for i, edge in enumerate(self.edges):
            if edge.from_node not in node_ids:
                errors.append(
                    f"Edge {i}: from_node '{edge.from_node}' not found in nodes"
                )
            if edge.to_node not in node_ids:
                errors.append(
                    f"Edge {i}: to_node '{edge.to_node}' not found in nodes"
                )
        
        # Validate vehicles reference valid types and locations
        for vehicle in self.vehicles:
            if vehicle.type_id not in vehicle_type_ids:
                errors.append(
                    f"Vehicle '{vehicle.id}': type_id '{vehicle.type_id}' "
                    f"not found in vehicle_types"
                )
            if vehicle.start_location not in node_ids:
                errors.append(
                    f"Vehicle '{vehicle.id}': start_location '{vehicle.start_location}' "
                    f"not found in nodes"
                )
        
        # Validate demand event locations
        for event in self.demand.manual_events:
            if event.location not in node_ids:
                errors.append(
                    f"Manual event at t={event.time_mins}: location '{event.location}' "
                    f"not found in nodes"
                )
        
        for rate_config in self.demand.rate_based:
            if rate_config.location not in node_ids:
                errors.append(
                    f"Rate-based demand: location '{rate_config.location}' "
                    f"not found in nodes"
                )
        
        if errors:
            raise ValueError(
                f"Scenario validation failed with {len(errors)} error(s):\n"
                + "\n".join(f"  - {e}" for e in errors)
            )
        
        return self
    
    @model_validator(mode="after")
    def validate_node_ids_unique(self) -> "Scenario":
        """Ensure all node IDs are unique."""
        ids = [n.id for n in self.nodes]
        duplicates = [id_ for id_ in ids if ids.count(id_) > 1]
        if duplicates:
            raise ValueError(
                f"Duplicate node IDs found: {set(duplicates)}"
            )
        return self
    
    @model_validator(mode="after")
    def validate_vehicle_ids_unique(self) -> "Scenario":
        """Ensure all vehicle IDs are unique."""
        ids = [v.id for v in self.vehicles]
        duplicates = [id_ for id_ in ids if ids.count(id_) > 1]
        if duplicates:
            raise ValueError(
                f"Duplicate vehicle IDs found: {set(duplicates)}"
            )
        return self
    
    def get_node_by_id(self, node_id: str) -> Optional[Node]:
        """Look up a node by ID."""
        for node in self.nodes:
            if node.id == node_id:
                return node
        return None
    
    def get_vehicle_type_by_id(self, type_id: str) -> Optional[VehicleType]:
        """Look up a vehicle type by ID."""
        for vt in self.vehicle_types:
            if vt.id == type_id:
                return vt
        return None
    
    def get_vehicles_by_role(self, role: str) -> list[Vehicle]:
        """Get all vehicles of a given role."""
        result = []
        for vehicle in self.vehicles:
            vtype = self.get_vehicle_type_by_id(vehicle.type_id)
            if vtype and vtype.role.value == role:
                result.append(vehicle)
        return result
    
    def to_json(self, indent: int = 2) -> str:
        """Serialize scenario to JSON string."""
        return self.model_dump_json(indent=indent, by_alias=True)
    
    @classmethod
    def from_json(cls, json_str: str) -> "Scenario":
        """Deserialize scenario from JSON string."""
        return cls.model_validate_json(json_str)
    
    def summary(self) -> dict:
        """Generate a summary of the scenario."""
        return {
            "name": self.name,
            "nodes": len(self.nodes),
            "edges": len(self.edges),
            "vehicle_types": len(self.vehicle_types),
            "vehicles": len(self.vehicles),
            "duration_hours": self.config.duration_hours,
            "demand_mode": self.demand.mode.value,
            "manual_events": len(self.demand.manual_events),
            "rate_based_sources": len(self.demand.rate_based),
        }
