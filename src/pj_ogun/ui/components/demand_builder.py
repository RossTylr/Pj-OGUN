"""Demand event builder UI component."""

from uuid import uuid4

import streamlit as st

from pj_ogun.models.enums import DemandMode, DemandType, Priority
from pj_ogun.ui.state.canvas_state import (
    ManualEvent,
    RateConfig,
    get_canvas_state,
)


def render_demand_builder() -> None:
    """Render the demand configuration interface."""
    canvas_state = get_canvas_state()

    st.subheader("Events & Demand")
    st.caption("Define what the simulation needs to respond to")

    # Get available locations from nodes
    node_ids = []
    if canvas_state.flow_state and canvas_state.flow_state.nodes:
        node_ids = [n.id for n in canvas_state.flow_state.nodes]

    if not node_ids:
        st.info("Add locations to the network first, then define events here.")
        return

    # Mode selector with explanation
    st.markdown("**How should events be generated?**")
    mode_options = [DemandMode.MANUAL, DemandMode.RATE_BASED]
    current_mode_idx = mode_options.index(canvas_state.demand_mode) if canvas_state.demand_mode in mode_options else 0

    new_mode = st.radio(
        "Generation Mode",
        options=mode_options,
        format_func=lambda x: "Manual (specific times)" if x == DemandMode.MANUAL else "Rate-Based (statistical)",
        index=current_mode_idx,
        horizontal=True,
        help="Manual: You specify exact event times. Rate-Based: Events generated randomly at specified rates.",
        label_visibility="collapsed",
    )

    if new_mode != canvas_state.demand_mode:
        canvas_state.demand_mode = new_mode
        st.rerun()

    st.divider()

    if canvas_state.demand_mode == DemandMode.MANUAL:
        render_manual_events(canvas_state, node_ids)
    else:
        render_rate_based(canvas_state, node_ids)


