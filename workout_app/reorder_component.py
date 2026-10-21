"""Direct drag-to-reorder behavior for native Streamlit workout cards."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import streamlit as st


_DRAG_REORDER = st.components.v2.component(
    "workout_drag_reorder",
    html="""
<div class="workout-drag-controller" aria-hidden="true"></div>
""",
    css="""
.workout-drag-controller {
    width: 0;
    height: 0;
    overflow: hidden;
}
div[class*="st-key-workout_card_"],
div[class*="st-key-superset_member_"] {
    position: relative;
    overflow: visible !important;
}
button.workout-drag-handle {
    position: absolute;
    left: -2.4rem;
    top: 50%;
    transform: translateY(-50%);
    z-index: 10001;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 2rem;
    height: 2.75rem;
    min-height: 0;
    padding: 0;
    border: 0;
    border-radius: 0.35rem;
    background: transparent;
    cursor: grab;
    touch-action: none;
    user-select: none;
    color: var(--st-text-color);
    opacity: 0.7;
}
button.workout-drag-handle:hover,
button.workout-drag-handle:focus-visible {
    opacity: 1;
    color: var(--st-primary-color);
    background: var(--st-secondary-background-color);
    outline: none;
}
button.workout-drag-handle:active {
    cursor: grabbing;
}
button.workout-drag-handle svg {
    width: 1.25rem;
    height: 1.25rem;
    fill: currentColor;
    pointer-events: none;
}
.workout-unit-dragging {
    opacity: 0.65 !important;
    z-index: 10000 !important;
    pointer-events: none;
    transition: none !important;
}
.workout-drop-before {
    box-shadow: inset 0 4px 0 var(--st-primary-color) !important;
}
.workout-drop-after {
    box-shadow: inset 0 -4px 0 var(--st-primary-color) !important;
}
""",
    js="""
const instances = new WeakMap()

function cardCandidates(doc) {
  return Array.from(doc.querySelectorAll(
    'div[class*="st-key-workout_card_"], div[class*="st-key-superset_member_"]'
  ))
}

function classContainsSlot(element, slotKey) {
  return Array.from(element.classList).some(name =>
    (name.startsWith("st-key-workout_card_") ||
      name.startsWith("st-key-superset_member_")) && name.endsWith(`_${slotKey}`)
  )
}

function clearDropMarkers(state) {
  for (const card of state.cards || []) {
    card.classList.remove(
      "workout-unit-dragging",
      "workout-drop-before",
      "workout-drop-after"
    )
    card.style.removeProperty("transform")
    card.style.removeProperty("z-index")
  }
}

function collectUnits(state) {
  const doc = state.doc
  const cards = cardCandidates(doc)
  const collected = []
  for (const unit of state.data.units || []) {
    const unitCards = unit.slot_keys
      .map(slotKey => cards.find(card => classContainsSlot(card, slotKey)))
      .filter(Boolean)
    if (unitCards.length !== unit.slot_keys.length) return []
    collected.push({ id: unit.id, cards: unitCards })
  }
  return collected
}

function emitKeyboardMove(state, unitId, direction) {
  const ids = (state.data.units || []).map(unit => unit.id)
  const index = ids.indexOf(unitId)
  const nextIndex = index + direction
  if (index < 0 || nextIndex < 0 || nextIndex >= ids.length) return
  ids.splice(index, 1)
  ids.splice(nextIndex, 0, unitId)
  state.setTriggerValue("reordered", ids)
}

function endDrag(state, shouldCommit) {
  const drag = state.drag
  if (!drag) return
  state.doc.removeEventListener("pointermove", state.onPointerMove)
  state.doc.removeEventListener("pointerup", state.onPointerUp)
  state.doc.removeEventListener("pointercancel", state.onPointerCancel)
  clearDropMarkers(state)
  state.drag = null

  if (!shouldCommit || drag.targetIndex === drag.startIndex) return
  const ids = (state.data.units || []).map(unit => unit.id)
  ids.splice(drag.startIndex, 1)
  ids.splice(drag.targetIndex, 0, drag.unitId)
  state.setTriggerValue("reordered", ids)
}

function updateDropTarget(state, clientY) {
  const drag = state.drag
  if (!drag) return
  const units = collectUnits(state)
  const remaining = units.filter(unit => unit.id !== drag.unitId)
  let targetIndex = 0
  for (const unit of remaining) {
    const firstRect = unit.cards[0].getBoundingClientRect()
    const lastRect = unit.cards[unit.cards.length - 1].getBoundingClientRect()
    const midpoint = (firstRect.top + lastRect.bottom) / 2
    if (clientY > midpoint) targetIndex += 1
  }
  drag.targetIndex = targetIndex

  for (const unit of remaining) {
    for (const card of unit.cards) {
      card.classList.remove("workout-drop-before", "workout-drop-after")
    }
  }
  if (remaining.length === 0) return
  if (targetIndex < remaining.length) {
    remaining[targetIndex].cards[0].classList.add("workout-drop-before")
  } else {
    const lastUnit = remaining[remaining.length - 1]
    lastUnit.cards[lastUnit.cards.length - 1].classList.add("workout-drop-after")
  }
}

