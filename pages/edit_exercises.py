"""Exercise library maintenance page."""

from __future__ import annotations

from copy import deepcopy
from uuid import uuid4

import streamlit as st

from workout_app.storage import exercise_reference_locations, save_data
from workout_app.ui_helpers import (
    load_data_or_stop,
    normalized_tags,
    render_data_portability,
    show_save_error,
)
from workout_app.validation import DataValidationError
from workout_app.storage import DataLoadError


exercise_document, routine_document = load_data_or_stop()
render_data_portability(exercise_document, routine_document)

st.title("Edit exercises")
st.caption("Exercises are reusable. Sets, reps, and weight are configured in routine slots.")

exercises = sorted(exercise_document["exercises"], key=lambda exercise: exercise["name"].casefold())
st.dataframe(
    [
        {
            "Exercise": exercise["name"],
            "Muscles targeted": ", ".join(exercise["muscles_targeted"]),
            "Tags": ", ".join(exercise["tags"]),
            "Notes": exercise.get("notes", ""),
        }
        for exercise in exercises
    ],
    width="stretch",
    hide_index=True,
)

st.subheader("Exercise details")
exercise_by_id = {exercise["id"]: exercise for exercise in exercises}
new_exercise_option = "__new_exercise__"

# After creating or deleting an item, select the most useful next option on the
# following rerun. The assignment must happen before the selectbox is created.
pending_selection = st.session_state.pop("exercise_editor_pending_selection", None)
if pending_selection is not None:
    st.session_state.exercise_editor_selection = pending_selection

selected_id = st.selectbox(
    "Exercise",
    options=[new_exercise_option, *exercise_by_id],
    format_func=lambda exercise_id: (
        "New exercise" if exercise_id == new_exercise_option else exercise_by_id[exercise_id]["name"]
    ),
    key="exercise_editor_selection",
)
is_new_exercise = selected_id == new_exercise_option
selected = exercise_by_id.get(selected_id, {})

# Creation and editing intentionally share one form so the page stays compact
# and every exercise field behaves consistently in both modes.
with st.form(f"exercise_details_{selected_id}", clear_on_submit=is_new_exercise):
    edited_name = st.text_input("Name", value=selected.get("name", ""))
    edited_muscles = st.text_input(
        "Muscles targeted",
        value=", ".join(selected.get("muscles_targeted", [])),
        help="Required. Separate multiple muscle groups with commas.",
    )
    edited_tags = st.text_input(
        "Tags (optional)",
        value=", ".join(selected.get("tags", [])),
        help="Use these for additional labels such as Push, Compound, or equipment.",
    )
    edited_notes = st.text_area("Notes (optional)", value=selected.get("notes", ""))
    save_submitted = st.form_submit_button(
        "Add exercise" if is_new_exercise else "Save changes", type="primary"
    )

if save_submitted:
    muscles_targeted = normalized_tags(edited_muscles)
    tags = normalized_tags(edited_tags)
    if not edited_name.strip() or not muscles_targeted:
        st.error("Enter an exercise name and at least one targeted muscle.")
    else:
        updated_exercises = deepcopy(exercise_document)
        if is_new_exercise:
            saved_exercise_id = str(uuid4())
            updated_exercises["exercises"].append(
                {
                    "id": saved_exercise_id,
                    "name": edited_name.strip(),
                    "muscles_targeted": muscles_targeted,
                    "tags": tags,
                    "notes": edited_notes.strip(),
                }
            )
        else:
            saved_exercise_id = selected_id
            target = next(
                exercise
                for exercise in updated_exercises["exercises"]
                if exercise["id"] == selected_id
            )
            target.update(
                name=edited_name.strip(),
                muscles_targeted=muscles_targeted,
                tags=tags,
                notes=edited_notes.strip(),
            )
        try:
            save_data(updated_exercises, routine_document)
        except (DataLoadError, DataValidationError) as error:
            show_save_error(error)
        else:
            st.session_state.exercise_editor_pending_selection = saved_exercise_id
            st.rerun()

if not is_new_exercise:
    references = exercise_reference_locations(routine_document, selected_id)
    with st.expander("Delete this exercise"):
        if references:
            st.warning("This exercise cannot be deleted because these routine slots use it:")
            for reference in references:
                st.write(f"- {reference}")
        elif st.button("Delete exercise", type="secondary"):
            updated_exercises = deepcopy(exercise_document)
            updated_exercises["exercises"] = [
                exercise for exercise in updated_exercises["exercises"] if exercise["id"] != selected_id
            ]
            try:
                save_data(updated_exercises, routine_document)
            except (DataLoadError, DataValidationError) as error:
                show_save_error(error)
            else:
                st.session_state.exercise_editor_pending_selection = new_exercise_option
                st.rerun()
