"""Profile-specific repeating workout split editor."""

from __future__ import annotations

from typing import Any

import streamlit as st

from workout_app.profile_ui import require_active_user
from workout_app.split_logic import empty_split_document
from workout_app.storage import DataLoadError, load_split, save_split
from workout_app.ui_helpers import (
    load_data_or_stop,
    render_data_portability,
    show_save_error,
)
from workout_app.validation import DataValidationError


active_user_id = require_active_user()
exercise_document, routine_document = load_data_or_stop(active_user_id)
render_data_portability(active_user_id, exercise_document, routine_document)

st.title("Workout split")
st.caption(
    "Choose the repeating routine order used when no workout is scheduled on the calendar."
)

routines = sorted(
    routine_document["routines"], key=lambda routine: routine["name"].casefold()
)
routine_by_id = {routine["id"]: routine for routine in routines}
if not routines:
    st.info("Create a routine before setting a workout split.")
    st.stop()

try:
    split_document = load_split(active_user_id, routine_document)
except (DataLoadError, DataValidationError) as error:
    st.error("The workout split could not be loaded.")
    st.code(str(error))
    st.stop()

saved_routine_ids = split_document["routine_ids"]
if saved_routine_ids:
    current_index = split_document["current_index"]
    next_routine = routine_by_id[saved_routine_ids[current_index]]
    st.info(
        f"Next workout: {next_routine['name']} "
        f"(slot {current_index + 1} of {len(saved_routine_ids)})"
    )
else:
    st.info("No workout split is currently active.")

slot_count_key = f"split_slot_count_{active_user_id}"
slot_count_arguments: dict[str, Any] = {
    "label": "Number of routines in the split",
    "min_value": 1,
    "max_value": 20,
    "step": 1,
    "key": slot_count_key,
}
if slot_count_key not in st.session_state:
    slot_count_arguments["value"] = len(saved_routine_ids) or 1
slot_count = int(st.number_input(**slot_count_arguments))

routine_ids = list(routine_by_id)
selected_routine_ids: list[str] = []
with st.container(border=True):
    for index in range(slot_count):
        initial_id = (
            saved_routine_ids[index]
            if index < len(saved_routine_ids)
            else routine_ids[0]
        )
        widget_key = f"split_slot_{active_user_id}_{index}"
        select_arguments: dict[str, Any] = {
            "label": f"Slot {index + 1}",
            "options": routine_ids,
            "format_func": lambda routine_id: routine_by_id[routine_id]["name"],
            "key": widget_key,
        }
        if widget_key not in st.session_state:
            select_arguments["index"] = routine_ids.index(initial_id)
        selected_routine_ids.append(st.selectbox(**select_arguments))

next_slot_key = f"split_next_slot_{active_user_id}"
if st.session_state.get(next_slot_key) not in range(slot_count):
    st.session_state[next_slot_key] = min(
        split_document["current_index"], slot_count - 1
    )
next_slot_arguments: dict[str, Any] = {
    "label": "Next workout",
    "options": list(range(slot_count)),
    "format_func": lambda index: (
        f"Slot {index + 1} — {routine_by_id[selected_routine_ids[index]]['name']}"
    ),
    "key": next_slot_key,
}
next_index = int(st.selectbox(**next_slot_arguments))

action_columns = st.columns(2)
if action_columns[0].button("Save workout split", type="primary", width="stretch"):
    updated_split = {
        "schema_version": 1,
        "routine_ids": selected_routine_ids,
        "current_index": next_index,
    }
    try:
        save_split(active_user_id, updated_split, routine_document)
    except (DataLoadError, DataValidationError) as error:
        show_save_error(error)
    else:
        st.session_state.workout_routine_id = selected_routine_ids[next_index]
        st.session_state.pop("active_workout_identity", None)
        st.success("Workout split saved.")
        st.rerun()

if action_columns[1].button(
    "Clear workout split",
    disabled=not saved_routine_ids,
    width="stretch",
):
    try:
        save_split(active_user_id, empty_split_document(), routine_document)
    except (DataLoadError, DataValidationError) as error:
        show_save_error(error)
    else:
        st.rerun()
