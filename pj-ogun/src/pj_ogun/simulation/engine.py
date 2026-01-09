"""SimPy-based discrete-event simulation engine.

This module contains the main SimulationEngine class that:
1. Builds the network graph from scenario nodes/edges
2. Initialises SimPy environment and resources
3. Spawns vehicle processes and demand generators
4. Runs the simulation and collects events
"""

import heapq
import random
from dataclasses import dataclass, field
from typing import Any, Generator, Optional

import networkx as nx
import simpy

from pj_ogun.models import (
    DemandMode,
    DemandType,
    Node,
    NodeType,
    Priority,
    Scenario,
    Vehicle,
    VehicleRole,
    VehicleState,
    VehicleType,
)
from pj_ogun.models.enums import EventType
from pj_ogun.simulation.events import AmmoRequest, Breakdown, Casualty, EventLog


@dataclass
class VehicleRuntime:
    """Runtime state for a vehicle during simulation."""

    vehicle: Vehicle
    vehicle_type: VehicleType

    # Current state
    state: VehicleState = VehicleState.IDLE
    current_location: str = ""
    current_load: float = 0.0

    # Cargo tracking
    casualties_aboard: list[Casualty] = field(default_factory=list)

    # Statistics
    total_distance_km: float = 0.0
    total_time_busy_mins: float = 0.0
    missions_completed: int = 0

    # Extended operations tracking
    continuous_ops_start: float = 0.0  # When current continuous ops period started
    total_ops_time_mins: float = 0.0  # Total time spent in operations
    next_maintenance_time: float = 0.0  # When next scheduled maintenance
    time_since_last_breakdown: float = 0.0  # For MTBF tracking

    def __post_init__(self):
        self.current_location = self.vehicle.start_location
        self.current_load = self.vehicle.initial_load_fraction
        self.state = self.vehicle.initial_state


@dataclass(order=True)
class CasualtyRequest:
    """A request for casualty evacuation, ordered by priority."""

    priority: int
    time_requested: float = field(compare=False)
    casualty: Casualty = field(compare=False)
    location: str = field(compare=False)


@dataclass(order=True)
class RecoveryRequest:
    """A request for vehicle recovery, ordered by priority."""

    priority: int
    time_requested: float = field(compare=False)
    breakdown: Breakdown = field(compare=False)
    location: str = field(compare=False)
    vehicle_class: str = field(compare=False)


@dataclass(order=True)
class AmmoDeliveryRequest:
    """A request for ammunition delivery, ordered by priority."""

    priority: int
    time_requested: float = field(compare=False)
    ammo_request: AmmoRequest = field(compare=False)
    location: str = field(compare=False)
    quantity: int = field(compare=False)


