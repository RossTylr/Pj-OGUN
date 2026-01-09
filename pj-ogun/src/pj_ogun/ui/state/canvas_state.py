"""Canvas state management for scenario builder.

Manages the synchronisation between:
- Streamlit Flow component state (visual graph)
- Pydantic scenario models (validated data)
- Streamlit session state (persistence across reruns)
"""

from dataclasses import dataclass, field
from typing import Optional
from uuid import uuid4

import streamlit as st
from streamlit_flow import StreamlitFlowState
from streamlit_flow.elements import StreamlitFlowNode, StreamlitFlowEdge

from pj_ogun.models.enums import (
    NodeType,
    VehicleRole,
    VehicleClass,
    DemandMode,
    DemandType,
    Priority,
)
from pj_ogun.models.vehicles import VEHICLE_TYPE_LIBRARY


# Visual configuration for node types
NODE_CONFIG = {
    NodeType.COMBAT: {
        "icon": "position",
        "color": "#FF4444",
        "label": "Field Position",
        "style": {"backgroundColor": "#FF4444", "color": "white"},
    },
    NodeType.MEDICAL_ROLE1: {
        "icon": "medical",
        "color": "#44FF44",
        "label": "Role 1 Medical",
        "style": {"backgroundColor": "#44FF44", "color": "black"},
    },
    NodeType.MEDICAL_ROLE2: {
        "icon": "hospital",
        "color": "#00AA00",
        "label": "Role 2 Medical",
        "style": {"backgroundColor": "#00AA00", "color": "white"},
    },
    NodeType.REPAIR_WORKSHOP: {
        "icon": "workshop",
        "color": "#FFAA00",
        "label": "Workshop",
        "style": {"backgroundColor": "#FFAA00", "color": "black"},
    },
    NodeType.AMMO_POINT: {
        "icon": "ammo",
        "color": "#FF8800",
        "label": "Supply Point",
        "style": {"backgroundColor": "#FF8800", "color": "white"},
    },
    NodeType.FUEL_POINT: {
        "icon": "fuel",
        "color": "#8888FF",
        "label": "Fuel Point",
        "style": {"backgroundColor": "#8888FF", "color": "white"},
    },
    NodeType.HQ: {
        "icon": "hq",
        "color": "#FFFF00",
        "label": "HQ",
        "style": {"backgroundColor": "#FFFF00", "color": "black"},
    },
    NodeType.EXCHANGE_POINT: {
        "icon": "exchange",
        "color": "#AA88FF",
        "label": "Exchange Point",
        "style": {"backgroundColor": "#AA88FF", "color": "white"},
    },
    NodeType.FORWARD_ARMING: {
        "icon": "farp",
        "color": "#FF88AA",
        "label": "Forward Arming",
        "style": {"backgroundColor": "#FF88AA", "color": "white"},
    },
}

# Map node types to emoji for display
NODE_ICONS = {
    NodeType.COMBAT: "position",
    NodeType.MEDICAL_ROLE1: "Role 1",
    NodeType.MEDICAL_ROLE2: "Role 2",
    NodeType.REPAIR_WORKSHOP: "Workshop",
    NodeType.AMMO_POINT: "Ammo",
    NodeType.FUEL_POINT: "Fuel",
    NodeType.HQ: "HQ",
    NodeType.EXCHANGE_POINT: "XP",
    NodeType.FORWARD_ARMING: "FARP",
}


@dataclass
class NodeData:
    """Extended data stored with each node."""

    id: str
    name: str
    node_type: NodeType
    # Capacity
    treatment_slots: Optional[int] = None
    repair_bays: Optional[int] = None
    holding_capacity: Optional[int] = None
    storage_capacity: Optional[int] = None
    # Properties
    treatment_time_mins: Optional[float] = None
    triage_time_mins: Optional[float] = None
    repair_time_light: Optional[float] = None
    repair_time_medium: Optional[float] = None
    repair_time_heavy: Optional[float] = None
    initial_stock: Optional[int] = None
    resupply_interval_hours: Optional[float] = None


