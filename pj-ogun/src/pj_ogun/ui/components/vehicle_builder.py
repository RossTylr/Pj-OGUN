"""Vehicle fleet builder UI component."""

from uuid import uuid4

import streamlit as st

from pj_ogun.models.enums import VehicleRole
from pj_ogun.models.vehicles import VEHICLE_TYPE_LIBRARY
from pj_ogun.ui.state.canvas_state import (
    VehicleEntry,
    get_canvas_state,
    generate_callsign,
)


# Group vehicle types by role
VEHICLE_TYPES_BY_ROLE = {
    VehicleRole.AMBULANCE: ["amb_light", "amb_medium"],
    VehicleRole.RECOVERY: ["rec_light", "rec_medium", "rec_heavy"],
    VehicleRole.AMMO_LOGISTICS: ["log_ammo_medium"],
    VehicleRole.FUEL_LOGISTICS: ["log_fuel_medium"],
    VehicleRole.GENERAL_LOGISTICS: ["log_general_medium"],
}

ROLE_ICONS = {
    VehicleRole.AMBULANCE: "Ambulances (CASEVAC)",
    VehicleRole.RECOVERY: "Recovery Vehicles",
    VehicleRole.AMMO_LOGISTICS: "Ammo Transport",
    VehicleRole.FUEL_LOGISTICS: "Fuel Transport",
    VehicleRole.GENERAL_LOGISTICS: "General Logistics",
}

# Role descriptions for stakeholders
ROLE_DESCRIPTIONS = {
    VehicleRole.AMBULANCE: "Evacuate casualties from field to medical facilities",
    VehicleRole.RECOVERY: "Tow broken-down vehicles to repair workshops",
    VehicleRole.AMMO_LOGISTICS: "Deliver ammunition from supply points to units",
    VehicleRole.FUEL_LOGISTICS: "Deliver fuel from fuel points to units",
    VehicleRole.GENERAL_LOGISTICS: "General cargo and supply transport",
}


def render_vehicle_builder() -> None:
    """Render the vehicle fleet builder interface."""
    canvas_state = get_canvas_state()

    st.subheader("Vehicle Fleet")
    st.caption("Configure the vehicles available for operations")

    # Get available start locations from nodes
    node_ids = []
    if canvas_state.flow_state and canvas_state.flow_state.nodes:
        node_ids = [n.id for n in canvas_state.flow_state.nodes]

    if not node_ids:
        st.info("Add locations to the network first, then add vehicles here.")
        return

    # Count vehicles by role
    role_counts = {}
    for v in canvas_state.vehicles:
        role = v.role
        role_counts[role] = role_counts.get(role, 0) + 1

    # Add vehicle section
    with st.expander("Add New Vehicle", expanded=False):
        st.caption("Each vehicle can perform tasks based on its role (medical evacuation, recovery, logistics)")

        col1, col2 = st.columns(2)

        with col1:
            # Select vehicle type
            type_options = list(VEHICLE_TYPE_LIBRARY.keys())
            selected_type = st.selectbox(
                "Vehicle Type",
                options=type_options,
                format_func=lambda x: VEHICLE_TYPE_LIBRARY[x]["name"],
                key="new_vehicle_type",
                help="Different vehicle types have different speeds, capacities, and capabilities",
            )

        with col2:
            # Select start location
            start_loc = st.selectbox(
                "Starting Location",
                options=node_ids,
                key="new_vehicle_location",
                help="Where this vehicle will be positioned at the start of the simulation",
            )

        # Auto-generate callsign
        if selected_type:
            role = VehicleRole(VEHICLE_TYPE_LIBRARY[selected_type]["role"])
            existing_callsigns = [v.callsign for v in canvas_state.vehicles]
            suggested_callsign = generate_callsign(role, existing_callsigns)

            callsign = st.text_input(
                "Callsign",
                value=suggested_callsign,
                key="new_vehicle_callsign",
                help="Unique identifier for this vehicle (auto-generated, but you can customize)",
            )

        if st.button("Add Vehicle", type="primary"):
            # Create new vehicle
            vehicle_id = f"veh_{uuid4().hex[:8]}"
            new_vehicle = VehicleEntry(
                id=vehicle_id,
                type_id=selected_type,
                callsign=callsign,
                start_location=start_loc,
            )
            canvas_state.vehicles.append(new_vehicle)
            st.success(f"Added {callsign}")
            st.rerun()

    st.divider()

    # Display vehicles grouped by role
    st.markdown("**Your Fleet by Role**")
    for role, icon in ROLE_ICONS.items():
        role_vehicles = [v for v in canvas_state.vehicles if v.role == role]
        count = len(role_vehicles)
        role_desc = ROLE_DESCRIPTIONS.get(role, "")

        with st.expander(f"{icon} ({count})", expanded=(count > 0)):
            if role_desc:
                st.caption(role_desc)

            if not role_vehicles:
                st.info("No vehicles of this type yet")

                # Quick add button
                if role in VEHICLE_TYPES_BY_ROLE:
                    type_id = VEHICLE_TYPES_BY_ROLE[role][0]
                    if st.button(
                        f"+ Add {VEHICLE_TYPE_LIBRARY[type_id]['name']}",
                        key=f"quick_add_{role.value}",
                    ):
                        existing_callsigns = [v.callsign for v in canvas_state.vehicles]
                        callsign = generate_callsign(role, existing_callsigns)
                        vehicle_id = f"veh_{uuid4().hex[:8]}"
                        new_vehicle = VehicleEntry(
                            id=vehicle_id,
                            type_id=type_id,
                            callsign=callsign,
                            start_location=node_ids[0],
                        )
                        canvas_state.vehicles.append(new_vehicle)
                        st.rerun()
            else:
                for vehicle in role_vehicles:
                    type_info = VEHICLE_TYPE_LIBRARY.get(vehicle.type_id, {})
                    type_name = type_info.get("name", vehicle.type_id)

                    col1, col2, col3, col4 = st.columns([2, 2, 2, 1])

                    with col1:
                        st.text(vehicle.callsign)

                    with col2:
                        st.caption(type_name)

                    with col3:
                        # Location selector
                        current_idx = node_ids.index(vehicle.start_location) if vehicle.start_location in node_ids else 0
                        new_loc = st.selectbox(
                            "Location",
                            options=node_ids,
                            index=current_idx,
                            key=f"veh_loc_{vehicle.id}",
                            label_visibility="collapsed",
                        )
                        if new_loc != vehicle.start_location:
                            vehicle.start_location = new_loc

                    with col4:
                        if st.button("X", key=f"del_veh_{vehicle.id}", help="Delete"):
                            canvas_state.vehicles = [
                                v for v in canvas_state.vehicles if v.id != vehicle.id
                            ]
                            st.rerun()

    # Summary
    st.divider()
    total = len(canvas_state.vehicles)
    ambulance_count = len([v for v in canvas_state.vehicles if v.role == VehicleRole.AMBULANCE])
    st.caption(f"**Fleet Summary:** {total} total vehicles ({ambulance_count} ambulances)")
    if total == 0:
        st.info("Add vehicles to your fleet using the 'Add New Vehicle' section above, or use Quick Add buttons in each category.")
