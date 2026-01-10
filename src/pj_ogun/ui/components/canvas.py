"""Interactive network canvas using streamlit-flow."""

import inspect
from uuid import uuid4

import streamlit as st
from streamlit_flow import streamlit_flow
from streamlit_flow.state import StreamlitFlowState
from streamlit_flow.layouts import ManualLayout

from pj_ogun.models.enums import NodeType
from pj_ogun.ui.state.canvas_state import (
    CanvasState,
    NodeData,
    NODE_CONFIG,
    create_flow_node,
    create_flow_edge,
    get_canvas_state,
    get_node_position,
)


def render_node_palette() -> None:
    """Render the node type selection palette."""
    st.subheader("Add Locations")
    st.caption("Click a type to add it to the canvas")

    # Group node types by category with descriptions
    categories = {
        "Operations": [NodeType.COMBAT, NodeType.HQ],
        "Medical": [NodeType.MEDICAL_ROLE1, NodeType.MEDICAL_ROLE2],
        "Support": [NodeType.REPAIR_WORKSHOP],
        "Logistics": [NodeType.AMMO_POINT, NodeType.FUEL_POINT],
        "Other": [NodeType.EXCHANGE_POINT, NodeType.FORWARD_ARMING],
    }

    # Category descriptions for stakeholders
    category_help = {
        "Operations": "Field positions where events occur and HQ locations",
        "Medical": "Treatment facilities - Role 1 (forward aid) and Role 2 (surgical)",
        "Support": "Vehicle repair and maintenance facilities",
        "Logistics": "Supply points for ammunition and fuel",
        "Other": "Exchange points and forward arming/refueling points",
    }

    canvas_state = get_canvas_state()

    for category, node_types in categories.items():
        help_text = category_help.get(category, "")
        with st.expander(category, expanded=(category in ["Operations", "Medical"])):
            if help_text:
                st.caption(help_text)
            cols = st.columns(2)
            for i, nt in enumerate(node_types):
                config = NODE_CONFIG.get(nt, {})
                with cols[i % 2]:
                    if st.button(
                        config.get("label", nt.value),
                        key=f"add_{nt.value}",
                        use_container_width=True,
                    ):
                        canvas_state.node_type_to_add = nt
                        st.rerun()