@dataclass
class VehicleEntry:
    """A vehicle in the fleet."""

    id: str
    type_id: str
    callsign: str
    start_location: str

    @property
    def role(self) -> VehicleRole:
        """Get the role from the type library."""
        if self.type_id in VEHICLE_TYPE_LIBRARY:
            return VehicleRole(VEHICLE_TYPE_LIBRARY[self.type_id]["role"])
        return VehicleRole.GENERAL_LOGISTICS


@dataclass
class ManualEvent:
    """A manual demand event."""

    id: str
    time_mins: float
    event_type: DemandType
    location: str
    quantity: int = 1
    priority: int = 2


@dataclass
class RateConfig:
    """Rate-based demand configuration."""

    id: str
    event_type: DemandType
    location: str
    rate_per_hour: float = 1.0
    priority_p1: float = 0.1
    priority_p2: float = 0.3
    priority_p3: float = 0.6


@dataclass
class CanvasState:
    """Complete state for the scenario builder canvas."""

    # Flow state (nodes and edges)
    flow_state: Optional[StreamlitFlowState] = None

    # Node extended data (keyed by node id)
    node_data: dict[str, NodeData] = field(default_factory=dict)

    # Vehicles
    vehicles: list[VehicleEntry] = field(default_factory=list)

    # Demand configuration
    demand_mode: DemandMode = DemandMode.MANUAL
    manual_events: list[ManualEvent] = field(default_factory=list)
    rate_configs: list[RateConfig] = field(default_factory=list)

    # Simulation config
    duration_hours: float = 8.0
    random_seed: int = 42
    enable_crew_fatigue: bool = False
    enable_breakdowns: bool = False

    # Scenario metadata
    scenario_name: str = "New Scenario"

    # Selection state
    selected_node_id: Optional[str] = None
    node_type_to_add: Optional[NodeType] = None


def init_canvas_state() -> CanvasState:
    """Initialize canvas state with empty scenario."""
    return CanvasState(
        flow_state=StreamlitFlowState(nodes=[], edges=[]),
    )


def get_canvas_state() -> CanvasState:
    """Get or create canvas state from session state."""
    if "canvas_state" not in st.session_state:
        st.session_state.canvas_state = init_canvas_state()
    return st.session_state.canvas_state


def create_flow_node(
    node_id: str,
    name: str,
    node_type: NodeType,
    x: float,
    y: float,
) -> StreamlitFlowNode:
    """Create a StreamlitFlowNode with proper styling."""
    config = NODE_CONFIG.get(node_type, NODE_CONFIG[NodeType.COMBAT])
    label = NODE_ICONS.get(node_type, "Node")

    return StreamlitFlowNode(
        id=node_id,
        pos=(x * 50, y * 50),  # Scale for better visual spacing
        data={
            "content": f"**{name}**\n{label}",
            "node_type": node_type.value,
            "name": name,
        },
        node_type="default",
        source_position="right",
        target_position="left",
        draggable=True,
        connectable=True,
        style={
            "backgroundColor": config["color"],
            "color": "white" if config["color"] not in ["#FFFF00", "#44FF44", "#FFAA00"] else "black",
            "padding": "10px",
            "borderRadius": "8px",
            "border": "2px solid #333",
            "minWidth": "100px",
            "textAlign": "center",
        },
    )


def get_node_position(flow_node: StreamlitFlowNode) -> tuple[float, float]:
    """Return node position across streamlit-flow versions."""
    pos = None
    if hasattr(flow_node, "pos") and flow_node.pos is not None:
        pos = flow_node.pos
    elif hasattr(flow_node, "position") and flow_node.position is not None:
        pos = flow_node.position
    elif hasattr(flow_node, "x") and hasattr(flow_node, "y"):
        pos = (flow_node.x, flow_node.y)

    if isinstance(pos, dict):
        return float(pos.get("x", 0.0)), float(pos.get("y", 0.0))
    if isinstance(pos, (list, tuple)) and len(pos) >= 2:
        return float(pos[0]), float(pos[1])
    return 0.0, 0.0


