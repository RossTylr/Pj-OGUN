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


def main():
    st.title("Pj-OGUN")
    st.caption("Logistics & Field Operations Simulation Platform")

    # Welcome message for new users
    if "has_seen_intro" not in st.session_state:
        with st.expander("Welcome to Pj-OGUN - Click to learn how it works", expanded=True):
            st.markdown("""
            **Pj-OGUN** helps you model and analyze field logistics operations before real-world deployment.

            **How it works:**
            1. **Build** - Design your operational network (locations, vehicles, expected events)
            2. **Simulate** - Run the model to see how your setup handles the workload
            3. **Replay** - Watch an animated timeline of what happened
            4. **Analyze** - Review key performance metrics and identify bottlenecks
            5. **Export** - Download results for reports and further analysis

            **What you'll learn:** Response times, resource utilization, potential bottlenecks, and whether your plan meets operational requirements.
            """)
            if st.button("Got it, let's start"):
                st.session_state.has_seen_intro = True
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
    """Render the Phase 4 interactive scenario builder."""
    st.header("Build Your Scenario")
    st.markdown("""
    Design your operational network by placing locations on the canvas and connecting them with routes.
    Then add vehicles and define the events (casualties, supply requests) the system needs to handle.
    """)

    with st.expander("How the Scenario Builder works", expanded=False):
        st.markdown("""
        **Behind the scenes:** Your scenario defines the operational environment the simulation will model.

        **Key components you'll set up:**
        - **Network nodes** - Physical locations (medical facilities, supply points, field positions)
        - **Routes** - Connections between locations with travel distances
        - **Vehicles** - Your fleet of ambulances, recovery vehicles, and logistics trucks
        - **Demand events** - When and where casualties occur, or supplies are needed

        **The simulation engine** will then dispatch vehicles, route them optimally, and track response times.
        """)

    canvas_state = get_canvas_state()

    # Top row: scenario name and load/save
    col1, col2, col3 = st.columns([2, 1, 1])

    with col1:
        canvas_state.scenario_name = st.text_input(
            "Scenario Name",
            value=canvas_state.scenario_name,
            label_visibility="collapsed",
            placeholder="Scenario Name",
        )

    with col2:
        uploaded = st.file_uploader(
            "Load JSON",
            type=["json"],
            key="scenario_upload",
            label_visibility="collapsed",
        )
        if uploaded:
            try:
                data = json.load(uploaded)
                # Convert to canvas state
                flow_state, node_data = scenario_to_flow_state(data)
                canvas_state.flow_state = flow_state
                canvas_state.node_data = node_data
                canvas_state.scenario_name = data.get("name", "Loaded Scenario")

                # Load vehicles
                canvas_state.vehicles = []
                from pj_ogun.ui.state.canvas_state import VehicleEntry
                for v in data.get("vehicles", []):
                    canvas_state.vehicles.append(VehicleEntry(
                        id=v["id"],
                        type_id=v["type_id"],
                        callsign=v.get("callsign", v["id"]),
                        start_location=v["start_location"],
                    ))

                # Load config
                config = data.get("config", {})
                canvas_state.duration_hours = config.get("duration_hours", 8.0)
                canvas_state.random_seed = config.get("random_seed", 42)

                # Also store raw data for simulation
                st.session_state["scenario_data"] = data

                st.success(f"Loaded: {canvas_state.scenario_name}")
                st.rerun()
            except Exception as e:
                st.error(f"Failed to load: {e}")

    with col3:
        # Load example button
        example_path = Path(__file__).parent.parent.parent.parent / "scenarios" / "example_medevac.json"
        if example_path.exists():
            if st.button("Load Example"):
                with open(example_path) as f:
                    data = json.load(f)
                flow_state, node_data = scenario_to_flow_state(data)
                canvas_state.flow_state = flow_state
                canvas_state.node_data = node_data
                canvas_state.scenario_name = data.get("name", "Example Scenario")

                # Load vehicles
                canvas_state.vehicles = []
                from pj_ogun.ui.state.canvas_state import VehicleEntry
                for v in data.get("vehicles", []):
                    canvas_state.vehicles.append(VehicleEntry(
                        id=v["id"],
                        type_id=v["type_id"],
                        callsign=v.get("callsign", v["id"]),
                        start_location=v["start_location"],
                    ))

                # Load demand events
                from pj_ogun.ui.state.canvas_state import ManualEvent
                from pj_ogun.models.enums import DemandMode, DemandType
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

                config = data.get("config", {})
                canvas_state.duration_hours = config.get("duration_hours", 8.0)
                canvas_state.random_seed = config.get("random_seed", 42)

                st.session_state["scenario_data"] = data
                st.success("Loaded example scenario")
                st.rerun()

    st.divider()

    # Main builder layout: left panel + canvas + right panel
    col_left, col_main, col_right = st.columns([1, 2, 1])

    with col_left:
        # Node palette for adding new nodes
        render_node_palette()

        st.divider()

        # Edge editor
        with st.expander("Edges", expanded=False):
            render_edge_editor()

    with col_main:
        # Main canvas
        render_network_canvas()

    with col_right:
        # Node property panel
        render_node_panel()

        st.divider()

        # Vehicle builder
        with st.expander("Vehicles", expanded=True):
            render_vehicle_builder()

        st.divider()

        # Demand builder
        with st.expander("Demand Events", expanded=True):
            render_demand_builder()

    st.divider()

    # Bottom row: config and validate
    col1, col2, col3, col4 = st.columns([1, 1, 1, 1])

    with col1:
        canvas_state.duration_hours = st.number_input(
            "Simulation Duration (hours)",
            value=float(canvas_state.duration_hours),
            min_value=1.0,
            max_value=72.0,
            step=1.0,
            help="How long the simulated operation will run. Longer durations show sustained ops effects.",
        )

    with col2:
        canvas_state.random_seed = st.number_input(
            "Random Seed",
            value=canvas_state.random_seed,
            min_value=0,
            max_value=999999,
            help="Controls randomness. Same seed = same results. Change to see different outcomes.",
        )

    with col3:
        st.markdown("**Realism Options**")
        canvas_state.enable_crew_fatigue = st.checkbox(
            "Crew Fatigue",
            value=canvas_state.enable_crew_fatigue,
            key="builder_enable_crew_fatigue",
            help="Crews need rest after extended operations. Vehicles pause when crews are fatigued.",
        )
        canvas_state.enable_breakdowns = st.checkbox(
            "Random Breakdowns",
            value=canvas_state.enable_breakdowns,
            key="builder_enable_breakdowns",
            help="Vehicles may break down randomly, requiring recovery. Tests system resilience.",
        )

    with col4:
        if st.button("Save & Validate Scenario", type="primary", help="Check your scenario is complete and ready to simulate"):
            try:
                scenario_dict = flow_state_to_scenario_dict(canvas_state)

                # Validate with Pydantic
                from pj_ogun.models.scenario import Scenario
                scenario = Scenario.model_validate(scenario_dict)

                st.session_state["scenario_data"] = scenario_dict
                st.success(f"Scenario ready! {len(scenario.nodes)} locations, {len(scenario.vehicles)} vehicles configured. Go to 'Run Simulation' to start.")
            except Exception as e:
                st.error(f"Validation error: {e}")