def render_manual_events(canvas_state, node_ids: list[str]) -> None:
    """Render manual event list editor."""
    st.caption("Specify exactly when and where each event occurs")

    # Add event form
    with st.expander("Add New Event", expanded=False):
        st.markdown("**Schedule a specific event**")

        col1, col2 = st.columns(2)

        with col1:
            time_mins = st.number_input(
                "Time (minutes from start)",
                value=30.0,
                min_value=0.0,
                max_value=float(canvas_state.duration_hours * 60),
                step=5.0,
                key="new_event_time",
                help="When this event occurs (e.g., 30 = 30 minutes into the simulation)",
            )

            event_type = st.selectbox(
                "Event Type",
                options=[DemandType.CASUALTY, DemandType.AMMO_REQUEST, DemandType.VEHICLE_BREAKDOWN],
                format_func=lambda x: {
                    DemandType.CASUALTY: "Casualty (requires CASEVAC)",
                    DemandType.AMMO_REQUEST: "Ammo Request (requires logistics)",
                    DemandType.VEHICLE_BREAKDOWN: "Vehicle Breakdown (requires recovery)",
                }.get(x, x.value),
                key="new_event_type",
            )

        with col2:
            location = st.selectbox(
                "Location",
                options=node_ids,
                key="new_event_location",
                help="Where the event occurs",
            )

            priority = st.selectbox(
                "Priority",
                options=[1, 2, 3, 4],
                format_func=lambda x: f"P{x} - {['Urgent (life-threatening)', 'Priority (serious)', 'Routine (stable)', 'Convenience (minor)'][x-1]}",
                index=1,
                key="new_event_priority",
                help="Higher priority events are handled first",
            )

        quantity = st.number_input(
            "Quantity",
            value=1,
            min_value=1,
            max_value=10,
            key="new_event_qty",
            help="Number of this event type at this time/location",
        )

        if st.button("Add Event", type="primary"):
            event = ManualEvent(
                id=f"evt_{uuid4().hex[:8]}",
                time_mins=time_mins,
                event_type=event_type,
                location=location,
                quantity=quantity,
                priority=priority,
            )
            canvas_state.manual_events.append(event)
            # Sort by time
            canvas_state.manual_events.sort(key=lambda e: e.time_mins)
            st.success(f"Added event at T+{time_mins:.0f} mins")
            st.rerun()

    # Event list
    st.markdown("**Scheduled Events Timeline**")

    if not canvas_state.manual_events:
        st.info("No events scheduled yet. Use 'Add New Event' above to schedule casualties, supply requests, or breakdowns.")
        return

    # Group events by type for visual display
    type_colors = {
        DemandType.CASUALTY: "#FF4444",
        DemandType.AMMO_REQUEST: "#FF8800",
        DemandType.VEHICLE_BREAKDOWN: "#FFAA00",
    }

    priority_labels = {1: "P1", 2: "P2", 3: "P3", 4: "P4"}

    for event in canvas_state.manual_events:
        col1, col2, col3, col4, col5, col6 = st.columns([1, 1.5, 1.5, 0.5, 0.5, 0.5])

        with col1:
            hours = int(event.time_mins // 60)
            mins = int(event.time_mins % 60)
            st.text(f"{hours:02d}:{mins:02d}")

        with col2:
            type_label = event.event_type.value.replace("_", " ").title()
            st.caption(type_label)

        with col3:
            st.caption(event.location)

        with col4:
            st.text(f"x{event.quantity}")

        with col5:
            st.text(priority_labels.get(event.priority, "P2"))

        with col6:
            if st.button("X", key=f"del_evt_{event.id}", help="Delete"):
                canvas_state.manual_events = [
                    e for e in canvas_state.manual_events if e.id != event.id
                ]
                st.rerun()

    st.divider()
    total_casualties = sum(
        e.quantity for e in canvas_state.manual_events
        if e.event_type == DemandType.CASUALTY
    )
    st.markdown(f"**Summary:** {len(canvas_state.manual_events)} events scheduled | {total_casualties} total casualties")
    st.caption("The simulation will process these events in chronological order")


def render_rate_based(canvas_state, node_ids: list[str]) -> None:
    """Render rate-based demand configuration."""
    st.caption("Events generated statistically based on rates (uses Poisson distribution)")

    with st.expander("How rate-based generation works", expanded=False):
        st.markdown("""
        **Behind the scenes:** The simulation uses a Poisson process to randomly generate events.

        - **Rate** = average events per hour at each location
        - **Actual timing** varies randomly, but averages to your specified rate
        - **Priority distribution** determines the mix of urgent vs routine cases

        **Example:** A rate of 2.0/hour at a combat position means ~2 casualties per hour on average,
        but actual timing is random (sometimes 3 in an hour, sometimes 1).

        **Use this mode** for realistic, unpredictable event patterns rather than fixed schedules.
        """)

    # Filter to casualty-generating nodes (typically combat positions)
    combat_nodes = []
    for node_id in node_ids:
        node_data = canvas_state.node_data.get(node_id)
        if node_data and node_data.node_type.value in ("combat", "forward_arming"):
            combat_nodes.append(node_id)

    if not combat_nodes:
        combat_nodes = node_ids  # Fall back to all nodes

    # Add rate config
    with st.expander("Add Event Rate", expanded=False):
        st.markdown("**Configure an event generation rate for a location**")

        col1, col2 = st.columns(2)

        with col1:
            event_type = st.selectbox(
                "Event Type",
                options=[DemandType.CASUALTY, DemandType.AMMO_REQUEST],
                format_func=lambda x: {
                    DemandType.CASUALTY: "Casualties",
                    DemandType.AMMO_REQUEST: "Ammo Requests",
                }.get(x, x.value),
                key="new_rate_type",
            )

            location = st.selectbox(
                "Location",
                options=combat_nodes,
                key="new_rate_location",
                help="Field positions are pre-selected as typical casualty sources",
            )

        with col2:
            rate = st.number_input(
                "Rate (per hour)",
                value=1.0,
                min_value=0.1,
                max_value=10.0,
                step=0.1,
                key="new_rate_value",
                help="Average events per hour at this location",
            )

        st.markdown("**Priority Distribution** (what percentage of each severity?)")
        st.caption("Adjust sliders so they sum to 100%")
        col1, col2, col3 = st.columns(3)
        with col1:
            p1 = st.slider("P1 Urgent", 0.0, 1.0, 0.1, 0.05, key="new_rate_p1", help="Life-threatening")
        with col2:
            p2 = st.slider("P2 Priority", 0.0, 1.0, 0.3, 0.05, key="new_rate_p2", help="Serious but stable")
        with col3:
            p3 = st.slider("P3 Routine", 0.0, 1.0, 0.6, 0.05, key="new_rate_p3", help="Minor injuries")

        total = p1 + p2 + p3
        if abs(total - 1.0) > 0.01:
            st.warning(f"Priority weights sum to {total*100:.0f}%, should be 100%")

        if st.button("Add Rate Config", type="primary"):
            # Normalize weights
            if total > 0:
                p1_norm, p2_norm, p3_norm = p1/total, p2/total, p3/total
            else:
                p1_norm, p2_norm, p3_norm = 0.1, 0.3, 0.6

            config = RateConfig(
                id=f"rate_{uuid4().hex[:8]}",
                event_type=event_type,
                location=location,
                rate_per_hour=rate,
                priority_p1=p1_norm,
                priority_p2=p2_norm,
                priority_p3=p3_norm,
            )
            canvas_state.rate_configs.append(config)
            st.success(f"Added {rate}/hr at {location}")
            st.rerun()

    # Rate config list
    st.markdown("**Active Event Rates**")

    if not canvas_state.rate_configs:
        st.info("No event rates configured yet. Use 'Add Event Rate' above to define how events are generated.")
        return

    for config in canvas_state.rate_configs:
        col1, col2, col3, col4, col5 = st.columns([2, 2, 1.5, 1.5, 0.5])

        with col1:
            st.text(config.location)

        with col2:
            type_label = config.event_type.value.replace("_", " ").title()
            st.caption(type_label)

        with col3:
            new_rate = st.number_input(
                "Rate",
                value=config.rate_per_hour,
                min_value=0.1,
                max_value=10.0,
                step=0.1,
                key=f"rate_{config.id}",
                label_visibility="collapsed",
            )
            if new_rate != config.rate_per_hour:
                config.rate_per_hour = new_rate

        with col4:
            st.caption(f"P1:{config.priority_p1:.0%}")

        with col5:
            if st.button("X", key=f"del_rate_{config.id}", help="Delete"):
                canvas_state.rate_configs = [
                    r for r in canvas_state.rate_configs if r.id != config.id
                ]
                st.rerun()

    # Expected demand preview
    st.divider()
    total_rate = sum(c.rate_per_hour for c in canvas_state.rate_configs if c.event_type == DemandType.CASUALTY)
    expected = total_rate * canvas_state.duration_hours

    st.markdown(f"**Expected Casualties:** approximately **{expected:.0f}** over {canvas_state.duration_hours:.0f} hours")
    st.caption(f"Combined casualty rate: {total_rate:.1f} per hour across all locations")
    st.caption("Actual numbers will vary due to random generation - run multiple simulations to see the range")
