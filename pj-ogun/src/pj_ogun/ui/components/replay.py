"""Animation and replay component for simulation playback.

Phase 5: Pre-computed replay from EventLog with:
- Playback controls (play/pause, speed, scrubber)
- Vehicle position interpolation
- Event markers with priority colours
"""

import time
from dataclasses import dataclass, field
from typing import Optional

import streamlit as st
import plotly.graph_objects as go
import networkx as nx

from pj_ogun.models.enums import EventType, VehicleRole, VehicleState


# State colours for vehicles
STATE_COLORS = {
    VehicleState.IDLE: "#22CC22",
    VehicleState.TRANSITING_UNLADEN: "#2288FF",
    VehicleState.TRANSITING_LADEN: "#2288FF",
    VehicleState.LOADING: "#FFAA00",
    VehicleState.UNLOADING: "#FFAA00",
    VehicleState.HOOKUP: "#FFAA00",
    VehicleState.BROKEN_DOWN: "#FF4444",
    VehicleState.CREW_REST: "#888888",
    VehicleState.UNDER_REPAIR: "#FF8888",
    VehicleState.MAINTENANCE: "#888888",
}

# Role symbols for vehicles
ROLE_SYMBOLS = {
    VehicleRole.AMBULANCE: "cross",
    VehicleRole.RECOVERY: "square",
    VehicleRole.AMMO_LOGISTICS: "diamond",
    VehicleRole.FUEL_LOGISTICS: "diamond",
    VehicleRole.GENERAL_LOGISTICS: "diamond",
}

# Priority colours for casualties
PRIORITY_COLORS = {
    1: "#FF0000",  # Red - Urgent
    2: "#FF8800",  # Orange - Priority
    3: "#FFCC00",  # Yellow - Routine
    4: "#88FF88",  # Green - Convenience
}


@dataclass
class PlaybackState:
    """Controls animation playback."""

    is_playing: bool = False
    current_time_mins: float = 0.0
    playback_speed: float = 1.0
    duration_mins: float = 480.0
    last_update_time: float = 0.0

    # Cache of event times for jumping
    event_times: list[float] = field(default_factory=list)

    def advance(self, real_delta_ms: float) -> None:
        """Advance simulation time based on real time elapsed."""
        if not self.is_playing:
            return

        # Convert real ms to simulation minutes
        # At 1x speed: 1 real second = 1 sim minute
        sim_delta = (real_delta_ms / 1000) * self.playback_speed

        self.current_time_mins = min(
            self.current_time_mins + sim_delta,
            self.duration_mins,
        )

        if self.current_time_mins >= self.duration_mins:
            self.is_playing = False

    def jump_to_next_event(self) -> None:
        """Jump to next event after current time."""
        future_events = [t for t in self.event_times if t > self.current_time_mins + 0.1]
        if future_events:
            self.current_time_mins = future_events[0]

    def jump_to_prev_event(self) -> None:
        """Jump to previous event before current time."""
        past_events = [t for t in self.event_times if t < self.current_time_mins - 0.1]
        if past_events:
            self.current_time_mins = past_events[-1]


def get_playback_state() -> PlaybackState:
    """Get or create playback state from session state."""
    if "playback_state" not in st.session_state:
        st.session_state.playback_state = PlaybackState()
    return st.session_state.playback_state


def build_event_times(event_log) -> list[float]:
    """Extract unique event times from log for jumping."""
    times = set()
    for event in event_log.events:
        times.add(event.time_mins)
    return sorted(times)


def build_network_graph(scenario_data: dict) -> nx.Graph:
    """Build NetworkX graph from scenario data."""
    G = nx.Graph()

    # Add nodes
    for node in scenario_data.get("nodes", []):
        G.add_node(
            node["id"],
            x=node["coordinates"]["x"],
            y=node["coordinates"]["y"],
            name=node.get("name", node["id"]),
            node_type=node["type"],
        )

    # Add edges
    for edge in scenario_data.get("edges", []):
        from_node = edge.get("from") or edge.get("from_node")
        to_node = edge.get("to") or edge.get("to_node")
        G.add_edge(
            from_node,
            to_node,
            distance_km=edge.get("distance_km", 1.0),
        )

    return G


