"""Simulation event logging and tracking.

All simulation events are recorded to an EventLog, which can be
queried for KPI calculation and exported for analysis.
"""

from dataclasses import dataclass, field
from typing import Any, Optional

from pj_ogun.models.enums import EventType, Priority


@dataclass
class SimEvent:
    """A single simulation event.
    
    Events are the atomic units of simulation output. Each event
    records what happened, when, where, and to whom.
    """
    
    time_mins: float
    """Simulation time when event occurred (minutes from start)"""
    
    event_type: EventType
    """Category of event"""
    
    entity_id: str
    """ID of primary entity involved (vehicle, casualty, etc.)"""
    
    location: Optional[str] = None
    """Node ID where event occurred (if applicable)"""
    
    details: dict[str, Any] = field(default_factory=dict)
    """Additional event-specific data"""
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialisation."""
        return {
            "time_mins": self.time_mins,
            "event_type": self.event_type.value,
            "entity_id": self.entity_id,
            "location": self.location,
            **self.details,
        }


@dataclass
class Casualty:
    """Tracks a casualty through the evacuation chain.

    Created when a casualty event occurs, updated as they move
    through the system, closed when treatment completes.
    """

    id: str
    """Unique casualty identifier"""

    priority: Priority
    """Triage priority"""

    origin_node: str
    """Node where casualty occurred"""

    time_generated: float
    """When casualty was generated (sim minutes)"""

    mechanism: str = "Unknown"
    """Injury mechanism"""

    # Timestamps for KPI calculation
    time_collected: Optional[float] = None
    """When ambulance collected casualty"""

    time_delivered: Optional[float] = None
    """When casualty arrived at treatment facility"""

    time_treatment_started: Optional[float] = None
    """When treatment began"""

    time_treatment_completed: Optional[float] = None
    """When treatment finished"""

    # Tracking
    collected_by: Optional[str] = None
    """Vehicle ID that collected"""

    delivered_to: Optional[str] = None
    """Node ID where delivered"""

    @property
    def wait_time_mins(self) -> Optional[float]:
        """Time from generation to collection."""
        if self.time_collected is not None:
            return self.time_collected - self.time_generated
        return None

    @property
    def evacuation_time_mins(self) -> Optional[float]:
        """Time from generation to delivery at facility."""
        if self.time_delivered is not None:
            return self.time_delivered - self.time_generated
        return None

    @property
    def total_time_mins(self) -> Optional[float]:
        """Time from generation to treatment complete."""
        if self.time_treatment_completed is not None:
            return self.time_treatment_completed - self.time_generated
        return None


@dataclass
class Breakdown:
    """Tracks a vehicle breakdown through recovery and repair.

    Created when a breakdown occurs, updated through recovery
    and repair processes, closed when vehicle returns to service.
    """

    id: str
    """Unique breakdown identifier"""

    vehicle_id: str
    """ID of broken down vehicle"""

    vehicle_class: str
    """Vehicle class (light/medium/heavy) for recovery matching"""

    location: str
    """Node where breakdown occurred"""

    time_occurred: float
    """When breakdown happened (sim minutes)"""

    priority: Priority = Priority.PRIORITY
    """Recovery priority"""

    # Timestamps
    time_recovery_dispatched: Optional[float] = None
    """When recovery vehicle was dispatched"""

    time_recovery_arrived: Optional[float] = None
    """When recovery vehicle arrived at scene"""

    time_hookup_completed: Optional[float] = None
    """When vehicle was hooked up for towing"""

    time_arrived_workshop: Optional[float] = None
    """When vehicle arrived at repair workshop"""

    time_repair_started: Optional[float] = None
    """When repair began"""

    time_repair_completed: Optional[float] = None
    """When repair finished and vehicle returned to service"""

    # Tracking
    recovered_by: Optional[str] = None
    """Recovery vehicle ID"""

    repaired_at: Optional[str] = None
    """Workshop node ID"""

    @property
    def response_time_mins(self) -> Optional[float]:
        """Time from breakdown to recovery arrival."""
        if self.time_recovery_arrived is not None:
            return self.time_recovery_arrived - self.time_occurred
        return None

    @property
    def recovery_time_mins(self) -> Optional[float]:
        """Time from breakdown to arrival at workshop."""
        if self.time_arrived_workshop is not None:
            return self.time_arrived_workshop - self.time_occurred
        return None

    @property
    def repair_time_mins(self) -> Optional[float]:
        """Time spent in repair."""
        if self.time_repair_completed is not None and self.time_repair_started is not None:
            return self.time_repair_completed - self.time_repair_started
        return None

    @property
    def total_downtime_mins(self) -> Optional[float]:
        """Total time from breakdown to return to service."""
        if self.time_repair_completed is not None:
            return self.time_repair_completed - self.time_occurred
        return None


@dataclass
class AmmoRequest:
    """Tracks an ammunition resupply request through fulfillment.

    Created when ammo is requested, updated through delivery,
    closed when ammunition is delivered.
    """

    id: str
    """Unique request identifier"""

    location: str
    """Node requesting ammunition"""

    quantity_requested: int
    """Units of ammunition requested"""

    time_requested: float
    """When request was made (sim minutes)"""

    priority: Priority = Priority.PRIORITY
    """Delivery priority"""

    # Fulfillment tracking
    quantity_delivered: int = 0
    """Units actually delivered"""

    # Timestamps
    time_dispatched: Optional[float] = None
    """When logistics vehicle was dispatched"""

    time_loaded: Optional[float] = None
    """When ammunition was loaded at supply point"""

    time_delivered: Optional[float] = None
    """When ammunition was delivered"""

    # Tracking
    fulfilled_by: Optional[str] = None
    """Logistics vehicle ID"""

    loaded_from: Optional[str] = None
    """Ammo point node ID"""

    @property
    def wait_time_mins(self) -> Optional[float]:
        """Time from request to dispatch."""
        if self.time_dispatched is not None:
            return self.time_dispatched - self.time_requested
        return None

    @property
    def delivery_time_mins(self) -> Optional[float]:
        """Time from request to delivery."""
        if self.time_delivered is not None:
            return self.time_delivered - self.time_requested
        return None

    @property
    def is_fulfilled(self) -> bool:
        """Whether request was fully satisfied."""
        return self.quantity_delivered >= self.quantity_requested


class EventLog:
    """Collects and manages simulation events.

    The EventLog is the primary output of a simulation run.
    It can be queried for specific event types, filtered by
    time range, and exported for analysis.
    """

    def __init__(self):
        self._events: list[SimEvent] = []
        self._casualties: dict[str, Casualty] = {}
        self._casualty_counter: int = 0
        self._breakdowns: dict[str, Breakdown] = {}
        self._breakdown_counter: int = 0
        self._ammo_requests: dict[str, AmmoRequest] = {}
        self._ammo_request_counter: int = 0

    def log(self, event: SimEvent) -> None:
        """Record an event."""
        self._events.append(event)

    def log_event(
        self,
        time_mins: float,
        event_type: EventType,
        entity_id: str,
        location: Optional[str] = None,
        **details: Any,
    ) -> SimEvent:
        """Convenience method to create and log an event."""
        event = SimEvent(
            time_mins=time_mins,
            event_type=event_type,
            entity_id=entity_id,
            location=location,
            details=details,
        )
        self.log(event)
        return event

    # === Casualty Tracking ===

    def create_casualty(
        self,
        priority: Priority,
        origin_node: str,
        time_generated: float,
        mechanism: str = "Unknown",
    ) -> Casualty:
        """Create and register a new casualty."""
        self._casualty_counter += 1
        cas_id = f"CAS_{self._casualty_counter:04d}"

        casualty = Casualty(
            id=cas_id,
            priority=priority,
            origin_node=origin_node,
            time_generated=time_generated,
            mechanism=mechanism,
        )
        self._casualties[cas_id] = casualty
        return casualty

    def get_casualty(self, cas_id: str) -> Optional[Casualty]:
        """Retrieve casualty by ID."""
        return self._casualties.get(cas_id)

    @property
    def casualties(self) -> list[Casualty]:
        """All registered casualties."""
        return list(self._casualties.values())

    # === Breakdown Tracking ===

    def create_breakdown(
        self,
        vehicle_id: str,
        vehicle_class: str,
        location: str,
        time_occurred: float,
        priority: Priority = Priority.PRIORITY,
    ) -> Breakdown:
        """Create and register a new breakdown."""
        self._breakdown_counter += 1
        bd_id = f"BD_{self._breakdown_counter:04d}"

        breakdown = Breakdown(
            id=bd_id,
            vehicle_id=vehicle_id,
            vehicle_class=vehicle_class,
            location=location,
            time_occurred=time_occurred,
            priority=priority,
        )
        self._breakdowns[bd_id] = breakdown
        return breakdown

    def get_breakdown(self, bd_id: str) -> Optional[Breakdown]:
        """Retrieve breakdown by ID."""
        return self._breakdowns.get(bd_id)

    @property
    def breakdowns(self) -> list[Breakdown]:
        """All registered breakdowns."""
        return list(self._breakdowns.values())

    # === Ammo Request Tracking ===

    def create_ammo_request(
        self,
        location: str,
        quantity_requested: int,
        time_requested: float,
        priority: Priority = Priority.PRIORITY,
    ) -> AmmoRequest:
        """Create and register a new ammo request."""
        self._ammo_request_counter += 1
        req_id = f"AMMO_{self._ammo_request_counter:04d}"

        request = AmmoRequest(
            id=req_id,
            location=location,
            quantity_requested=quantity_requested,
            time_requested=time_requested,
            priority=priority,
        )
        self._ammo_requests[req_id] = request
        return request

    def get_ammo_request(self, req_id: str) -> Optional[AmmoRequest]:
        """Retrieve ammo request by ID."""
        return self._ammo_requests.get(req_id)

    @property
    def ammo_requests(self) -> list[AmmoRequest]:
        """All registered ammo requests."""
        return list(self._ammo_requests.values())
    
    # === Event Queries ===
    
    @property
    def events(self) -> list[SimEvent]:
        """All events in chronological order."""
        return sorted(self._events, key=lambda e: e.time_mins)
    
    def filter_by_type(self, event_type: EventType) -> list[SimEvent]:
        """Get events of a specific type."""
        return [e for e in self._events if e.event_type == event_type]
    
    def filter_by_entity(self, entity_id: str) -> list[SimEvent]:
        """Get events for a specific entity."""
        return [e for e in self._events if e.entity_id == entity_id]
    
    def filter_by_location(self, location: str) -> list[SimEvent]:
        """Get events at a specific location."""
        return [e for e in self._events if e.location == location]
    
    def filter_by_time(
        self, 
        start_mins: float = 0, 
        end_mins: Optional[float] = None,
    ) -> list[SimEvent]:
        """Get events within a time range."""
        events = [e for e in self._events if e.time_mins >= start_mins]
        if end_mins is not None:
            events = [e for e in events if e.time_mins <= end_mins]
        return events
    
    # === Export ===
    
    def to_list(self) -> list[dict[str, Any]]:
        """Export all events as list of dicts."""
        return [e.to_dict() for e in self.events]
    
    def to_dataframe(self):
        """Export events to pandas DataFrame."""
        import pandas as pd
        return pd.DataFrame(self.to_list())
    
    def casualties_to_dataframe(self):
        """Export casualty tracking to DataFrame."""
        import pandas as pd

        records = []
        for cas in self._casualties.values():
            records.append({
                "id": cas.id,
                "priority": cas.priority.value,
                "origin_node": cas.origin_node,
                "mechanism": cas.mechanism,
                "time_generated": cas.time_generated,
                "time_collected": cas.time_collected,
                "time_delivered": cas.time_delivered,
                "time_treatment_started": cas.time_treatment_started,
                "time_treatment_completed": cas.time_treatment_completed,
                "collected_by": cas.collected_by,
                "delivered_to": cas.delivered_to,
                "wait_time_mins": cas.wait_time_mins,
                "evacuation_time_mins": cas.evacuation_time_mins,
                "total_time_mins": cas.total_time_mins,
            })

        return pd.DataFrame(records)

    def breakdowns_to_dataframe(self):
        """Export breakdown tracking to DataFrame."""
        import pandas as pd

        records = []
        for bd in self._breakdowns.values():
            records.append({
                "id": bd.id,
                "vehicle_id": bd.vehicle_id,
                "vehicle_class": bd.vehicle_class,
                "location": bd.location,
                "priority": bd.priority.value,
                "time_occurred": bd.time_occurred,
                "time_recovery_dispatched": bd.time_recovery_dispatched,
                "time_recovery_arrived": bd.time_recovery_arrived,
                "time_hookup_completed": bd.time_hookup_completed,
                "time_arrived_workshop": bd.time_arrived_workshop,
                "time_repair_started": bd.time_repair_started,
                "time_repair_completed": bd.time_repair_completed,
                "recovered_by": bd.recovered_by,
                "repaired_at": bd.repaired_at,
                "response_time_mins": bd.response_time_mins,
                "recovery_time_mins": bd.recovery_time_mins,
                "repair_time_mins": bd.repair_time_mins,
                "total_downtime_mins": bd.total_downtime_mins,
            })

        return pd.DataFrame(records)

    def ammo_requests_to_dataframe(self):
        """Export ammo request tracking to DataFrame."""
        import pandas as pd

        records = []
        for req in self._ammo_requests.values():
            records.append({
                "id": req.id,
                "location": req.location,
                "quantity_requested": req.quantity_requested,
                "quantity_delivered": req.quantity_delivered,
                "priority": req.priority.value,
                "time_requested": req.time_requested,
                "time_dispatched": req.time_dispatched,
                "time_loaded": req.time_loaded,
                "time_delivered": req.time_delivered,
                "fulfilled_by": req.fulfilled_by,
                "loaded_from": req.loaded_from,
                "wait_time_mins": req.wait_time_mins,
                "delivery_time_mins": req.delivery_time_mins,
                "is_fulfilled": req.is_fulfilled,
            })

        return pd.DataFrame(records)

    def __len__(self) -> int:
        return len(self._events)

    def __repr__(self) -> str:
        return (
            f"EventLog({len(self._events)} events, "
            f"{len(self._casualties)} casualties, "
            f"{len(self._breakdowns)} breakdowns, "
            f"{len(self._ammo_requests)} ammo requests)"
        )
