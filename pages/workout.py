"""Default workout checklist page."""

from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any

import streamlit as st
from st_keyup import st_keyup

from workout_app.profile_ui import require_active_user
from workout_app.reorder_component import workout_drag_reorder
from workout_app.storage import (
    DataLoadError,
    delete_workout_draft,
    load_workout_draft,
    save_workout_draft,
)
from workout_app.ui_helpers import load_data_or_stop, render_data_portability
from workout_app.workout_logic import (
    group_slots_by_snapshot,
    is_valid_weight_input,
    move_completed_units_to_end,
    new_workout_snapshot,
    reorder_snapshot_units,
    restore_snapshot_order,
    shuffle_snapshot,
    shuffle_snapshot_alternates,
    snapshot_unit_id,
)


active_user_id = require_active_user()
exercise_document, routine_document = load_data_or_stop(active_user_id)
render_data_portability(active_user_id, exercise_document, routine_document)

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

saved_draft = load_workout_draft(active_user_id, routine_document)
if saved_draft and not st.session_state.get("workout_draft_handled", False):
    completed_in_draft = sum(
        row["completed"] for row in saved_draft["snapshot"]
    )
    total_in_draft = len(saved_draft["snapshot"])
    st.info(
        f"Resume {saved_draft['routine_name']}? "
        f"{completed_in_draft} of {total_in_draft} exercises were completed."
    )
    resume_column, fresh_column = st.columns(2)
    if resume_column.button("Resume workout", type="primary", width="stretch"):
        routine_id = saved_draft["routine_id"]
        requested = saved_draft["requested_count"]
        st.session_state.workout_routine_id = routine_id
        st.session_state[f"workout_requested_count_{routine_id}"] = requested
        st.session_state.active_workout = saved_draft["snapshot"]
        st.session_state.active_workout_identity = (
            active_user_id,
            routine_id,
            requested,
        )
        st.session_state.workout_widget_nonce = (
            st.session_state.get("workout_widget_nonce", 0) + 1
        )
        st.session_state.workout_draft_handled = True
        st.rerun()
    if fresh_column.button("Start fresh", width="stretch"):
        delete_workout_draft(active_user_id)
        st.session_state.workout_draft_handled = True
        st.rerun()
    st.stop()

if st.session_state.get("workout_routine_id") not in (None, *routine_ids):
    del st.session_state["workout_routine_id"]
routine_selectbox_arguments: dict[str, Any] = {
    "label": "Select workout",
    "options": routine_ids,
    "format_func": lambda routine_id: routine_by_id[routine_id]["name"],
    "key": "workout_routine_id",
}
if "workout_routine_id" not in st.session_state:
    routine_selectbox_arguments["index"] = default_routine_index
selected_routine_id = st.selectbox(**routine_selectbox_arguments)
selected_routine = routine_by_id[selected_routine_id]
slot_count = len(selected_routine["slots"])
if slot_count == 0:
    st.info("This routine has no exercise slots yet.")
    st.stop()

requested_count_key = f"workout_requested_count_{selected_routine_id}"
number_input_arguments: dict[str, Any] = {
    "label": "Number of exercises",
    "min_value": 1,
    "max_value": slot_count,
    "step": 1,
    "help": (
        "Higher-priority items are kept first. Supersets stay together, so the "
        "displayed total can be below this target."
    ),
    "key": requested_count_key,
}
if requested_count_key not in st.session_state:
    number_input_arguments["value"] = slot_count
requested_count = st.number_input(**number_input_arguments)


def reset_active_workout() -> None:
    """Build a clean snapshot and invalidate prior widget state via a nonce."""

    st.session_state.active_workout = new_workout_snapshot(selected_routine, int(requested_count))
    st.session_state.active_workout_identity = (
        active_user_id,
        selected_routine_id,
        int(requested_count),
    )
    st.session_state.workout_widget_nonce = st.session_state.get("workout_widget_nonce", 0) + 1
    delete_workout_draft(active_user_id)


current_identity = (active_user_id, selected_routine_id, int(requested_count))
if st.session_state.get("active_workout_identity") != current_identity:
    reset_active_workout()

snapshot: list[dict[str, Any]] = st.session_state.active_workout


