"""Enumeration types for Pj-OGUN schema"""

from enum import Enum


class NodeType(str, Enum):
    """Functional categories for network nodes"""
    
    COMBAT = "combat"
    """Front-line position generating casualties and consuming supplies"""
    
    MEDICAL_ROLE1 = "medical_role1"
    """Unit-level field medical facility (Role 1)"""
    
    MEDICAL_ROLE2 = "medical_role2"
    """Enhanced medical facility with surgical capability (Role 2)"""
    
    REPAIR_WORKSHOP = "repair_workshop"
    """REME workshop for vehicle repair"""
    
    AMMO_POINT = "ammo_point"
    """Ammunition supply point"""
    
    FUEL_POINT = "fuel_point"
    """Fuel distribution point"""
    
    EXCHANGE_POINT = "exchange_point"
    """Generic transfer/handover location (e.g., Ambulance Exchange Point)"""
    
    HQ = "hq"
    """Headquarters/command node"""
    
    FORWARD_ARMING = "forward_arming"
    """Forward Arming and Refuelling Point (FARP)"""


class VehicleClass(str, Enum):
    """Weight/size classification affecting route access and recovery requirements"""
    
    LIGHT = "light"
    """Land Rover class - can use all routes"""
    
    MEDIUM = "medium"
    """MAN SV class - restricted on some routes"""
    
    HEAVY = "heavy"
    """Challenger/AS90 class - limited route access, requires heavy recovery"""


class VehicleRole(str, Enum):
    """Functional role determining vehicle behaviour in simulation"""
    
    AMBULANCE = "ambulance"
    """Casualty evacuation - responds to casualty events"""
    
    RECOVERY = "recovery"
    """Vehicle recovery - responds to breakdown events"""
    
    AMMO_LOGISTICS = "ammo_logistics"
    """Ammunition resupply - responds to ammo requests"""
    
    FUEL_LOGISTICS = "fuel_logistics"
    """Fuel resupply - responds to fuel requests"""
    
    GENERAL_LOGISTICS = "general_logistics"
    """General cargo - scheduled resupply runs"""


class VehicleState(str, Enum):
    """Current operational state of a vehicle"""
    
    IDLE = "idle"
    """Available at base location, awaiting tasking"""
    
    TRANSITING_UNLADEN = "transiting_unladen"
    """Moving without load (faster speed)"""
    
    TRANSITING_LADEN = "transiting_laden"
    """Moving with load (reduced speed)"""
    
    LOADING = "loading"
    """At pickup location, loading casualties/cargo"""
    
    UNLOADING = "unloading"
    """At delivery location, unloading"""
    
    HOOKUP = "hookup"
    """Recovery vehicle preparing disabled vehicle for tow"""
    
    UNDER_REPAIR = "under_repair"
    """Vehicle being repaired at workshop"""
    
    BROKEN_DOWN = "broken_down"
    """Vehicle disabled, awaiting recovery"""
    
    CREW_REST = "crew_rest"
    """Vehicle unavailable due to mandatory crew rest"""
    
    MAINTENANCE = "maintenance"
    """Scheduled maintenance window"""


class DemandType(str, Enum):
    """Types of demand events the simulation can generate"""
    
    CASUALTY = "casualty"
    """Personnel casualty requiring MEDEVAC"""
    
    AMMO_REQUEST = "ammo_request"
    """Ammunition resupply request"""
    
    FUEL_REQUEST = "fuel_request"
    """Fuel resupply request"""
    
    VEHICLE_BREAKDOWN = "vehicle_breakdown"
    """Vehicle has become non-operational"""
    
    SCHEDULED_RESUPPLY = "scheduled_resupply"
    """Pre-planned logistics push"""


class DemandMode(str, Enum):
    """How demand is generated in the simulation"""
    
    MANUAL = "manual"
    """User-specified event list with exact times"""
    
    RATE_BASED = "rate_based"
    """Stochastic generation from arrival rates (Poisson process)"""
    
    PHASE_DRIVEN = "phase_driven"
    """Demand rates linked to operational phases (future)"""


class Priority(int, Enum):
    """Casualty/task priority levels (NATO standard)"""
    
    URGENT = 1
    """P1 - Immediate, life-threatening"""
    
    PRIORITY = 2  
    """P2 - Surgery within 4 hours"""
    
    ROUTINE = 3
    """P3 - Can wait, walking wounded"""
    
    CONVENIENCE = 4
    """P4 - Non-urgent, administrative move"""


class EventType(str, Enum):
    """Types of events recorded in simulation log"""
    
    # Demand events
    CASUALTY_GENERATED = "casualty_generated"
    AMMO_REQUEST_GENERATED = "ammo_request_generated"
    BREAKDOWN_OCCURRED = "breakdown_occurred"
    
    # Vehicle lifecycle
    VEHICLE_DISPATCHED = "vehicle_dispatched"
    VEHICLE_ARRIVED = "vehicle_arrived"
    VEHICLE_DEPARTED = "vehicle_departed"
    VEHICLE_RETURNED = "vehicle_returned"
    
    # Service events
    LOADING_STARTED = "loading_started"
    LOADING_COMPLETED = "loading_completed"
    UNLOADING_STARTED = "unloading_started"
    UNLOADING_COMPLETED = "unloading_completed"
    
    # Medical specific
    CASUALTY_COLLECTED = "casualty_collected"
    CASUALTY_DELIVERED = "casualty_delivered"
    TREATMENT_STARTED = "treatment_started"
    TREATMENT_COMPLETED = "treatment_completed"
    
    # Recovery specific
    HOOKUP_STARTED = "hookup_started"
    HOOKUP_COMPLETED = "hookup_completed"
    REPAIR_STARTED = "repair_started"
    REPAIR_COMPLETED = "repair_completed"
    
    # Logistics specific
    AMMO_LOADED = "ammo_loaded"
    AMMO_DELIVERED = "ammo_delivered"
    STOCKOUT = "stockout"
    
    # System events
    SIMULATION_STARTED = "simulation_started"
    SIMULATION_ENDED = "simulation_ended"
    SHIFT_CHANGE = "shift_change"
    CREW_REST_STARTED = "crew_rest_started"
    CREW_REST_ENDED = "crew_rest_ended"
