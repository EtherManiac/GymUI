PROJECT BRIEF: PERSONAL WORKOUT PLANNER (STREAMLIT MVP)
=====================================================

1. PROJECT OVERVIEW
-------------------
Build a lightweight personal workout planning and checklist application using Python and Streamlit.

This is a personal utility, not a commercial product. Prioritize simplicity, reliability, readable code, and easy maintenance over elaborate features.

I will provide three UI mockups. Use them as conceptual visual references, not pixel-perfect requirements. The app should work well on desktop and on a phone during workouts.

My primary fitness goal is consistency. I typically have 45–60 minutes for lifting but occasionally need a shorter session. I currently use a Push/Pull/Legs/Cardio rotation with Push 1/2 and Pull 1/2 variations. I may add Upper/Lower routines later. No schedule management is needed in this MVP.

2. APPLICATION PAGES AND NAVIGATION
-----------------------------------
Use three main pages accessible through a collapsible sidebar/hamburger navigation. Prefer native Streamlit navigation and controls.

PAGE 1: WORKOUT (DEFAULT PAGE)
- Select a workout/routine from a dropdown.
- Select the number of exercises to perform.
- Show the chosen exercises in a clear, mobile-friendly checklist.
- Each exercise row displays: exercise name, sets x reps, reference weight, completion checkbox, and an alternative-selection control when alternatives exist.
- Provide a session-only optional field for the weight used on each workout exercise.
- Show visually grouped supersets, keeping their exercise rows adjacent.
- Allow optional shuffling of the selected exercises while preserving superset grouping.
- Provide a way to restore the original order and reset the active workout.
- Completed exercises should be visually distinguishable.
- Choosing fewer exercises should initially use the routine's defined order; keep the selection logic simple and isolated so it can be improved later.
- Do not save checklist completion or substitutions back to the routine definition.

PAGE 2: EDIT EXERCISES
- View the master exercise library.
- Create, edit, and delete exercises.
- Store: stable unique exercise ID, name, muscles targeted (one or more), optional tags, and optional notes.
- Allow tags to be added or edited easily.
- Prevent or clearly handle deleting an exercise referenced by a routine.
- The supplied exercise-editor mockup includes sets/reps and weight, but these should be configured in routine slots instead of in the master exercise library.

PAGE 3: EDIT ROUTINES
- Create, rename, edit, and delete routines.
- Add, remove, and reorder exercise slots.
- Each slot has a stable unique ID, order, required muscles, optional tags, default exercise ID, alternative exercise IDs, sets, reps, reference weight, and optional superset group ID.
- Slot workflow: add a slot; choose at least one required muscle and any optional tags; filter library exercises; select a default exercise and optional alternatives; enter sets/reps/weight; optionally group it into a superset; save.
- Muscle and optional tag filters use simple match-all behavior.
- Do not add elaborate tag rules or automatic exercise recommendations.

3. DATA MODEL
-------------
An EXERCISE is a reusable item in the exercise library.
A ROUTINE contains ordered EXERCISE SLOTS.
Each SLOT references a default exercise and may reference alternate exercises.
Sets, reps, and reference weight belong to the routine slot.
Alternatives belong to slots, not globally to exercises.
Use stable IDs rather than names or list positions for references.

Supersets:
- Use a shared superset group ID to link two or more slots.
- Display grouped slots together and keep them together when shuffling.
- Give each exercise its own completion checkbox.
- For shortened workouts, avoid splitting a superset automatically. Pick a simple, predictable rule for situations where a group would exceed the requested exercise count; document the rule clearly.

Substitutions:
- Offer only alternatives explicitly assigned to a slot.
- Swapping does not change the saved routine.
- Keep the slot's sets/reps/reference weight when swapping in the MVP, but label weight as a reference rather than implying it is suitable for every alternative.

4. DATA STORAGE
---------------
- Do NOT use my Excel workout-audit spreadsheet as an app data source.
- Use simple JSON files for the exercise library and routine definitions during local development.
- Keep data files separate from UI code.
- Include basic validation of IDs, references, required fields, and malformed JSON.
- Include sample data only, not my real workout program.
- Seed a small exercise library and sample Push 1, Pull 1, and Legs routines, demonstrating tags, alternatives, supersets, sets/reps, and weights.
- Additional routines should be addable without modifying UI code.