class SimulationEngine:
    """Main simulation engine orchestrating all processes.
    
    Usage:
        scenario = load_scenario("my_scenario.json")
        engine = SimulationEngine(scenario)
        event_log = engine.run()
    """
    
    def __init__(self, scenario: Scenario):
        self.scenario = scenario
        self.event_log = EventLog()
        
        # SimPy environment
        self.env: simpy.Environment = None
        
        # Network graph
        self.graph: nx.Graph = None
        
        # Resources (SimPy)
        self.node_resources: dict[str, simpy.Resource] = {}
        
        # Vehicle runtime states
        self.vehicles: dict[str, VehicleRuntime] = {}
        
        # Request queues (priority heaps)
        self.casualty_queue: list[CasualtyRequest] = []
        self.recovery_queue: list[RecoveryRequest] = []
        self.ammo_queue: list[AmmoDeliveryRequest] = []

        # Vehicle availability tracking by role
        self.idle_ambulances: list[str] = []
        self.idle_recovery: dict[str, list[str]] = {  # by vehicle class capability
            "light": [],
            "medium": [],
            "heavy": [],
        }
        self.idle_logistics: list[str] = []

        # Random state
        self._rng: random.Random = None
    
    def run(self) -> EventLog:
        """Execute the simulation and return event log."""
        # Initialise
        self._setup()
        
        # Log start
        self.event_log.log_event(
            time_mins=0,
            event_type=EventType.SIMULATION_STARTED,
            entity_id="SYSTEM",
            duration_hours=self.scenario.config.duration_hours,
            seed=self.scenario.config.random_seed,
        )
        
        # Run until duration
        duration_mins = self.scenario.config.duration_hours * 60
        self.env.run(until=duration_mins)
        
        # Log end
        self.event_log.log_event(
            time_mins=self.env.now,
            event_type=EventType.SIMULATION_ENDED,
            entity_id="SYSTEM",
            total_events=len(self.event_log),
            total_casualties=len(self.event_log.casualties),
        )
        
        return self.event_log
    
    def _setup(self) -> None:
        """Initialise all simulation components."""
        # Seed RNG
        self._rng = random.Random(self.scenario.config.random_seed)

        # Create SimPy environment
        self.env = simpy.Environment()

        # Build network graph
        self._build_graph()

        # Create node resources
        self._create_resources()

        # Initialise vehicles
        self._init_vehicles()

        # Start demand generators
        self._start_demand_generators()

        # Start vehicle processes
        self._start_vehicle_processes()

        # Start extended operations processes (Phase 4)
        self._start_extended_operations()
    
    def _build_graph(self) -> None:
        """Build NetworkX graph from scenario edges."""
        self.graph = nx.Graph()
        
        # Add nodes with attributes
        for node in self.scenario.nodes:
            self.graph.add_node(
                node.id,
                node=node,
                x=node.coordinates.x,
                y=node.coordinates.y,
            )
        
        # Add edges with distance as weight
        for edge in self.scenario.edges:
            # Effective distance includes terrain factor
            effective_dist = edge.distance_km * edge.properties.terrain_factor
            
            self.graph.add_edge(
                edge.from_node,
                edge.to_node,
                distance_km=edge.distance_km,
                effective_km=effective_dist,
                edge=edge,
            )
            
            # If not bidirectional, mark for directed routing
            # (For MVP, we treat all as bidirectional)
    
    def _create_resources(self) -> None:
        """Create SimPy resources for nodes with capacity limits."""
        for node in self.scenario.nodes:
            capacity = None
            
            # Determine capacity based on node type
            if node.type in (NodeType.MEDICAL_ROLE1, NodeType.MEDICAL_ROLE2):
                capacity = node.capacity.treatment_slots
            elif node.type == NodeType.REPAIR_WORKSHOP:
                capacity = node.capacity.repair_bays
            
            if capacity and capacity > 0:
                self.node_resources[node.id] = simpy.Resource(
                    self.env, capacity=capacity
                )
    
    def _init_vehicles(self) -> None:
        """Initialise vehicle runtime states."""
        for vehicle in self.scenario.vehicles:
            vtype = self.scenario.get_vehicle_type_by_id(vehicle.type_id)
            if vtype is None:
                raise ValueError(f"Unknown vehicle type: {vehicle.type_id}")

            runtime = VehicleRuntime(vehicle=vehicle, vehicle_type=vtype)
            self.vehicles[vehicle.id] = runtime

            # Track idle vehicles by role
            if runtime.state == VehicleState.IDLE:
                if vtype.role == VehicleRole.AMBULANCE:
                    self.idle_ambulances.append(vehicle.id)
                elif vtype.role == VehicleRole.RECOVERY:
                    # Add to appropriate class list based on tow capability
                    tow_class = vtype.tow_capacity_class.value if vtype.tow_capacity_class else "light"
                    self.idle_recovery[tow_class].append(vehicle.id)
                elif vtype.role == VehicleRole.AMMO_LOGISTICS:
                    self.idle_logistics.append(vehicle.id)
    
    def _start_demand_generators(self) -> None:
        """Start processes that generate demand events."""
        if self.scenario.demand.mode == DemandMode.MANUAL:
            self.env.process(self._manual_demand_generator())
        elif self.scenario.demand.mode == DemandMode.RATE_BASED:
            for rate_config in self.scenario.demand.rate_based:
                self.env.process(self._rate_based_generator(rate_config))
    
    def _start_vehicle_processes(self) -> None:
        """Start vehicle behaviour processes."""
        for vid, vruntime in self.vehicles.items():
            if vruntime.vehicle_type.role == VehicleRole.AMBULANCE:
                self.env.process(self._ambulance_process(vid))
            elif vruntime.vehicle_type.role == VehicleRole.RECOVERY:
                self.env.process(self._recovery_process(vid))
            elif vruntime.vehicle_type.role == VehicleRole.AMMO_LOGISTICS:
                self.env.process(self._logistics_process(vid))

    def _start_extended_operations(self) -> None:
        """Start extended operations processes (Phase 4 features)."""
        config = self.scenario.config

        # Crew fatigue monitoring
        if config.enable_crew_fatigue:
            for vid in self.vehicles:
                self.env.process(self._crew_fatigue_monitor(vid))

        # Scheduled maintenance
        if config.enable_vehicle_maintenance:
            for vid, vruntime in self.vehicles.items():
                # Schedule first maintenance at random offset
                mtbf = vruntime.vehicle_type.mtbf_hours
                if mtbf:
                    offset = self._rng.uniform(0, mtbf * 60 * 0.5)  # Random offset up to half MTBF
                    vruntime.next_maintenance_time = offset
                    self.env.process(self._maintenance_scheduler(vid))

        # Random breakdowns from MTBF
        if config.enable_breakdowns:
            for vid in self.vehicles:
                self.env.process(self._breakdown_generator(vid))
    
    # === Demand Generators ===
    
    def _manual_demand_generator(self) -> Generator:
        """Generate demand events from manual event list."""
        # Sort events by time
        events = sorted(
            self.scenario.demand.manual_events,
            key=lambda e: e.time_mins
        )

        for event in events:
            # Wait until event time
            if event.time_mins > self.env.now:
                yield self.env.timeout(event.time_mins - self.env.now)

            # Generate based on type
            if event.type == DemandType.CASUALTY:
                for _ in range(event.quantity):
                    self._generate_casualty(
                        location=event.location,
                        priority=event.priority,
                        mechanism=event.properties.get("mechanism", "Unknown"),
                    )
            elif event.type == DemandType.VEHICLE_BREAKDOWN:
                vehicle_id = event.properties.get("vehicle_id")
                if vehicle_id and vehicle_id in self.vehicles:
                    self._generate_breakdown(
                        vehicle_id=vehicle_id,
                        location=event.location,
                        priority=event.priority,
                    )
            elif event.type == DemandType.AMMO_REQUEST:
                self._generate_ammo_request(
                    location=event.location,
                    quantity=event.quantity,
                    priority=event.priority,
                )
    
    def _rate_based_generator(self, config) -> Generator:
        """Generate demand events from Poisson process."""
        # Wait until active period starts
        if config.active_from_mins > 0:
            yield self.env.timeout(config.active_from_mins)
        
        # Calculate mean inter-arrival time
        mean_interval = 60.0 / config.rate_per_hour  # minutes
        
        end_time = config.active_until_mins or (self.scenario.config.duration_hours * 60)
        
        while self.env.now < end_time:
            # Exponential inter-arrival
            interval = self._rng.expovariate(1.0 / mean_interval)
            yield self.env.timeout(interval)
            
            if self.env.now >= end_time:
                break
            
            # Sample priority
            priority = self._sample_priority(config.priority_weights)
            
            # Sample quantity
            qty = self._rng.randint(config.min_quantity, config.max_quantity)
            
            # Generate casualties
            if config.type == DemandType.CASUALTY:
                for _ in range(qty):
                    self._generate_casualty(
                        location=config.location,
                        priority=priority,
                    )
    
    def _sample_priority(self, weights: dict[int, float]) -> Priority:
        """Sample a priority level from weight distribution."""
        priorities = list(weights.keys())
        probs = list(weights.values())
        chosen = self._rng.choices(priorities, weights=probs, k=1)[0]
        return Priority(chosen)
    
    def _generate_casualty(
        self,
        location: str,
        priority: Priority | int,
        mechanism: str = "Unknown",
    ) -> None:
        """Create a casualty and add to evacuation queue."""
        if isinstance(priority, int):
            priority = Priority(priority)
        
        # Create casualty record
        casualty = self.event_log.create_casualty(
            priority=priority,
            origin_node=location,
            time_generated=self.env.now,
            mechanism=mechanism,
        )
        
        # Log event
        self.event_log.log_event(
            time_mins=self.env.now,
            event_type=EventType.CASUALTY_GENERATED,
            entity_id=casualty.id,
            location=location,
            priority=priority.value,
            mechanism=mechanism,
        )
        
        # Add to queue
        request = CasualtyRequest(
            priority=priority.value,
            time_requested=self.env.now,
            casualty=casualty,
            location=location,
        )
        heapq.heappush(self.casualty_queue, request)

    def _generate_breakdown(
        self,
        vehicle_id: str,
        location: str,
        priority: Priority | int = Priority.PRIORITY,
    ) -> None:
        """Create a breakdown and add to recovery queue."""
        if isinstance(priority, int):
            priority = Priority(priority)

        vruntime = self.vehicles.get(vehicle_id)
        if not vruntime:
            return

        # Mark vehicle as broken down
        vruntime.state = VehicleState.BROKEN_DOWN
        vruntime.current_location = location

        # Get vehicle class for recovery matching
        vehicle_class = vruntime.vehicle_type.vehicle_class.value

        # Create breakdown record
        breakdown = self.event_log.create_breakdown(
            vehicle_id=vehicle_id,
            vehicle_class=vehicle_class,
            location=location,
            time_occurred=self.env.now,
            priority=priority,
        )

        # Log event
        self.event_log.log_event(
            time_mins=self.env.now,
            event_type=EventType.BREAKDOWN_OCCURRED,
            entity_id=breakdown.id,
            location=location,
            vehicle_id=vehicle_id,
            vehicle_class=vehicle_class,
            priority=priority.value,
        )

        # Add to recovery queue
        request = RecoveryRequest(
            priority=priority.value,
            time_requested=self.env.now,
            breakdown=breakdown,
            location=location,
            vehicle_class=vehicle_class,
        )
        heapq.heappush(self.recovery_queue, request)

    def _generate_ammo_request(
        self,
        location: str,
        quantity: int,
        priority: Priority | int = Priority.PRIORITY,
    ) -> None:
        """Create an ammo request and add to delivery queue."""
        if isinstance(priority, int):
            priority = Priority(priority)

        # Create ammo request record
        ammo_req = self.event_log.create_ammo_request(
            location=location,
            quantity_requested=quantity,
            time_requested=self.env.now,
            priority=priority,
        )

        # Log event
        self.event_log.log_event(
            time_mins=self.env.now,
            event_type=EventType.AMMO_REQUEST_GENERATED,
            entity_id=ammo_req.id,
            location=location,
            quantity=quantity,
            priority=priority.value,
        )

        # Add to delivery queue
        request = AmmoDeliveryRequest(
            priority=priority.value,
            time_requested=self.env.now,
            ammo_request=ammo_req,
            location=location,
            quantity=quantity,
        )
        heapq.heappush(self.ammo_queue, request)

    # === Vehicle Processes ===
    
    def _ambulance_process(self, vehicle_id: str) -> Generator:
        """Main process loop for an ambulance."""
        vruntime = self.vehicles[vehicle_id]
        vtype = vruntime.vehicle_type
        
        while True:
            # Wait for a casualty request if queue is empty
            while not self.casualty_queue:
                yield self.env.timeout(1)  # Check every minute
            
            # Check if this ambulance is available
            if vehicle_id not in self.idle_ambulances:
                yield self.env.timeout(1)
                continue
            
            # Get highest priority casualty
            request = heapq.heappop(self.casualty_queue)
            casualty = request.casualty
            pickup_location = request.location
            
            # Mark ambulance busy
            self.idle_ambulances.remove(vehicle_id)
            vruntime.state = VehicleState.TRANSITING_UNLADEN
            
            # Log dispatch
            self.event_log.log_event(
                time_mins=self.env.now,
                event_type=EventType.VEHICLE_DISPATCHED,
                entity_id=vehicle_id,
                location=vruntime.current_location,
                destination=pickup_location,
                casualty_id=casualty.id,
            )
            
            # Travel to pickup location
            travel_time = self._calculate_travel_time(
                vruntime.current_location,
                pickup_location,
                vtype.speed.unladen_kmh,
            )
            
            if travel_time > 0:
                yield self.env.timeout(travel_time)
            
            vruntime.current_location = pickup_location
            
            # Arrive at pickup
            self.event_log.log_event(
                time_mins=self.env.now,
                event_type=EventType.VEHICLE_ARRIVED,
                entity_id=vehicle_id,
                location=pickup_location,
            )
            
            # Load casualty
            vruntime.state = VehicleState.LOADING
            self.event_log.log_event(
                time_mins=self.env.now,
                event_type=EventType.LOADING_STARTED,
                entity_id=vehicle_id,
                location=pickup_location,
                casualty_id=casualty.id,
            )
            
            yield self.env.timeout(vtype.service_times.load_time_mins)
            
            # Update casualty record
            casualty.time_collected = self.env.now
            casualty.collected_by = vehicle_id
            vruntime.casualties_aboard.append(casualty)
            
            self.event_log.log_event(
                time_mins=self.env.now,
                event_type=EventType.CASUALTY_COLLECTED,
                entity_id=casualty.id,
                location=pickup_location,
                vehicle_id=vehicle_id,
                wait_time_mins=casualty.wait_time_mins,
            )
            
            # Find nearest medical facility
            delivery_node = self._find_nearest_medical(pickup_location)
            
            if delivery_node is None:
                # No medical facility - return to base (shouldn't happen in valid scenario)
                continue
            
            # Travel to medical facility (laden)
            vruntime.state = VehicleState.TRANSITING_LADEN
            
            self.event_log.log_event(
                time_mins=self.env.now,
                event_type=EventType.VEHICLE_DEPARTED,
                entity_id=vehicle_id,
                location=pickup_location,
                destination=delivery_node,
            )
            
            travel_time = self._calculate_travel_time(
                pickup_location,
                delivery_node,
                vtype.speed.laden_kmh,
            )
            
            if travel_time > 0:
                yield self.env.timeout(travel_time)
            
            vruntime.current_location = delivery_node
            
            # Arrive at medical facility
            self.event_log.log_event(
                time_mins=self.env.now,
                event_type=EventType.VEHICLE_ARRIVED,
                entity_id=vehicle_id,
                location=delivery_node,
            )
            
            # Unload casualty
            vruntime.state = VehicleState.UNLOADING
            self.event_log.log_event(
                time_mins=self.env.now,
                event_type=EventType.UNLOADING_STARTED,
                entity_id=vehicle_id,
                location=delivery_node,
            )
            
            yield self.env.timeout(vtype.service_times.unload_time_mins)
            
            # Update casualty record
            casualty.time_delivered = self.env.now
            casualty.delivered_to = delivery_node
            vruntime.casualties_aboard.remove(casualty)
            
            self.event_log.log_event(
                time_mins=self.env.now,
                event_type=EventType.CASUALTY_DELIVERED,
                entity_id=casualty.id,
                location=delivery_node,
                vehicle_id=vehicle_id,
                evacuation_time_mins=casualty.evacuation_time_mins,
            )
            
            # Start treatment process for casualty
            self.env.process(self._treatment_process(casualty, delivery_node))
            
            # Update stats
            vruntime.missions_completed += 1
            
            # Return to base or stay at medical facility
            # For MVP: ambulance stays at delivery location, ready for next call
            vruntime.state = VehicleState.IDLE
            self.idle_ambulances.append(vehicle_id)
            
            self.event_log.log_event(
                time_mins=self.env.now,
                event_type=EventType.VEHICLE_RETURNED,
                entity_id=vehicle_id,
                location=delivery_node,
            )
    
    def _treatment_process(self, casualty: Casualty, node_id: str) -> Generator:
        """Process casualty through treatment at medical facility."""
        node = self.scenario.get_node_by_id(node_id)
        if node is None:
            return
        
        # Get treatment time
        treatment_time = node.properties.treatment_time_mins or 30
        
        # Request treatment slot (may queue)
        resource = self.node_resources.get(node_id)
        
        if resource:
            with resource.request() as req:
                yield req
                
                # Treatment starts
                casualty.time_treatment_started = self.env.now
                self.event_log.log_event(
                    time_mins=self.env.now,
                    event_type=EventType.TREATMENT_STARTED,
                    entity_id=casualty.id,
                    location=node_id,
                    queue_time_mins=(
                        self.env.now - casualty.time_delivered
                        if casualty.time_delivered else 0
                    ),
                )
                
                yield self.env.timeout(treatment_time)
                
                # Treatment complete
                casualty.time_treatment_completed = self.env.now
                self.event_log.log_event(
                    time_mins=self.env.now,
                    event_type=EventType.TREATMENT_COMPLETED,
                    entity_id=casualty.id,
                    location=node_id,
                    total_time_mins=casualty.total_time_mins,
                )
        else:
            # No capacity constraint - treat immediately
            casualty.time_treatment_started = self.env.now
            yield self.env.timeout(treatment_time)
            casualty.time_treatment_completed = self.env.now

    def _recovery_process(self, vehicle_id: str) -> Generator:
        """Main process loop for a recovery vehicle."""
        vruntime = self.vehicles[vehicle_id]
        vtype = vruntime.vehicle_type
        tow_class = vtype.tow_capacity_class.value if vtype.tow_capacity_class else "light"

        while True:
            # Wait for a recovery request if queue is empty
            while not self.recovery_queue:
                yield self.env.timeout(1)

            # Check if this recovery vehicle is available
            if vehicle_id not in self.idle_recovery.get(tow_class, []):
                yield self.env.timeout(1)
                continue

            # Find a request we can handle (matching vehicle class)
            suitable_request = None
            temp_queue = []

            while self.recovery_queue:
                request = heapq.heappop(self.recovery_queue)
                # Check if we can tow this vehicle class
                if self._can_tow(tow_class, request.vehicle_class):
                    suitable_request = request
                    break
                temp_queue.append(request)

            # Put back requests we couldn't handle
            for req in temp_queue:
                heapq.heappush(self.recovery_queue, req)

            if suitable_request is None:
                yield self.env.timeout(1)
                continue

            breakdown = suitable_request.breakdown
            pickup_location = suitable_request.location

            # Mark recovery vehicle busy
            self.idle_recovery[tow_class].remove(vehicle_id)
            vruntime.state = VehicleState.TRANSITING_UNLADEN

            # Log dispatch
            breakdown.time_recovery_dispatched = self.env.now
            breakdown.recovered_by = vehicle_id
            self.event_log.log_event(
                time_mins=self.env.now,
                event_type=EventType.VEHICLE_DISPATCHED,
                entity_id=vehicle_id,
                location=vruntime.current_location,
                destination=pickup_location,
                breakdown_id=breakdown.id,
            )

            # Travel to breakdown location
            travel_time = self._calculate_travel_time(
                vruntime.current_location,
                pickup_location,
                vtype.speed.unladen_kmh,
            )

            if travel_time > 0:
                yield self.env.timeout(travel_time)

            vruntime.current_location = pickup_location
            breakdown.time_recovery_arrived = self.env.now

            # Arrive at breakdown
            self.event_log.log_event(
                time_mins=self.env.now,
                event_type=EventType.VEHICLE_ARRIVED,
                entity_id=vehicle_id,
                location=pickup_location,
            )

            # Hookup process
            vruntime.state = VehicleState.HOOKUP
            self.event_log.log_event(
                time_mins=self.env.now,
                event_type=EventType.HOOKUP_STARTED,
                entity_id=vehicle_id,
                location=pickup_location,
                breakdown_id=breakdown.id,
            )

            hookup_time = vtype.service_times.hookup_time_mins or 15
            yield self.env.timeout(hookup_time)

            breakdown.time_hookup_completed = self.env.now
            self.event_log.log_event(
                time_mins=self.env.now,
                event_type=EventType.HOOKUP_COMPLETED,
                entity_id=vehicle_id,
                location=pickup_location,
                breakdown_id=breakdown.id,
            )

            # Find nearest workshop
            workshop_node = self._find_nearest_workshop(pickup_location)

            if workshop_node is None:
                # No workshop - return broken vehicle to current location
                vruntime.state = VehicleState.IDLE
                self.idle_recovery[tow_class].append(vehicle_id)
                continue

            # Travel to workshop (laden/towing)
            vruntime.state = VehicleState.TRANSITING_LADEN

            self.event_log.log_event(
                time_mins=self.env.now,
                event_type=EventType.VEHICLE_DEPARTED,
                entity_id=vehicle_id,
                location=pickup_location,
                destination=workshop_node,
            )

            travel_time = self._calculate_travel_time(
                pickup_location,
                workshop_node,
                vtype.speed.laden_kmh,
            )

            if travel_time > 0:
                yield self.env.timeout(travel_time)

            vruntime.current_location = workshop_node
            breakdown.time_arrived_workshop = self.env.now
            breakdown.repaired_at = workshop_node

            # Arrive at workshop
            self.event_log.log_event(
                time_mins=self.env.now,
                event_type=EventType.VEHICLE_ARRIVED,
                entity_id=vehicle_id,
                location=workshop_node,
            )

            # Start repair process for broken vehicle
            self.env.process(self._repair_process(breakdown, workshop_node))

            # Update stats
            vruntime.missions_completed += 1

            # Recovery vehicle is now idle at workshop
            vruntime.state = VehicleState.IDLE
            self.idle_recovery[tow_class].append(vehicle_id)

            self.event_log.log_event(
                time_mins=self.env.now,
                event_type=EventType.VEHICLE_RETURNED,
                entity_id=vehicle_id,
                location=workshop_node,
            )

    def _repair_process(self, breakdown: Breakdown, node_id: str) -> Generator:
        """Process vehicle through repair at workshop."""
        node = self.scenario.get_node_by_id(node_id)
        if node is None:
            return

        # Get repair time (default 60 mins)
        repair_time = node.properties.repair_time_mins if hasattr(node.properties, 'repair_time_mins') else 60

        # Request repair bay (may queue)
        resource = self.node_resources.get(node_id)

        if resource:
            with resource.request() as req:
                yield req

                # Repair starts
                breakdown.time_repair_started = self.env.now
                self.event_log.log_event(
                    time_mins=self.env.now,
                    event_type=EventType.REPAIR_STARTED,
                    entity_id=breakdown.id,
                    location=node_id,
                    vehicle_id=breakdown.vehicle_id,
                )

                yield self.env.timeout(repair_time)

                # Repair complete
                breakdown.time_repair_completed = self.env.now
                self.event_log.log_event(
                    time_mins=self.env.now,
                    event_type=EventType.REPAIR_COMPLETED,
                    entity_id=breakdown.id,
                    location=node_id,
                    vehicle_id=breakdown.vehicle_id,
                    total_downtime_mins=breakdown.total_downtime_mins,
                )

                # Return broken vehicle to service
                broken_vruntime = self.vehicles.get(breakdown.vehicle_id)
                if broken_vruntime:
                    broken_vruntime.state = VehicleState.IDLE
                    broken_vruntime.current_location = node_id
                    # Re-add to appropriate idle list
                    self._return_vehicle_to_service(breakdown.vehicle_id)
        else:
            # No capacity constraint - repair immediately
            breakdown.time_repair_started = self.env.now
            yield self.env.timeout(repair_time)
            breakdown.time_repair_completed = self.env.now

            broken_vruntime = self.vehicles.get(breakdown.vehicle_id)
            if broken_vruntime:
                broken_vruntime.state = VehicleState.IDLE
                broken_vruntime.current_location = node_id
                self._return_vehicle_to_service(breakdown.vehicle_id)

    def _logistics_process(self, vehicle_id: str) -> Generator:
        """Main process loop for a logistics vehicle."""
        vruntime = self.vehicles[vehicle_id]
        vtype = vruntime.vehicle_type

        while True:
            # Wait for an ammo request if queue is empty
            while not self.ammo_queue:
                yield self.env.timeout(1)

            # Check if this logistics vehicle is available
            if vehicle_id not in self.idle_logistics:
                yield self.env.timeout(1)
                continue

            # Get highest priority request
            request = heapq.heappop(self.ammo_queue)
            ammo_req = request.ammo_request
            delivery_location = request.location

            # Mark vehicle busy
            self.idle_logistics.remove(vehicle_id)
            vruntime.state = VehicleState.TRANSITING_UNLADEN

            # Find nearest ammo point to load from
            ammo_point = self._find_nearest_ammo_point(vruntime.current_location)

            if ammo_point is None:
                # No ammo point - can't fulfill
                self.event_log.log_event(
                    time_mins=self.env.now,
                    event_type=EventType.STOCKOUT,
                    entity_id=ammo_req.id,
                    location=delivery_location,
                )
                self.idle_logistics.append(vehicle_id)
                vruntime.state = VehicleState.IDLE
                continue

            # Log dispatch
            ammo_req.time_dispatched = self.env.now
            ammo_req.fulfilled_by = vehicle_id
            self.event_log.log_event(
                time_mins=self.env.now,
                event_type=EventType.VEHICLE_DISPATCHED,
                entity_id=vehicle_id,
                location=vruntime.current_location,
                destination=ammo_point,
                ammo_request_id=ammo_req.id,
            )

            # Travel to ammo point
            travel_time = self._calculate_travel_time(
                vruntime.current_location,
                ammo_point,
                vtype.speed.unladen_kmh,
            )

            if travel_time > 0:
                yield self.env.timeout(travel_time)

            vruntime.current_location = ammo_point

            # Arrive at ammo point
            self.event_log.log_event(
                time_mins=self.env.now,
                event_type=EventType.VEHICLE_ARRIVED,
                entity_id=vehicle_id,
                location=ammo_point,
            )

            # Load ammunition
            vruntime.state = VehicleState.LOADING
            self.event_log.log_event(
                time_mins=self.env.now,
                event_type=EventType.LOADING_STARTED,
                entity_id=vehicle_id,
                location=ammo_point,
            )

            yield self.env.timeout(vtype.service_times.load_time_mins)

            ammo_req.time_loaded = self.env.now
            ammo_req.loaded_from = ammo_point

            # Calculate how much we can carry
            capacity = vtype.ammo_capacity_units or 1000
            quantity_loaded = min(request.quantity, capacity)

            self.event_log.log_event(
                time_mins=self.env.now,
                event_type=EventType.AMMO_LOADED,
                entity_id=vehicle_id,
                location=ammo_point,
                quantity=quantity_loaded,
            )

            # Travel to delivery location
            vruntime.state = VehicleState.TRANSITING_LADEN

            self.event_log.log_event(
                time_mins=self.env.now,
                event_type=EventType.VEHICLE_DEPARTED,
                entity_id=vehicle_id,
                location=ammo_point,
                destination=delivery_location,
            )

            travel_time = self._calculate_travel_time(
                ammo_point,
                delivery_location,
                vtype.speed.laden_kmh,
            )

            if travel_time > 0:
                yield self.env.timeout(travel_time)

            vruntime.current_location = delivery_location

            # Arrive at delivery location
            self.event_log.log_event(
                time_mins=self.env.now,
                event_type=EventType.VEHICLE_ARRIVED,
                entity_id=vehicle_id,
                location=delivery_location,
            )

            # Unload ammunition
            vruntime.state = VehicleState.UNLOADING
            self.event_log.log_event(
                time_mins=self.env.now,
                event_type=EventType.UNLOADING_STARTED,
                entity_id=vehicle_id,
                location=delivery_location,
            )

            yield self.env.timeout(vtype.service_times.unload_time_mins)

            # Update request
            ammo_req.time_delivered = self.env.now
            ammo_req.quantity_delivered = quantity_loaded

            self.event_log.log_event(
                time_mins=self.env.now,
                event_type=EventType.AMMO_DELIVERED,
                entity_id=ammo_req.id,
                location=delivery_location,
                vehicle_id=vehicle_id,
                quantity=quantity_loaded,
                delivery_time_mins=ammo_req.delivery_time_mins,
            )

            # Update stats
            vruntime.missions_completed += 1

            # Vehicle is now idle at delivery location
            vruntime.state = VehicleState.IDLE
            self.idle_logistics.append(vehicle_id)

            self.event_log.log_event(
                time_mins=self.env.now,
                event_type=EventType.VEHICLE_RETURNED,
                entity_id=vehicle_id,
                location=delivery_location,
            )

    def _can_tow(self, recovery_class: str, broken_class: str) -> bool:
        """Check if a recovery vehicle can tow a broken vehicle."""
        class_order = {"light": 0, "medium": 1, "heavy": 2}
        return class_order.get(recovery_class, 0) >= class_order.get(broken_class, 0)

    def _return_vehicle_to_service(self, vehicle_id: str) -> None:
        """Return a repaired vehicle to the appropriate idle list."""
        vruntime = self.vehicles.get(vehicle_id)
        if not vruntime:
            return

        role = vruntime.vehicle_type.role
        if role == VehicleRole.AMBULANCE:
            if vehicle_id not in self.idle_ambulances:
                self.idle_ambulances.append(vehicle_id)
        elif role == VehicleRole.RECOVERY:
            tow_class = vruntime.vehicle_type.tow_capacity_class.value if vruntime.vehicle_type.tow_capacity_class else "light"
            if vehicle_id not in self.idle_recovery[tow_class]:
                self.idle_recovery[tow_class].append(vehicle_id)
        elif role == VehicleRole.AMMO_LOGISTICS:
            if vehicle_id not in self.idle_logistics:
                self.idle_logistics.append(vehicle_id)

    def _remove_vehicle_from_service(self, vehicle_id: str) -> None:
        """Remove a vehicle from idle lists (for breakdown/rest)."""
        vruntime = self.vehicles.get(vehicle_id)
        if not vruntime:
            return

        role = vruntime.vehicle_type.role
        if role == VehicleRole.AMBULANCE:
            if vehicle_id in self.idle_ambulances:
                self.idle_ambulances.remove(vehicle_id)
        elif role == VehicleRole.RECOVERY:
            tow_class = vruntime.vehicle_type.tow_capacity_class.value if vruntime.vehicle_type.tow_capacity_class else "light"
            if vehicle_id in self.idle_recovery.get(tow_class, []):
                self.idle_recovery[tow_class].remove(vehicle_id)
        elif role == VehicleRole.AMMO_LOGISTICS:
            if vehicle_id in self.idle_logistics:
                self.idle_logistics.remove(vehicle_id)

    # === Extended Operations Processes (Phase 4) ===

    def _crew_fatigue_monitor(self, vehicle_id: str) -> Generator:
        """Monitor crew fatigue and enforce mandatory rest periods."""
        vruntime = self.vehicles[vehicle_id]
        vtype = vruntime.vehicle_type
        max_ops_mins = vtype.max_continuous_ops_hours * 60
        rest_duration_mins = 8 * 60  # 8 hour rest period

        while True:
            # Check every 15 minutes
            yield self.env.timeout(15)

            # Only track active states (not already resting or broken)
            if vruntime.state in (VehicleState.CREW_REST, VehicleState.BROKEN_DOWN,
                                  VehicleState.UNDER_REPAIR, VehicleState.MAINTENANCE):
                vruntime.continuous_ops_start = self.env.now
                continue

            # Calculate continuous ops time
            if vruntime.state != VehicleState.IDLE:
                ops_time = self.env.now - vruntime.continuous_ops_start
                vruntime.total_ops_time_mins = ops_time

                if ops_time >= max_ops_mins:
                    # Force crew rest
                    prev_state = vruntime.state
                    vruntime.state = VehicleState.CREW_REST

                    # Remove from service
                    self._remove_vehicle_from_service(vehicle_id)

                    self.event_log.log_event(
                        time_mins=self.env.now,
                        event_type=EventType.CREW_REST_STARTED,
                        entity_id=vehicle_id,
                        location=vruntime.current_location,
                        ops_time_mins=ops_time,
                    )

                    # Rest period
                    yield self.env.timeout(rest_duration_mins)

                    # Return to service
                    vruntime.state = VehicleState.IDLE
                    vruntime.continuous_ops_start = self.env.now
                    self._return_vehicle_to_service(vehicle_id)

                    self.event_log.log_event(
                        time_mins=self.env.now,
                        event_type=EventType.CREW_REST_ENDED,
                        entity_id=vehicle_id,
                        location=vruntime.current_location,
                    )
            else:
                # Reset counter when idle
                vruntime.continuous_ops_start = self.env.now

    def _maintenance_scheduler(self, vehicle_id: str) -> Generator:
        """Schedule periodic maintenance windows."""
        vruntime = self.vehicles[vehicle_id]
        vtype = vruntime.vehicle_type
        maintenance_interval_mins = (vtype.mtbf_hours or 200) * 60 * 0.8  # 80% of MTBF
        maintenance_duration_mins = 120  # 2 hour maintenance

        # Wait for first scheduled maintenance
        if vruntime.next_maintenance_time > 0:
            yield self.env.timeout(vruntime.next_maintenance_time)

        while True:
            # Only enter maintenance if idle
            while vruntime.state != VehicleState.IDLE:
                yield self.env.timeout(5)

            # Start maintenance
            vruntime.state = VehicleState.MAINTENANCE
            self._remove_vehicle_from_service(vehicle_id)

            self.event_log.log_event(
                time_mins=self.env.now,
                event_type=EventType.SHIFT_CHANGE,  # Reusing for maintenance start
                entity_id=vehicle_id,
                location=vruntime.current_location,
                event_subtype="maintenance_started",
            )

            yield self.env.timeout(maintenance_duration_mins)

            # Complete maintenance
            vruntime.state = VehicleState.IDLE
            vruntime.time_since_last_breakdown = 0  # Reset breakdown timer
            self._return_vehicle_to_service(vehicle_id)

            self.event_log.log_event(
                time_mins=self.env.now,
                event_type=EventType.SHIFT_CHANGE,  # Reusing for maintenance end
                entity_id=vehicle_id,
                location=vruntime.current_location,
                event_subtype="maintenance_completed",
            )

            # Schedule next maintenance
            vruntime.next_maintenance_time = self.env.now + maintenance_interval_mins
            yield self.env.timeout(maintenance_interval_mins)

    def _breakdown_generator(self, vehicle_id: str) -> Generator:
        """Generate random breakdowns based on MTBF."""
        vruntime = self.vehicles[vehicle_id]
        vtype = vruntime.vehicle_type
        mtbf_mins = (vtype.mtbf_hours or 200) * 60

        while True:
            # Generate time to next breakdown using exponential distribution
            time_to_breakdown = self._rng.expovariate(1.0 / mtbf_mins)
            yield self.env.timeout(time_to_breakdown)

            # Only break down if vehicle is operational (not already broken/resting)
            if vruntime.state in (VehicleState.BROKEN_DOWN, VehicleState.UNDER_REPAIR,
                                  VehicleState.CREW_REST, VehicleState.MAINTENANCE):
                continue

            # Generate breakdown
            self._generate_breakdown(
                vehicle_id=vehicle_id,
                location=vruntime.current_location,
                priority=Priority.PRIORITY,
            )

    # === Routing Helpers ===
    
    def _calculate_travel_time(
        self,
        from_node: str,
        to_node: str,
        speed_kmh: float,
    ) -> float:
        """Calculate travel time in minutes between two nodes."""
        if from_node == to_node:
            return 0.0
        
        try:
            # Use NetworkX shortest path
            path = nx.shortest_path(
                self.graph,
                from_node,
                to_node,
                weight="effective_km",
            )
            
            # Sum distances along path
            total_km = 0.0
            for i in range(len(path) - 1):
                edge_data = self.graph.edges[path[i], path[i + 1]]
                total_km += edge_data["effective_km"]
            
            # Convert to time
            time_hours = total_km / speed_kmh
            return time_hours * 60  # minutes
            
        except nx.NetworkXNoPath:
            # No path exists - return large value
            return float("inf")
    
    def _find_nearest_medical(self, from_node: str) -> Optional[str]:
        """Find nearest medical facility from given node."""
        medical_types = {NodeType.MEDICAL_ROLE1, NodeType.MEDICAL_ROLE2}
        
        best_node = None
        best_distance = float("inf")
        
        for node in self.scenario.nodes:
            if node.type in medical_types:
                try:
                    dist = nx.shortest_path_length(
                        self.graph,
                        from_node,
                        node.id,
                        weight="effective_km",
                    )
                    if dist < best_distance:
                        best_distance = dist
                        best_node = node.id
                except nx.NetworkXNoPath:
                    continue
        
        return best_node

    def _find_nearest_workshop(self, from_node: str) -> Optional[str]:
        """Find nearest repair workshop from given node."""
        best_node = None
        best_distance = float("inf")

        for node in self.scenario.nodes:
            if node.type == NodeType.REPAIR_WORKSHOP:
                try:
                    dist = nx.shortest_path_length(
                        self.graph,
                        from_node,
                        node.id,
                        weight="effective_km",
                    )
                    if dist < best_distance:
                        best_distance = dist
                        best_node = node.id
                except nx.NetworkXNoPath:
                    continue

        return best_node

    def _find_nearest_ammo_point(self, from_node: str) -> Optional[str]:
        """Find nearest ammunition supply point from given node."""
        best_node = None
        best_distance = float("inf")

        for node in self.scenario.nodes:
            if node.type == NodeType.AMMO_POINT:
                try:
                    dist = nx.shortest_path_length(
                        self.graph,
                        from_node,
                        node.id,
                        weight="effective_km",
                    )
                    if dist < best_distance:
                        best_distance = dist
                        best_node = node.id
                except nx.NetworkXNoPath:
                    continue

        return best_node

    # === Statistics ===
    
    def get_vehicle_stats(self) -> dict[str, dict[str, Any]]:
        """Get statistics for all vehicles."""
        stats = {}
        for vid, vruntime in self.vehicles.items():
            stats[vid] = {
                "callsign": vruntime.vehicle.callsign,
                "type": vruntime.vehicle_type.name,
                "missions_completed": vruntime.missions_completed,
                "current_state": vruntime.state.value,
                "current_location": vruntime.current_location,
            }
        return stats