def render_simulate_tab():
    """Render the simulation execution tab."""
    st.header("Run Simulation")
    st.markdown("""
    Execute the discrete-event simulation to see how your operational setup performs.
    The engine processes all events chronologically and tracks every vehicle movement, casualty, and supply delivery.
    """)

    if "scenario_data" not in st.session_state:
        st.warning("No scenario loaded. Please build or load a scenario in the 'Build Scenario' tab first.")
        st.info("**Tip:** Click 'Load Example' in the Build tab to quickly load a pre-configured scenario and see how the tool works.")
        return

    with st.expander("What happens during simulation?", expanded=False):
        st.markdown("""
        **The simulation engine:**
        1. **Generates events** - Casualties and supply requests appear at the times/rates you configured
        2. **Dispatches vehicles** - Assigns the nearest available vehicle to each request
        3. **Routes movement** - Calculates travel times based on network distances
        4. **Tracks status** - Records when patients are collected, delivered, and treated
        5. **Handles complications** - If enabled, simulates breakdowns and crew fatigue

        **Result:** A complete timeline of every action, which we analyze to compute performance metrics.
        """)

    data = st.session_state["scenario_data"]

    st.subheader("Simulation Settings")
    col1, col2, col3 = st.columns(3)

    with col1:
        seed = st.number_input(
            "Random Seed",
            value=data.get("config", {}).get("random_seed", 42),
            min_value=0,
            help="Controls randomness. Use the same seed to reproduce results, or change it to explore different outcomes.",
        )

    with col2:
        duration = st.slider(
            "Duration (hours)",
            min_value=1,
            max_value=72,
            value=int(data.get("config", {}).get("duration_hours", 8)),
            help="How long to run the simulated operation.",
        )

    with col3:
        st.markdown("**Stress Testing**")
        enable_fatigue = st.checkbox(
            "Enable Crew Fatigue",
            value=data.get("config", {}).get("enable_crew_fatigue", False),
            key="simulate_enable_crew_fatigue",
            help="Crews require rest after extended operations, reducing vehicle availability.",
        )
        enable_breakdowns = st.checkbox(
            "Enable Random Breakdowns",
            value=data.get("config", {}).get("enable_breakdowns", False),
            key="simulate_enable_breakdowns",
            help="Vehicles may break down, testing your recovery capability.",
        )

    st.divider()

    col_run, col_info = st.columns([1, 2])
    with col_run:
        run_clicked = st.button("Run Simulation", type="primary", use_container_width=True)

    with col_info:
        if "event_log" not in st.session_state:
            st.info("Click 'Run Simulation' to start. Results will appear below.")

    if run_clicked:
        # Update config
        if "config" not in data:
            data["config"] = {}
        data["config"]["random_seed"] = seed
        data["config"]["duration_hours"] = duration
        data["config"]["enable_crew_fatigue"] = enable_fatigue
        data["config"]["enable_breakdowns"] = enable_breakdowns

        with st.spinner("Running simulation... Processing events chronologically"):
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

                # Clear replay graph cache to rebuild with new data
                if "replay_graph" in st.session_state:
                    del st.session_state["replay_graph"]

                # Summary message
                cas_count = len(event_log.casualties) if hasattr(event_log, 'casualties') else 0
                st.success(f"""
                Simulation complete!
                - **{len(event_log.events)}** total events processed
                - **{cas_count}** casualties handled
                - Check the **View Results** tab for performance metrics
                - Use **Watch Replay** to see an animated timeline
                """)

            except Exception as e:
                st.error(f"Simulation failed: {e}")
                import traceback
                st.code(traceback.format_exc())

    # Show event log preview if available
    if "event_log" in st.session_state:
        st.divider()
        st.subheader("Event Log Preview")
        st.caption("First 20 events from the simulation timeline. Download full log in the Export tab.")
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
