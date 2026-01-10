"""Demand generation configuration for simulations."""

from typing import Optional

from pydantic import BaseModel, Field, model_validator

from pj_ogun.schema.enums import CasualtyPriority, DemandMode, DemandType


class ManualDemandEvent(BaseModel):
    """A specific demand event at a predetermined time.
    
    Used in MANUAL demand mode to specify exactly when
    events occur. Useful for reproducing specific scenarios
    or training exercises with known event sequences.
    """
    
    time_mins: float = Field(
        ...,
        ge=0,
        description="Time from simulation start when event occurs (minutes)"
    )
    type: DemandType = Field(
        ...,
        description="Type of demand event"
    )
    location: str = Field(
        ...,
        description="Node ID where demand occurs"
    )
    quantity: int = Field(
        1,
        ge=1,
        description="Number of items (casualties, rounds, vehicles)"
    )
    priority: CasualtyPriority = Field(
        CasualtyPriority.P2_URGENT,
        description="Priority category (primarily for casualties)"
    )
    
    # ===== Type-specific properties =====
    # For casualties
    injury_description: Optional[str] = Field(
        None,
        description="Brief injury description for casualties"
    )
    
    # For ammo requests
    ammo_type: Optional[str] = Field(
        None,
        description="Type of ammunition requested"
    )
    
    # For vehicle breakdowns
    broken_vehicle_id: Optional[str] = Field(
        None,
        description="ID of vehicle that has broken down"
    )
    breakdown_severity: Optional[str] = Field(
        None,
        description="Severity: 'minor', 'major', 'catastrophic'"
    )


class RateBasedDemand(BaseModel):
    """Stochastic demand generation parameters.
    
    Used in RATE_BASED demand mode to generate events
    according to statistical distributions (Poisson process).
    """
    
    type: DemandType = Field(
        ...,
        description="Type of demand to generate"
    )
    location: str = Field(
        ...,
        description="Node ID where demand occurs"
    )
    rate_per_hour: float = Field(
        ...,
        gt=0,
        description="Average events per hour (lambda for Poisson)"
    )
    
    # ===== Priority Distribution =====
    priority_weights: dict[str, float] = Field(
        default={
            "P1": 0.1,
            "P2": 0.3,
            "P3": 0.6,
        },
        description="Probability weights for each priority level"
    )
    
    # ===== Time Window =====
    active_from_mins: float = Field(
        0,
        ge=0,
        description="Simulation time when this demand source activates"
    )
    active_until_mins: Optional[float] = Field(
        None,
        ge=0,
        description="Simulation time when this demand source deactivates (None=end)"
    )
    
    # ===== Quantity Distribution =====
    min_quantity: int = Field(
        1,
        ge=1,
        description="Minimum quantity per event"
    )
    max_quantity: int = Field(
        1,
        ge=1,
        description="Maximum quantity per event"
    )
    
    @model_validator(mode="after")
    def validate_quantity_range(self) -> "RateBasedDemand":
        """Ensure min <= max for quantity."""
        if self.min_quantity > self.max_quantity:
            raise ValueError(
                f"min_quantity ({self.min_quantity}) cannot exceed "
                f"max_quantity ({self.max_quantity})"
            )
        return self
    
    @model_validator(mode="after")
    def validate_time_window(self) -> "RateBasedDemand":
        """Ensure time window is valid."""
        if (
            self.active_until_mins is not None
            and self.active_from_mins >= self.active_until_mins
        ):
            raise ValueError(
                f"active_from_mins ({self.active_from_mins}) must be less than "
                f"active_until_mins ({self.active_until_mins})"
            )
        return self
    
    @model_validator(mode="after")
    def validate_priority_weights(self) -> "RateBasedDemand":
        """Ensure priority weights are valid probabilities."""
        total = sum(self.priority_weights.values())
        if abs(total - 1.0) > 0.01:  # Allow small floating point tolerance
            raise ValueError(
                f"Priority weights must sum to 1.0, got {total}"
            )
        return self


class PhaseDrivenDemand(BaseModel):
    """Demand linked to operational phases (future implementation).
    
    Allows demand rates to change based on the operational
    phase (e.g., higher casualty rates during assault phase).
    """
    
    phase_name: str = Field(
        ...,
        description="Name of operational phase"
    )
    start_time_mins: float = Field(
        ...,
        ge=0,
        description="When this phase begins"
    )
    end_time_mins: Optional[float] = Field(
        None,
        ge=0,
        description="When this phase ends (None=until next phase)"
    )
    demand_multiplier: float = Field(
        1.0,
        gt=0,
        description="Multiplier applied to base demand rates during this phase"
    )
    
    # Phase-specific rate overrides
    casualty_rate_override: Optional[float] = Field(
        None,
        ge=0,
        description="Override casualty rate for this phase"
    )
    breakdown_rate_override: Optional[float] = Field(
        None,
        ge=0,
        description="Override breakdown rate for this phase"
    )


class DemandConfiguration(BaseModel):
    """Complete demand generation configuration.
    
    Supports multiple modes:
    - MANUAL: Explicit event list
    - RATE_BASED: Stochastic generation from rates
    - PHASE_DRIVEN: Rates vary by operational phase (future)
    """
    
    mode: DemandMode = Field(
        DemandMode.MANUAL,
        description="How demand events are generated"
    )
    
    # ===== Manual Mode =====
    manual_events: list[ManualDemandEvent] = Field(
        default_factory=list,
        description="Explicit list of demand events (for MANUAL mode)"
    )
    
    # ===== Rate-Based Mode =====
    rate_based: list[RateBasedDemand] = Field(
        default_factory=list,
        description="Stochastic demand sources (for RATE_BASED mode)"
    )
    
    # ===== Phase-Driven Mode (Future) =====
    phases: list[PhaseDrivenDemand] = Field(
        default_factory=list,
        description="Operational phases with demand modifiers"
    )
    
    @model_validator(mode="after")
    def validate_mode_has_data(self) -> "DemandConfiguration":
        """Ensure the selected mode has corresponding data."""
        if self.mode == DemandMode.MANUAL:
            if not self.manual_events:
                raise ValueError(
                    "MANUAL mode requires at least one event in manual_events"
                )
        elif self.mode == DemandMode.RATE_BASED:
            if not self.rate_based:
                raise ValueError(
                    "RATE_BASED mode requires at least one config in rate_based"
                )
        elif self.mode == DemandMode.PHASE_DRIVEN:
            if not self.phases:
                raise ValueError(
                    "PHASE_DRIVEN mode requires at least one phase definition"
                )
        return self
    
    def get_manual_events_sorted(self) -> list[ManualDemandEvent]:
        """Get manual events sorted by time."""
        return sorted(self.manual_events, key=lambda e: e.time_mins)
