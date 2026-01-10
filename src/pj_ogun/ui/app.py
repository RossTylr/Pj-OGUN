"""Pj-OGUN Streamlit Application.

Run with: streamlit run src/pj_ogun/ui/app.py
"""

import json
from pathlib import Path

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# Page config must be first
st.set_page_config(
    page_title="Pj-OGUN",
    page_icon="gear",
    layout="wide",
)

# Import components after page config
from pj_ogun.ui.components.canvas import render_network_canvas, render_node_palette, render_edge_editor
from pj_ogun.ui.components.node_panel import render_node_panel
from pj_ogun.ui.components.vehicle_builder import render_vehicle_builder
from pj_ogun.ui.components.demand_builder import render_demand_builder
from pj_ogun.ui.components.replay import render_replay_tab
from pj_ogun.ui.state.canvas_state import (
    get_canvas_state,
    scenario_to_flow_state,
    flow_state_to_scenario_dict,
)


# Node type icons and colors for legacy display
NODE_TYPES = {
    "combat": {"icon": "position", "color": "#FF4444", "label": "Field Position"},
    "medical_role1": {"icon": "R1", "color": "#44FF44", "label": "Role 1 Medical"},
    "medical_role2": {"icon": "R2", "color": "#00AA00", "label": "Role 2 Medical"},
    "repair_workshop": {"icon": "WS", "color": "#FFAA00", "label": "Workshop"},
    "ammo_point": {"icon": "AP", "color": "#FF8800", "label": "Ammo Point"},
    "fuel_point": {"icon": "FP", "color": "#8888FF", "label": "Fuel Point"},
    "hq": {"icon": "HQ", "color": "#FFFF00", "label": "HQ"},
}


