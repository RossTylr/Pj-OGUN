"""Base class for vehicle processes."""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Generator, Optional

import simpy

from pj_ogun.schema import Vehicle, VehicleType
from pj_ogun.schema.enums import VehicleState
from pj_ogun.simulation.events import EventLog, EventType

if TYPE_CHECKING:
    from pj_ogun.simulation.engine import SimulationEngine


class VehicleProcess(ABC):
    """Base class for all vehicle behaviour processes.
    
    Each vehicle in the simulation runs as a SimPy process,
    responding to tasks and moving through the network.
    
    Subclasses implement role-specific behaviour (ambulance,
    recovery, logistics).
    """
    
    def __init__(
        self,
        env: simpy.Environment,
        vehicle: Vehicle,
        vehicle_type: VehicleType,
        engine: "SimulationEngine",
    ):
        """Initialise vehicle process.
        
        Args:
            env: SimPy environment
            vehicle: Vehicle instance configuration
            vehicle_type: Vehicle type specification
            engine: Parent simulation engine (for network, resources, etc.)
        """
        self.env = env
        self.vehicle = vehicle
        self.vehicle_type = vehicle_type
        self.engine = engine
        
        # Current state
        self._state = vehicle.initial_state
        self._current_location = vehicle.start_location
        self._current_load = int(
            vehicle.initial_load_fraction * vehicle_type.get_capacity_for_role()
        )
        
        # Crew state (for fatigue tracking)
        self._crew_fatigue_hours = vehicle.initial_crew_fatigue_hours
        self._continuous_ops_start: Optional[float] = None
        
        # Task queue - processes wait on this for assignments
        self.task_queue: simpy.Store = simpy.Store(env)
        
        # SimPy process handle
        self._process: Optional[simpy.Process] = None
    
    @property
    def id(self) -> str:
        """Vehicle ID."""
        return self.vehicle.id
    
    @property
    def state(self) -> VehicleState:
        """Current vehicle state."""
        return self._state
    
    @state.setter
    def state(self, new_state: VehicleState) -> None:
        """Update vehicle state."""
        self._state = new_state
    
    @property
    def location(self) -> str:
        """Current node ID."""
        return self._current_location
    
    @location.setter
    def location(self, node_id: str) -> None:
        """Update current location."""
        self._current_location = node_id
    
    @property
    def current_load(self) -> int:
        """Current load count."""
        return self._current_load
    
    @property
    def capacity(self) -> int:
        """Maximum capacity."""
        return self.vehicle_type.get_capacity_for_role()
    
    @property
    def is_laden(self) -> bool:
        """Check if vehicle is carrying anything."""
        return self._current_load > 0
    
    @property
    def event_log(self) -> EventLog:
        """Shortcut to engine's event log."""
        return self.engine.event_log
    
    def start(self) -> simpy.Process:
        """Start the vehicle process.
        
        Returns:
            The SimPy process handle
        """
        self._process = self.env.process(self.run())
        return self._process
    
    @abstractmethod
    def run(self) -> Generator:
        """Main process loop - implement in subclasses.
        
        Typically:
        1. Wait for task assignment
        2. Travel to pickup location
        3. Load
        4. Travel to destination
        5. Unload
        6. Return to base or wait for next task
        """
        pass
    
    def travel_to(
        self,
        destination: str,
        log_events: bool = True,
    ) -> Generator:
        """Travel from current location to destination.
        
        Yields SimPy timeout for travel duration.
        
        Args:
            destination: Target node ID
            log_events: Whether to log departure/arrival events
        """
        if destination == self._current_location:
            return  # Already there
        
        # Find path
        path = self.engine.network.find_shortest_path(
            self._current_location,
            destination,
            vehicle_class=self.vehicle_type.vehicle_class,
        )
        
        if path is None:
            raise ValueError(
                f"No path from {self._current_location} to {destination} "
                f"for vehicle class {self.vehicle_type.vehicle_class}"
            )
        
        # Calculate travel time
        speed = self.vehicle_type.speed.get_speed(self.is_laden)
        travel_time_mins = self.engine.network.get_path_travel_time(path, speed)
        
        # Update state
        old_state = self._state
        self._state = (
            VehicleState.TRANSITING_LADEN if self.is_laden
            else VehicleState.TRANSITING_UNLADEN
        )
        
        if log_events:
            self.event_log.log_simple(
                time=self.env.now,
                event_type=EventType.VEHICLE_DEPARTED,
                entity_id=self.id,
                entity_type="vehicle",
                from_location=self._current_location,
                to_location=destination,
                data={"path": path, "speed_kmh": speed},
            )
        
        # Simulate travel
        yield self.env.timeout(travel_time_mins)
        
        # Update location
        self._current_location = destination
        self._state = old_state
        
        if log_events:
            self.event_log.log_simple(
                time=self.env.now,
                event_type=EventType.VEHICLE_ARRIVED,
                entity_id=self.id,
                entity_type="vehicle",
                location=destination,
                duration=travel_time_mins,
            )
    
    def load(self, quantity: int = 1) -> Generator:
        """Load cargo/casualties.
        
        Args:
            quantity: Number of items to load
        """
        load_time = self.vehicle_type.service_times.load_time_mins
        
        self._state = VehicleState.LOADING
        self.event_log.log_simple(
            time=self.env.now,
            event_type=EventType.VEHICLE_LOADING,
            entity_id=self.id,
            entity_type="vehicle",
            location=self._current_location,
            quantity=quantity,
        )
        
        yield self.env.timeout(load_time)
        
        self._current_load += quantity
        self._state = VehicleState.IDLE
        
        self.event_log.log_simple(
            time=self.env.now,
            event_type=EventType.VEHICLE_LOADING_COMPLETE,
            entity_id=self.id,
            entity_type="vehicle",
            location=self._current_location,
            quantity=self._current_load,
            duration=load_time,
        )
    
    def unload(self, quantity: Optional[int] = None) -> Generator:
        """Unload cargo/casualties.
        
        Args:
            quantity: Number of items to unload (None = all)
        """
        if quantity is None:
            quantity = self._current_load
        
        unload_time = self.vehicle_type.service_times.unload_time_mins
        
        self._state = VehicleState.UNLOADING
        self.event_log.log_simple(
            time=self.env.now,
            event_type=EventType.VEHICLE_UNLOADING,
            entity_id=self.id,
            entity_type="vehicle",
            location=self._current_location,
            quantity=quantity,
        )
        
        yield self.env.timeout(unload_time)
        
        self._current_load -= quantity
        self._state = VehicleState.IDLE
        
        self.event_log.log_simple(
            time=self.env.now,
            event_type=EventType.VEHICLE_UNLOADING_COMPLETE,
            entity_id=self.id,
            entity_type="vehicle",
            location=self._current_location,
            quantity=self._current_load,
            duration=unload_time,
        )
    
    def assign_task(self, task: dict) -> None:
        """Assign a task to this vehicle.
        
        Args:
            task: Task specification dictionary
        """
        self.task_queue.put(task)
    
    def log_idle(self) -> None:
        """Log vehicle becoming idle."""
        self._state = VehicleState.IDLE
        self.event_log.log_simple(
            time=self.env.now,
            event_type=EventType.VEHICLE_IDLE,
            entity_id=self.id,
            entity_type="vehicle",
            location=self._current_location,
        )
