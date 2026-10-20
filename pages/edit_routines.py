"""Routine and ordered slot maintenance page."""

from __future__ import annotations

from copy import deepcopy
from uuid import uuid4

import streamlit as st

from workout_app.storage import DataLoadError, save_data
from workout_app.ui_helpers import (
    all_tags,
    exercises_matching_tags,
    load_data_or_stop,
    render_data_portability,
    show_save_error,
)
from workout_app.validation import DataValidationError


exercise_document, routine_document = load_data_or_stop()
render_data_portability(exercise_document, routine_document)

st.title("Edit routines")
st.caption("Routine slots own their sets, reps, reference weight, alternatives, and superset grouping.")


def persist(updated_routines: dict) -> bool:
    """Save routine edits and show consistent feedback to the user."""

    try:
        save_data(exercise_document, updated_routines)
    except (DataLoadError, DataValidationError) as error:
        show_save_error(error)
        return False
    return True


routines = sorted(routine_document["routines"], key=lambda routine: routine["name"].casefold())
routine_by_id = {routine["id"]: routine for routine in routines}
new_routine_option = "__new_routine__"

# Apply post-save selection before constructing the widget. This lets a newly
# created routine open immediately without mutating an instantiated selectbox.
pending_selection = st.session_state.pop("routine_editor_pending_selection", None)
if pending_selection is not None:
    st.session_state.routine_editor_selection = pending_selection

st.subheader("Routine details")
selected_routine_id = st.selectbox(
    "Routine",
    options=[new_routine_option, *routine_by_id],
    format_func=lambda routine_id: (
        "New routine" if routine_id == new_routine_option else routine_by_id[routine_id]["name"]
    ),
    key="routine_editor_selection",
)
is_new_routine = selected_routine_id == new_routine_option
selected_routine = routine_by_id.get(selected_routine_id)

# The same small form creates a routine or renames the selected routine.
with st.form(f"routine_details_{selected_routine_id}", clear_on_submit=is_new_routine):
    routine_name = st.text_input(
        "Routine name", value="" if is_new_routine else selected_routine["name"]
    )
    routine_details_submitted = st.form_submit_button(
        "Create routine" if is_new_routine else "Save name", type="primary"
    )

if routine_details_submitted:
    if not routine_name.strip():
        st.error("Enter a routine name.")
    else:
        updated = deepcopy(routine_document)
        if is_new_routine:
            saved_routine_id = str(uuid4())
            updated["routines"].append(
                {"id": saved_routine_id, "name": routine_name.strip(), "slots": []}
            )
        else:
            saved_routine_id = selected_routine_id
            target = next(
                routine for routine in updated["routines"] if routine["id"] == selected_routine_id
            )
            target["name"] = routine_name.strip()
        if persist(updated):
            st.session_state.routine_editor_pending_selection = saved_routine_id
            st.rerun()

if is_new_routine:
    st.info("Create the routine to begin adding exercise slots.")
    st.stop()

if st.button("Delete routine", type="secondary"):
    updated = deepcopy(routine_document)
    updated["routines"] = [
        routine for routine in updated["routines"] if routine["id"] != selected_routine_id
    ]
    if persist(updated):
        st.session_state.routine_editor_pending_selection = new_routine_option
        st.rerun()

available_tags = all_tags(exercise_document)
exercise_name_by_id = {
    exercise["id"]: exercise["name"] for exercise in exercise_document["exercises"]
}
existing_group_ids = sorted(
    {
        slot["superset_group_id"]
        for slot in selected_routine["slots"]
        if slot.get("superset_group_id")
    }
)

st.subheader("Add a slot")
with st.container(border=True):
    add_tags = st.multiselect(
        "Required tags",
        options=available_tags,
        key=f"add_tags_{selected_routine_id}",
        help="Exercises must match every selected tag.",
    )
    add_matches = exercises_matching_tags(exercise_document, add_tags) if add_tags else []
    add_match_ids = [exercise["id"] for exercise in add_matches]
    if not add_tags:
        st.info("Select at least one required tag to choose an exercise.")
    elif not add_match_ids:
        st.warning("No exercises match all selected tags.")
    else:
        add_default_id = st.selectbox(
            "Default exercise",
            options=add_match_ids,
            format_func=lambda exercise_id: exercise_name_by_id[exercise_id],
            key=f"add_default_{selected_routine_id}",
        )
        add_alternatives = st.multiselect(
            "Alternatives (optional)",
            options=[exercise_id for exercise_id in add_match_ids if exercise_id != add_default_id],
            format_func=lambda exercise_id: exercise_name_by_id[exercise_id],
            key=f"add_alternatives_{selected_routine_id}",
        )
        add_detail_columns = st.columns(3)
        add_sets = add_detail_columns[0].text_input("Sets", value="3")
        add_reps = add_detail_columns[1].text_input("Reps", value="8-12")
        add_weight = add_detail_columns[2].text_input("Reference weight", value="Bodyweight")
        group_options = ["None", "New superset", *existing_group_ids]
        add_group_choice = st.selectbox("Superset group (optional)", group_options)
        if st.button("Add slot", type="primary"):
            if not all(value.strip() for value in (add_sets, add_reps, add_weight)):
                st.error("Sets, reps, and reference weight are required.")
            else:
                group_id = None
                if add_group_choice == "New superset":
                    group_id = str(uuid4())
                elif add_group_choice != "None":
                    group_id = add_group_choice
                updated = deepcopy(routine_document)
                target = next(
                    routine for routine in updated["routines"] if routine["id"] == selected_routine_id
                )
                target["slots"].append(
                    {
                        "id": str(uuid4()),
                        "order": len(target["slots"]) + 1,
                        "required_tags": add_tags,
                        "default_exercise_id": add_default_id,
                        "alternative_exercise_ids": add_alternatives,
                        "sets": add_sets.strip(),
                        "reps": add_reps.strip(),
                        "reference_weight": add_weight.strip(),
                        "superset_group_id": group_id,
                    }
                )
                if persist(updated):
                    st.success("Slot added.")
                    st.rerun()

