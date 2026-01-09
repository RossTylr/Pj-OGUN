"""Vehicle process implementations for SimPy simulation."""

from pj_ogun.simulation.processes.ambulance import AmbulanceProcess
from pj_ogun.simulation.processes.base import VehicleProcess

__all__ = [
    "VehicleProcess",
    "AmbulanceProcess",
]
