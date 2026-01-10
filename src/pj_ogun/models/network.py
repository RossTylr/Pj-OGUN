"""Network topology models: nodes and edges"""

from typing import Optional

from pydantic import BaseModel, Field, field_validator

from pj_ogun.models.enums import NodeType, VehicleClass


class Coordinates(BaseModel):
    """Spatial coordinates for node placement.
    
    For MVP, uses simple grid coordinates (x, y).
    Future: extend with lat/lon for real geography.
    """
    
    x: float = Field(..., description="X coordinate (grid units or easting)")
    y: float = Field(..., description="Y coordinate (grid units or northing)")
    
    # Future geographic support
    # latitude: Optional[float] = Field(None, ge=-90, le=90)
    # longitude: Optional[float] = Field(None, ge=-180, le=180)
    
    def distance_to(self, other: "Coordinates") -> float:
        """Euclidean distance to another coordinate point."""
        return ((self.x - other.x) ** 2 + (self.y - other.y) ** 2) ** 0.5


class NodeCapacity(BaseModel):
    """Structured capacity constraints for different node functions.
    
    Each capacity type maps to a SimPy Resource with that many slots.
    None means unlimited/not applicable for this node type.
    """
    
    treatment_slots: Optional[int] = Field(
        None, ge=0, 
        description="Medical treatment capacity (concurrent patients)"
    )
    repair_bays: Optional[int] = Field(
        None, ge=0,
        description="Vehicle repair bays (concurrent repairs)"
    )
    storage_ammo: Optional[int] = Field(
        None, ge=0,
        description="Ammunition storage capacity (units)"
    )
    storage_fuel: Optional[int] = Field(
        None, ge=0,
        description="Fuel storage capacity (litres)"
    )
    holding_casualties: Optional[int] = Field(
        None, ge=0,
        description="Casualty holding area capacity"
    )
    parking_vehicles: Optional[int] = Field(
        None, ge=0,
        description="Vehicle parking/staging capacity"
    )
    loading_bays: Optional[int] = Field(
        None, ge=0,
        description="Concurrent loading/unloading operations"
    )


class NodeProperties(BaseModel):
    """Role-specific operational parameters for nodes.
    
    Different node types use different subsets of these properties.
    Unused properties should be left as None.
    """
    
    # === Medical Properties ===
    treatment_time_mins: Optional[float] = Field(
        None, gt=0,
        description="Average treatment time per casualty (minutes)"
    )
    triage_time_mins: Optional[float] = Field(
        None, gt=0,
        description="Time to triage incoming casualty (minutes)"
    )
    
    # === Workshop Properties ===
    repair_time_light_mins: Optional[float] = Field(
        None, gt=0,
        description="Average repair time for light vehicles (minutes)"
    )
    repair_time_medium_mins: Optional[float] = Field(
        None, gt=0,
        description="Average repair time for medium vehicles (minutes)"
    )
    repair_time_heavy_mins: Optional[float] = Field(
        None, gt=0,
        description="Average repair time for heavy vehicles (minutes)"
    )
    
    # === Supply Point Properties ===
    initial_ammo_stock: Optional[int] = Field(
        None, ge=0,
        description="Starting ammunition inventory (units)"
    )
    initial_fuel_stock: Optional[int] = Field(
        None, ge=0,
        description="Starting fuel inventory (litres)"
    )
    resupply_interval_hours: Optional[float] = Field(
        None, gt=0,
        description="Time between automatic resupply deliveries"
    )
    resupply_quantity: Optional[int] = Field(
        None, gt=0,
        description="Quantity delivered per resupply cycle"
    )
    
    # === Combat Node Properties ===
    ammo_consumption_rate: Optional[float] = Field(
        None, ge=0,
        description="Ammunition consumption rate (units/hour)"
    )
    fuel_consumption_rate: Optional[float] = Field(
        None, ge=0,
        description="Fuel consumption rate (litres/hour)"
    )
    
    # === Operational Hours ===
    operating_start_hour: Optional[int] = Field(
        None, ge=0, le=23,
        description="Start of operating hours (24h clock)"
    )
    operating_end_hour: Optional[int] = Field(
        None, ge=0, le=23,
        description="End of operating hours (24h clock)"
    )


class Node(BaseModel):
    """A location in the logistics network.
    
    Nodes represent physical facilities (combat positions, medical stations,
    workshops, supply points) that vehicles travel between and where
    service operations occur.
    """
    
    id: str = Field(
        ..., 
        min_length=1, 
        max_length=50,
        description="Unique identifier for the node"
    )
    name: str = Field(
        ..., 
        min_length=1,
        description="Human-readable display name"
    )
    type: NodeType = Field(
        ...,
        description="Functional category determining node behaviour"
    )
    coordinates: Coordinates = Field(
        ...,
        description="Spatial position for routing and visualisation"
    )
    capacity: NodeCapacity = Field(
        default_factory=NodeCapacity,
        description="Resource capacity constraints"
    )
    properties: NodeProperties = Field(
        default_factory=NodeProperties,
        description="Role-specific operational parameters"
    )
    
    @field_validator("id")
    @classmethod
    def clean_id(cls, v: str) -> str:
        """Normalise node ID: strip whitespace, replace spaces with underscores."""
        return v.strip().replace(" ", "_")
    
    model_config = {"extra": "forbid"}


class EdgeProperties(BaseModel):
    """Route characteristics affecting vehicle transit."""
    
    terrain_factor: float = Field(
        1.0, 
        gt=0, 
        le=3.0,
        description="Travel time multiplier (1.0=normal road, >1=difficult terrain)"
    )
    max_vehicle_class: VehicleClass = Field(
        VehicleClass.HEAVY,
        description="Heaviest vehicle class permitted on this route"
    )
    is_operational: bool = Field(
        True,
        description="Route currently usable (can be disabled for scenarios)"
    )
    route_name: Optional[str] = Field(
        None,
        description="Optional name for the route (e.g., 'MSR BRONZE')"
    )


class Edge(BaseModel):
    """A route connecting two nodes in the network.
    
    Edges represent roads or paths that vehicles traverse.
    Travel time = distance / vehicle_speed * terrain_factor
    """
    
    from_node: str = Field(
        ..., 
        alias="from",
        description="Source node ID"
    )
    to_node: str = Field(
        ..., 
        alias="to",
        description="Destination node ID"
    )
    distance_km: float = Field(
        ..., 
        gt=0,
        description="Route length in kilometres"
    )
    bidirectional: bool = Field(
        True,
        description="If True, travel permitted in both directions"
    )
    properties: EdgeProperties = Field(
        default_factory=EdgeProperties,
        description="Route characteristics"
    )
    
    model_config = {
        "extra": "forbid",
        "populate_by_name": True,  # Allow both 'from' and 'from_node'
    }
    
    def travel_time_mins(
        self, 
        speed_kmh: float, 
        include_terrain: bool = True
    ) -> float:
        """Calculate travel time in minutes for given speed.
        
        Args:
            speed_kmh: Vehicle speed in km/h
            include_terrain: If True, apply terrain factor
            
        Returns:
            Travel time in minutes
        """
        base_time_hours = self.distance_km / speed_kmh
        factor = self.properties.terrain_factor if include_terrain else 1.0
        return base_time_hours * factor * 60  # Convert to minutes