# Phase 6: Scenario Templates for multi-echelon networks
SCENARIO_TEMPLATES = {
    "Basic MEDEVAC (4 nodes)": {
        "name": "Basic MEDEVAC Exercise",
        "description": "Simple evacuation chain: 2 combat positions → Role 1 → Role 2",
        "nodes": [
            {"id": "combat_1", "name": "Alpha Position", "type": "combat", "coordinates": {"x": 2, "y": 3}},
            {"id": "combat_2", "name": "Bravo Position", "type": "combat", "coordinates": {"x": 2, "y": 7}},
            {"id": "r1_aid", "name": "Aid Station", "type": "medical_role1", "coordinates": {"x": 6, "y": 5},
             "capacity": {"treatment_slots": 2, "holding_casualties": 8},
             "properties": {"treatment_time_mins": 15}},
            {"id": "r2_hospital", "name": "Field Hospital", "type": "medical_role2", "coordinates": {"x": 10, "y": 5},
             "capacity": {"treatment_slots": 4, "holding_casualties": 20},
             "properties": {"treatment_time_mins": 45, "triage_time_mins": 5}},
        ],
        "edges": [
            {"from": "combat_1", "to": "r1_aid", "distance_km": 8.0, "bidirectional": True},
            {"from": "combat_2", "to": "r1_aid", "distance_km": 6.0, "bidirectional": True},
            {"from": "r1_aid", "to": "r2_hospital", "distance_km": 15.0, "bidirectional": True},
        ],
        "vehicles": [
            {"id": "amb_1", "type_id": "amb_light", "callsign": "MEDIC 1", "start_location": "r1_aid"},
            {"id": "amb_2", "type_id": "amb_light", "callsign": "MEDIC 2", "start_location": "r1_aid"},
        ],
        "demand": {
            "mode": "manual",
            "manual_events": [
                {"time_mins": 30, "type": "casualty", "location": "combat_1", "quantity": 1, "priority": 2},
                {"time_mins": 60, "type": "casualty", "location": "combat_2", "quantity": 2, "priority": 1},
                {"time_mins": 120, "type": "casualty", "location": "combat_1", "quantity": 1, "priority": 3},
            ]
        },
        "config": {"duration_hours": 4, "random_seed": 42, "enable_crew_fatigue": False, "enable_breakdowns": False},
    },
    "Battalion Support (10 nodes)": {
        "name": "Battalion Support Operations",
        "description": "Multi-echelon: 4 combat → 2 Role 1 → Role 2 + logistics chain",
        "nodes": [
            # Combat positions
            {"id": "combat_a", "name": "Alpha Company", "type": "combat", "coordinates": {"x": 1, "y": 2}},
            {"id": "combat_b", "name": "Bravo Company", "type": "combat", "coordinates": {"x": 1, "y": 5}},
            {"id": "combat_c", "name": "Charlie Company", "type": "combat", "coordinates": {"x": 1, "y": 8}},
            {"id": "combat_d", "name": "Delta Company", "type": "combat", "coordinates": {"x": 1, "y": 11}},
            # Medical chain
            {"id": "r1_fwd", "name": "Forward Aid Post", "type": "medical_role1", "coordinates": {"x": 5, "y": 3.5},
             "capacity": {"treatment_slots": 2, "holding_casualties": 6}},
            {"id": "r1_main", "name": "Main Aid Station", "type": "medical_role1", "coordinates": {"x": 5, "y": 9.5},
             "capacity": {"treatment_slots": 3, "holding_casualties": 10}},
            {"id": "r2_hosp", "name": "Field Hospital", "type": "medical_role2", "coordinates": {"x": 10, "y": 6.5},
             "capacity": {"treatment_slots": 6, "holding_casualties": 30}},
            # Logistics
            {"id": "ammo_pt", "name": "Ammo Point", "type": "ammo_point", "coordinates": {"x": 8, "y": 2},
             "capacity": {"storage_ammo": 10000}, "properties": {"initial_ammo_stock": 8000}},
            {"id": "fuel_pt", "name": "Fuel Point", "type": "fuel_point", "coordinates": {"x": 8, "y": 11},
             "capacity": {"storage_fuel": 20000}},
            # Support
            {"id": "workshop", "name": "Workshop", "type": "repair_workshop", "coordinates": {"x": 12, "y": 6.5},
             "capacity": {"repair_bays": 3}},
        ],
        "edges": [
            {"from": "combat_a", "to": "r1_fwd", "distance_km": 5.0, "bidirectional": True},
            {"from": "combat_b", "to": "r1_fwd", "distance_km": 4.0, "bidirectional": True},
            {"from": "combat_c", "to": "r1_main", "distance_km": 4.0, "bidirectional": True},
            {"from": "combat_d", "to": "r1_main", "distance_km": 5.0, "bidirectional": True},
            {"from": "r1_fwd", "to": "r2_hosp", "distance_km": 12.0, "bidirectional": True},
            {"from": "r1_main", "to": "r2_hosp", "distance_km": 10.0, "bidirectional": True},
            {"from": "ammo_pt", "to": "combat_a", "distance_km": 10.0, "bidirectional": True},
            {"from": "ammo_pt", "to": "combat_b", "distance_km": 8.0, "bidirectional": True},
            {"from": "fuel_pt", "to": "combat_c", "distance_km": 8.0, "bidirectional": True},
            {"from": "fuel_pt", "to": "combat_d", "distance_km": 6.0, "bidirectional": True},
            {"from": "workshop", "to": "r2_hosp", "distance_km": 5.0, "bidirectional": True},
        ],
        "vehicles": [
            {"id": "amb_1", "type_id": "amb_medium", "callsign": "MEDIC 1", "start_location": "r1_fwd"},
            {"id": "amb_2", "type_id": "amb_medium", "callsign": "MEDIC 2", "start_location": "r1_fwd"},
            {"id": "amb_3", "type_id": "amb_medium", "callsign": "MEDIC 3", "start_location": "r1_main"},
            {"id": "amb_4", "type_id": "amb_medium", "callsign": "MEDIC 4", "start_location": "r1_main"},
            {"id": "rec_1", "type_id": "rec_medium", "callsign": "WRECKER 1", "start_location": "workshop"},
            {"id": "log_1", "type_id": "log_ammo_medium", "callsign": "CARGO 1", "start_location": "ammo_pt"},
        ],
        "demand": {
            "mode": "rate_based",
            "rate_based": [
                {"type": "casualty", "location": "combat_a", "rate_per_hour": 0.5, "priority_weights": {1: 0.1, 2: 0.3, 3: 0.6}},
                {"type": "casualty", "location": "combat_b", "rate_per_hour": 0.5, "priority_weights": {1: 0.1, 2: 0.3, 3: 0.6}},
                {"type": "casualty", "location": "combat_c", "rate_per_hour": 0.5, "priority_weights": {1: 0.1, 2: 0.3, 3: 0.6}},
                {"type": "casualty", "location": "combat_d", "rate_per_hour": 0.5, "priority_weights": {1: 0.1, 2: 0.3, 3: 0.6}},
            ]
        },
        "config": {"duration_hours": 8, "random_seed": 42, "enable_crew_fatigue": False, "enable_breakdowns": True},
    },
    "Brigade TIRGOLD (20+ nodes)": {
        "name": "Brigade TIRGOLD Exercise",
        "description": "Full brigade: Role 1 → Role 2 → Role 3 chain with logistics and recovery",
        "nodes": [
            # Combat positions (8 companies)
            {"id": "cbt_a1", "name": "A Coy 1 Plt", "type": "combat", "coordinates": {"x": 1, "y": 1}},
            {"id": "cbt_a2", "name": "A Coy 2 Plt", "type": "combat", "coordinates": {"x": 1, "y": 3}},
            {"id": "cbt_b1", "name": "B Coy 1 Plt", "type": "combat", "coordinates": {"x": 1, "y": 5}},
            {"id": "cbt_b2", "name": "B Coy 2 Plt", "type": "combat", "coordinates": {"x": 1, "y": 7}},
            {"id": "cbt_c1", "name": "C Coy 1 Plt", "type": "combat", "coordinates": {"x": 1, "y": 9}},
            {"id": "cbt_c2", "name": "C Coy 2 Plt", "type": "combat", "coordinates": {"x": 1, "y": 11}},
            {"id": "cbt_d1", "name": "D Coy 1 Plt", "type": "combat", "coordinates": {"x": 1, "y": 13}},
            {"id": "cbt_d2", "name": "D Coy 2 Plt", "type": "combat", "coordinates": {"x": 1, "y": 15}},
            # Role 1 (4 aid posts)
            {"id": "r1_a", "name": "A Coy Aid Post", "type": "medical_role1", "coordinates": {"x": 4, "y": 2},
             "capacity": {"treatment_slots": 2, "holding_casualties": 6}},
            {"id": "r1_b", "name": "B Coy Aid Post", "type": "medical_role1", "coordinates": {"x": 4, "y": 6},
             "capacity": {"treatment_slots": 2, "holding_casualties": 6}},
            {"id": "r1_c", "name": "C Coy Aid Post", "type": "medical_role1", "coordinates": {"x": 4, "y": 10},
             "capacity": {"treatment_slots": 2, "holding_casualties": 6}},
            {"id": "r1_d", "name": "D Coy Aid Post", "type": "medical_role1", "coordinates": {"x": 4, "y": 14},
             "capacity": {"treatment_slots": 2, "holding_casualties": 6}},
            # Role 2 (2 surgical facilities)
            {"id": "r2_north", "name": "R2 North", "type": "medical_role2", "coordinates": {"x": 8, "y": 4},
             "capacity": {"treatment_slots": 4, "holding_casualties": 20}},
            {"id": "r2_south", "name": "R2 South", "type": "medical_role2", "coordinates": {"x": 8, "y": 12},
             "capacity": {"treatment_slots": 4, "holding_casualties": 20}},
            # Logistics chain
            {"id": "ammo_fwd", "name": "Fwd Ammo Pt", "type": "ammo_point", "coordinates": {"x": 3, "y": 8},
             "capacity": {"storage_ammo": 5000}},
            {"id": "ammo_main", "name": "Main ASP", "type": "ammo_point", "coordinates": {"x": 10, "y": 8},
             "capacity": {"storage_ammo": 20000}},
            {"id": "fuel_pt", "name": "Main Fuel Pt", "type": "fuel_point", "coordinates": {"x": 10, "y": 5},
             "capacity": {"storage_fuel": 50000}},
            # Recovery
            {"id": "ws_fwd", "name": "Fwd Workshop", "type": "repair_workshop", "coordinates": {"x": 6, "y": 8},
             "capacity": {"repair_bays": 2}},
            {"id": "ws_main", "name": "Main Workshop", "type": "repair_workshop", "coordinates": {"x": 12, "y": 8},
             "capacity": {"repair_bays": 4}},
            # HQ
            {"id": "hq", "name": "Brigade HQ", "type": "hq", "coordinates": {"x": 10, "y": 11}},
        ],
        "edges": [
            # Combat to R1
            {"from": "cbt_a1", "to": "r1_a", "distance_km": 4.0, "bidirectional": True},
            {"from": "cbt_a2", "to": "r1_a", "distance_km": 3.0, "bidirectional": True},
            {"from": "cbt_b1", "to": "r1_b", "distance_km": 4.0, "bidirectional": True},
            {"from": "cbt_b2", "to": "r1_b", "distance_km": 3.0, "bidirectional": True},
            {"from": "cbt_c1", "to": "r1_c", "distance_km": 4.0, "bidirectional": True},
            {"from": "cbt_c2", "to": "r1_c", "distance_km": 3.0, "bidirectional": True},
            {"from": "cbt_d1", "to": "r1_d", "distance_km": 4.0, "bidirectional": True},
            {"from": "cbt_d2", "to": "r1_d", "distance_km": 3.0, "bidirectional": True},
            # R1 to R2
            {"from": "r1_a", "to": "r2_north", "distance_km": 8.0, "bidirectional": True},
            {"from": "r1_b", "to": "r2_north", "distance_km": 6.0, "bidirectional": True},
            {"from": "r1_c", "to": "r2_south", "distance_km": 6.0, "bidirectional": True},
            {"from": "r1_d", "to": "r2_south", "distance_km": 8.0, "bidirectional": True},
            # Logistics
            {"from": "ammo_main", "to": "ammo_fwd", "distance_km": 10.0, "bidirectional": True},
            {"from": "ammo_fwd", "to": "cbt_b1", "distance_km": 6.0, "bidirectional": True},
            {"from": "ammo_fwd", "to": "cbt_c1", "distance_km": 6.0, "bidirectional": True},
            {"from": "fuel_pt", "to": "r2_north", "distance_km": 4.0, "bidirectional": True},
            # Recovery
            {"from": "ws_fwd", "to": "ws_main", "distance_km": 8.0, "bidirectional": True},
            {"from": "ws_fwd", "to": "r1_b", "distance_km": 5.0, "bidirectional": True},
            {"from": "ws_fwd", "to": "r1_c", "distance_km": 5.0, "bidirectional": True},
        ],
        "vehicles": [
            # Ambulances
            {"id": "amb_1", "type_id": "amb_medium", "callsign": "MEDIC 1", "start_location": "r1_a"},
            {"id": "amb_2", "type_id": "amb_medium", "callsign": "MEDIC 2", "start_location": "r1_b"},
            {"id": "amb_3", "type_id": "amb_medium", "callsign": "MEDIC 3", "start_location": "r1_c"},
            {"id": "amb_4", "type_id": "amb_medium", "callsign": "MEDIC 4", "start_location": "r1_d"},
            {"id": "amb_5", "type_id": "amb_medium", "callsign": "MEDIC 5", "start_location": "r2_north"},
            {"id": "amb_6", "type_id": "amb_medium", "callsign": "MEDIC 6", "start_location": "r2_south"},
            # Recovery
            {"id": "rec_1", "type_id": "rec_medium", "callsign": "WRECKER 1", "start_location": "ws_fwd"},
            {"id": "rec_2", "type_id": "rec_heavy", "callsign": "WRECKER 2", "start_location": "ws_main"},
            # Logistics
            {"id": "log_1", "type_id": "log_ammo_medium", "callsign": "CARGO 1", "start_location": "ammo_main"},
            {"id": "log_2", "type_id": "log_ammo_medium", "callsign": "CARGO 2", "start_location": "ammo_fwd"},
        ],
        "demand": {
            "mode": "rate_based",
            "rate_based": [
                {"type": "casualty", "location": "cbt_a1", "rate_per_hour": 0.3, "priority_weights": {1: 0.15, 2: 0.35, 3: 0.5}},
                {"type": "casualty", "location": "cbt_a2", "rate_per_hour": 0.3, "priority_weights": {1: 0.15, 2: 0.35, 3: 0.5}},
                {"type": "casualty", "location": "cbt_b1", "rate_per_hour": 0.4, "priority_weights": {1: 0.2, 2: 0.4, 3: 0.4}},
                {"type": "casualty", "location": "cbt_b2", "rate_per_hour": 0.4, "priority_weights": {1: 0.2, 2: 0.4, 3: 0.4}},
                {"type": "casualty", "location": "cbt_c1", "rate_per_hour": 0.4, "priority_weights": {1: 0.2, 2: 0.4, 3: 0.4}},
                {"type": "casualty", "location": "cbt_c2", "rate_per_hour": 0.4, "priority_weights": {1: 0.2, 2: 0.4, 3: 0.4}},
                {"type": "casualty", "location": "cbt_d1", "rate_per_hour": 0.3, "priority_weights": {1: 0.15, 2: 0.35, 3: 0.5}},
                {"type": "casualty", "location": "cbt_d2", "rate_per_hour": 0.3, "priority_weights": {1: 0.15, 2: 0.35, 3: 0.5}},
            ]
        },
        "config": {"duration_hours": 12, "random_seed": 42, "enable_crew_fatigue": True, "enable_breakdowns": True},
    },
}


