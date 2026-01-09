"""Pj-OGUN Streamlit Application.

Run with: streamlit run src/pj_ogun/ui/app.py
"""

import json
from pathlib import Path

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from streamlit_drawable_canvas import st_canvas

# Page config
st.set_page_config(
    page_title="Pj-OGUN",
    page_icon="⚔️",
    layout="wide",
)

# Node type icons and colors
NODE_TYPES = {
    "combat": {"icon": "⚔️", "color": "#FF4444", "label": "Combat Position"},
    "medical_role1": {"icon": "🏥", "color": "#44FF44", "label": "Role 1 Medical"},
    "medical_role2": {"icon": "🏨", "color": "#00AA00", "label": "Role 2 Medical"},
    "repair_workshop": {"icon": "🔧", "color": "#FFAA00", "label": "REME Workshop"},
    "ammo_point": {"icon": "💣", "color": "#FF8800", "label": "Ammo Point"},
    "fuel_point": {"icon": "⛽", "color": "#8888FF", "label": "Fuel Point"},
    "hq": {"icon": "🎖️", "color": "#FFFF00", "label": "HQ"},
}


def render_network_map(scenario_data):
    """Render interactive network map using plotly."""
    if not scenario_data:
        return None

    nodes = scenario_data.get("nodes", [])
    edges = scenario_data.get("edges", [])

    if not nodes:
        return None

    fig = go.Figure()

    # Draw edges first (so nodes appear on top)
    for edge in edges:
        from_node = next((n for n in nodes if n["id"] == edge.get("from") or n["id"] == edge.get("from_node")), None)
        to_node = next((n for n in nodes if n["id"] == edge.get("to") or n["id"] == edge.get("to_node")), None)

        if from_node and to_node:
            fig.add_trace(go.Scatter(
                x=[from_node["coordinates"]["x"], to_node["coordinates"]["x"]],
                y=[from_node["coordinates"]["y"], to_node["coordinates"]["y"]],
                mode="lines",
                line=dict(color="gray", width=2),
                hoverinfo="text",
                hovertext=f"{edge.get('properties', {}).get('route_name', 'Route')}: {edge.get('distance_km', '?')} km",
                showlegend=False,
            ))

    # Draw nodes
    for node_type, config in NODE_TYPES.items():
        type_nodes = [n for n in nodes if n.get("type") == node_type]
        if type_nodes:
            fig.add_trace(go.Scatter(
                x=[n["coordinates"]["x"] for n in type_nodes],
                y=[n["coordinates"]["y"] for n in type_nodes],
                mode="markers+text",
                marker=dict(size=20, color=config["color"]),
                text=[config["icon"] for _ in type_nodes],
                textposition="middle center",
                hovertext=[f"{n.get('name', n['id'])}" for n in type_nodes],
                hoverinfo="text",
                name=config["label"],
            ))

    fig.update_layout(
        title="Network Topology",
        xaxis_title="X (km)",
        yaxis_title="Y (km)",
        height=500,
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )

    return fig


