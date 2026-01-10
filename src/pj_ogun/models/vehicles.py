"""Vehicle type definitions and fleet management models."""

from typing import Optional

from pydantic import BaseModel, Field, model_validator

from pj_ogun.models.enums import VehicleClass, VehicleRole, VehicleState


class SpeedProfile(BaseModel):
    """Vehicle speed varies by load state.
    
    Laden speed is always <= unladen speed. The simulation uses
    the appropriate speed based on current load.
    """
    
    unladen_kmh: float = Field(
        ..., 
        gt=0, 
        le=150,
        description="Speed when empty (km/h)"
    )
    laden_kmh: float = Field(
        ..., 
        gt=0, 
        le=150,
        description="Speed when carrying load (km/h)"
    )
    
    @model_validator(mode="after")
    def laden_not_faster_than_unladen(self) -> "SpeedProfile":
        """Validate that laden speed doesn't exceed unladen speed."""
        if self.laden_kmh > self.unladen_kmh:
            raise ValueError(
                f"Laden speed ({self.laden_kmh} km/h) cannot exceed "
                f"unladen speed ({self.unladen_kmh} km/h)"
            )
        return self
    
    def get_speed(self, is_laden: bool) -> float:
        """Return appropriate speed based on load state."""
        return self.laden_kmh if is_laden else self.unladen_kmh


class ServiceTimes(BaseModel):
    """Time durations for loading/unloading operations.
    
    Different vehicle roles use different subsets of these times.
    Times are in minutes.
    """
    
    load_time_mins: float = Field(
        ..., 
        ge=0,
        description="Time to load cargo/casualties at pickup (minutes)"
    )
    unload_time_mins: float = Field(
        ..., 
        ge=0,
        description="Time to unload at delivery point (minutes)"
    )
    hookup_time_mins: Optional[float] = Field(
        None, 
        ge=0,
        description="Time to prepare disabled vehicle for towing (recovery only)"
    )
    
    @model_validator(mode="after")
    def recovery_needs_hookup(self) -> "ServiceTimes":
        """Note: hookup_time validation happens at VehicleType level."""
        return self


class VehicleType(BaseModel):
    """Template defining a class of vehicle.
    
    Multiple individual vehicles can be instantiated from a single type.
    The type defines capabilities and performance characteristics.
    """
    
    id: str = Field(
        ..., 
        min_length=1, 
        max_length=50,
        description="Unique identifier for this vehicle type"
    )
    name: str = Field(
        ...,
        description="Human-readable name (e.g., 'Land Rover Ambulance')"
    )
    role: VehicleRole = Field(
        ...,
        description="Functional role determining behaviour"
    )
    vehicle_class: VehicleClass = Field(
        ...,
        description="Weight class affecting route access"
    )
    
    # === Capacity ===
    casualty_capacity: Optional[int] = Field(
        None, 
        ge=0,
        description="Number of casualties (litter + sitting)"
    )
    cargo_capacity_kg: Optional[float] = Field(
        None, 
        ge=0,
        description="General cargo capacity (kg)"
    )
    ammo_capacity_units: Optional[int] = Field(
        None, 
        ge=0,
        description="Ammunition carrying capacity (units)"
    )
    fuel_capacity_litres: Optional[float] = Field(
        None, 
        ge=0,
        description="Fuel carrying capacity (litres) - for tankers"
    )
    tow_capacity_class: Optional[VehicleClass] = Field(
        None,
        description="Max vehicle class this can tow (recovery vehicles only)"
    )
    
    # === Performance ===
    speed: SpeedProfile = Field(
        ...,
        description="Speed profile (unladen/laden)"
    )
    service_times: ServiceTimes = Field(
        ...,
        description="Loading/unloading durations"
    )
    
    # === Reliability ===
    mtbf_hours: Optional[float] = Field(
        None, 
        gt=0,
        description="Mean Time Between Failures (hours)"
    )
    
    # === Crew ===
    crew_size: int = Field(
        2, 
        ge=1, 
        le=10,
        description="Number of crew required to operate"
    )
    max_continuous_ops_hours: float = Field(
        12.0, 
        gt=0, 
        le=24,
        description="Maximum hours before mandatory crew rest"
    )
    
    @model_validator(mode="after")
    def validate_role_requirements(self) -> "VehicleType":
        """Ensure role-specific requirements are met."""
        
        # Ambulances must have casualty capacity
        if self.role == VehicleRole.AMBULANCE:
            if not self.casualty_capacity or self.casualty_capacity < 1:
                raise ValueError("Ambulance must have casualty_capacity >= 1")
        
        # Recovery vehicles must have tow capacity and hookup time
        if self.role == VehicleRole.RECOVERY:
            if not self.tow_capacity_class:
                raise ValueError("Recovery vehicle must specify tow_capacity_class")
            if self.service_times.hookup_time_mins is None:
                raise ValueError("Recovery vehicle must specify hookup_time_mins")
        
        # Ammo logistics must have ammo capacity
        if self.role == VehicleRole.AMMO_LOGISTICS:
            if not self.ammo_capacity_units or self.ammo_capacity_units < 1:
                raise ValueError("Ammo logistics vehicle must have ammo_capacity_units >= 1")
        
        # Fuel logistics must have fuel capacity
        if self.role == VehicleRole.FUEL_LOGISTICS:
            if not self.fuel_capacity_litres or self.fuel_capacity_litres < 1:
                raise ValueError("Fuel logistics vehicle must have fuel_capacity_litres >= 1")
        
        return self
    
    model_config = {"extra": "forbid"}