def load_scenario_template(template_name: str) -> None:
    """Load a scenario template into the canvas state."""
    if template_name not in SCENARIO_TEMPLATES:
        st.error(f"Template '{template_name}' not found")
        return

    template = SCENARIO_TEMPLATES[template_name]

    # Convert to flow state and load
    flow_state, node_data = scenario_to_flow_state(template)
    canvas_state = get_canvas_state()

    canvas_state.flow_state = flow_state
    canvas_state.node_data = node_data
    canvas_state.scenario_name = template["name"]

    # Load vehicles
    from pj_ogun.ui.state.canvas_state import VehicleEntry
    canvas_state.vehicles = []
    for v in template.get("vehicles", []):
        canvas_state.vehicles.append(VehicleEntry(
            id=v["id"],
            type_id=v["type_id"],
            callsign=v.get("callsign", v["id"]),
            start_location=v["start_location"],
        ))

    # Load demand
    from pj_ogun.ui.state.canvas_state import ManualEvent, RateConfig
    from pj_ogun.models.enums import DemandMode, DemandType
    demand = template.get("demand", {})

    if demand.get("mode") == "manual":
        canvas_state.demand_mode = DemandMode.MANUAL
        canvas_state.manual_events = []
        for evt in demand.get("manual_events", []):
            canvas_state.manual_events.append(ManualEvent(
                id=f"evt_{len(canvas_state.manual_events)}",
                time_mins=evt["time_mins"],
                event_type=DemandType(evt["type"]),
                location=evt["location"],
                quantity=evt.get("quantity", 1),
                priority=evt.get("priority", 2),
            ))
    else:
        canvas_state.demand_mode = DemandMode.RATE_BASED
        canvas_state.rate_configs = []
        for rc in demand.get("rate_based", []):
            weights = rc.get("priority_weights", {1: 0.1, 2: 0.3, 3: 0.6})
            canvas_state.rate_configs.append(RateConfig(
                id=f"rate_{len(canvas_state.rate_configs)}",
                event_type=DemandType(rc["type"]),
                location=rc["location"],
                rate_per_hour=rc["rate_per_hour"],
                priority_p1=weights.get(1, 0.1),
                priority_p2=weights.get(2, 0.3),
                priority_p3=weights.get(3, 0.6),
            ))

    # Load config
    config = template.get("config", {})
    canvas_state.duration_hours = config.get("duration_hours", 8.0)
    canvas_state.random_seed = config.get("random_seed", 42)
    canvas_state.enable_crew_fatigue = config.get("enable_crew_fatigue", False)
    canvas_state.enable_breakdowns = config.get("enable_breakdowns", False)

    # Store for simulation
    st.session_state["scenario_data"] = template
    st.success(f"Loaded template: {template['name']}")


