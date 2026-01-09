"""Demand generation configuration models.

Demand represents events that require logistics response:
- Casualties needing evacuation
- Ammunition requests
- Vehicle breakdowns
- Scheduled resupply

Demand can be specified manually (explicit event list) or
generated stochastically from rates (Poisson process).
"""

from typing import Optional

from pydantic import BaseModel, Field, model_validator

from pj_ogun.models.enums import DemandMode, DemandType, Priority


class ManualDemandEvent(BaseModel):
    """A specific demand event at a known time.
    
    Used when demand mode is MANUAL - user specifies exactly
    when and where events occur.
    """
    
    time_mins: float = Field(
        ..., 
        ge=0,
        description="Time from simulation start (minutes)"
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
        description="Number of items (casualties, units, vehicles)"
    )
    priority: Priority = Field(
        Priority.PRIORITY,
        description="Urgency level (affects dispatch order)"
    )
    properties: dict = Field(
        default_factory=dict,
        description="Additional event-specific properties"
    )
    
    model_config = {"extra": "forbid"}


class RateBasedDemand(BaseModel):
    """Stochastic demand generation parameters.
    
    Used when demand mode is RATE_BASED - events generated
    via Poisson process with specified arrival rate.
    """
    
    type: DemandType = Field(
        ...,
        description="Type of demand events to generate"
    )
    location: str = Field(
        ...,
        description="Node ID where events occur"
    )
    rate_per_hour: float = Field(
        ..., 
        gt=0,
        description="Mean arrival rate (events per hour)"
    )
    priority_weights: dict[int, float] = Field(
        default={1: 0.1, 2: 0.3, 3: 0.6},
        description="Probability weights for priority levels {1: P(urgent), 2: P(priority), 3: P(routine)}"
    )
    
    # Time window for generation
    active_from_mins: float = Field(
        0, 
        ge=0,
        description="Start generating events after this time (minutes)"
    )
    active_until_mins: Optional[float] = Field(
        None, 
        ge=0,
        description="Stop generating events after this time (None=until sim end)"
    )
    
    # Optional quantity distribution
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
    def validate_time_window(self) -> "RateBasedDemand":
        """Ensure active window is valid."""
        if self.active_until_mins is not None:
            if self.active_until_mins <= self.active_from_mins:
                raise ValueError(
                    f"active_until_mins ({self.active_until_mins}) must be > "
                    f"active_from_mins ({self.active_from_mins})"
                )
        return self
    
    @model_validator(mode="after")
    def validate_quantity_range(self) -> "RateBasedDemand":
        """Ensure quantity range is valid."""
        if self.max_quantity < self.min_quantity:
            raise ValueError(
                f"max_quantity ({self.max_quantity}) must be >= "
                f"min_quantity ({self.min_quantity})"
            )
        return self
    
    @model_validator(mode="after")
    def validate_priority_weights(self) -> "RateBasedDemand":
        """Ensure priority weights sum to ~1 and use valid priorities."""
        if not self.priority_weights:
            raise ValueError("priority_weights cannot be empty")
        
        valid_priorities = {1, 2, 3, 4}
        for p in self.priority_weights:
            if p not in valid_priorities:
                raise ValueError(f"Invalid priority {p}. Must be in {valid_priorities}")
        
        total = sum(self.priority_weights.values())
        if not (0.99 <= total <= 1.01):
            raise ValueError(
                f"priority_weights must sum to 1.0, got {total:.3f}"
            )
        return self
    
    model_config = {"extra": "forbid"}


class DemandConfiguration(BaseModel):
    """Complete demand specification for a scenario.
    
    Demand can be specified in different modes:
    - MANUAL: Explicit event list with exact times
    - RATE_BASED: Stochastic generation from arrival rates
    - PHASE_DRIVEN: Rates linked to operational phases (future)
    
    The mode determines which fields are used. Validation ensures
    the appropriate fields are populated for the selected mode.
    """
    
    mode: DemandMode = Field(
        DemandMode.MANUAL,
        description="How demand is generated"
    )
    
    # Manual mode events
    manual_events: list[ManualDemandEvent] = Field(
        default_factory=list,
        description="Explicit event list (used when mode=MANUAL)"
    )
    
    # Rate-based mode config
    rate_based: list[RateBasedDemand] = Field(
        default_factory=list,
        description="Arrival rate definitions (used when mode=RATE_BASED)"
    )
    
    @model_validator(mode="after")
    def validate_mode_has_data(self) -> "DemandConfiguration":
        """Ensure selected mode has corresponding data."""
        if self.mode == DemandMode.MANUAL:
            if not self.manual_events:
                raise ValueError(
                    "Manual demand mode requires at least one event in manual_events"
                )
        elif self.mode == DemandMode.RATE_BASED:
            if not self.rate_based:
                raise ValueError(
                    "Rate-based demand mode requires at least one config in rate_based"
                )
        elif self.mode == DemandMode.PHASE_DRIVEN:
            # Future: validate phase configuration
            raise ValueError("Phase-driven demand mode not yet implemented")
        
        return self
    
    def get_all_locations(self) -> set[str]:
        """Get all node IDs referenced by demand configuration."""
        locations = set()
        for event in self.manual_events:
            locations.add(event.location)
        for rate in self.rate_based:
            locations.add(rate.location)
        return locations
    
    model_config = {"extra": "forbid"}


# === Convenience Functions ===

def create_casualty_demand_manual(
    events: list[tuple[float, str, int]]
) -> DemandConfiguration:
    """Create manual casualty demand from simple event list.
    
    Args:
        events: List of (time_mins, node_id, priority) tuples
        
    Returns:
        DemandConfiguration with manual mode
        
    Example:
        demand = create_casualty_demand_manual([
            (30, "combat_a", 2),   # Priority casualty at T+30
            (60, "combat_a", 1),   # Urgent casualty at T+60
            (90, "combat_b", 3),   # Routine at T+90
        ])
    """
    manual_events = [
        ManualDemandEvent(
            time_mins=time,
            type=DemandType.CASUALTY,
            location=node,
            priority=Priority(priority),
        )
        for time, node, priority in events
    ]
    return DemandConfiguration(
        mode=DemandMode.MANUAL,
        manual_events=manual_events,
    )


def create_casualty_demand_rate(
    node_rates: dict[str, float],
    priority_dist: dict[int, float] | None = None,
) -> DemandConfiguration:
    """Create rate-based casualty demand from node -> rate mapping.
    
    Args:
        node_rates: Dict of {node_id: casualties_per_hour}
        priority_dist: Optional priority distribution (default: 10% P1, 30% P2, 60% P3)
        
    Returns:
        DemandConfiguration with rate_based mode
        
    Example:
        demand = create_casualty_demand_rate({
            "combat_a": 2.0,  # 2 casualties/hour
            "combat_b": 1.0,  # 1 casualty/hour
        })
    """
    if priority_dist is None:
        priority_dist = {1: 0.1, 2: 0.3, 3: 0.6}
    
    rate_configs = [
        RateBasedDemand(
            type=DemandType.CASUALTY,
            location=node,
            rate_per_hour=rate,
            priority_weights=priority_dist,
        )
        for node, rate in node_rates.items()
    ]
    return DemandConfiguration(
        mode=DemandMode.RATE_BASED,
        rate_based=rate_configs,
    )