def get_vehicle_state_at_time(
    vehicle_id: str,
    current_time: float,
    event_log,
) -> tuple[Optional[str], VehicleState]:
    """Get vehicle location and state at given time."""
    location = None
    state = VehicleState.IDLE

    # Find most recent events for this vehicle
    vehicle_events = [
        e for e in event_log.events
        if e.entity_id == vehicle_id and e.time_mins <= current_time
    ]
    vehicle_events.sort(key=lambda e: e.time_mins)

    for event in vehicle_events:
        if event.location:
            location = event.location

        # Update state based on event type
        if event.event_type == EventType.VEHICLE_DISPATCHED:
            state = VehicleState.TRANSITING_UNLADEN
        elif event.event_type == EventType.VEHICLE_ARRIVED:
            state = VehicleState.IDLE
        elif event.event_type == EventType.LOADING_STARTED:
            state = VehicleState.LOADING
        elif event.event_type == EventType.LOADING_COMPLETED:
            state = VehicleState.TRANSITING_LADEN
        elif event.event_type == EventType.UNLOADING_STARTED:
            state = VehicleState.UNLOADING
        elif event.event_type == EventType.UNLOADING_COMPLETED:
            state = VehicleState.IDLE
        elif event.event_type == EventType.VEHICLE_RETURNED:
            state = VehicleState.IDLE
        elif event.event_type == EventType.HOOKUP_STARTED:
            state = VehicleState.HOOKUP
        elif event.event_type == EventType.HOOKUP_COMPLETED:
            state = VehicleState.TRANSITING_LADEN
        elif event.event_type == EventType.CREW_REST_STARTED:
            state = VehicleState.CREW_REST
        elif event.event_type == EventType.CREW_REST_ENDED:
            state = VehicleState.IDLE

    return location, state


def get_vehicle_position_at_time(
    vehicle_id: str,
    current_time: float,
    event_log,
    graph: nx.Graph,
) -> tuple[float, float]:
    """Calculate interpolated vehicle position at given time."""
    # Get events for this vehicle
    vehicle_events = [
        e for e in event_log.events
        if e.entity_id == vehicle_id
    ]
    vehicle_events.sort(key=lambda e: e.time_mins)

    # Find the bracketing events
    last_location = None
    last_time = 0.0
    next_location = None
    next_time = None

    for event in vehicle_events:
        if event.time_mins <= current_time:
            if event.location:
                last_location = event.location
                last_time = event.time_mins

            # Check for departure to destination
            if event.event_type == EventType.VEHICLE_DISPATCHED:
                dest = event.details.get("destination")
                if dest:
                    next_location = dest
                    # Find arrival time
                    for future_event in vehicle_events:
                        if (future_event.time_mins > event.time_mins and
                            future_event.event_type == EventType.VEHICLE_ARRIVED):
                            next_time = future_event.time_mins
                            break
        else:
            break

    # If not in transit, return last known location
    if (next_location is None or next_time is None or
        current_time >= next_time or last_location is None):
        if last_location and last_location in graph.nodes:
            node = graph.nodes[last_location]
            return (node["x"], node["y"])
        return (0, 0)

    # Interpolate position
    progress = (current_time - last_time) / (next_time - last_time) if next_time > last_time else 0

    if last_location in graph.nodes and next_location in graph.nodes:
        start = graph.nodes[last_location]
        end = graph.nodes[next_location]
        return (
            start["x"] + (end["x"] - start["x"]) * progress,
            start["y"] + (end["y"] - start["y"]) * progress,
        )

    return (0, 0)


def get_active_casualties(
    current_time: float,
    event_log,
) -> list[dict]:
    """Get casualties that are waiting for collection at current time."""
    active = []

    for casualty in event_log.casualties:
        # Casualty exists if generated before current time
        if casualty.time_generated > current_time:
            continue

        # Casualty is active if not yet collected
        if casualty.time_collected is None or casualty.time_collected > current_time:
            active.append({
                "id": casualty.id,
                "location": casualty.origin_node,
                "priority": casualty.priority,
                "time_generated": casualty.time_generated,
            })

    return active