def main():
    st.title("Pj-OGUN")
    st.caption("Logistics & Field Operations Simulation Platform")

    # Sidebar for help and settings (always accessible)
    with st.sidebar:
        st.markdown("### Quick Actions")
        if st.button("Show Help Guide", use_container_width=True):
            st.session_state.show_help = True

        st.divider()
        st.markdown("### Scenario Templates")
        st.caption("Pre-built configurations for common exercises")

        template_selected = st.selectbox(
            "Load Template",
            options=["-- Select --", "Basic MEDEVAC (4 nodes)", "Battalion Support (10 nodes)", "Brigade TIRGOLD (20+ nodes)"],
            key="template_selector",
            label_visibility="collapsed",
        )

        if template_selected != "-- Select --":
            if st.button("Apply Template", type="primary", use_container_width=True):
                load_scenario_template(template_selected)
                st.rerun()

        st.divider()
        st.caption("v1.0 | Phase 6: Advanced Scenarios")

    # Show help modal/expander if requested or first visit
    show_help = st.session_state.get("show_help", False) or "has_seen_intro" not in st.session_state

    if show_help:
        with st.container():
            st.info("**Welcome to Pj-OGUN** - Field Operations Simulation Platform")

            col1, col2 = st.columns([2, 1])

            with col1:
                st.markdown("""
                **5-Step Workflow:**
                1. **Build** - Design your operational network (locations, vehicles, events)
                2. **Simulate** - Run the model to test your setup
                3. **Replay** - Watch an animated timeline
                4. **Analyze** - Review performance metrics
                5. **Export** - Download results for reports

                **Quick Start:** Use a template from the sidebar, or click "Load Example" in Build tab.
                """)

            with col2:
                st.markdown("""
                **Key Metrics:**
                - Response times
                - Resource utilization
                - Bottleneck identification
                - Capacity validation
                """)

            if st.button("Got it, let's start", type="primary"):
                st.session_state.has_seen_intro = True
                st.session_state.show_help = False
                st.rerun()

    # Tabs with clearer labels
    tab_builder, tab_simulate, tab_replay, tab_dashboard, tab_export = st.tabs([
        "1. Build Scenario",
        "2. Run Simulation",
        "3. Watch Replay",
        "4. View Results",
        "5. Export Data",
    ])

    # === SCENARIO BUILDER TAB (Phase 4) ===
    with tab_builder:
        render_scenario_builder()

    # === SIMULATE TAB ===
    with tab_simulate:
        render_simulate_tab()

    # === REPLAY TAB (Phase 5) ===
    with tab_replay:
        render_replay_tab()

    # === DASHBOARD TAB ===
    with tab_dashboard:
        render_dashboard_tab()

    # === EXPORT TAB ===
    with tab_export:
        render_export_tab()