class Vehicle(BaseModel):
    """Individual vehicle instance in the simulation.
    
    References a VehicleType for capabilities and tracks
    instance-specific state like location and callsign.
    """
    
    id: str = Field(
        ..., 
        min_length=1, 
        max_length=50,
        description="Unique identifier for this vehicle instance"
    )
    type_id: str = Field(
        ...,
        description="Reference to VehicleType.id"
    )
    callsign: Optional[str] = Field(
        None,
        description="Radio callsign (e.g., 'MEDIC 21')"
    )
    start_location: str = Field(
        ...,
        description="Node ID for initial position at simulation start"
    )
    
    # === Initial State ===
    initial_state: VehicleState = Field(
        VehicleState.IDLE,
        description="State at simulation start"
    )
    initial_load_fraction: float = Field(
        0.0, 
        ge=0, 
        le=1,
        description="Starting load as fraction of capacity (0=empty, 1=full)"
    )
    
    model_config = {"extra": "forbid"}


# === Pre-built Vehicle Type Library ===
# These can be used as templates or starting points

VEHICLE_TYPE_LIBRARY: dict[str, dict] = {
    # === AMBULANCES ===
    "amb_light": {
        "id": "amb_light",
        "name": "Land Rover Ambulance",
        "role": "ambulance",
        "vehicle_class": "light",
        "casualty_capacity": 2,
        "speed": {"unladen_kmh": 80, "laden_kmh": 60},
        "service_times": {"load_time_mins": 5, "unload_time_mins": 5},
        "mtbf_hours": 200,
        "crew_size": 2,
        "max_continuous_ops_hours": 12,
    },
    "amb_medium": {
        "id": "amb_medium",
        "name": "MAN SV Ambulance",
        "role": "ambulance",
        "vehicle_class": "medium",
        "casualty_capacity": 4,
        "speed": {"unladen_kmh": 70, "laden_kmh": 50},
        "service_times": {"load_time_mins": 8, "unload_time_mins": 8},
        "mtbf_hours": 300,
        "crew_size": 2,
        "max_continuous_ops_hours": 12,
    },
    
    # === RECOVERY ===
    "rec_light": {
        "id": "rec_light",
        "name": "REME Light Recovery",
        "role": "recovery",
        "vehicle_class": "light",
        "tow_capacity_class": "light",
        "speed": {"unladen_kmh": 70, "laden_kmh": 30},
        "service_times": {"load_time_mins": 0, "unload_time_mins": 0, "hookup_time_mins": 15},
        "mtbf_hours": 250,
        "crew_size": 2,
        "max_continuous_ops_hours": 12,
    },
    "rec_medium": {
        "id": "rec_medium",
        "name": "Foden Recovery",
        "role": "recovery",
        "vehicle_class": "medium",
        "tow_capacity_class": "medium",
        "speed": {"unladen_kmh": 60, "laden_kmh": 25},
        "service_times": {"load_time_mins": 0, "unload_time_mins": 0, "hookup_time_mins": 20},
        "mtbf_hours": 200,
        "crew_size": 2,
        "max_continuous_ops_hours": 12,
    },
    "rec_heavy": {
        "id": "rec_heavy",
        "name": "CRARRV",
        "role": "recovery",
        "vehicle_class": "heavy",
        "tow_capacity_class": "heavy",
        "speed": {"unladen_kmh": 50, "laden_kmh": 20},
        "service_times": {"load_time_mins": 0, "unload_time_mins": 0, "hookup_time_mins": 30},
        "mtbf_hours": 150,
        "crew_size": 3,
        "max_continuous_ops_hours": 10,
    },
    
    # === LOGISTICS ===
    "log_ammo_medium": {
        "id": "log_ammo_medium",
        "name": "MAN SV Ammo",
        "role": "ammo_logistics",
        "vehicle_class": "medium",
        "ammo_capacity_units": 2000,
        "cargo_capacity_kg": 8000,
        "speed": {"unladen_kmh": 70, "laden_kmh": 50},
        "service_times": {"load_time_mins": 20, "unload_time_mins": 15},
        "mtbf_hours": 350,
        "crew_size": 2,
        "max_continuous_ops_hours": 12,
    },
    "log_fuel_medium": {
        "id": "log_fuel_medium",
        "name": "EPLS Fuel Pod",
        "role": "fuel_logistics",
        "vehicle_class": "medium",
        "fuel_capacity_litres": 5000,
        "speed": {"unladen_kmh": 65, "laden_kmh": 45},
        "service_times": {"load_time_mins": 15, "unload_time_mins": 20},
        "mtbf_hours": 300,
        "crew_size": 2,
        "max_continuous_ops_hours": 12,
    },
    "log_general_medium": {
        "id": "log_general_medium",
        "name": "MAN SV Cargo",
        "role": "general_logistics",
        "vehicle_class": "medium",
        "cargo_capacity_kg": 9000,
        "speed": {"unladen_kmh": 70, "laden_kmh": 50},
        "service_times": {"load_time_mins": 25, "unload_time_mins": 20},
        "mtbf_hours": 350,
        "crew_size": 2,
        "max_continuous_ops_hours": 12,
    },
}


def get_vehicle_type_template(type_id: str) -> VehicleType:
    """Get a pre-built vehicle type from the library.
    
    Args:
        type_id: One of the keys in VEHICLE_TYPE_LIBRARY
        
    Returns:
        Validated VehicleType instance
        
    Raises:
        KeyError: If type_id not in library
        ValidationError: If template data is invalid (shouldn't happen)
    """
    if type_id not in VEHICLE_TYPE_LIBRARY:
        raise KeyError(
            f"Unknown vehicle type '{type_id}'. "
            f"Available: {list(VEHICLE_TYPE_LIBRARY.keys())}"
        )
    return VehicleType.model_validate(VEHICLE_TYPE_LIBRARY[type_id])