def render_network_canvas() -> None:
    """Render the main interactive network canvas."""
    canvas_state = get_canvas_state()

    # Initialize flow state if needed
    if canvas_state.flow_state is None:
        canvas_state.flow_state = StreamlitFlowState(nodes=[], edges=[])

    # Handle adding a new node
    if canvas_state.node_type_to_add is not None:
        node_type = canvas_state.node_type_to_add
        canvas_state.node_type_to_add = None

        # Generate unique id and name
        existing_ids = {n.id for n in canvas_state.flow_state.nodes}
        base_name = node_type.value
        counter = 1
        while f"{base_name}_{counter}" in existing_ids:
            counter += 1
        node_id = f"{base_name}_{counter}"
        name = f"{NODE_CONFIG.get(node_type, {}).get('label', node_type.value)} {counter}"

        # Position based on existing nodes (offset from last or center)
        if canvas_state.flow_state.nodes:
            last_node = canvas_state.flow_state.nodes[-1]
            last_x, last_y = get_node_position(last_node)
            x = (last_x / 50) + 3
            y = last_y / 50
        else:
            x, y = 5, 5

        # Create the flow node
        flow_node = create_flow_node(node_id, name, node_type, x, y)
        canvas_state.flow_state.nodes.append(flow_node)

        # Create node data
        canvas_state.node_data[node_id] = NodeData(
            id=node_id,
            name=name,
            node_type=node_type,
        )

        # Select the new node
        canvas_state.selected_node_id = node_id
        st.rerun()

    # Toolbar
    col1, col2, col3, col4 = st.columns([1, 1, 1, 2])

    with col1:
        if st.button("Clear All", type="secondary"):
            canvas_state.flow_state = StreamlitFlowState(nodes=[], edges=[])
            canvas_state.node_data = {}
            canvas_state.selected_node_id = None
            st.rerun()

    with col2:
        if canvas_state.selected_node_id and st.button("Delete Selected"):
            # Remove node
            canvas_state.flow_state.nodes = [
                n for n in canvas_state.flow_state.nodes
                if n.id != canvas_state.selected_node_id
            ]
            # Remove connected edges
            canvas_state.flow_state.edges = [
                e for e in canvas_state.flow_state.edges
                if e.source != canvas_state.selected_node_id
                and e.target != canvas_state.selected_node_id
            ]
            # Remove node data
            canvas_state.node_data.pop(canvas_state.selected_node_id, None)
            canvas_state.selected_node_id = None
            st.rerun()

    with col3:
        node_count = len(canvas_state.flow_state.nodes)
        edge_count = len(canvas_state.flow_state.edges)
        st.caption(f"Nodes: {node_count} | Edges: {edge_count}")

    # Render the flow canvas
    if canvas_state.flow_state.nodes:
        flow_kwargs = {
            "layout": ManualLayout(),
            "fit_view": True,
            "height": 500,
            "enable_node_menu": True,
            "enable_edge_menu": True,
            "enable_pane_menu": True,
            "hide_watermark": True,
            "allow_new_edges": True,
            "animate_new_edges": False,
            "min_zoom": 0.2,
            "max_zoom": 4,
        }
        # Filter out kwargs not supported by the installed streamlit_flow version.
        supported = set(inspect.signature(streamlit_flow).parameters)
        flow_kwargs = {k: v for k, v in flow_kwargs.items() if k in supported}
        updated_state = streamlit_flow(
            "scenario_canvas",
            canvas_state.flow_state,
            **flow_kwargs,
        )

        # Update state if changed
        if updated_state is not None:
            # Check for node selection
            for node in updated_state.nodes:
                if hasattr(node, "selected") and node.selected:
                    if canvas_state.selected_node_id != node.id:
                        canvas_state.selected_node_id = node.id

            # Check for new edges
            new_edge_ids = {e.id for e in updated_state.edges}
            old_edge_ids = {e.id for e in canvas_state.flow_state.edges}

            for edge in updated_state.edges:
                if edge.id not in old_edge_ids:
                    # New edge created - add distance label
                    edge.label = "5.0 km"

            # Sync node positions (user may have dragged)
            for updated_node in updated_state.nodes:
                for i, existing_node in enumerate(canvas_state.flow_state.nodes):
                    if existing_node.id == updated_node.id:
                        canvas_state.flow_state.nodes[i] = updated_node
                        break

            canvas_state.flow_state = updated_state

    else:
        st.info("""
        **Getting started:** Click a location type on the left panel to add your first node.

        **Then:** Drag between nodes to create routes (edges). The simulation uses these routes to calculate travel times.
        """)

    # Show selected node info
    if canvas_state.selected_node_id:
        node_data = canvas_state.node_data.get(canvas_state.selected_node_id)
        if node_data:
            st.success(f"Selected: **{node_data.name}** - Edit properties in the right panel")


def render_edge_editor() -> None:
    """Render edge distance editor."""
    canvas_state = get_canvas_state()

    if not canvas_state.flow_state or not canvas_state.flow_state.edges:
        st.info("No routes yet. Drag from one node's edge to another to create a connection.")
        return

    st.subheader("Route Distances")
    st.caption("Set travel distances between locations (affects vehicle travel time)")

    for i, edge in enumerate(canvas_state.flow_state.edges):
        col1, col2 = st.columns([2, 1])

        with col1:
            st.text(f"{edge.source} -> {edge.target}")

        with col2:
            # Extract current distance
            try:
                current = float(edge.label.replace(" km", "")) if edge.label else 5.0
            except (ValueError, AttributeError):
                current = 5.0

            new_dist = st.number_input(
                "km",
                value=current,
                min_value=0.1,
                max_value=500.0,
                step=0.5,
                key=f"edge_dist_{edge.id}",
                label_visibility="collapsed",
            )

            if new_dist != current:
                canvas_state.flow_state.edges[i].label = f"{new_dist:.1f} km"
