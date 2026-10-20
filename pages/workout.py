"""Default workout checklist page."""

from __future__ import annotations

from typing import Any

import streamlit as st

from workout_app.ui_helpers import load_data_or_stop, render_data_portability
from workout_app.workout_logic import (
    new_workout_snapshot,
    restore_snapshot_order,
    shuffle_snapshot,
)


exercise_document, routine_document = load_data_or_stop()
render_data_portability(exercise_document, routine_document)

st.title("Workout")
st.caption("Choose a routine, adjust its length, and work through the checklist.")

routines = sorted(routine_document["routines"], key=lambda routine: routine["name"].casefold())
if not routines:
    st.info("No routines exist yet. Create one on the Edit routines page.")
    st.stop()

routine_by_id = {routine["id"]: routine for routine in routines}
selected_routine_id = st.selectbox(
    "Select workout",
    options=list(routine_by_id),
    format_func=lambda routine_id: routine_by_id[routine_id]["name"],
)
selected_routine = routine_by_id[selected_routine_id]
slot_count = len(selected_routine["slots"])
if slot_count == 0:
    st.info("This routine has no exercise slots yet.")
    st.stop()

requested_count = st.number_input(
    "Number of exercises",
    min_value=1,
    max_value=slot_count,
    value=slot_count,
    step=1,
    help="Supersets stay together, so the displayed total can be below this target.",
)


def reset_active_workout() -> None:
    """Build a clean snapshot and invalidate prior widget state via a nonce."""

    st.session_state.active_workout = new_workout_snapshot(selected_routine, int(requested_count))
    st.session_state.active_workout_identity = (selected_routine_id, int(requested_count))
    st.session_state.workout_widget_nonce = st.session_state.get("workout_widget_nonce", 0) + 1


current_identity = (selected_routine_id, int(requested_count))
if st.session_state.get("active_workout_identity") != current_identity:
    reset_active_workout()

button_columns = st.columns(3)
if button_columns[0].button("Shuffle", width="stretch"):
    shuffle_snapshot(st.session_state.active_workout)
    st.rerun()
if button_columns[1].button("Original order", width="stretch"):
    restore_snapshot_order(st.session_state.active_workout)
    st.rerun()
if button_columns[2].button("Reset", width="stretch", type="secondary"):
    reset_active_workout()
    st.rerun()

snapshot: list[dict[str, Any]] = st.session_state.active_workout
if len(snapshot) < int(requested_count):
    st.caption(
        f"Showing {len(snapshot)} exercises. A superset that would exceed your target was kept intact and skipped."
    )

exercise_by_id = {
    exercise["id"]: exercise for exercise in exercise_document["exercises"]
}
widget_nonce = st.session_state.workout_widget_nonce
last_group_id: str | None = None

for row in snapshot:
    slot = row["slot"]
    group_id = slot.get("superset_group_id")
    if group_id and group_id != last_group_id:
        st.markdown("#### Superset")
    last_group_id = group_id

    allowed_ids = [slot["default_exercise_id"], *slot["alternative_exercise_ids"]]
    with st.container(border=True):
        checkbox_column, details_column = st.columns([1, 6], vertical_alignment="center")
        completed = checkbox_column.checkbox(
            "Done",
            value=row["completed"],
            key=f"done_{widget_nonce}_{slot['id']}",
            label_visibility="collapsed",
        )
        row["completed"] = completed

        selected_exercise_id = row["selected_exercise_id"]
        if len(allowed_ids) > 1:
            selected_exercise_id = details_column.selectbox(
                "Exercise",
                options=allowed_ids,
                index=allowed_ids.index(selected_exercise_id),
                format_func=lambda exercise_id: exercise_by_id[exercise_id]["name"],
                key=f"alternative_{widget_nonce}_{slot['id']}",
            )
        else:
            exercise_name = exercise_by_id[selected_exercise_id]["name"]
            details_column.markdown(f"### {'~~' + exercise_name + '~~' if completed else exercise_name}")
        row["selected_exercise_id"] = selected_exercise_id

        exercise = exercise_by_id[selected_exercise_id]
        if completed:
            details_column.caption("✅ Completed")
        details_column.write(
            f"**{slot['sets']} × {slot['reps']}** · Reference weight: **{slot['reference_weight']}**"
        )
        if exercise.get("notes"):
            with details_column.expander("Notes"):
                st.write(exercise["notes"])
        if exercise.get("demo_url"):
            details_column.link_button("View demonstration", exercise["demo_url"])

completed_count = sum(row["completed"] for row in snapshot)
st.progress(completed_count / len(snapshot), text=f"{completed_count} of {len(snapshot)} complete")