def create_flow_edge(
    edge_id: str,
    from_node: str,
    to_node: str,
    distance_km: float,
) -> StreamlitFlowEdge:
    """Create a StreamlitFlowEdge."""
    return StreamlitFlowEdge(
        id=edge_id,
        source=from_node,
        target=to_node,
        edge_type="default",
        animated=False,
        label=f"{distance_km:.1f} km",
        style={"stroke": "#666", "strokeWidth": 2},
    )


def scenario_to_flow_state(scenario_dict: dict) -> tuple[StreamlitFlowState, dict[str, NodeData]]:
    """Convert a scenario dictionary to flow state and node data."""
    nodes = []
    edges = []
    node_data = {}

    # Convert nodes
    for node in scenario_dict.get("nodes", []):
        node_id = node["id"]
        node_type = NodeType(node["type"])
        name = node.get("name", node_id)
        x = node["coordinates"]["x"]
        y = node["coordinates"]["y"]

        flow_node = create_flow_node(node_id, name, node_type, x, y)
        nodes.append(flow_node)

        # Store extended data
        capacity = node.get("capacity", {})
        properties = node.get("properties", {})

        node_data[node_id] = NodeData(
            id=node_id,
            name=name,
            node_type=node_type,
            treatment_slots=capacity.get("treatment_slots"),
            repair_bays=capacity.get("repair_bays"),
            holding_capacity=capacity.get("holding_casualties"),
            storage_capacity=capacity.get("storage_ammo"),
            treatment_time_mins=properties.get("treatment_time_mins"),
            triage_time_mins=properties.get("triage_time_mins"),
            repair_time_light=properties.get("repair_time_light_mins"),
            repair_time_medium=properties.get("repair_time_medium_mins"),
            repair_time_heavy=properties.get("repair_time_heavy_mins"),
            initial_stock=properties.get("initial_ammo_stock"),
            resupply_interval_hours=properties.get("resupply_interval_hours"),
        )

    # Convert edges
    for edge in scenario_dict.get("edges", []):
        from_node = edge.get("from") or edge.get("from_node")
        to_node = edge.get("to") or edge.get("to_node")
        distance = edge.get("distance_km", 1.0)
        edge_id = f"{from_node}-{to_node}"

        flow_edge = create_flow_edge(edge_id, from_node, to_node, distance)
        edges.append(flow_edge)

    return StreamlitFlowState(nodes=nodes, edges=edges), node_data


