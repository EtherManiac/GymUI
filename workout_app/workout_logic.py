"""Pure workout-selection and ordering logic that can be tested without UI."""

from __future__ import annotations

import random
from copy import deepcopy
from typing import Any


def ordered_slots(routine: dict[str, Any]) -> list[dict[str, Any]]:
    """Return routine slots in their explicit saved order."""

    return sorted(deepcopy(routine["slots"]), key=lambda slot: slot["order"])


def group_slots(slots: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    """Turn slots into movable units while keeping each superset together.

    Group members are placed at the position of their first member even if a
    hand-edited JSON file made them non-adjacent.
    """

    units: list[list[dict[str, Any]]] = []
    group_positions: dict[str, int] = {}
    for slot in slots:
        group_id = slot.get("superset_group_id")
        if not group_id:
            units.append([slot])
        elif group_id in group_positions:
            units[group_positions[group_id]].append(slot)
        else:
            group_positions[group_id] = len(units)
            units.append([slot])
    return units


def select_slots(routine: dict[str, Any], requested_count: int) -> list[dict[str, Any]]:
    """Select slots predictably without splitting supersets.

    Units are considered in routine order. A unit that would exceed the target
    is skipped, allowing a later smaller unit to fill the remaining space.
    Consequently, very small targets may omit a large superset entirely.
    """

    selected: list[dict[str, Any]] = []
    for unit in group_slots(ordered_slots(routine)):
        if len(selected) + len(unit) <= requested_count:
            selected.extend(unit)
        if len(selected) == requested_count:
            break
    return selected


def new_workout_snapshot(routine: dict[str, Any], requested_count: int) -> list[dict[str, Any]]:
    """Create session-only workout rows without altering the routine model."""

    return [
        {
            "slot": slot,
            "selected_exercise_id": slot["default_exercise_id"],
            "completed": False,
        }
        for slot in select_slots(routine, requested_count)
    ]


def shuffle_snapshot(snapshot: list[dict[str, Any]], randomizer: random.Random | None = None) -> None:
    """Shuffle singles/supersets as units and mutate the active snapshot order."""

    randomizer = randomizer or random.Random()
    units = group_slots_by_snapshot(snapshot)
    randomizer.shuffle(units)
    snapshot[:] = [row for unit in units for row in unit]


def group_slots_by_snapshot(snapshot: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    """Group active rows by their slot's superset ID while preserving state."""

    units: list[list[dict[str, Any]]] = []
    group_positions: dict[str, int] = {}
    for row in snapshot:
        group_id = row["slot"].get("superset_group_id")
        if not group_id:
            units.append([row])
        elif group_id in group_positions:
            units[group_positions[group_id]].append(row)
        else:
            group_positions[group_id] = len(units)
            units.append([row])
    return units


def restore_snapshot_order(snapshot: list[dict[str, Any]]) -> None:
    """Restore routine order while retaining completion and substitutions."""

    snapshot.sort(key=lambda row: row["slot"]["order"])

