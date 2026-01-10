"""Pydantic schema models for Pj-OGUN scenarios"""

from pj_ogun.models.enums import (
    DemandMode,
    DemandType,
    EventType,
    NodeType,
    Priority,
    VehicleClass,
    VehicleRole,
    VehicleState,
)
from pj_ogun.models.network import Coordinates, Edge, EdgeProperties, Node, NodeCapacity, NodeProperties
from pj_ogun.models.vehicles import ServiceTimes, SpeedProfile, Vehicle, VehicleType
from pj_ogun.models.demand import DemandConfiguration, ManualDemandEvent, RateBasedDemand
from pj_ogun.models.scenario import Scenario, SimulationConfig

__all__ = [
    # Enums
    "DemandMode",
    "DemandType",
    "EventType",
    "NodeType",
    "Priority",
    "VehicleClass",
    "VehicleRole",
    "VehicleState",
    # Network
    "Coordinates",
    "Edge",
    "EdgeProperties",
    "Node",
    "NodeCapacity",
    "NodeProperties",
    # Vehicles
    "ServiceTimes",
    "SpeedProfile",
    "Vehicle",
    "VehicleType",
    # Demand
    "DemandConfiguration",
    "ManualDemandEvent",
    "RateBasedDemand",
    # Scenario
    "Scenario",
    "SimulationConfig",
]