function beginDrag(state, unitId, event) {
  if (event.pointerType === "mouse" && event.button !== 0) return
  const units = collectUnits(state)
  const startIndex = units.findIndex(unit => unit.id === unitId)
  if (startIndex < 0) return
  event.preventDefault()
  for (const card of units[startIndex].cards) {
    card.classList.add("workout-unit-dragging")
  }
  state.drag = {
    unitId,
    startIndex,
    targetIndex: startIndex,
    startY: event.clientY,
    cards: units[startIndex].cards,
  }
  updateDropTarget(state, event.clientY)
  state.doc.addEventListener("pointermove", state.onPointerMove, { passive: false })
  state.doc.addEventListener("pointerup", state.onPointerUp)
  state.doc.addEventListener("pointercancel", state.onPointerCancel)
}

function wireHandles(state) {
  const units = collectUnits(state)
  if (!units.length) return
  state.cards = units.flatMap(unit => unit.cards)
  state.handles = []

  const handleCards = new Set(units.map(unit => unit.cards[0]))
  for (const card of state.cards) {
    if (handleCards.has(card)) continue
    card.querySelector(":scope > button.workout-drag-handle")?.remove()
  }

  for (const unit of units) {
    const card = unit.cards[0]
    let handle = card.querySelector(":scope > button.workout-drag-handle")
    if (!handle) {
      handle = state.doc.createElement("button")
      handle.type = "button"
      handle.className = "workout-drag-handle"
      handle.innerHTML = `
        <svg aria-hidden="true" viewBox="0 0 24 24">
          <circle cx="8" cy="5" r="1.8"></circle>
          <circle cx="16" cy="5" r="1.8"></circle>
          <circle cx="8" cy="12" r="1.8"></circle>
          <circle cx="16" cy="12" r="1.8"></circle>
          <circle cx="8" cy="19" r="1.8"></circle>
          <circle cx="16" cy="19" r="1.8"></circle>
        </svg>`
      card.appendChild(handle)
    }
    const firstRect = unit.cards[0].getBoundingClientRect()
    const lastRect = unit.cards[unit.cards.length - 1].getBoundingClientRect()
    handle.style.top = `${(lastRect.bottom - firstRect.top) / 2}px`
    handle.setAttribute(
      "aria-label",
      unit.cards.length > 1 ? "Drag to reorder exercise group" : "Drag to reorder exercise"
    )
    handle.onpointerdown = event => beginDrag(state, unit.id, event)
    handle.onkeydown = event => {
      if (event.key !== "ArrowUp" && event.key !== "ArrowDown") return
      event.preventDefault()
      emitKeyboardMove(state, unit.id, event.key === "ArrowUp" ? -1 : 1)
    }
    state.handles.push(handle)
  }
}

export default function (component) {
  const { data, parentElement, setTriggerValue } = component
  const doc = parentElement.ownerDocument || document
  let state = instances.get(parentElement)
  if (!state) {
    state = {
      data,
      doc,
      setTriggerValue,
      cards: [],
      handles: [],
      drag: null,
      frame: null,
    }
    state.onPointerMove = event => {
      event.preventDefault()
      const view = state.doc.defaultView
      if (event.clientY < 80) view.scrollBy({ top: -18, behavior: "auto" })
      if (event.clientY > view.innerHeight - 80) view.scrollBy({ top: 18, behavior: "auto" })
      if (state.drag) {
        const offset = event.clientY - state.drag.startY
        for (const card of state.drag.cards) {
          card.style.transform = `translateY(${offset}px)`
          card.style.zIndex = "10000"
        }
      }
      updateDropTarget(state, event.clientY)
    }
    state.onPointerUp = () => endDrag(state, true)
    state.onPointerCancel = () => endDrag(state, false)
    state.onResize = () => {
      if (state.frame !== null) return
      state.frame = requestAnimationFrame(() => {
        state.frame = null
        wireHandles(state)
      })
    }
    state.observer = new MutationObserver(() => {
      if (state.frame !== null) return
      state.frame = requestAnimationFrame(() => {
        state.frame = null
        wireHandles(state)
      })
    })
    state.observer.observe(doc.body, { childList: true, subtree: true })
    doc.defaultView.addEventListener("resize", state.onResize)
    instances.set(parentElement, state)
  }

  state.data = data
  state.setTriggerValue = setTriggerValue
  requestAnimationFrame(() => wireHandles(state))

  return () => {
    endDrag(state, false)
    state.observer.disconnect()
    state.doc.defaultView.removeEventListener("resize", state.onResize)
    if (state.frame !== null) cancelAnimationFrame(state.frame)
    for (const handle of state.handles || []) handle.remove()
    instances.delete(parentElement)
  }
}
""",
    isolate_styles=False,
)


def workout_drag_reorder(
    units: list[dict[str, Any]],
    *,
    key: str,
    on_reordered_change: Callable[[], None],
) -> None:
    """Attach drag and keyboard reorder behavior to rendered workout cards."""

    _DRAG_REORDER(
        key=key,
        data={"units": units},
        height=0,
        on_reordered_change=on_reordered_change,
    )