def workout_has_progress() -> bool:
    """Avoid creating a recovery prompt for an untouched default workout."""

    natural_order = [
        row["slot"]["id"] for row in sorted(snapshot, key=lambda row: row["slot"]["order"])
    ]
    base_order = [
        row["slot"]["id"] for row in sorted(snapshot, key=lambda row: row["base_position"])
    ]
    return (
        int(requested_count) != slot_count
        or natural_order != base_order
        or any(
            row["completed"]
            or row.get("weight_used", "")
            or row["selected_exercise_id"] != row["slot"]["default_exercise_id"]
            for row in snapshot
        )
    )


def sync_workout_draft() -> None:
    """Write current progress, or remove the draft when no progress remains."""

    try:
        if workout_has_progress():
            save_workout_draft(
                active_user_id,
                selected_routine_id,
                int(requested_count),
                snapshot,
            )
        else:
            delete_workout_draft(active_user_id)
    except DataLoadError as error:
        st.warning(f"Workout recovery could not be updated: {error}")

button_columns = st.columns(4)
if button_columns[0].button("Shuffle", width="stretch"):
    shuffle_snapshot(st.session_state.active_workout)
    sync_workout_draft()
    st.rerun()
if button_columns[1].button("Shuffle to alternates", width="stretch"):
    shuffle_snapshot_alternates(st.session_state.active_workout)
    sync_workout_draft()
    st.rerun()
if button_columns[2].button("Original order", width="stretch"):
    restore_snapshot_order(st.session_state.active_workout)
    sync_workout_draft()
    st.rerun()
if button_columns[3].button("Reset", width="stretch", type="secondary"):
    reset_active_workout()
    st.rerun()

if len(snapshot) < int(requested_count):
    st.caption(
        f"Showing {len(snapshot)} exercises. A superset that would exceed your target was kept intact and skipped."
    )

exercise_by_id = {
    exercise["id"]: exercise for exercise in exercise_document["exercises"]
}
widget_nonce = st.session_state.workout_widget_nonce


def safe_dom_id(value: str) -> str:
    """Return the key suffix used by workout card and drag-handle elements."""

    return "".join(character if character.isalnum() else "_" for character in value)


drag_reorder_key = f"workout_drag_reorder_{widget_nonce}"


def apply_dragged_order() -> None:
    """Apply a component reorder event before the workout page rerenders."""

    component_state = st.session_state.get(drag_reorder_key)
    ordered_unit_ids = getattr(component_state, "reordered", None)
    if ordered_unit_ids is None and isinstance(component_state, dict):
        ordered_unit_ids = component_state.get("reordered")
    if ordered_unit_ids:
        reorder_snapshot_units(st.session_state.active_workout, list(ordered_unit_ids))
        sync_workout_draft()


drag_units = [
    {
        "id": snapshot_unit_id(unit),
        "slot_keys": [safe_dom_id(row["slot"]["id"]) for row in unit],
    }
    for unit in group_slots_by_snapshot(snapshot)
]
workout_drag_reorder(
    drag_units,
    key=drag_reorder_key,
    on_reordered_change=apply_dragged_order,
)