def render_scenario_builder():
    """Render the Phase 4 interactive scenario builder with improved UX."""
    canvas_state = get_canvas_state()

    # Header with scenario name and quick actions
    col_title, col_name, col_actions = st.columns([1, 2, 2])

    with col_title:
        st.header("Build Scenario")

    with col_name:
        canvas_state.scenario_name = st.text_input(
            "Scenario Name",
            value=canvas_state.scenario_name,
            label_visibility="collapsed",
            placeholder="Enter scenario name...",
        )

    with col_actions:
        action_col1, action_col2, action_col3 = st.columns(3)
        with action_col1:
            uploaded = st.file_uploader(
                "Load",
                type=["json"],
                key="scenario_upload",
                label_visibility="collapsed",
            )
        with action_col2:
            example_path = Path(__file__).parent.parent.parent.parent / "scenarios" / "example_medevac.json"
            if example_path.exists() and st.button("Load Example", use_container_width=True):
                _load_example_scenario(canvas_state, example_path)
                st.rerun()
        with action_col3:
            if st.button("Validate", type="primary", use_container_width=True):
                _validate_and_save_scenario(canvas_state)

    # Handle file upload
    if uploaded:
        _handle_file_upload(canvas_state, uploaded)

    # Progress indicator showing build completeness
    _render_build_progress(canvas_state)

    st.divider()

    # Sub-tabs for cleaner organization (reduces cognitive overload)
    build_tab_network, build_tab_fleet, build_tab_events, build_tab_settings = st.tabs([
        "Network",
        "Fleet",
        "Events",
        "Settings",
    ])

    with build_tab_network:
        _render_network_subtab(canvas_state)

    with build_tab_fleet:
        _render_fleet_subtab(canvas_state)

    with build_tab_events:
        _render_events_subtab(canvas_state)

    with build_tab_settings:
        _render_settings_subtab(canvas_state)


def _render_build_progress(canvas_state) -> None:
    """Show progress indicator for scenario completeness."""
    node_count = len(canvas_state.flow_state.nodes) if canvas_state.flow_state else 0
    edge_count = len(canvas_state.flow_state.edges) if canvas_state.flow_state else 0
    vehicle_count = len(canvas_state.vehicles)
    event_count = len(canvas_state.manual_events) + len(canvas_state.rate_configs)

    # Calculate completion
    steps_complete = 0
    if node_count >= 2:
        steps_complete += 1
    if edge_count >= 1:
        steps_complete += 1
    if vehicle_count >= 1:
        steps_complete += 1
    if event_count >= 1:
        steps_complete += 1

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        status = "complete" if node_count >= 2 else "incomplete"
        st.caption(f"Nodes: {node_count}" + (" [ok]" if status == "complete" else " [need 2+]"))
    with col2:
        status = "complete" if edge_count >= 1 else "incomplete"
        st.caption(f"Routes: {edge_count}" + (" [ok]" if status == "complete" else " [need 1+]"))
    with col3:
        status = "complete" if vehicle_count >= 1 else "incomplete"
        st.caption(f"Vehicles: {vehicle_count}" + (" [ok]" if status == "complete" else " [need 1+]"))
    with col4:
        status = "complete" if event_count >= 1 else "incomplete"
        st.caption(f"Events: {event_count}" + (" [ok]" if status == "complete" else " [need 1+]"))


def _render_network_subtab(canvas_state) -> None:
    """Render the network building interface."""
    st.markdown("**Design your operational network.** Add locations, then connect them with routes.")

    col_palette, col_canvas = st.columns([1, 3])

    with col_palette:
        render_node_palette()
        st.divider()
        with st.expander("Route Distances", expanded=False):
            render_edge_editor()

    with col_canvas:
        render_network_canvas()
        # Node properties inline below canvas
        if canvas_state.selected_node_id:
            st.divider()
            render_node_panel()


def _render_fleet_subtab(canvas_state) -> None:
    """Render the fleet configuration interface."""
    st.markdown("**Configure your vehicle fleet.** Add ambulances, recovery vehicles, and logistics trucks.")

    if not canvas_state.flow_state or not canvas_state.flow_state.nodes:
        st.warning("Add locations to your network first (in the Network tab), then come back to add vehicles.")
        return

    render_vehicle_builder()


def _render_events_subtab(canvas_state) -> None:
    """Render the demand events interface."""
    st.markdown("**Define operational demand.** Specify when and where casualties or supply requests occur.")

    if not canvas_state.flow_state or not canvas_state.flow_state.nodes:
        st.warning("Add locations to your network first (in the Network tab), then define events.")
        return

    render_demand_builder()


def _render_settings_subtab(canvas_state) -> None:
    """Render simulation settings."""
    st.markdown("**Simulation parameters.** These settings control how the simulation runs.")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Duration & Randomness")
        canvas_state.duration_hours = st.number_input(
            "Duration (hours)",
            value=float(canvas_state.duration_hours),
            min_value=1.0,
            max_value=72.0,
            step=1.0,
            help="How long the simulated operation will run.",
        )
        canvas_state.random_seed = st.number_input(
            "Random Seed",
            value=canvas_state.random_seed,
            min_value=0,
            max_value=999999,
            help="Same seed = reproducible results. Change for different random outcomes.",
        )

    with col2:
        st.subheader("Realism Options")
        st.caption("Enable stress-testing features to simulate real-world complications.")
        canvas_state.enable_crew_fatigue = st.checkbox(
            "Crew Fatigue",
            value=canvas_state.enable_crew_fatigue,
            key="settings_enable_crew_fatigue",
            help="Crews require rest after extended operations, reducing vehicle availability.",
        )
        canvas_state.enable_breakdowns = st.checkbox(
            "Vehicle Breakdowns",
            value=canvas_state.enable_breakdowns,
            key="settings_enable_breakdowns",
            help="Vehicles may break down randomly, requiring recovery operations.",
        )


def _load_example_scenario(canvas_state, example_path: Path) -> None:
    """Load the example scenario file."""
    with open(example_path) as f:
        data = json.load(f)
    _apply_scenario_data(canvas_state, data)
    st.success("Loaded example scenario")


