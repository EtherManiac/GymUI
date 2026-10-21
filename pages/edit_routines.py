"""Routine and grouped exercise-slot maintenance page."""

from __future__ import annotations

from copy import deepcopy
from typing import Any
from uuid import uuid4

import streamlit as st

from workout_app.profile_ui import require_active_user
from workout_app.sharing import copy_routine_into_documents, missing_routine_exercises
from workout_app.storage import DataLoadError, load_data, save_data
from workout_app.ui_helpers import (
    all_muscles,
    all_tags,
    exercises_matching_filters,
    load_data_or_stop,
    render_data_portability,
    show_save_error,
)
from workout_app.validation import DataValidationError
from workout_app.workout_logic import group_slots, ordered_slots
from workout_app.users import USER_NAMES, user_name


active_user_id = require_active_user()
exercise_document, routine_document = load_data_or_stop(active_user_id)
render_data_portability(active_user_id, exercise_document, routine_document)

st.title("Edit routines")
st.caption("Add a single exercise or build and edit a complete superset in one place.")


def persist(updated_routines: dict[str, Any]) -> bool:
    """Save routine edits and show consistent feedback to the user."""

    try:
        save_data(active_user_id, exercise_document, updated_routines)
    except (DataLoadError, DataValidationError) as error:
        show_save_error(error)
        return False
    return True


routines = sorted(routine_document["routines"], key=lambda routine: routine["name"].casefold())
routine_by_id = {routine["id"]: routine for routine in routines}
new_routine_option = "__new_routine__"
import_routine_option = "__import_routine__"

# Apply post-save selection before constructing the widget. This lets a newly
# created routine open immediately without mutating an instantiated selectbox.
pending_selection = st.session_state.pop("routine_editor_pending_selection", None)
if pending_selection is not None:
    st.session_state.routine_editor_selection = pending_selection

st.subheader("Routine details")
selected_routine_id = st.selectbox(
    "Routine",
    options=[new_routine_option, import_routine_option, *routine_by_id],
    format_func=lambda routine_id: (
        "New routine"
        if routine_id == new_routine_option
        else "Import from other user"
        if routine_id == import_routine_option
        else routine_by_id[routine_id]["name"]
    ),
    key="routine_editor_selection",
)
is_new_routine = selected_routine_id == new_routine_option
is_importing_routine = selected_routine_id == import_routine_option
selected_routine = routine_by_id.get(selected_routine_id)

if is_importing_routine:
    with st.container(border=True):
        other_user_ids = [user_id for user_id in USER_NAMES if user_id != active_user_id]
        source_user_id = st.selectbox(
            "Import from user",
            options=other_user_ids,
            format_func=user_name,
            key="routine_import_source_user",
        )
        try:
            source_exercise_document, source_routine_document = load_data(source_user_id)
        except (DataLoadError, DataValidationError) as error:
            st.error("That user's routines could not be loaded.")
            st.code(str(error))
            st.stop()

        source_routines = sorted(
            source_routine_document["routines"],
            key=lambda routine: routine["name"].casefold(),
        )
        if not source_routines:
            st.info(f"{user_name(source_user_id)} has no routines to import yet.")
        else:
            source_routine_by_id = {
                routine["id"]: routine for routine in source_routines
            }
            source_routine_id = st.selectbox(
                "Routine to import",
                options=list(source_routine_by_id),
                format_func=lambda routine_id: source_routine_by_id[routine_id]["name"],
                key=f"routine_import_selection_{source_user_id}",
            )
            source_routine = source_routine_by_id[source_routine_id]
            missing_exercises = missing_routine_exercises(
                exercise_document,
                source_exercise_document,
                source_routine,
            )

            if missing_exercises:
                st.warning(
                    "This routine needs exercises that are not exact matches for "
                    "exercises in your profile. Import all of them to continue:"
                )
                for exercise in missing_exercises:
                    st.write(f"- {exercise['name']}")
                import_label = "Import routine and missing exercises"
            else:
                st.info(
                    "Every exercise in this routine already has an exact match in "
                    "your profile."
                )
                import_label = "Import routine"

            action_columns = st.columns(2)
            if action_columns[0].button(
                import_label,
                type="primary",
                width="stretch",
            ):
                updated_exercises, updated_routines, imported_routine_id = (
                    copy_routine_into_documents(
                        exercise_document,
                        routine_document,
                        source_exercise_document,
                        source_routine,
                        lambda: str(uuid4()),
                    )
                )
                try:
                    save_data(active_user_id, updated_exercises, updated_routines)
                except (DataLoadError, DataValidationError) as error:
                    show_save_error(error)
                else:
                    st.session_state.routine_editor_pending_selection = (
                        imported_routine_id
                    )
                    st.rerun()

            if missing_exercises and action_columns[1].button(
                "Cancel",
                width="stretch",
            ):
                st.session_state.routine_editor_pending_selection = new_routine_option
                st.rerun()
    st.stop()

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
    st.info("Create the routine to begin adding exercises or supersets.")
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
available_muscles = all_muscles(exercise_document)
exercise_name_by_id = {
    exercise["id"]: exercise["name"] for exercise in exercise_document["exercises"]
}