IMPORTANT HOSTING CONSIDERATION:
Development happens locally, then the code will be versioned on GitHub and deployed to Streamlit Community Cloud. Local JSON file writes are fine for local development, but writes to the hosted app's filesystem should NOT be assumed to persist through restarts, redeployments, or replica changes. Keep data access isolated behind small, readable functions. For the MVP, propose a simple hosting-compatible way to preserve user edits (for example, exporting/importing JSON files), and explain its tradeoffs before implementing anything requiring external services. Do not silently add a database, credentials, or paid service. Keep the hosted app's behavior clear and avoid implying that unsaved edits are durable.

5. UI GUIDANCE
--------------
Mockup 1: workout page with navigation sidebar open.
Mockup 2: workout page with navigation sidebar closed.
Mockup 3: exercise library/editor page.

The routine editor can resemble the workout page but with controls for creating and editing slots.
Use native Streamlit components where practical. Avoid custom JavaScript or heavy CSS unless essential. Prioritize phone usability and readability over pixel-perfect reproduction.

6. CODING STANDARDS (IMPORTANT)
-------------------------------
- ALWAYS COMMENT CODE. I should be able to read the code and understand what each section is doing.
- Include helpful comments explaining the purpose of functions, non-obvious logic, data transformations, state management, and important design decisions.
- Prefer meaningful comments that explain WHY, not redundant comments that merely restate a line of code.
- Use descriptive variable, function, class, and file names. Avoid cryptic single-letter names such as a, b, or c, except for universally understood short loop indices when truly appropriate.
- Keep functions small and responsibilities clear.
- Prefer straightforward Python over clever or overly abstract implementations.
- Document the JSON schema and any non-obvious decisions.
- Make error messages understandable and actionable.
- Keep dependencies minimal.
- Use a conventional, easy-to-navigate project structure.

7. DEVELOPMENT AND DEPLOYMENT
-----------------------------
- Develop and test locally first.
- Use Python, Streamlit, and standard-library JSON; add dependencies only as needed.
- Track the project in GitHub.
- Plan for eventual deployment to Streamlit Community Cloud from the GitHub repository.
- Include a requirements.txt and a README.md with local setup, launch, GitHub, and Streamlit Community Cloud deployment instructions.
- Do not assume a specific operating system, Python version, existing folder structure, or credentials. Inspect the environment and ask if a required detail cannot be determined.
- Do not hardcode secrets or machine-specific paths.
- Avoid unnecessary services, APIs, authentication, and paid infrastructure.

8. STATE AND SCOPE
------------------
- Use Streamlit session state to retain the active workout checklist, substitutions, and order across reruns.
- Reset the active checklist when switching workouts, and provide an explicit reset control.
- Exercise and routine edits should be saved through the chosen storage mechanism; workout checkboxes and substitutions are session-only.

OUT OF SCOPE:
- Calendars and fixed workout schedules
- Automatic next-workout or recovery recommendations
- Workout history and analytics
- Progression algorithms
- AI-generated exercise recommendations
- User accounts and authentication
- Cloud sync or databases unless explicitly approved
- Complex tag logic or elaborate UI frameworks

9. DELIVERABLES
---------------
1. Working Streamlit app with all three pages.
2. Sample JSON exercise and routine data.
3. requirements.txt.
4. README.md with local setup and Streamlit Community Cloud deployment guidance.
5. Brief explanation of the JSON schema.
6. Clear explanation of how edits are saved locally and how hosted users can preserve them.

10. DEVELOPMENT PROCESS
-----------------------
First, review the three attached UI mockups and propose the smallest sensible project structure, JSON schema, and implementation plan. Flag any essential unresolved decisions, especially hosted data persistence.

Then implement the MVP using readable, commented code and descriptive names. Prefer a functioning end-to-end workflow over extensive styling. Do not expand scope without asking.

SUCCESS CRITERION:
I can open the app, select a routine, choose how many exercises I want to perform, swap among defined alternatives, follow a checklist, and easily maintain my exercise library and routine definitions.