def render_animated_map(
    current_time: float,
    scenario_data: dict,
    event_log,
    graph: nx.Graph,
) -> go.Figure:
    """Render the map at the given time."""
    fig = go.Figure()

    # Draw edges
    for edge in scenario_data.get("edges", []):
        from_node = edge.get("from") or edge.get("from_node")
        to_node = edge.get("to") or edge.get("to_node")

        if from_node in graph.nodes and to_node in graph.nodes:
            n1 = graph.nodes[from_node]
            n2 = graph.nodes[to_node]

            fig.add_trace(go.Scatter(
                x=[n1["x"], n2["x"]],
                y=[n1["y"], n2["y"]],
                mode="lines",
                line=dict(color="#CCCCCC", width=2),
                hoverinfo="skip",
                showlegend=False,
            ))

    # Draw nodes
    node_x = []
    node_y = []
    node_text = []
    node_colors = []

    NODE_TYPE_COLORS = {
        "combat": "#FF4444",
        "medical_role1": "#44FF44",
        "medical_role2": "#00AA00",
        "repair_workshop": "#FFAA00",
        "ammo_point": "#FF8800",
        "fuel_point": "#8888FF",
        "hq": "#FFFF00",
    }

    for node_id, node_data in graph.nodes(data=True):
        node_x.append(node_data["x"])
        node_y.append(node_data["y"])
        node_text.append(node_data.get("name", node_id))
        node_colors.append(NODE_TYPE_COLORS.get(node_data.get("node_type"), "#888888"))

    fig.add_trace(go.Scatter(
        x=node_x,
        y=node_y,
        mode="markers+text",
        marker=dict(size=20, color=node_colors, line=dict(width=2, color="white")),
        text=node_text,
        textposition="top center",
        textfont=dict(size=10),
        hoverinfo="text",
        showlegend=False,
    ))

    # Draw active casualties
    active_casualties = get_active_casualties(current_time, event_log)
    for cas in active_casualties:
        if cas["location"] in graph.nodes:
            node = graph.nodes[cas["location"]]
            color = PRIORITY_COLORS.get(cas["priority"], "#FF8800")

            # Offset slightly to not overlap with node
            offset_x = 1.5
            offset_y = -1.5

            fig.add_trace(go.Scatter(
                x=[node["x"] + offset_x],
                y=[node["y"] + offset_y],
                mode="markers",
                marker=dict(
                    size=12,
                    color=color,
                    symbol="x",
                    line=dict(width=2, color="white"),
                ),
                hovertext=f"Casualty P{cas['priority']}<br>{cas['id']}",
                hoverinfo="text",
                showlegend=False,
            ))

    # Draw vehicles
    vehicles = scenario_data.get("vehicles", [])
    vehicle_types = {vt["id"]: vt for vt in scenario_data.get("vehicle_types", [])}

    for vehicle in vehicles:
        vehicle_id = vehicle["id"]
        type_id = vehicle.get("type_id", "")
        callsign = vehicle.get("callsign", vehicle_id)

        # Get vehicle type info
        vtype = vehicle_types.get(type_id, {})
        role_str = vtype.get("role", "general_logistics")
        try:
            role = VehicleRole(role_str)
        except ValueError:
            role = VehicleRole.GENERAL_LOGISTICS

        # Get position and state
        x, y = get_vehicle_position_at_time(vehicle_id, current_time, event_log, graph)
        _, state = get_vehicle_state_at_time(vehicle_id, current_time, event_log)

        color = STATE_COLORS.get(state, "#888888")
        symbol = ROLE_SYMBOLS.get(role, "circle")

        fig.add_trace(go.Scatter(
            x=[x],
            y=[y],
            mode="markers+text",
            marker=dict(
                size=15,
                color=color,
                symbol=symbol,
                line=dict(width=2, color="white"),
            ),
            text=[callsign],
            textposition="bottom center",
            textfont=dict(size=9),
            hovertext=f"<b>{callsign}</b><br>State: {state.value}",
            hoverinfo="text",
            showlegend=False,
        ))

    # Update layout
    fig.update_layout(
        height=450,
        margin=dict(l=20, r=20, t=20, b=20),
        xaxis=dict(
            showgrid=True,
            zeroline=False,
            title="X (km)",
        ),
        yaxis=dict(
            showgrid=True,
            zeroline=False,
            title="Y (km)",
            scaleanchor="x",
            scaleratio=1,
        ),
        showlegend=False,
    )

    return fig


def render_events_at_time(current_time: float, event_log) -> None:
    """Render events occurring at or near the current time."""
    # Find events within +/- 1 minute
    nearby_events = [
        e for e in event_log.events
        if abs(e.time_mins - current_time) < 1.0
    ]

    if nearby_events:
        st.markdown("**Current Events:**")
        for event in nearby_events[:5]:  # Limit to 5
            st.caption(f"T+{event.time_mins:.0f}: {event.event_type.value} - {event.entity_id}")
    else:
        st.caption("No events at this time")


