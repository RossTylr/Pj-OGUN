"""Node configuration panel with type-specific fields."""

import streamlit as st

from pj_ogun.models.enums import NodeType
from pj_ogun.ui.state.canvas_state import (
    CanvasState,
    NodeData,
    NODE_CONFIG,
    get_canvas_state,
    create_flow_node,
    get_node_position,
)


def render_node_panel() -> None:
    """Render the property panel for the selected node."""
    canvas_state = get_canvas_state()

    if not canvas_state.selected_node_id:
        st.subheader("Location Properties")
        st.info("Click a node on the canvas to configure its properties.")
        st.caption("Each location type has specific settings that affect how the simulation handles events there.")
        return

    node_data = canvas_state.node_data.get(canvas_state.selected_node_id)
    if not node_data:
        st.warning("Node data not found.")
        return

    st.subheader(f"Configure: {node_data.name}")
    st.caption("These settings determine how this location operates in the simulation")

    with st.form(key=f"node_form_{canvas_state.selected_node_id}"):
        # Common fields
        new_name = st.text_input("Name", value=node_data.name)

        # Node type selector
        current_type_index = list(NodeType).index(node_data.node_type)
        type_options = [(nt, NODE_CONFIG.get(nt, {}).get("label", nt.value)) for nt in NodeType]
        new_type = st.selectbox(
            "Type",
            options=[nt for nt, _ in type_options],
            format_func=lambda x: NODE_CONFIG.get(x, {}).get("label", x.value),
            index=current_type_index,
        )

        # Coordinates
        flow_node = next(
            (n for n in canvas_state.flow_state.nodes if n.id == canvas_state.selected_node_id),
            None,
        )
        if flow_node:
            col1, col2 = st.columns(2)
            pos_x, pos_y = get_node_position(flow_node)
            with col1:
                x = st.number_input("X", value=pos_x / 50, step=1.0)
            with col2:
                y = st.number_input("Y", value=pos_y / 50, step=1.0)
        else:
            x, y = 0.0, 0.0

        st.divider()

        # Type-specific fields
        if new_type in (NodeType.MEDICAL_ROLE1, NodeType.MEDICAL_ROLE2):
            st.markdown("**Medical Facility Settings**")
            if new_type == NodeType.MEDICAL_ROLE1:
                st.caption("Role 1: Forward aid station providing initial stabilization")
            else:
                st.caption("Role 2: Enhanced medical facility with surgical capability")

            treatment_slots = st.number_input(
                "Treatment Slots",
                value=node_data.treatment_slots or 2,
                min_value=1,
                max_value=20,
                help="How many patients can receive treatment at the same time. More slots = higher throughput but requires more staff.",
            )

            holding_capacity = st.number_input(
                "Holding Capacity",
                value=node_data.holding_capacity or 10,
                min_value=0,
                max_value=100,
                help="Maximum patients waiting for treatment. Excess arrivals may need to be diverted.",
            )

            treatment_time = st.number_input(
                "Treatment Time (mins)",
                value=node_data.treatment_time_mins or 30.0,
                min_value=5.0,
                max_value=240.0,
                step=5.0,
                help="Average time to treat one patient. Longer times reduce throughput.",
            )

            if new_type == NodeType.MEDICAL_ROLE2:
                triage_time = st.number_input(
                    "Triage Time (mins)",
                    value=node_data.triage_time_mins or 5.0,
                    min_value=1.0,
                    max_value=30.0,
                    step=1.0,
                    help="Time to assess and prioritize incoming patients before treatment.",
                )
            else:
                triage_time = None

        elif new_type == NodeType.REPAIR_WORKSHOP:
            st.markdown("**Repair Workshop Settings**")
            st.caption("Where broken-down vehicles are towed for repair")

            repair_bays = st.number_input(
                "Repair Bays",
                value=node_data.repair_bays or 2,
                min_value=1,
                max_value=10,
                help="Concurrent repair capacity. More bays = faster fleet recovery.",
            )

            st.markdown("**Repair Times by Severity**")
            st.caption("How long each repair type takes (affects vehicle downtime)")
            col1, col2, col3 = st.columns(3)
            with col1:
                repair_light = st.number_input(
                    "Light (mins)",
                    value=node_data.repair_time_light or 60.0,
                    min_value=15.0,
                    max_value=480.0,
                    step=15.0,
                    help="Minor issues: tire changes, fluid top-ups",
                )
            with col2:
                repair_medium = st.number_input(
                    "Medium (mins)",
                    value=node_data.repair_time_medium or 120.0,
                    min_value=30.0,
                    max_value=720.0,
                    step=15.0,
                    help="Moderate repairs: component replacement",
                )
            with col3:
                repair_heavy = st.number_input(
                    "Heavy (mins)",
                    value=node_data.repair_time_heavy or 240.0,
                    min_value=60.0,
                    max_value=1440.0,
                    step=30.0,
                    help="Major repairs: engine/transmission work",
                )

        elif new_type == NodeType.AMMO_POINT:
            st.markdown("**Ammunition Supply Point**")
            st.caption("Storage and distribution point for ammunition")

            storage_capacity = st.number_input(
                "Storage Capacity (units)",
                value=node_data.storage_capacity or 5000,
                min_value=100,
                max_value=50000,
                step=100,
                help="Maximum ammunition that can be stored here",
            )

            initial_stock = st.number_input(
                "Initial Stock (units)",
                value=node_data.initial_stock or 5000,
                min_value=0,
                max_value=50000,
                step=100,
                help="Ammunition available at simulation start",
            )

            resupply_interval = st.number_input(
                "Resupply Interval (hours)",
                value=node_data.resupply_interval_hours or 8.0,
                min_value=1.0,
                max_value=72.0,
                step=1.0,
                help="How often this point receives new stock from higher echelon",
            )

        elif new_type == NodeType.FUEL_POINT:
            st.markdown("**Fuel Distribution Point**")
            st.caption("Storage and distribution point for fuel")

            storage_capacity = st.number_input(
                "Storage Capacity (litres)",
                value=node_data.storage_capacity or 10000,
                min_value=1000,
                max_value=100000,
                step=1000,
                help="Maximum fuel that can be stored here",
            )

            initial_stock = st.number_input(
                "Initial Stock (litres)",
                value=node_data.initial_stock or 10000,
                min_value=0,
                max_value=100000,
                step=1000,
                help="Fuel available at simulation start",
            )

        # Submit buttons
        col1, col2 = st.columns(2)
        with col1:
            submitted = st.form_submit_button("Apply Changes", type="primary")
        with col2:
            cancelled = st.form_submit_button("Cancel")

        if submitted:
            # Update node data
            node_data.name = new_name
            node_data.node_type = new_type

            # Update type-specific fields
            if new_type in (NodeType.MEDICAL_ROLE1, NodeType.MEDICAL_ROLE2):
                node_data.treatment_slots = treatment_slots
                node_data.holding_capacity = holding_capacity
                node_data.treatment_time_mins = treatment_time
                if new_type == NodeType.MEDICAL_ROLE2:
                    node_data.triage_time_mins = triage_time
            elif new_type == NodeType.REPAIR_WORKSHOP:
                node_data.repair_bays = repair_bays
                node_data.repair_time_light = repair_light
                node_data.repair_time_medium = repair_medium
                node_data.repair_time_heavy = repair_heavy
            elif new_type in (NodeType.AMMO_POINT, NodeType.FUEL_POINT):
                node_data.storage_capacity = storage_capacity
                node_data.initial_stock = initial_stock
                if new_type == NodeType.AMMO_POINT:
                    node_data.resupply_interval_hours = resupply_interval

            # Update flow node visual
            if flow_node:
                new_flow_node = create_flow_node(
                    node_data.id,
                    node_data.name,
                    node_data.node_type,
                    x,
                    y,
                )
                for i, n in enumerate(canvas_state.flow_state.nodes):
                    if n.id == node_data.id:
                        canvas_state.flow_state.nodes[i] = new_flow_node
                        break

            st.success("Node updated!")
            st.rerun()

        if cancelled:
            canvas_state.selected_node_id = None
            st.rerun()