def _handle_file_upload(canvas_state, uploaded) -> None:
    """Handle uploaded JSON file."""
    try:
        data = json.load(uploaded)
        _apply_scenario_data(canvas_state, data)
        st.success(f"Loaded: {canvas_state.scenario_name}")
        st.rerun()
    except Exception as e:
        st.error(f"Failed to load: {e}")


def _apply_scenario_data(canvas_state, data: dict) -> None:
    """Apply loaded scenario data to canvas state."""
    from pj_ogun.ui.state.canvas_state import VehicleEntry, ManualEvent, RateConfig
    from pj_ogun.models.enums import DemandMode, DemandType

    # Convert to canvas state
    flow_state, node_data = scenario_to_flow_state(data)
    canvas_state.flow_state = flow_state
    canvas_state.node_data = node_data
    canvas_state.scenario_name = data.get("name", "Loaded Scenario")

    # Load vehicles
    canvas_state.vehicles = []
    for v in data.get("vehicles", []):
        canvas_state.vehicles.append(VehicleEntry(
            id=v["id"],
            type_id=v["type_id"],
            callsign=v.get("callsign", v["id"]),
            start_location=v["start_location"],
        ))

    # Load demand
    demand = data.get("demand", {})
    if demand.get("mode") == "manual":
        canvas_state.demand_mode = DemandMode.MANUAL
        canvas_state.manual_events = []
        for evt in demand.get("manual_events", []):
            canvas_state.manual_events.append(ManualEvent(
                id=f"evt_{len(canvas_state.manual_events)}",
                time_mins=evt["time_mins"],
                event_type=DemandType(evt["type"]),
                location=evt["location"],
                quantity=evt.get("quantity", 1),
                priority=evt.get("priority", 2),
            ))
    elif demand.get("mode") == "rate_based":
        canvas_state.demand_mode = DemandMode.RATE_BASED
        canvas_state.rate_configs = []
        for rc in demand.get("rate_based", []):
            weights = rc.get("priority_weights", {1: 0.1, 2: 0.3, 3: 0.6})
            canvas_state.rate_configs.append(RateConfig(
                id=f"rate_{len(canvas_state.rate_configs)}",
                event_type=DemandType(rc["type"]),
                location=rc["location"],
                rate_per_hour=rc["rate_per_hour"],
                priority_p1=weights.get(1, 0.1),
                priority_p2=weights.get(2, 0.3),
                priority_p3=weights.get(3, 0.6),
            ))

    # Load config
    config = data.get("config", {})
    canvas_state.duration_hours = config.get("duration_hours", 8.0)
    canvas_state.random_seed = config.get("random_seed", 42)
    canvas_state.enable_crew_fatigue = config.get("enable_crew_fatigue", False)
    canvas_state.enable_breakdowns = config.get("enable_breakdowns", False)

    # Store for simulation
    st.session_state["scenario_data"] = data


def _validate_and_save_scenario(canvas_state) -> None:
    """Validate and save the current scenario."""
    try:
        scenario_dict = flow_state_to_scenario_dict(canvas_state)

        # Validate with Pydantic
        from pj_ogun.models.scenario import Scenario
        scenario = Scenario.model_validate(scenario_dict)

        st.session_state["scenario_data"] = scenario_dict
        st.success(f"Scenario valid! {len(scenario.nodes)} locations, {len(scenario.vehicles)} vehicles. Ready to simulate.")
    except Exception as e:
        st.error(f"Validation error: {e}")


def render_simulate_tab():
    """Render the simulation execution tab with streamlined UX."""
    st.header("Run Simulation")

    if "scenario_data" not in st.session_state:
        st.warning("No scenario loaded.")
        st.markdown("""
        **To get started:**
        1. Go to **Build Scenario** tab and create a network
        2. Or use the **Scenario Templates** in the sidebar for a quick start
        3. Or click **Load Example** in Build tab
        """)
        return

    data = st.session_state["scenario_data"]
    canvas_state = get_canvas_state()

    # Show current scenario summary
    st.markdown(f"**Scenario:** {data.get('name', 'Unnamed')}")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Locations", len(data.get("nodes", [])))
    with col2:
        st.metric("Vehicles", len(data.get("vehicles", [])))
    with col3:
        st.metric("Duration", f"{canvas_state.duration_hours:.0f}h")
    with col4:
        features = []
        if canvas_state.enable_crew_fatigue:
            features.append("Fatigue")
        if canvas_state.enable_breakdowns:
            features.append("Breakdowns")
        st.metric("Realism", ", ".join(features) if features else "Standard")

    st.divider()

    # Quick override for seed (common use case: re-run with different randomness)
    col_seed, col_run = st.columns([1, 2])
    with col_seed:
        override_seed = st.number_input(
            "Random Seed (override)",
            value=canvas_state.random_seed,
            min_value=0,
            help="Change to get different random outcomes. Other settings from Build > Settings tab.",
        )
    with col_run:
        st.write("")  # Spacing
        run_clicked = st.button("Run Simulation", type="primary", use_container_width=True)

    if run_clicked:
        # Use settings from canvas_state (Build tab Settings)
        if "config" not in data:
            data["config"] = {}
        data["config"]["random_seed"] = override_seed
        data["config"]["duration_hours"] = canvas_state.duration_hours
        data["config"]["enable_crew_fatigue"] = canvas_state.enable_crew_fatigue
        data["config"]["enable_breakdowns"] = canvas_state.enable_breakdowns

        with st.spinner("Running simulation..."):
            try:
                from pj_ogun.models.scenario import Scenario
                from pj_ogun.simulation.engine import SimulationEngine
                from pj_ogun.analysis.kpis import (
                    compute_medevac_kpis,
                    compute_recovery_kpis,
                    compute_resupply_kpis,
                )

                # Validate and run
                scenario = Scenario.model_validate(data)
                engine = SimulationEngine(scenario)
                event_log = engine.run()

                # Compute KPIs
                medevac_kpis = compute_medevac_kpis(event_log)
                recovery_kpis = compute_recovery_kpis(event_log)
                resupply_kpis = compute_resupply_kpis(event_log)

                # Store results
                st.session_state["event_log"] = event_log
                st.session_state["medevac_kpis"] = medevac_kpis
                st.session_state["recovery_kpis"] = recovery_kpis
                st.session_state["resupply_kpis"] = resupply_kpis
                st.session_state["kpis"] = medevac_kpis

                # Clear replay graph cache
                if "replay_graph" in st.session_state:
                    del st.session_state["replay_graph"]

                # Summary
                cas_count = len(event_log.casualties) if hasattr(event_log, 'casualties') else 0
                st.success(f"Complete! {len(event_log.events)} events, {cas_count} casualties processed.")

            except Exception as e:
                st.error(f"Simulation failed: {e}")
                import traceback
                with st.expander("Error Details"):
                    st.code(traceback.format_exc())

    # Results preview
    if "event_log" in st.session_state:
        st.divider()

        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Quick Results")
            medevac_kpis = st.session_state.get("medevac_kpis")
            if medevac_kpis:
                st.metric("Casualties", medevac_kpis.total_casualties)
                if medevac_kpis.mean_evacuation_time:
                    st.metric("Mean Evac Time", f"{medevac_kpis.mean_evacuation_time:.1f} min")

        with col2:
            st.subheader("Next Steps")
            st.markdown("""
            - **View Results** tab for detailed KPIs
            - **Watch Replay** for animated timeline
            - **Export Data** for reports
            """)

        with st.expander("Event Log Preview (first 20 events)"):
            log = st.session_state["event_log"]
            df = log.to_dataframe()
            st.dataframe(df.head(20), use_container_width=True)