@st.dialog("Exercise details", width="small", position="center")
def show_exercise_details(exercise_id: str) -> None:
    """Show only the selected exercise's notes and optional external link."""

    exercise = exercise_by_id[exercise_id]
    st.subheader(exercise["name"])

    notes = exercise.get("notes", "").strip()
    exercise_url = exercise.get("demo_url", "").strip()
    if notes:
        st.markdown(f"**Notes:** {notes}")
    if exercise_url:
        st.link_button(
            "Open exercise link",
            exercise_url,
            icon=":material/open_in_new:",
        )
    if not notes and not exercise_url:
        st.caption("No notes or link have been added for this exercise.")

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
        /* Every middle member gets its own horizontal connection to the
           shared vertical rail, not just the first and last cards. */
        background: linear-gradient(
            var(--workout-progress-blue),
            var(--workout-progress-blue)
        ) left center / 100% 4px no-repeat;
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
    .workout-prescription {
        margin: 0.15rem 0 0.45rem;
        line-height: 1.4;
        overflow-wrap: anywhere;
    }
    .workout-prescription__separator {
        display: none;
    }
    .workout-prescription__weight {
        display: block;
        margin-top: 0.1rem;
    }
    .weight-validation-warning {
        margin: 0.15rem 0 0;
        color: #b45309;
        font-size: 0.75rem;
        line-height: 1.25;
    }
    /* Exercise names are labels, not page sections, so suppress the anchor
       that Streamlit normally adds to Markdown headings. */
    div[class*="st-key-exercise_header_"] h3 a,
    div[class*="st-key-exercise_header_"] [data-testid="stHeaderActionElements"] {
        display: none !important;
    }
    /* Keep the accessible label while showing only the requested info icon. */
    div[class*="st-key-details_"] button p {
        display: none;
    }
    /* Streamlit's center dialog preset centers horizontally but aligns the
       dialog to the top of its overlay. Center this details dialog on both
       axes while retaining a small viewport-edge safety margin. */
    div[data-testid="stDialog"] {
        align-items: center !important;
        padding-top: 1rem !important;
        padding-bottom: 1rem !important;
    }
    @media (max-width: 640px) {
        html,
        body,
        [data-testid="stAppViewContainer"],
        section[data-testid="stMain"] {
            max-width: 100%;
            overflow-x: hidden;
        }
        .block-container {
            max-width: 100%;
            padding-left: 0.75rem;
            padding-right: 0.75rem;
        }
        /* Every card uses the same width. The shared empty lane means regular
           exercises and grouped members remain visually aligned. */
        div[class*="st-key-workout_card_"],
        div[class*="st-key-superset_member_"] {
            width: calc(100% - 7.25rem) !important;
            margin-left: 1.75rem;
            margin-bottom: -0.2rem;
        }
        div[class*="st-key-superset_member_"]::after {
            right: -1.35rem;
            width: 0.8rem;
        }
        div[class*="st-key-superset_member_"][class*="_label_"]::before {
            right: -5.35rem;
            padding: 0.1rem 0.25rem;
            font-size: 0.72rem;
        }
        div[class*="st-key-workout_card_"] [data-testid="stVerticalBlockBorderWrapper"],
        div[class*="st-key-superset_member_"] [data-testid="stVerticalBlockBorderWrapper"] {
            padding: 0.6rem 0.65rem !important;
        }
        div[class*="st-key-workout_card_"] [data-testid="stVerticalBlock"],
        div[class*="st-key-superset_member_"] [data-testid="stVerticalBlock"] {
            gap: 0.4rem;
        }
        div[class*="st-key-workout_card_"] h3,
        div[class*="st-key-superset_member_"] h3 {
            margin: 0;
            padding: 0;
            font-size: 1.05rem !important;
            line-height: 1.2;
        }
        div[class*="st-key-workout_card_"] p,
        div[class*="st-key-superset_member_"] p {
            margin-top: 0.1rem;
            margin-bottom: 0.1rem;
            font-size: 0.82rem;
            line-height: 1.25;
        }
        div[class*="st-key-workout_card_"] button,
        div[class*="st-key-superset_member_"] button {
            min-height: 2rem;
            padding: 0.25rem 0.4rem;
            font-size: 0.78rem;
        }
        /* Keep this specific row horizontal when Streamlit stacks other
           columns on narrow screens. */
        div[class*="st-key-exercise_header_"] [data-testid="stHorizontalBlock"] {
            display: flex;
            flex-wrap: nowrap !important;
            align-items: center;
            gap: 0.35rem !important;
        }
        div[class*="st-key-exercise_header_"] [data-testid="stColumn"] {
            width: auto !important;
            min-width: 0 !important;
        }
        div[class*="st-key-exercise_header_"] [data-testid="stColumn"]:nth-child(1) {
            flex: 0 0 2rem !important;
        }
        div[class*="st-key-exercise_header_"] [data-testid="stColumn"]:nth-child(2) {
            flex: 1 1 auto !important;
        }
        div[class*="st-key-exercise_header_"] [data-testid="stColumn"]:nth-child(3) {
            flex: 0 0 5rem !important;
        }
        div[class*="st-key-exercise_header_"] [data-testid="stPopover"] button {
            min-height: 1.7rem;
            padding: 0.1rem 0.15rem;
            font-size: 0.7rem;
        }
        div[class*="st-key-exercise_header_"] [data-testid="stPopover"] button p {
            display: none;
        }
        div[class*="st-key-weight_used_"] input {
            min-height: 2rem;
            font-size: 0.8rem;
        }
        .workout-prescription {
            margin: 0.15rem 0 0.45rem;
            font-size: 0.8rem;
            line-height: 1.35;
        }
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
    safe_slot_id = safe_dom_id(slot["id"])
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
        selected_exercise_id = row["selected_exercise_id"]
        weight_key = f"weight_used_{widget_nonce}_{slot['id']}"
        current_weight = str(
            st.session_state.get(weight_key, row.get("weight_used", ""))
        )
        weight_is_valid = is_valid_weight_input(current_weight)
        done_key = f"done_{widget_nonce}_{slot['id']}"

        # Never allow a checked item with malformed weight data. This repairs
        # stale/hot-reloaded sessions that would otherwise leave the weight
        # field disabled before the user can correct it.
        is_currently_checked = bool(
            st.session_state.get(done_key, row["completed"])
        )
        if is_currently_checked and not weight_is_valid:
            row["completed"] = False
            st.session_state[done_key] = False

        with st.container(key=f"exercise_header_{safe_slot_id}"):
            checkbox_column, name_column, action_column = st.columns(
                [0.35, 5.2, 1.75], vertical_alignment="center"
            )
            completed = checkbox_column.checkbox(
                "Done",
                value=row["completed"],
                key=done_key,
                label_visibility="collapsed",
                disabled=not weight_is_valid,
            )
            row["completed"] = completed

            exercise_name = exercise_by_id[selected_exercise_id]["name"]
            name_column.markdown(
                f"### {'~~' + exercise_name + '~~' if completed else exercise_name}"
            )

            has_alternates = len(allowed_ids) > 1
            with action_column.container(
                horizontal=True,
                horizontal_alignment="right",
                vertical_alignment="center",
                gap="xsmall",
                wrap=False,
            ):
                show_details = st.button(
                    "Exercise information",
                    key=f"details_{widget_nonce}_{slot['id']}",
                    type="tertiary",
                    icon=":material/info:",
                )
                if show_details:
                    show_exercise_details(selected_exercise_id)

                with st.popover(
                    "Swap",
                    icon=":material/swap_horiz:",
                    disabled=not has_alternates,
                    width="content",
                    key=f"swap_{widget_nonce}_{slot['id']}",
                ):
                    st.caption("Choose an exercise")
                    for exercise_id in allowed_ids:
                        is_current = exercise_id == selected_exercise_id
                        if st.button(
                            exercise_by_id[exercise_id]["name"],
                            key=f"swap_option_{widget_nonce}_{slot['id']}_{exercise_id}",
                            disabled=is_current,
                            type="primary" if is_current else "secondary",
                            width="stretch",
                        ):
                            row["selected_exercise_id"] = exercise_id
                            sync_workout_draft()
                            st.rerun()

        st.markdown(
            '<div class="workout-prescription">'
            f"<strong>{escape(str(slot['sets']))} × {escape(str(slot['reps']))}</strong>"
            '<span class="workout-prescription__separator"> · </span>'
            '<span class="workout-prescription__weight">Reference weight: '
            f"<strong>{escape(str(slot['reference_weight']))}</strong></span>"
            "</div>",
            unsafe_allow_html=True,
        )
        entered_weight = st_keyup(
            "Weight used (optional)",
            value=row.get("weight_used", ""),
            placeholder="Weight used (optional)",
            key=weight_key,
            label_visibility="collapsed",
            disabled=completed,
        )
        if is_valid_weight_input(entered_weight):
            row["weight_used"] = entered_weight
        else:
            st.markdown(
                '<p class="weight-validation-warning">'
                "Enter numbers with at most one decimal point."
                "</p>",
                unsafe_allow_html=True,
            )


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
did_reorder_completed = move_completed_units_to_end(snapshot)
sync_workout_draft()
if did_reorder_completed:
    st.rerun()
st.progress(completed_count / len(snapshot), text=f"{completed_count} of {len(snapshot)} complete")

# A compact motivational footer, kept below the workout controls and progress.
st.write("")
_, motivation_column, _ = st.columns([1, 2, 1])
with motivation_column:
    st.image(Path(__file__).resolve().parent.parent / "Arnold.webp", width="stretch")