st.subheader("Routine slots")
ordered = sorted(selected_routine["slots"], key=lambda slot: slot["order"])
if not ordered:
    st.info("This routine does not have any slots yet.")

for position, slot in enumerate(ordered):
    default_name = exercise_name_by_id[slot["default_exercise_id"]]
    with st.expander(f"{position + 1}. {default_name}", expanded=False):
        move_columns = st.columns(2)
        if move_columns[0].button(
            "Move up", key=f"up_{slot['id']}", disabled=position == 0, width="stretch"
        ):
            updated = deepcopy(routine_document)
            target = next(
                routine for routine in updated["routines"] if routine["id"] == selected_routine_id
            )
            target_slots = sorted(target["slots"], key=lambda item: item["order"])
            target_slots[position - 1], target_slots[position] = target_slots[position], target_slots[position - 1]
            for order, target_slot in enumerate(target_slots, start=1):
                target_slot["order"] = order
            if persist(updated):
                st.rerun()
        if move_columns[1].button(
            "Move down",
            key=f"down_{slot['id']}",
            disabled=position == len(ordered) - 1,
            width="stretch",
        ):
            updated = deepcopy(routine_document)
            target = next(
                routine for routine in updated["routines"] if routine["id"] == selected_routine_id
            )
            target_slots = sorted(target["slots"], key=lambda item: item["order"])
            target_slots[position], target_slots[position + 1] = target_slots[position + 1], target_slots[position]
            for order, target_slot in enumerate(target_slots, start=1):
                target_slot["order"] = order
            if persist(updated):
                st.rerun()

        edited_tags = st.multiselect(
            "Required tags",
            options=available_tags,
            default=slot["required_tags"],
            key=f"tags_{slot['id']}",
        )
        matches = exercises_matching_tags(exercise_document, edited_tags) if edited_tags else []
        match_ids = [exercise["id"] for exercise in matches]
        # Retain current choices long enough for the user to repair a tag mismatch.
        for current_id in [slot["default_exercise_id"], *slot["alternative_exercise_ids"]]:
            if current_id not in match_ids:
                match_ids.append(current_id)
        edited_default = st.selectbox(
            "Default exercise",
            options=match_ids,
            index=match_ids.index(slot["default_exercise_id"]),
            format_func=lambda exercise_id: exercise_name_by_id[exercise_id],
            key=f"default_{slot['id']}",
        )
        edited_alternatives = st.multiselect(
            "Alternatives",
            options=[exercise_id for exercise_id in match_ids if exercise_id != edited_default],
            default=[
                exercise_id
                for exercise_id in slot["alternative_exercise_ids"]
                if exercise_id != edited_default
            ],
            format_func=lambda exercise_id: exercise_name_by_id[exercise_id],
            key=f"alternatives_{slot['id']}",
        )
        detail_columns = st.columns(3)
        edited_sets = detail_columns[0].text_input("Sets", value=slot["sets"], key=f"sets_{slot['id']}")
        edited_reps = detail_columns[1].text_input("Reps", value=slot["reps"], key=f"reps_{slot['id']}")
        edited_weight = detail_columns[2].text_input(
            "Reference weight", value=slot["reference_weight"], key=f"weight_{slot['id']}"
        )
        edit_group_options = ["None", "New superset", *existing_group_ids]
        current_group = slot.get("superset_group_id") or "None"
        edited_group_choice = st.selectbox(
            "Superset group",
            options=edit_group_options,
            index=edit_group_options.index(current_group),
            key=f"group_{slot['id']}",
        )
        action_columns = st.columns(2)
        if action_columns[0].button("Save slot", key=f"save_{slot['id']}", type="primary"):
            if not edited_tags:
                st.error("Select at least one required tag.")
            elif edited_default not in [exercise["id"] for exercise in matches] or any(
                exercise_id not in [exercise["id"] for exercise in matches]
                for exercise_id in edited_alternatives
            ):
                st.error("The default and alternatives must match every required tag.")
            elif not all(value.strip() for value in (edited_sets, edited_reps, edited_weight)):
                st.error("Sets, reps, and reference weight are required.")
            else:
                group_id = None
                if edited_group_choice == "New superset":
                    group_id = str(uuid4())
                elif edited_group_choice != "None":
                    group_id = edited_group_choice
                updated = deepcopy(routine_document)
                target_routine = next(
                    routine for routine in updated["routines"] if routine["id"] == selected_routine_id
                )
                target_slot = next(item for item in target_routine["slots"] if item["id"] == slot["id"])
                target_slot.update(
                    required_tags=edited_tags,
                    default_exercise_id=edited_default,
                    alternative_exercise_ids=edited_alternatives,
                    sets=edited_sets.strip(),
                    reps=edited_reps.strip(),
                    reference_weight=edited_weight.strip(),
                    superset_group_id=group_id,
                )
                if persist(updated):
                    st.success("Slot updated.")
                    st.rerun()
        if action_columns[1].button("Remove slot", key=f"remove_{slot['id']}"):
            updated = deepcopy(routine_document)
            target_routine = next(
                routine for routine in updated["routines"] if routine["id"] == selected_routine_id
            )
            target_routine["slots"] = [
                item for item in target_routine["slots"] if item["id"] != slot["id"]
            ]
            for order, target_slot in enumerate(
                sorted(target_routine["slots"], key=lambda item: item["order"]), start=1
            ):
                target_slot["order"] = order
            if persist(updated):
                st.success("Slot removed.")
                st.rerun()
