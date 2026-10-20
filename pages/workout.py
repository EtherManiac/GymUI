"""Default workout checklist page."""

from __future__ import annotations

from typing import Any

import streamlit as st

from workout_app.ui_helpers import load_data_or_stop, render_data_portability
from workout_app.workout_logic import (
    group_slots_by_snapshot,
    move_completed_units_to_end,
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
routine_ids = list(routine_by_id)
default_routine_index = next(
    (
        index
        for index, routine_id in enumerate(routine_ids)
        if routine_by_id[routine_id]["name"] == "UI Demo"
    ),
    0,
)
selected_routine_id = st.selectbox(
    "Select workout",
    options=routine_ids,
    index=default_routine_index,
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
    help=(
        "Higher-priority items are kept first. Supersets stay together, so the "
        "displayed total can be below this target."
    ),
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

# Every exercise uses the same full-width card. Superset membership is encoded
# only in the card key so CSS can overlay bracket segments outside the cards;
# there is no grouping wrapper to alter width, padding, or component layout.
st.markdown(
    """
    <style>
    :root {
        --workout-progress-blue: #4A80E4;
    }
    /* Streamlit's progress component uses an internal secondary theme token
       that is not exposed as a CSS variable. Set both elements from one local
       token so their rendered colors remain exactly identical. */
    div[data-testid="stProgressBarTrack"] > div {
        background-color: var(--workout-progress-blue) !important;
    }
    div[class*="st-key-superset_member_"] {
        position: relative;
        overflow: visible !important;
    }
    div[class*="st-key-superset_member_"]::after {
        content: "";
        position: absolute;
        /* Keep the indicator entirely outside the exercise card. */
        right: -1.75rem;
        width: 1.1rem;
        border-right: 4px solid var(--workout-progress-blue);
        pointer-events: none;
        z-index: 9998;
    }
    div[class*="st-key-superset_member_first_"]::after {
        top: 50%;
        bottom: -0.65rem;
        border-top: 4px solid var(--workout-progress-blue);
        border-radius: 0 0.4rem 0 0;
    }
    div[class*="st-key-superset_member_middle_"]::after {
        top: -0.65rem;
        bottom: -0.65rem;
    }
    div[class*="st-key-superset_member_last_"]::after {
        top: -0.65rem;
        bottom: 50%;
        border-bottom: 4px solid var(--workout-progress-blue);
        border-radius: 0 0 0.4rem 0;
    }
    div[class*="st-key-superset_member_"][class*="_label_"]::before {
        position: absolute;
        /* Place the label beyond the bracket instead of over card content. */
        right: -7.4rem;
        color: var(--text-color, #111827);
        background: var(--secondary-background-color, #f3f4f6);
        border: 2px solid var(--workout-progress-blue);
        border-radius: 0.25rem;
        padding: 0.15rem 0.4rem;
        font-size: 0.9rem;
        font-weight: 700;
        white-space: nowrap;
        transform: translateY(-50%);
        z-index: 9999;
    }
    div[class*="st-key-superset_member_"][class*="_label_center_"]::before {
        top: 50%;
    }
    div[class*="st-key-superset_member_"][class*="_label_gap_"]::before {
        top: calc(100% + 0.65rem);
    }
    div[class*="st-key-superset_member_"][class*="_label_superset_"]::before {
        content: "Superset";
    }
    div[class*="st-key-superset_member_"][class*="_label_triset_"]::before {
        content: "Triset";
    }
    div[class*="st-key-superset_member_"][class*="_label_giantset_"]::before {
        content: "Giant set";
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def render_workout_row(
    row: dict[str, Any], member_index: int | None = None, member_count: int = 1
) -> None:
    """Render one exercise card and update its session-only selections."""

    slot = row["slot"]
    allowed_ids = [slot["default_exercise_id"], *slot["alternative_exercise_ids"]]
    safe_slot_id = "".join(
        character if character.isalnum() else "_" for character in slot["id"]
    )
    card_key = f"workout_card_{safe_slot_id}"
    if member_index is not None:
        position = (
            "first"
            if member_index == 0
            else "last"
            if member_index == member_count - 1
            else "middle"
        )
        label_marker = ""
        if member_count % 2 == 0 and member_index == (member_count // 2) - 1:
            label_marker = "_label_gap"
        elif member_count % 2 == 1 and member_index == member_count // 2:
            label_marker = "_label_center"
        if label_marker:
            group_name = "superset" if member_count == 2 else "triset" if member_count == 3 else "giantset"
            label_marker += f"_label_{group_name}"
        card_key = f"superset_member_{position}{label_marker}_{safe_slot_id}"

    with st.container(border=True, key=card_key):
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


for unit in group_slots_by_snapshot(snapshot):
    is_superset = len(unit) > 1 and bool(unit[0]["slot"].get("superset_group_id"))
    if is_superset:
        for member_index, row in enumerate(unit):
            render_workout_row(row, member_index=member_index, member_count=len(unit))
    else:
        render_workout_row(unit[0])

completed_count = sum(row["completed"] for row in snapshot)
# Re-render only when completion changed the unit order. Widget keys are based
# on stable slot IDs, so checkbox and substitution state follows each row.
if move_completed_units_to_end(snapshot):
    st.rerun()
st.progress(completed_count / len(snapshot), text=f"{completed_count} of {len(snapshot)} complete")