def render_dashboard_tab():
    """Render the KPI dashboard tab."""
    st.header("Performance Results")
    st.markdown("""
    Key performance indicators (KPIs) from your simulation. Use these metrics to evaluate
    whether your operational setup meets requirements and identify areas for improvement.
    """)

    if "medevac_kpis" not in st.session_state:
        st.warning("No results available. Please run a simulation first.")
        st.info("Go to the **Run Simulation** tab and click 'Run Simulation' to generate results.")
        return

    with st.expander("Understanding these metrics", expanded=False):
        st.markdown("""
        **What the numbers mean:**

        - **Total/Collected/Treated** - Shows pipeline progression. If many are 'Pending', you may need more capacity.
        - **Mean Evacuation Time** - Average time from casualty generation to reaching treatment. Lower is better.
        - **P90 Evacuation Time** - 90% of casualties were evacuated faster than this. Shows worst-case performance.
        - **Response Time** - How quickly a vehicle was dispatched. Indicates availability.
        - **Fulfillment Rate** - Percentage of requests successfully completed. Target: 100%.

        **Red flags to watch for:**
        - High pending counts suggest capacity issues
        - P90 times much higher than mean suggest inconsistent performance
        - Low fulfillment rates indicate resource shortages
        """)

    medevac_kpis = st.session_state["medevac_kpis"]
    recovery_kpis = st.session_state.get("recovery_kpis")
    resupply_kpis = st.session_state.get("resupply_kpis")
    log = st.session_state["event_log"]

    # Three columns for subsystems
    col_med, col_rec, col_sup = st.columns(3)

    with col_med:
        st.subheader("Casualty Evacuation (CASEVAC)")
        st.caption("Medical evacuation performance")

        st.metric("Total Casualties", medevac_kpis.total_casualties)
        st.metric("Collected", medevac_kpis.casualties_collected)
        st.metric("Treated", medevac_kpis.casualties_treated)
        st.metric("Pending", medevac_kpis.casualties_pending)

        st.divider()

        if medevac_kpis.mean_evacuation_time:
            st.metric(
                "Mean Evac Time",
                f"{medevac_kpis.mean_evacuation_time:.1f} min"
            )
            st.metric(
                "Max Evac Time",
                f"{medevac_kpis.max_evacuation_time:.1f} min"
            )
            st.metric(
                "P90 Evac Time",
                f"{medevac_kpis.p90_evacuation_time:.1f} min"
            )

    with col_rec:
        st.subheader("Vehicle Recovery")
        st.caption("Breakdown response performance")

        if recovery_kpis:
            st.metric("Total Breakdowns", recovery_kpis.total_breakdowns)
            st.metric("Recovered", recovery_kpis.vehicles_recovered)
            st.metric("Repaired", recovery_kpis.vehicles_repaired)
            st.metric("Pending", recovery_kpis.vehicles_pending)

            st.divider()

            if recovery_kpis.mean_response_time:
                st.metric(
                    "Mean Response Time",
                    f"{recovery_kpis.mean_response_time:.1f} min"
                )
            if recovery_kpis.mean_total_downtime:
                st.metric(
                    "Mean Downtime",
                    f"{recovery_kpis.mean_total_downtime:.1f} min"
                )
        else:
            st.info("No breakdowns occurred (or breakdowns disabled)")

    with col_sup:
        st.subheader("Supply Delivery")
        st.caption("Logistics fulfillment performance")

        if resupply_kpis:
            st.metric("Total Requests", resupply_kpis.total_requests)
            st.metric("Fulfilled", resupply_kpis.requests_fulfilled)
            st.metric("Delivered", f"{resupply_kpis.total_delivered} units")
            st.metric("Pending", resupply_kpis.requests_pending)

            st.divider()

            if resupply_kpis.mean_delivery_time:
                st.metric(
                    "Mean Delivery Time",
                    f"{resupply_kpis.mean_delivery_time:.1f} min"
                )
            if resupply_kpis.fulfillment_rate:
                st.metric(
                    "Fulfillment Rate",
                    f"{resupply_kpis.fulfillment_rate:.1f}%"
                )
            st.metric("Stockouts", resupply_kpis.stockout_events, help="Times when supply was unavailable")
        else:
            st.info("No supply requests in this scenario")

    # Charts
    st.divider()
    st.subheader("Visual Analysis")
    st.caption("Charts to help identify patterns and bottlenecks")

    col1, col2 = st.columns(2)

    with col1:
        # Evacuation time by priority
        if medevac_kpis.by_priority:
            priorities = []
            evac_times = []
            for p, stats in sorted(medevac_kpis.by_priority.items()):
                if stats.get("mean_evac"):
                    priorities.append(f"P{p}")
                    evac_times.append(stats["mean_evac"])

            if priorities:
                fig = px.bar(
                    x=priorities,
                    y=evac_times,
                    title="Mean Evacuation Time by Priority",
                    labels={"x": "Priority", "y": "Time (mins)"},
                )
                st.plotly_chart(fig, use_container_width=True)

    with col2:
        # Casualty count by priority
        if medevac_kpis.by_priority:
            priorities = []
            counts = []
            for p, stats in sorted(medevac_kpis.by_priority.items()):
                priorities.append(f"P{p}")
                counts.append(stats["count"])

            fig = px.pie(
                values=counts,
                names=priorities,
                title="Casualties by Priority",
            )
            st.plotly_chart(fig, use_container_width=True)

    # Timeline chart
    if log:
        cas_df = log.casualties_to_dataframe()
        if len(cas_df) > 0 and "time_generated" in cas_df.columns:
            fig = go.Figure()

            for _, row in cas_df.iterrows():
                times = []
                labels = []

                if pd.notna(row["time_generated"]):
                    times.append(row["time_generated"])
                    labels.append("Generated")
                if pd.notna(row["time_collected"]):
                    times.append(row["time_collected"])
                    labels.append("Collected")
                if pd.notna(row["time_delivered"]):
                    times.append(row["time_delivered"])
                    labels.append("Delivered")
                if pd.notna(row["time_treatment_completed"]):
                    times.append(row["time_treatment_completed"])
                    labels.append("Treated")

                fig.add_trace(go.Scatter(
                    x=times,
                    y=[row["id"]] * len(times),
                    mode="lines+markers",
                    name=row["id"],
                    hovertext=labels,
                    showlegend=False,
                ))

            fig.update_layout(
                title="Casualty Timeline",
                xaxis_title="Time (mins)",
                yaxis_title="Casualty ID",
                height=400,
            )
            st.plotly_chart(fig, use_container_width=True)


