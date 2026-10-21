"""Exercise library maintenance page."""

from __future__ import annotations

from copy import deepcopy
from uuid import uuid4

import streamlit as st

from workout_app.profile_ui import require_active_user
from workout_app.sharing import copy_exercise_into_document
from workout_app.storage import exercise_reference_locations, load_data, save_data
from workout_app.ui_helpers import (
    load_data_or_stop,
    normalized_tags,
    render_data_portability,
    show_save_error,
)
from workout_app.validation import DataValidationError
from workout_app.storage import DataLoadError
from workout_app.users import USER_NAMES, user_name


active_user_id = require_active_user()
exercise_document, routine_document = load_data_or_stop(active_user_id)
render_data_portability(active_user_id, exercise_document, routine_document)

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
import_exercise_option = "__import_exercise__"

# After creating or deleting an item, select the most useful next option on the
# following rerun. The assignment must happen before the selectbox is created.
pending_selection = st.session_state.pop("exercise_editor_pending_selection", None)
if pending_selection is not None:
    st.session_state.exercise_editor_selection = pending_selection

selected_id = st.selectbox(
    "Exercise",
    options=[new_exercise_option, import_exercise_option, *exercise_by_id],
    format_func=lambda exercise_id: (
        "New exercise"
        if exercise_id == new_exercise_option
        else "Import from other user"
        if exercise_id == import_exercise_option
        else exercise_by_id[exercise_id]["name"]
    ),
    key="exercise_editor_selection",
)
is_new_exercise = selected_id == new_exercise_option
is_importing_exercise = selected_id == import_exercise_option
selected = exercise_by_id.get(selected_id, {})

if is_importing_exercise:
    with st.container(border=True):
        other_user_ids = [user_id for user_id in USER_NAMES if user_id != active_user_id]
        source_user_id = st.selectbox(
            "Import from user",
            options=other_user_ids,
            format_func=user_name,
            key="exercise_import_source_user",
        )
        try:
            source_exercise_document, _ = load_data(source_user_id)
        except (DataLoadError, DataValidationError) as error:
            st.error("That user's exercises could not be loaded.")
            st.code(str(error))
            st.stop()

        source_exercises = sorted(
            source_exercise_document["exercises"],
            key=lambda exercise: exercise["name"].casefold(),
        )
        if not source_exercises:
            st.info(f"{user_name(source_user_id)} has no exercises to import yet.")
        else:
            source_exercise_by_id = {
                exercise["id"]: exercise for exercise in source_exercises
            }
            source_exercise_id = st.selectbox(
                "Exercise to import",
                options=list(source_exercise_by_id),
                format_func=lambda exercise_id: source_exercise_by_id[exercise_id]["name"],
                key=f"exercise_import_selection_{source_user_id}",
            )
            if st.button("Import exercise", type="primary"):
                imported_exercise_id = str(uuid4())
                updated_exercises = copy_exercise_into_document(
                    exercise_document,
                    source_exercise_by_id[source_exercise_id],
                    imported_exercise_id,
                )
                try:
                    save_data(active_user_id, updated_exercises, routine_document)
                except (DataLoadError, DataValidationError) as error:
                    show_save_error(error)
                else:
                    st.session_state.exercise_editor_pending_selection = (
                        imported_exercise_id
                    )
                    st.rerun()
    st.stop()

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
    edited_demo_url = st.text_input(
        "Exercise URL (optional)",
        value=selected.get("demo_url", ""),
        type="url",
        placeholder="https://example.com/exercise",
    )
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
                    "demo_url": edited_demo_url.strip(),
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
                demo_url=edited_demo_url.strip(),
            )
        try:
            save_data(active_user_id, updated_exercises, routine_document)
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
                save_data(active_user_id, updated_exercises, routine_document)
            except (DataLoadError, DataValidationError) as error:
                show_save_error(error)
            else:
                st.session_state.exercise_editor_pending_selection = new_exercise_option
                st.rerun()