def render_replay_tab() -> None:
    """Render the full replay tab with playback controls and animated map."""
    st.header("Simulation Replay")
    st.markdown("Watch an animated timeline of your simulation. See how vehicles respond to events and move across the network.")

    if "scenario_data" not in st.session_state:
        st.warning("No scenario loaded. Please load or build a scenario first.")
        return

    if "event_log" not in st.session_state:
        st.warning("No simulation results. Please run a simulation first to watch the replay.")
        st.info("Go to the **Run Simulation** tab and click 'Run Simulation' to generate results.")
        return

    with st.expander("How to use the replay", expanded=False):
        st.markdown("""
        **Controls:**
        - **Play/Pause** - Start or stop the animation
        - **Speed** - Adjust how fast time passes (1x = real-time, 10x = 10 minutes per second)
        - **Prev/Next** - Jump to the previous or next event
        - **Slider** - Drag to any point in time

        **What you're seeing:**
        - **Colored circles** = Locations (color indicates type)
        - **Moving symbols** = Vehicles (cross = ambulance, square = recovery, diamond = logistics)
        - **X markers** = Active casualties waiting for pickup (color indicates priority)

        **Vehicle colors show status:**
        - Green = Idle, ready for tasking
        - Blue = Moving/in transit
        - Amber = Loading or unloading
        - Red = Broken down
        - Grey = Crew resting
        """)

    scenario_data = st.session_state["scenario_data"]
    event_log = st.session_state["event_log"]

    # Initialize playback state
    playback = get_playback_state()

    # Build graph and event times if needed
    if "replay_graph" not in st.session_state:
        st.session_state.replay_graph = build_network_graph(scenario_data)

    graph = st.session_state.replay_graph

    if not playback.event_times:
        playback.event_times = build_event_times(event_log)

    # Set duration from scenario
    duration_hours = scenario_data.get("config", {}).get("duration_hours", 8)
    playback.duration_mins = float(duration_hours) * 60.0

    # === Control Bar ===
    st.subheader("Playback Controls")
    col1, col2, col3, col4, col5, col6 = st.columns([1, 1, 1, 1, 1.5, 1.5])

    with col1:
        if st.button("Reset", help="Jump back to the start of the simulation"):
            playback.current_time_mins = 0
            playback.is_playing = False
            st.rerun()

    with col2:
        if st.button("Prev", help="Jump to the previous event"):
            playback.jump_to_prev_event()
            st.rerun()

    with col3:
        if playback.is_playing:
            if st.button("Pause", type="primary"):
                playback.is_playing = False
                st.rerun()
        else:
            if st.button("Play", type="primary"):
                playback.is_playing = True
                playback.last_update_time = time.time()
                st.rerun()

    with col4:
        if st.button("Next", help="Jump to the next event"):
            playback.jump_to_next_event()
            st.rerun()

    with col5:
        speed_options = [0.5, 1.0, 2.0, 5.0, 10.0]
        speed_idx = speed_options.index(playback.playback_speed) if playback.playback_speed in speed_options else 1
        new_speed = st.selectbox(
            "Playback Speed",
            options=speed_options,
            index=speed_idx,
            format_func=lambda x: f"{x}x speed",
            label_visibility="collapsed",
            help="How fast time passes in the replay (1x = 1 sim minute per real second)",
        )
        if new_speed != playback.playback_speed:
            playback.playback_speed = new_speed

    with col6:
        hours = int(playback.current_time_mins // 60)
        mins = int(playback.current_time_mins % 60)
        st.markdown(f"### T+{hours:02d}:{mins:02d}")
        st.caption("Simulation time")

    # === Time Scrubber ===
    new_time = st.slider(
        "Time",
        min_value=0.0,
        max_value=float(playback.duration_mins),
        value=float(playback.current_time_mins),
        step=1.0,
        format="%.0f mins",
        label_visibility="collapsed",
    )

    if abs(new_time - playback.current_time_mins) > 0.5:
        playback.current_time_mins = new_time
        playback.is_playing = False

    # === Map ===
    fig = render_animated_map(
        playback.current_time_mins,
        scenario_data,
        event_log,
        graph,
    )
    st.plotly_chart(fig, use_container_width=True)

    # === Events Panel ===
    st.subheader("Activity Log")
    render_events_at_time(playback.current_time_mins, event_log)

    # === Legend ===
    with st.expander("Map Legend & Symbol Guide"):
        col1, col2 = st.columns(2)

        with col1:
            st.markdown("**Vehicle Status Colors**")
            st.markdown("- **Green**: Idle - available for tasking")
            st.markdown("- **Blue**: In transit - moving between locations")
            st.markdown("- **Amber**: Loading/Unloading - at a location handling cargo/patients")
            st.markdown("- **Red**: Broken down - needs recovery")
            st.markdown("- **Grey**: Crew rest - temporarily unavailable")

        with col2:
            st.markdown("**Casualty Priority (X markers)**")
            st.markdown("- **Red X**: P1 Urgent - life-threatening, immediate response")
            st.markdown("- **Orange X**: P2 Priority - serious, prompt response")
            st.markdown("- **Yellow X**: P3 Routine - stable, can wait")
            st.markdown("")
            st.markdown("**Vehicle Symbols**")
            st.markdown("- **+** Cross: Ambulance")
            st.markdown("- **Square**: Recovery vehicle")
            st.markdown("- **Diamond**: Logistics vehicle")

    # === Auto-advance ===
    if playback.is_playing:
        current_time = time.time()
        delta_ms = (current_time - playback.last_update_time) * 1000
        playback.last_update_time = current_time

        playback.advance(delta_ms)

        # Refresh at ~30fps
        time.sleep(0.033)
        st.rerun()