def render_export_tab():
    """Render the data export tab."""
    st.header("Export Data")
    st.markdown("""
    Download your scenario configuration and simulation results for reporting, further analysis, or sharing with colleagues.
    """)

    with st.expander("About export formats", expanded=False):
        st.markdown("""
        **Available formats:**

        - **Scenario JSON** - Complete scenario definition. Can be re-loaded into Pj-OGUN or used by other tools.
        - **Event Log CSV** - Every event from the simulation timeline. Good for detailed analysis in Excel or Python.
        - **Casualties CSV** - One row per casualty with all timestamps. Useful for evacuation time analysis.
        - **Breakdowns CSV** - Vehicle breakdown and recovery records.
        - **KPIs JSON** - All computed metrics in structured format. Good for automated reporting.
        """)

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Scenario Configuration")

        # Export from canvas state
        canvas_state = get_canvas_state()
        if canvas_state.flow_state and canvas_state.flow_state.nodes:
            scenario_dict = flow_state_to_scenario_dict(canvas_state)
            scenario_json = json.dumps(scenario_dict, indent=2)
            st.download_button(
                "Download Scenario JSON",
                scenario_json,
                file_name=f"{canvas_state.scenario_name.replace(' ', '_')}.json",
                mime="application/json",
            )
        elif "scenario_data" in st.session_state:
            scenario_json = json.dumps(st.session_state["scenario_data"], indent=2)
            st.download_button(
                "Download Scenario JSON",
                scenario_json,
                file_name="scenario.json",
                mime="application/json",
            )
        else:
            st.info("Build or load a scenario to export it")

    with col2:
        st.subheader("Simulation Results")

        if "event_log" in st.session_state:
            log = st.session_state["event_log"]

            # Events CSV
            events_df = log.to_dataframe()
            events_csv = events_df.to_csv(index=False)
            st.download_button(
                "Download Event Log (CSV)",
                events_csv,
                file_name="events.csv",
                mime="text/csv",
            )

            # Casualties CSV
            cas_df = log.casualties_to_dataframe()
            cas_csv = cas_df.to_csv(index=False)
            st.download_button(
                "Download Casualties (CSV)",
                cas_csv,
                file_name="casualties.csv",
                mime="text/csv",
            )

            # Breakdowns CSV
            bd_df = log.breakdowns_to_dataframe()
            if len(bd_df) > 0:
                bd_csv = bd_df.to_csv(index=False)
                st.download_button(
                    "Download Breakdowns (CSV)",
                    bd_csv,
                    file_name="breakdowns.csv",
                    mime="text/csv",
                )

            # KPIs JSON
            if "medevac_kpis" in st.session_state:
                from pj_ogun.analysis.kpis import compute_all_kpis
                all_kpis = compute_all_kpis(log)
                kpis_json = json.dumps(all_kpis, indent=2)
                st.download_button(
                    "Download All KPIs (JSON)",
                    kpis_json,
                    file_name="kpis.json",
                    mime="application/json",
                )
        else:
            st.info("Run a simulation to export results")

    # Quick tips
    st.divider()
    st.caption("""
    **Tip:** Export your scenario JSON to save your work. You can reload it later using the file uploader in the Build tab.
    For reporting, the KPIs JSON provides a structured summary suitable for automated processing.
    """)


if __name__ == "__main__":
    main()