def render_exercise_fields(
    key_prefix: str,
    exercise_number: int,
    initial_slot: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Render one member of a single exercise or superset editor.

    Each member owns its filters, alternatives, and prescription. Existing choices
    remain visible if filters were changed so the UI can explain and repair a
    mismatch rather than crashing during the rerun.
    """

    initial_slot = initial_slot or {}
    st.markdown(f"**Exercise {exercise_number}**")
    required_muscles = st.multiselect(
        "Muscles targeted",
        options=available_muscles,
        default=initial_slot.get("required_muscles", []),
        key=f"{key_prefix}_muscles",
        help="Required. The exercise and every alternative must target all selected muscles.",
    )
    required_tags = st.multiselect(
        "Additional tags (optional)",
        options=available_tags,
        default=initial_slot.get("required_tags", []),
        key=f"{key_prefix}_tags",
        help="Optionally narrow the choices further using general exercise tags.",
    )
    matching_exercises = (
        exercises_matching_filters(exercise_document, required_muscles, required_tags)
        if required_muscles
        else []
    )
    matching_ids = [exercise["id"] for exercise in matching_exercises]

    # Keep saved selections in the control even when a tag edit temporarily
    # makes them invalid. Saving remains blocked until the mismatch is repaired.
    selectable_ids = list(matching_ids)
    existing_ids = [
        initial_slot.get("default_exercise_id"),
        *initial_slot.get("alternative_exercise_ids", []),
    ]
    for exercise_id in existing_ids:
        if exercise_id and exercise_id not in selectable_ids:
            selectable_ids.append(exercise_id)

    if not required_muscles:
        st.info("Select at least one targeted muscle.")
        return None
    if not selectable_ids:
        st.warning("No exercises match all selected muscle and tag filters.")
        return None

    initial_default = initial_slot.get("default_exercise_id")
    default_index = selectable_ids.index(initial_default) if initial_default in selectable_ids else 0
    default_exercise_id = st.selectbox(
        "Default exercise",
        options=selectable_ids,
        index=default_index,
        format_func=lambda exercise_id: exercise_name_by_id[exercise_id],
        key=f"{key_prefix}_default",
    )
    alternative_options = [
        exercise_id for exercise_id in selectable_ids if exercise_id != default_exercise_id
    ]
    initial_alternatives = [
        exercise_id
        for exercise_id in initial_slot.get("alternative_exercise_ids", [])
        if exercise_id in alternative_options
    ]
    alternative_exercise_ids = st.multiselect(
        "Alternatives (optional)",
        options=alternative_options,
        default=initial_alternatives,
        format_func=lambda exercise_id: exercise_name_by_id[exercise_id],
        key=f"{key_prefix}_alternatives",
    )

    detail_columns = st.columns(3)
    sets = detail_columns[0].text_input(
        "Sets", value=initial_slot.get("sets", "3"), key=f"{key_prefix}_sets"
    )
    reps = detail_columns[1].text_input(
        "Reps", value=initial_slot.get("reps", "8-12"), key=f"{key_prefix}_reps"
    )
    reference_weight = detail_columns[2].text_input(
        "Reference weight",
        value=initial_slot.get("reference_weight", "Bodyweight"),
        key=f"{key_prefix}_weight",
    )
    return {
        "required_muscles": required_muscles,
        "required_tags": required_tags,
        "default_exercise_id": default_exercise_id,
        "alternative_exercise_ids": alternative_exercise_ids,
        "sets": sets.strip(),
        "reps": reps.strip(),
        "reference_weight": reference_weight.strip(),
        "matching_ids": matching_ids,
    }


def draft_errors(drafts: list[dict[str, Any] | None]) -> list[str]:
    """Return concise errors for a group of exercise editor drafts."""

    errors: list[str] = []
    for index, draft in enumerate(drafts, start=1):
        if draft is None:
            errors.append(
                f"Exercise {index} needs a targeted muscle and a matching default exercise."
            )
            continue
        if not all((draft["sets"], draft["reps"], draft["reference_weight"])):
            errors.append(f"Exercise {index} needs sets, reps, and a reference weight.")
        selected_ids = [draft["default_exercise_id"], *draft["alternative_exercise_ids"]]
        if any(exercise_id not in draft["matching_ids"] for exercise_id in selected_ids):
            errors.append(f"Exercise {index}'s selections must match all selected filters.")
    return errors


def slot_from_draft(
    draft: dict[str, Any],
    slot_id: str,
    order: int,
    priority: int,
    group_id: str | None,
) -> dict[str, Any]:
    """Convert UI-only draft data into the documented persistent slot shape."""

    return {
        "id": slot_id,
        "order": order,
        "priority": priority,
        "required_muscles": draft["required_muscles"],
        "required_tags": draft["required_tags"],
        "default_exercise_id": draft["default_exercise_id"],
        "alternative_exercise_ids": draft["alternative_exercise_ids"],
        "sets": draft["sets"],
        "reps": draft["reps"],
        "reference_weight": draft["reference_weight"],
        "superset_group_id": group_id,
    }


def target_routine(document: dict[str, Any]) -> dict[str, Any]:
    """Find the currently selected routine inside a copied document."""

    return next(
        routine for routine in document["routines"] if routine["id"] == selected_routine_id
    )


st.subheader("Add an exercise or superset")
with st.container(border=True):
    add_as_superset = st.toggle(
        "Make this a superset", key=f"add_superset_{selected_routine_id}"
    )
    add_count = 1
    if add_as_superset:
        add_count = int(
            st.number_input(
                "Number of exercises in the superset",
                min_value=2,
                max_value=6,
                value=2,
                step=1,
                key=f"add_count_{selected_routine_id}",
            )
        )

    # New items default below current priorities, but priority is deliberately
    # independent from the item's position at the end of the routine.
    suggested_priority = max(
        (slot["priority"] for slot in selected_routine["slots"]), default=0
    ) + 1
    add_priority = int(
        st.number_input(
            "Priority",
            min_value=1,
            max_value=99,
            value=min(suggested_priority, 99),
            step=1,
            key=f"add_priority_{selected_routine_id}",
            help="1 is highest priority and is kept longest when shortening a workout.",
        )
    )

    add_drafts: list[dict[str, Any] | None] = []
    for member_index in range(add_count):
        with st.container(border=add_as_superset):
            add_drafts.append(
                render_exercise_fields(
                    f"add_{selected_routine_id}_{member_index}", member_index + 1
                )
            )

    if st.button(
        "Add superset" if add_as_superset else "Add exercise",
        type="primary",
        key=f"add_item_{selected_routine_id}",
    ):
        errors = draft_errors(add_drafts)
        if errors:
            for error in errors:
                st.error(error)
        else:
            updated = deepcopy(routine_document)
            routine = target_routine(updated)
            next_order = len(routine["slots"]) + 1
            group_id = str(uuid4()) if add_as_superset else None
            for member_index, draft in enumerate(add_drafts):
                routine["slots"].append(
                    slot_from_draft(
                        draft,
                        slot_id=str(uuid4()),
                        order=next_order + member_index,
                        priority=add_priority,
                        group_id=group_id,
                    )
                )
            if persist(updated):
                st.rerun()


st.subheader("Routine exercises")
routine_blocks = group_slots(ordered_slots(selected_routine))
if not routine_blocks:
    st.info("This routine does not have any exercises yet.")

for block_index, block in enumerate(routine_blocks):
    block_names = " + ".join(exercise_name_by_id[slot["default_exercise_id"]] for slot in block)
    block_title = f"Superset · {block_names}" if len(block) > 1 else block_names
    block_title = f"{block_title} | Priority {block[0]['priority']}"
    anchor_id = block[0]["id"]

    with st.expander(f"{block_index + 1}. {block_title}", expanded=False):
        move_columns = st.columns(2)
        if move_columns[0].button(
            "Move up",
            key=f"up_block_{anchor_id}",
            disabled=block_index == 0,
            width="stretch",
        ):
            reordered_blocks = deepcopy(routine_blocks)
            reordered_blocks[block_index - 1], reordered_blocks[block_index] = (
                reordered_blocks[block_index],
                reordered_blocks[block_index - 1],
            )
            flattened = [slot for routine_block in reordered_blocks for slot in routine_block]
            for order, slot in enumerate(flattened, start=1):
                slot["order"] = order
            updated = deepcopy(routine_document)
            target_routine(updated)["slots"] = flattened
            if persist(updated):
                st.rerun()

        if move_columns[1].button(
            "Move down",
            key=f"down_block_{anchor_id}",
            disabled=block_index == len(routine_blocks) - 1,
            width="stretch",
        ):
            reordered_blocks = deepcopy(routine_blocks)
            reordered_blocks[block_index], reordered_blocks[block_index + 1] = (
                reordered_blocks[block_index + 1],
                reordered_blocks[block_index],
            )
            flattened = [slot for routine_block in reordered_blocks for slot in routine_block]
            for order, slot in enumerate(flattened, start=1):
                slot["order"] = order
            updated = deepcopy(routine_document)
            target_routine(updated)["slots"] = flattened
            if persist(updated):
                st.rerun()

        edit_as_superset = st.toggle(
            "Make this a superset",
            value=len(block) > 1,
            key=f"is_superset_{anchor_id}",
        )
        edit_priority = int(
            st.number_input(
                "Priority",
                min_value=1,
                max_value=99,
                value=block[0]["priority"],
                step=1,
                key=f"priority_{anchor_id}",
                help="1 is highest. Changing this does not change routine order.",
            )
        )

        if edit_as_superset:
            edit_count = int(
                st.number_input(
                    "Number of exercises in the superset",
                    min_value=2,
                    max_value=6,
                    value=max(2, len(block)),
                    step=1,
                    key=f"member_count_{anchor_id}",
                    help="Increasing adds members; decreasing removes members from the end when saved.",
                )
            )
        else:
            # Turning off a saved superset splits all its current members into
            # individual routine exercises instead of deleting any of them.
            edit_count = len(block)
            if len(block) > 1:
                st.caption("Saving will split these members into individual exercises.")

        edit_drafts: list[dict[str, Any] | None] = []
        for member_index in range(edit_count):
            initial_slot = block[member_index] if member_index < len(block) else None
            with st.container(border=edit_as_superset or len(block) > 1):
                edit_drafts.append(
                    render_exercise_fields(
                        f"edit_{anchor_id}_{member_index}",
                        member_index + 1,
                        initial_slot,
                    )
                )

        action_columns = st.columns(2)
        if action_columns[0].button(
            "Save superset" if edit_as_superset else "Save exercise",
            key=f"save_block_{anchor_id}",
            type="primary",
            width="stretch",
        ):
            errors = draft_errors(edit_drafts)
            if errors:
                for error in errors:
                    st.error(error)
            else:
                original_group_id = block[0].get("superset_group_id")
                group_id = (original_group_id or str(uuid4())) if edit_as_superset else None
                replacement_slots = [
                    slot_from_draft(
                        draft,
                        slot_id=(
                            block[member_index]["id"]
                            if member_index < len(block)
                            else str(uuid4())
                        ),
                        order=1,
                        priority=edit_priority,
                        group_id=group_id,
                    )
                    for member_index, draft in enumerate(edit_drafts)
                ]
                replaced_ids = {slot["id"] for slot in block}
                rebuilt_slots: list[dict[str, Any]] = []
                replacement_inserted = False
                for slot in ordered_slots(selected_routine):
                    if slot["id"] in replaced_ids:
                        if not replacement_inserted:
                            rebuilt_slots.extend(replacement_slots)
                            replacement_inserted = True
                    else:
                        rebuilt_slots.append(slot)
                for order, slot in enumerate(rebuilt_slots, start=1):
                    slot["order"] = order
                updated = deepcopy(routine_document)
                target_routine(updated)["slots"] = rebuilt_slots
                if persist(updated):
                    st.rerun()

        if action_columns[1].button(
            "Remove superset" if len(block) > 1 else "Remove exercise",
            key=f"remove_block_{anchor_id}",
            width="stretch",
        ):
            removed_ids = {slot["id"] for slot in block}
            remaining_slots = [
                slot for slot in ordered_slots(selected_routine) if slot["id"] not in removed_ids
            ]
            for order, slot in enumerate(remaining_slots, start=1):
                slot["order"] = order
            updated = deepcopy(routine_document)
            target_routine(updated)["slots"] = remaining_slots
            if persist(updated):
                st.rerun()
