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
            "Tags": ", ".join(exercise["tags"]),
            "Notes": exercise.get("notes", ""),
            "Demo": exercise.get("demo_url", ""),
        }
        for exercise in exercises
    ],
    width="stretch",
    hide_index=True,
)

with st.expander("Add an exercise", expanded=not exercises):
    with st.form("add_exercise_form", clear_on_submit=True):
        new_name = st.text_input("Name")
        new_tags = st.text_input("Tags", help="Separate multiple tags with commas.")
        new_notes = st.text_area("Notes (optional)")
        new_demo_url = st.text_input("Demonstration URL (optional)")
        add_submitted = st.form_submit_button("Add exercise", type="primary")
    if add_submitted:
        tags = normalized_tags(new_tags)
        if not new_name.strip() or not tags:
            st.error("Enter an exercise name and at least one tag.")
        else:
            updated_exercises = deepcopy(exercise_document)
            updated_exercises["exercises"].append(
                {
                    "id": str(uuid4()),
                    "name": new_name.strip(),
                    "tags": tags,
                    "notes": new_notes.strip(),
                    "demo_url": new_demo_url.strip(),
                }
            )
            try:
                save_data(updated_exercises, routine_document)
            except (DataLoadError, DataValidationError) as error:
                show_save_error(error)
            else:
                st.success("Exercise added.")
                st.rerun()

if exercises:
    st.subheader("Update an exercise")
    exercise_by_id = {exercise["id"]: exercise for exercise in exercises}
    selected_id = st.selectbox(
        "Exercise to edit",
        options=list(exercise_by_id),
        format_func=lambda exercise_id: exercise_by_id[exercise_id]["name"],
    )
    selected = exercise_by_id[selected_id]
    with st.form(f"edit_exercise_{selected_id}"):
        edited_name = st.text_input("Name", value=selected["name"])
        edited_tags = st.text_input("Tags", value=", ".join(selected["tags"]))
        edited_notes = st.text_area("Notes (optional)", value=selected.get("notes", ""))
        edited_demo_url = st.text_input(
            "Demonstration URL (optional)", value=selected.get("demo_url", "")
        )
        save_submitted = st.form_submit_button("Save changes", type="primary")
    if save_submitted:
        tags = normalized_tags(edited_tags)
        if not edited_name.strip() or not tags:
            st.error("Enter an exercise name and at least one tag.")
        else:
            updated_exercises = deepcopy(exercise_document)
            target = next(
                exercise for exercise in updated_exercises["exercises"] if exercise["id"] == selected_id
            )
            target.update(
                name=edited_name.strip(),
                tags=tags,
                notes=edited_notes.strip(),
                demo_url=edited_demo_url.strip(),
            )
            try:
                save_data(updated_exercises, routine_document)
            except (DataLoadError, DataValidationError) as error:
                show_save_error(error)
            else:
                st.success("Exercise updated.")
                st.rerun()

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
                st.success("Exercise deleted.")
                st.rerun()