def flow_state_to_scenario_dict(canvas_state: CanvasState) -> dict:
    """Convert canvas state back to a scenario dictionary."""
    if not canvas_state.flow_state:
        return {}

    nodes = []
    edges = []

    # Convert nodes
    for flow_node in canvas_state.flow_state.nodes:
        node_id = flow_node.id
        data = canvas_state.node_data.get(node_id)

        if data:
            node_type = data.node_type.value
            name = data.name
        else:
            node_type = flow_node.data.get("node_type", "combat")
            name = flow_node.data.get("name", node_id)

        # Convert position back to coordinates
        pos_x, pos_y = get_node_position(flow_node)
        x = pos_x / 50
        y = pos_y / 50

        node_dict = {
            "id": node_id,
            "name": name,
            "type": node_type,
            "coordinates": {"x": x, "y": y},
        }

        # Add capacity if present
        if data:
            capacity = {}
            if data.treatment_slots is not None:
                capacity["treatment_slots"] = data.treatment_slots
            if data.repair_bays is not None:
                capacity["repair_bays"] = data.repair_bays
            if data.holding_capacity is not None:
                capacity["holding_casualties"] = data.holding_capacity
            if data.storage_capacity is not None:
                capacity["storage_ammo"] = data.storage_capacity
            if capacity:
                node_dict["capacity"] = capacity

            # Add properties if present
            properties = {}
            if data.treatment_time_mins is not None:
                properties["treatment_time_mins"] = data.treatment_time_mins
            if data.triage_time_mins is not None:
                properties["triage_time_mins"] = data.triage_time_mins
            if data.repair_time_light is not None:
                properties["repair_time_light_mins"] = data.repair_time_light
            if data.repair_time_medium is not None:
                properties["repair_time_medium_mins"] = data.repair_time_medium
            if data.repair_time_heavy is not None:
                properties["repair_time_heavy_mins"] = data.repair_time_heavy
            if data.initial_stock is not None:
                properties["initial_ammo_stock"] = data.initial_stock
            if data.resupply_interval_hours is not None:
                properties["resupply_interval_hours"] = data.resupply_interval_hours
            if properties:
                node_dict["properties"] = properties

        nodes.append(node_dict)

    # Convert edges
    for flow_edge in canvas_state.flow_state.edges:
        # Extract distance from label
        label = flow_edge.label or "1.0 km"
        try:
            distance = float(label.replace(" km", ""))
        except ValueError:
            distance = 1.0

        edge_dict = {
            "from": flow_edge.source,
            "to": flow_edge.target,
            "distance_km": distance,
            "bidirectional": True,
        }
        edges.append(edge_dict)

    # Convert vehicles
    vehicles = []
    for v in canvas_state.vehicles:
        vehicles.append({
            "id": v.id,
            "type_id": v.type_id,
            "callsign": v.callsign,
            "start_location": v.start_location,
        })

    # Convert vehicle types (include used types from library)
    used_types = set(v.type_id for v in canvas_state.vehicles)
    vehicle_types = []
    for type_id in used_types:
        if type_id in VEHICLE_TYPE_LIBRARY:
            vehicle_types.append(VEHICLE_TYPE_LIBRARY[type_id])

    # Convert demand
    demand = {"mode": canvas_state.demand_mode.value}

    if canvas_state.demand_mode == DemandMode.MANUAL:
        manual_events = []
        for event in canvas_state.manual_events:
            manual_events.append({
                "time_mins": event.time_mins,
                "type": event.event_type.value,
                "location": event.location,
                "quantity": event.quantity,
                "priority": event.priority,
            })
        demand["manual_events"] = manual_events
    else:
        rate_based = []
        for rc in canvas_state.rate_configs:
            rate_based.append({
                "type": rc.event_type.value,
                "location": rc.location,
                "rate_per_hour": rc.rate_per_hour,
                "priority_weights": {
                    1: rc.priority_p1,
                    2: rc.priority_p2,
                    3: rc.priority_p3,
                },
            })
        demand["rate_based"] = rate_based

    # Build config
    config = {
        "duration_hours": canvas_state.duration_hours,
        "random_seed": canvas_state.random_seed,
        "enable_crew_fatigue": canvas_state.enable_crew_fatigue,
        "enable_breakdowns": canvas_state.enable_breakdowns,
    }

    return {
        "name": canvas_state.scenario_name,
        "nodes": nodes,
        "edges": edges,
        "vehicle_types": vehicle_types,
        "vehicles": vehicles,
        "demand": demand,
        "config": config,
    }


def generate_callsign(role: VehicleRole, existing: list[str]) -> str:
    """Generate next available callsign for a vehicle role."""
    import re

    prefixes = {
        VehicleRole.AMBULANCE: "MEDIC",
        VehicleRole.RECOVERY: "WRECKER",
        VehicleRole.AMMO_LOGISTICS: "CARGO",
        VehicleRole.FUEL_LOGISTICS: "PETROL",
        VehicleRole.GENERAL_LOGISTICS: "LOGGY",
    }
    prefix = prefixes.get(role, "VEH")

    pattern = re.compile(rf"^{prefix}\s*(\d+)$", re.IGNORECASE)
    used_numbers = set()
    for cs in existing:
        match = pattern.match(cs)
        if match:
            used_numbers.add(int(match.group(1)))

    next_num = 1
    while next_num in used_numbers:
        next_num += 1

    return f"{prefix} {next_num}"
