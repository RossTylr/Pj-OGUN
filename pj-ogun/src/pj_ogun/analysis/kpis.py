"""KPI calculations for simulation results.

This module provides functions to compute Key Performance Indicators
from simulation event logs, organised by subsystem (MEDEVAC, Recovery, Resupply).
"""

from dataclasses import dataclass, field
from typing import Any, Optional

import pandas as pd
import numpy as np

from pj_ogun.models.enums import EventType, Priority


def _to_python(value: Any) -> Any:
    """Convert numpy/pandas types to native Python types for JSON serialization."""
    if value is None:
        return None
    if isinstance(value, (np.integer, np.int64, np.int32)):
        return int(value)
    if isinstance(value, (np.floating, np.float64, np.float32)):
        return float(value)
    if isinstance(value, np.bool_):
        return bool(value)
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, pd.Series):
        return value.tolist()
    if isinstance(value, dict):
        return {k: _to_python(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_to_python(v) for v in value]
    return value


from pj_ogun.simulation.events import EventLog


@dataclass
class MEDEVACKPIs:
    """Key Performance Indicators for casualty evacuation."""
    
    # Counts
    total_casualties: int = 0
    casualties_collected: int = 0
    casualties_delivered: int = 0
    casualties_treated: int = 0
    casualties_pending: int = 0
    
    # Time metrics (minutes)
    mean_wait_time: Optional[float] = None
    median_wait_time: Optional[float] = None
    max_wait_time: Optional[float] = None
    p90_wait_time: Optional[float] = None
    
    mean_evacuation_time: Optional[float] = None
    median_evacuation_time: Optional[float] = None
    max_evacuation_time: Optional[float] = None
    p90_evacuation_time: Optional[float] = None
    
    mean_total_time: Optional[float] = None
    median_total_time: Optional[float] = None
    max_total_time: Optional[float] = None
    
    # By priority
    by_priority: dict[int, dict[str, Any]] = field(default_factory=dict)
    
    # Vehicle utilisation
    ambulance_missions: int = 0
    ambulance_utilisation: Optional[float] = None
    
    # Facility metrics
    mean_queue_time: Optional[float] = None
    max_queue_length: int = 0
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialisation."""
        return _to_python({
            "total_casualties": self.total_casualties,
            "casualties_collected": self.casualties_collected,
            "casualties_delivered": self.casualties_delivered,
            "casualties_treated": self.casualties_treated,
            "casualties_pending": self.casualties_pending,
            "mean_wait_time_mins": self.mean_wait_time,
            "median_wait_time_mins": self.median_wait_time,
            "max_wait_time_mins": self.max_wait_time,
            "p90_wait_time_mins": self.p90_wait_time,
            "mean_evacuation_time_mins": self.mean_evacuation_time,
            "median_evacuation_time_mins": self.median_evacuation_time,
            "max_evacuation_time_mins": self.max_evacuation_time,
            "p90_evacuation_time_mins": self.p90_evacuation_time,
            "mean_total_time_mins": self.mean_total_time,
            "median_total_time_mins": self.median_total_time,
            "max_total_time_mins": self.max_total_time,
            "ambulance_missions": self.ambulance_missions,
            "ambulance_utilisation_pct": self.ambulance_utilisation,
            "by_priority": self.by_priority,
        })
    
    def summary(self) -> str:
        """Generate human-readable summary."""
        lines = [
            "=== MEDEVAC KPIs ===",
            "",
            "Casualty Counts:",
            f"  Total:     {self.total_casualties}",
            f"  Collected: {self.casualties_collected}",
            f"  Delivered: {self.casualties_delivered}",
            f"  Treated:   {self.casualties_treated}",
            f"  Pending:   {self.casualties_pending}",
            "",
            "Wait Time (generation → collection):",
            f"  Mean:   {self._fmt(self.mean_wait_time)} mins",
            f"  Median: {self._fmt(self.median_wait_time)} mins",
            f"  Max:    {self._fmt(self.max_wait_time)} mins",
            f"  P90:    {self._fmt(self.p90_wait_time)} mins",
            "",
            "Evacuation Time (generation → delivery):",
            f"  Mean:   {self._fmt(self.mean_evacuation_time)} mins",
            f"  Median: {self._fmt(self.median_evacuation_time)} mins",
            f"  Max:    {self._fmt(self.max_evacuation_time)} mins",
            f"  P90:    {self._fmt(self.p90_evacuation_time)} mins",
            "",
            "Total Time (generation → treatment complete):",
            f"  Mean:   {self._fmt(self.mean_total_time)} mins",
            f"  Median: {self._fmt(self.median_total_time)} mins",
            f"  Max:    {self._fmt(self.max_total_time)} mins",
            "",
            f"Ambulance Missions: {self.ambulance_missions}",
        ]
        
        if self.by_priority:
            lines.extend(["", "By Priority:"])
            for p, stats in sorted(self.by_priority.items()):
                pname = {1: "P1 (Urgent)", 2: "P2 (Priority)", 3: "P3 (Routine)"}.get(p, f"P{p}")
                lines.append(f"  {pname}: {stats['count']} casualties, mean evac {self._fmt(stats.get('mean_evac'))} mins")
        
        return "\n".join(lines)
    
    @staticmethod
    def _fmt(value: Optional[float]) -> str:
        return f"{value:.1f}" if value is not None else "N/A"


def compute_medevac_kpis(event_log: EventLog) -> MEDEVACKPIs:
    """Compute MEDEVAC KPIs from simulation event log.
    
    Args:
        event_log: Completed simulation event log
        
    Returns:
        MEDEVACKPIs with all computed metrics
    """
    kpis = MEDEVACKPIs()
    
    # Get casualty data
    casualties = event_log.casualties
    kpis.total_casualties = len(casualties)
    
    if not casualties:
        return kpis
    
    # Convert to DataFrame for easier analysis
    df = event_log.casualties_to_dataframe()
    
    # Counts - convert to native int
    kpis.casualties_collected = int(df["time_collected"].notna().sum())
    kpis.casualties_delivered = int(df["time_delivered"].notna().sum())
    kpis.casualties_treated = int(df["time_treatment_completed"].notna().sum())
    kpis.casualties_pending = kpis.total_casualties - kpis.casualties_treated

    # Wait times (generation → collection)
    wait_times = df["wait_time_mins"].dropna()
    if len(wait_times) > 0:
        kpis.mean_wait_time = float(wait_times.mean())
        kpis.median_wait_time = float(wait_times.median())
        kpis.max_wait_time = float(wait_times.max())
        kpis.p90_wait_time = float(wait_times.quantile(0.9))

    # Evacuation times (generation → delivery)
    evac_times = df["evacuation_time_mins"].dropna()
    if len(evac_times) > 0:
        kpis.mean_evacuation_time = float(evac_times.mean())
        kpis.median_evacuation_time = float(evac_times.median())
        kpis.max_evacuation_time = float(evac_times.max())
        kpis.p90_evacuation_time = float(evac_times.quantile(0.9))

    # Total times (generation → treatment complete)
    total_times = df["total_time_mins"].dropna()
    if len(total_times) > 0:
        kpis.mean_total_time = float(total_times.mean())
        kpis.median_total_time = float(total_times.median())
        kpis.max_total_time = float(total_times.max())

    # By priority breakdown
    for priority in df["priority"].unique():
        pdata = df[df["priority"] == priority]
        pevac = pdata["evacuation_time_mins"].dropna()
        pwait = pdata["wait_time_mins"].dropna()

        kpis.by_priority[int(priority)] = {
            "count": int(len(pdata)),
            "collected": int(pdata["time_collected"].notna().sum()),
            "delivered": int(pdata["time_delivered"].notna().sum()),
            "treated": int(pdata["time_treatment_completed"].notna().sum()),
            "mean_wait": float(pwait.mean()) if len(pwait) > 0 else None,
            "mean_evac": float(pevac.mean()) if len(pevac) > 0 else None,
            "max_evac": float(pevac.max()) if len(pevac) > 0 else None,
        }
    
    # Count ambulance missions from events
    dispatch_events = event_log.filter_by_type(EventType.VEHICLE_DISPATCHED)
    kpis.ambulance_missions = len(dispatch_events)
    
    return kpis


@dataclass
class RecoveryKPIs:
    """Key Performance Indicators for vehicle recovery."""

    # Counts
    total_breakdowns: int = 0
    vehicles_recovered: int = 0
    vehicles_repaired: int = 0
    vehicles_pending: int = 0

    # Time metrics (minutes)
    mean_response_time: Optional[float] = None
    median_response_time: Optional[float] = None
    max_response_time: Optional[float] = None
    p90_response_time: Optional[float] = None

    mean_recovery_time: Optional[float] = None
    mean_repair_time: Optional[float] = None
    mean_total_downtime: Optional[float] = None
    max_total_downtime: Optional[float] = None

    # Vehicle stats
    recovery_missions: int = 0

    def to_dict(self) -> dict[str, Any]:
        return _to_python({
            "total_breakdowns": self.total_breakdowns,
            "vehicles_recovered": self.vehicles_recovered,
            "vehicles_repaired": self.vehicles_repaired,
            "vehicles_pending": self.vehicles_pending,
            "mean_response_time_mins": self.mean_response_time,
            "median_response_time_mins": self.median_response_time,
            "max_response_time_mins": self.max_response_time,
            "p90_response_time_mins": self.p90_response_time,
            "mean_recovery_time_mins": self.mean_recovery_time,
            "mean_repair_time_mins": self.mean_repair_time,
            "mean_total_downtime_mins": self.mean_total_downtime,
            "max_total_downtime_mins": self.max_total_downtime,
            "recovery_missions": self.recovery_missions,
        })

    def summary(self) -> str:
        """Generate human-readable summary."""
        lines = [
            "=== Recovery KPIs ===",
            "",
            "Breakdown Counts:",
            f"  Total:     {self.total_breakdowns}",
            f"  Recovered: {self.vehicles_recovered}",
            f"  Repaired:  {self.vehicles_repaired}",
            f"  Pending:   {self.vehicles_pending}",
            "",
            "Response Time (breakdown -> recovery arrival):",
            f"  Mean:   {self._fmt(self.mean_response_time)} mins",
            f"  Median: {self._fmt(self.median_response_time)} mins",
            f"  Max:    {self._fmt(self.max_response_time)} mins",
            f"  P90:    {self._fmt(self.p90_response_time)} mins",
            "",
            "Repair/Downtime:",
            f"  Mean Repair Time:    {self._fmt(self.mean_repair_time)} mins",
            f"  Mean Total Downtime: {self._fmt(self.mean_total_downtime)} mins",
            f"  Max Total Downtime:  {self._fmt(self.max_total_downtime)} mins",
            "",
            f"Recovery Missions: {self.recovery_missions}",
        ]
        return "\n".join(lines)

    @staticmethod
    def _fmt(value: Optional[float]) -> str:
        return f"{value:.1f}" if value is not None else "N/A"


def compute_recovery_kpis(event_log: EventLog) -> RecoveryKPIs:
    """Compute Recovery KPIs from simulation event log."""
    kpis = RecoveryKPIs()

    breakdowns = event_log.breakdowns
    kpis.total_breakdowns = len(breakdowns)

    if not breakdowns:
        return kpis

    # Convert to DataFrame for analysis
    df = event_log.breakdowns_to_dataframe()

    # Counts - ensure native int
    kpis.vehicles_recovered = int(df["time_arrived_workshop"].notna().sum())
    kpis.vehicles_repaired = int(df["time_repair_completed"].notna().sum())
    kpis.vehicles_pending = kpis.total_breakdowns - kpis.vehicles_repaired

    # Response times
    response_times = df["response_time_mins"].dropna()
    if len(response_times) > 0:
        kpis.mean_response_time = float(response_times.mean())
        kpis.median_response_time = float(response_times.median())
        kpis.max_response_time = float(response_times.max())
        kpis.p90_response_time = float(response_times.quantile(0.9))

    # Recovery times
    recovery_times = df["recovery_time_mins"].dropna()
    if len(recovery_times) > 0:
        kpis.mean_recovery_time = float(recovery_times.mean())

    # Repair times
    repair_times = df["repair_time_mins"].dropna()
    if len(repair_times) > 0:
        kpis.mean_repair_time = float(repair_times.mean())

    # Total downtime
    downtime = df["total_downtime_mins"].dropna()
    if len(downtime) > 0:
        kpis.mean_total_downtime = float(downtime.mean())
        kpis.max_total_downtime = float(downtime.max())

    # Count recovery missions from dispatch events
    dispatch_events = [
        e for e in event_log.filter_by_type(EventType.VEHICLE_DISPATCHED)
        if e.details.get("breakdown_id")
    ]
    kpis.recovery_missions = len(dispatch_events)

    return kpis


@dataclass
class ResupplyKPIs:
    """Key Performance Indicators for ammunition resupply."""

    # Counts
    total_requests: int = 0
    requests_fulfilled: int = 0
    requests_partial: int = 0
    requests_pending: int = 0

    # Quantities
    total_requested: int = 0
    total_delivered: int = 0
    fulfillment_rate: Optional[float] = None

    # Time metrics (minutes)
    mean_wait_time: Optional[float] = None
    mean_delivery_time: Optional[float] = None
    median_delivery_time: Optional[float] = None
    max_delivery_time: Optional[float] = None
    p90_delivery_time: Optional[float] = None

    # Events
    stockout_events: int = 0
    logistics_missions: int = 0

    def to_dict(self) -> dict[str, Any]:
        return _to_python({
            "total_requests": self.total_requests,
            "requests_fulfilled": self.requests_fulfilled,
            "requests_partial": self.requests_partial,
            "requests_pending": self.requests_pending,
            "total_requested": self.total_requested,
            "total_delivered": self.total_delivered,
            "fulfillment_rate_pct": self.fulfillment_rate,
            "mean_wait_time_mins": self.mean_wait_time,
            "mean_delivery_time_mins": self.mean_delivery_time,
            "median_delivery_time_mins": self.median_delivery_time,
            "max_delivery_time_mins": self.max_delivery_time,
            "p90_delivery_time_mins": self.p90_delivery_time,
            "stockout_events": self.stockout_events,
            "logistics_missions": self.logistics_missions,
        })

    def summary(self) -> str:
        """Generate human-readable summary."""
        lines = [
            "=== Resupply KPIs ===",
            "",
            "Request Counts:",
            f"  Total:     {self.total_requests}",
            f"  Fulfilled: {self.requests_fulfilled}",
            f"  Partial:   {self.requests_partial}",
            f"  Pending:   {self.requests_pending}",
            "",
            "Quantities:",
            f"  Requested: {self.total_requested} units",
            f"  Delivered: {self.total_delivered} units",
            f"  Fulfillment Rate: {self._fmt(self.fulfillment_rate)}%",
            "",
            "Delivery Time (request -> delivery):",
            f"  Mean:   {self._fmt(self.mean_delivery_time)} mins",
            f"  Median: {self._fmt(self.median_delivery_time)} mins",
            f"  Max:    {self._fmt(self.max_delivery_time)} mins",
            f"  P90:    {self._fmt(self.p90_delivery_time)} mins",
            "",
            f"Stockout Events: {self.stockout_events}",
            f"Logistics Missions: {self.logistics_missions}",
        ]
        return "\n".join(lines)

    @staticmethod
    def _fmt(value: Optional[float]) -> str:
        return f"{value:.1f}" if value is not None else "N/A"


def compute_resupply_kpis(event_log: EventLog) -> ResupplyKPIs:
    """Compute Resupply KPIs from simulation event log."""
    kpis = ResupplyKPIs()

    requests = event_log.ammo_requests
    kpis.total_requests = len(requests)

    if not requests:
        return kpis

    # Convert to DataFrame for analysis
    df = event_log.ammo_requests_to_dataframe()

    # Quantities - ensure native int
    kpis.total_requested = int(df["quantity_requested"].sum())
    kpis.total_delivered = int(df["quantity_delivered"].sum())

    if kpis.total_requested > 0:
        kpis.fulfillment_rate = float((kpis.total_delivered / kpis.total_requested) * 100)

    # Request status counts - ensure native int
    kpis.requests_fulfilled = int(df["is_fulfilled"].sum())
    delivered_mask = df["time_delivered"].notna()
    partial_mask = delivered_mask & ~df["is_fulfilled"]
    kpis.requests_partial = int(partial_mask.sum())
    kpis.requests_pending = kpis.total_requests - int(delivered_mask.sum())

    # Wait times
    wait_times = df["wait_time_mins"].dropna()
    if len(wait_times) > 0:
        kpis.mean_wait_time = float(wait_times.mean())

    # Delivery times
    delivery_times = df["delivery_time_mins"].dropna()
    if len(delivery_times) > 0:
        kpis.mean_delivery_time = float(delivery_times.mean())
        kpis.median_delivery_time = float(delivery_times.median())
        kpis.max_delivery_time = float(delivery_times.max())
        kpis.p90_delivery_time = float(delivery_times.quantile(0.9))

    # Stockout events
    stockout_events = event_log.filter_by_type(EventType.STOCKOUT)
    kpis.stockout_events = len(stockout_events)

    # Count logistics missions from dispatch events
    dispatch_events = [
        e for e in event_log.filter_by_type(EventType.VEHICLE_DISPATCHED)
        if e.details.get("ammo_request_id")
    ]
    kpis.logistics_missions = len(dispatch_events)

    return kpis


def compute_all_kpis(event_log: EventLog) -> dict[str, Any]:
    """Compute all KPIs from event log.

    Returns dict with keys: medevac, recovery, resupply
    All values are JSON-serializable (native Python types).
    """
    return {
        "medevac": compute_medevac_kpis(event_log).to_dict(),
        "recovery": compute_recovery_kpis(event_log).to_dict(),
        "resupply": compute_resupply_kpis(event_log).to_dict(),
    }