def main():
    st.title("⚔️ Pj-OGUN")
    st.subheader("British Army CS/CSS Logistics Simulation")

    # Tabs
    tab_builder, tab_simulate, tab_dashboard, tab_export = st.tabs([
        "📐 Scenario Builder",
        "▶️ Simulate",
        "📊 Dashboard",
        "💾 Export",
    ])

    # === SCENARIO BUILDER TAB ===
    with tab_builder:
        st.header("Scenario Builder")

        col1, col2 = st.columns([2, 1])

        with col1:
            st.subheader("Network Map")

            # File uploader
            uploaded = st.file_uploader(
                "Load Scenario JSON",
                type=["json"],
                key="scenario_upload",
            )

            if uploaded:
                try:
                    data = json.load(uploaded)
                    st.session_state["scenario_data"] = data
                    st.success(f"Loaded: {data.get('name', 'Unnamed')}")
                except Exception as e:
                    st.error(f"Failed to load: {e}")

            # Show example scenario option
            example_path = Path(__file__).parent.parent.parent.parent / "scenarios" / "example_medevac.json"
            if example_path.exists():
                if st.button("Load Example MEDEVAC Scenario"):
                    with open(example_path) as f:
                        st.session_state["scenario_data"] = json.load(f)
                    st.success("Loaded example scenario")
                    st.rerun()

            # Render network map if scenario loaded
            if "scenario_data" in st.session_state:
                fig = render_network_map(st.session_state["scenario_data"])
                if fig:
                    st.plotly_chart(fig, use_container_width=True)

                # Interactive node editor
                with st.expander("Edit Nodes"):
                    nodes = st.session_state["scenario_data"].get("nodes", [])
                    if nodes:
                        node_df = pd.DataFrame([{
                            "id": n["id"],
                            "name": n.get("name", ""),
                            "type": n["type"],
                            "x": n["coordinates"]["x"],
                            "y": n["coordinates"]["y"],
                        } for n in nodes])
                        edited_df = st.data_editor(node_df, num_rows="dynamic", key="node_editor")

                        if st.button("Apply Node Changes"):
                            # Update scenario with edited nodes
                            for i, row in edited_df.iterrows():
                                if i < len(st.session_state["scenario_data"]["nodes"]):
                                    st.session_state["scenario_data"]["nodes"][i]["id"] = row["id"]
                                    st.session_state["scenario_data"]["nodes"][i]["name"] = row["name"]
                                    st.session_state["scenario_data"]["nodes"][i]["type"] = row["type"]
                                    st.session_state["scenario_data"]["nodes"][i]["coordinates"]["x"] = row["x"]
                                    st.session_state["scenario_data"]["nodes"][i]["coordinates"]["y"] = row["y"]
                            st.success("Nodes updated")
                            st.rerun()

                # Interactive edge editor
                with st.expander("Edit Edges"):
                    edges = st.session_state["scenario_data"].get("edges", [])
                    if edges:
                        edge_df = pd.DataFrame([{
                            "from": e.get("from") or e.get("from_node"),
                            "to": e.get("to") or e.get("to_node"),
                            "distance_km": e["distance_km"],
                            "terrain_factor": e.get("properties", {}).get("terrain_factor", 1.0),
                        } for e in edges])
                        st.dataframe(edge_df)

                # Vehicle editor
                with st.expander("Edit Vehicles"):
                    vehicles = st.session_state["scenario_data"].get("vehicles", [])
                    if vehicles:
                        veh_df = pd.DataFrame([{
                            "id": v["id"],
                            "type_id": v["type_id"],
                            "callsign": v.get("callsign", ""),
                            "start_location": v["start_location"],
                        } for v in vehicles])
                        st.dataframe(veh_df)

        with col2:
            st.subheader("Scenario Summary")

            if "scenario_data" in st.session_state:
                data = st.session_state["scenario_data"]
                st.metric("Nodes", len(data.get("nodes", [])))
                st.metric("Edges", len(data.get("edges", [])))
                st.metric("Vehicles", len(data.get("vehicles", [])))
                st.metric("Duration (hrs)", data.get("config", {}).get("duration_hours", "?"))

                # Node type breakdown
                st.subheader("Node Types")
                nodes = data.get("nodes", [])
                type_counts = {}
                for n in nodes:
                    t = n.get("type", "unknown")
                    type_counts[t] = type_counts.get(t, 0) + 1

                for t, count in sorted(type_counts.items()):
                    icon = NODE_TYPES.get(t, {}).get("icon", "📍")
                    st.write(f"{icon} {t}: {count}")

                # Vehicle type breakdown
                st.subheader("Vehicle Types")
                vehicles = data.get("vehicles", [])
                vtypes = {}
                for v in vehicles:
                    t = v.get("type_id", "unknown")
                    vtypes[t] = vtypes.get(t, 0) + 1

                for t, count in sorted(vtypes.items()):
                    st.write(f"• {t}: {count}")

                with st.expander("Demand Events"):
                    events = data.get("demand", {}).get("manual_events", [])
                    if events:
                        df = pd.DataFrame(events)
                        cols = [c for c in ["time_mins", "type", "location", "quantity", "priority"] if c in df.columns]
                        st.dataframe(df[cols])
            else:
                st.info("Load a scenario to see summary")

    # === SIMULATE TAB ===
    with tab_simulate:
        st.header("Run Simulation")

        if "scenario_data" not in st.session_state:
            st.warning("Please load a scenario in the Builder tab first")
        else:
            data = st.session_state["scenario_data"]

            col1, col2, col3 = st.columns(3)

            with col1:
                seed = st.number_input(
                    "Random Seed",
                    value=data.get("config", {}).get("random_seed", 42),
                    min_value=0,
                )

            with col2:
                duration = st.slider(
                    "Duration (hours)",
                    min_value=1,
                    max_value=72,
                    value=int(data.get("config", {}).get("duration_hours", 8)),
                )

            with col3:
                st.write("Extended Operations")
                enable_fatigue = st.checkbox(
                    "Crew Fatigue",
                    value=data.get("config", {}).get("enable_crew_fatigue", False),
                )
                enable_breakdowns = st.checkbox(
                    "Random Breakdowns",
                    value=data.get("config", {}).get("enable_breakdowns", False),
                )

            if st.button("▶️ Run Simulation", type="primary"):
                # Update config
                data["config"]["random_seed"] = seed
                data["config"]["duration_hours"] = duration
                data["config"]["enable_crew_fatigue"] = enable_fatigue
                data["config"]["enable_breakdowns"] = enable_breakdowns

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
                        # Keep backward compatibility
                        st.session_state["kpis"] = medevac_kpis

                        st.success(f"Simulation complete! {len(event_log)} events logged.")

                    except Exception as e:
                        st.error(f"Simulation failed: {e}")
                        import traceback
                        st.code(traceback.format_exc())

            # Show event log preview if available
            if "event_log" in st.session_state:
                st.subheader("Event Log Preview")
                log = st.session_state["event_log"]
                df = log.to_dataframe()
                st.dataframe(df.head(20), use_container_width=True)

    # === DASHBOARD TAB ===
    with tab_dashboard:
        st.header("KPI Dashboard")

        if "medevac_kpis" not in st.session_state:
            st.warning("Run a simulation first to see KPIs")
        else:
            medevac_kpis = st.session_state["medevac_kpis"]
            recovery_kpis = st.session_state.get("recovery_kpis")
            resupply_kpis = st.session_state.get("resupply_kpis")
            log = st.session_state["event_log"]

            # Three columns for subsystems
            col_med, col_rec, col_sup = st.columns(3)

            with col_med:
                st.subheader("🚑 MEDEVAC")

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
                st.subheader("🔧 Recovery")

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
                    st.info("No recovery data")

            with col_sup:
                st.subheader("📦 Resupply")

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
                    st.metric("Stockouts", resupply_kpis.stockout_events)
                else:
                    st.info("No resupply data")

            # Charts
            st.divider()
            st.subheader("📈 Analysis Charts")

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

                    # Add traces for each casualty timeline
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

    # === EXPORT TAB ===
    with tab_export:
        st.header("Export Data")

        col1, col2 = st.columns(2)

        with col1:
            st.subheader("Scenario")

            if "scenario_data" in st.session_state:
                scenario_json = json.dumps(st.session_state["scenario_data"], indent=2)
                st.download_button(
                    "📥 Download Scenario JSON",
                    scenario_json,
                    file_name="scenario.json",
                    mime="application/json",
                )
            else:
                st.info("Load a scenario to export")

        with col2:
            st.subheader("Results")

            if "event_log" in st.session_state:
                log = st.session_state["event_log"]

                # Events CSV
                events_df = log.to_dataframe()
                events_csv = events_df.to_csv(index=False)
                st.download_button(
                    "📥 Download Event Log (CSV)",
                    events_csv,
                    file_name="events.csv",
                    mime="text/csv",
                )

                # Casualties CSV
                cas_df = log.casualties_to_dataframe()
                cas_csv = cas_df.to_csv(index=False)
                st.download_button(
                    "📥 Download Casualties (CSV)",
                    cas_csv,
                    file_name="casualties.csv",
                    mime="text/csv",
                )

                # Breakdowns CSV
                bd_df = log.breakdowns_to_dataframe()
                if len(bd_df) > 0:
                    bd_csv = bd_df.to_csv(index=False)
                    st.download_button(
                        "📥 Download Breakdowns (CSV)",
                        bd_csv,
                        file_name="breakdowns.csv",
                        mime="text/csv",
                    )

                # Ammo Requests CSV
                ammo_df = log.ammo_requests_to_dataframe()
                if len(ammo_df) > 0:
                    ammo_csv = ammo_df.to_csv(index=False)
                    st.download_button(
                        "📥 Download Ammo Requests (CSV)",
                        ammo_csv,
                        file_name="ammo_requests.csv",
                        mime="text/csv",
                    )

                # KPIs JSON
                if "medevac_kpis" in st.session_state:
                    from pj_ogun.analysis.kpis import compute_all_kpis
                    all_kpis = compute_all_kpis(log)
                    kpis_json = json.dumps(all_kpis, indent=2)
                    st.download_button(
                        "📥 Download All KPIs (JSON)",
                        kpis_json,
                        file_name="kpis.json",
                        mime="application/json",
                    )
            else:
                st.info("Run a simulation to export results")


if __name__ == "__main__":
    main()
