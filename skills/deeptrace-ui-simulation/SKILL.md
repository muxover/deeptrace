---
name: deeptrace-ui-simulation
description: UI state and rendering audit built on the DeepTrace method. Simulates component state transitions, async timing, and re-render behavior to find stale state and UI races. Use when explicitly named to debug frontend state, effects, or rendering bugs.
disable-model-invocation: true
---

# DeepTrace UI Simulation

Applies the DeepTrace method with UI state as the primary perspective. Prioritize Analysis Level 3 (state and data flow) and simulate the component lifecycle: mount, update, async resolution, and unmount.

## Method

Model the UI as STATE, TRANSITIONS, TRIGGERS, and OUTPUTS (rendered view). For the target component, list its state and props, the events that change them, and the order in which renders and effects fire. Simulate interleavings where async work resolves after state has already moved on. Reason only from the visible component and its inputs; mark external stores or APIs as "not defined in provided context".

## Checklist

- Stale state: closures capturing old state/props, effects reading values from a previous render, missing or wrong dependency arrays.
- Async races: a slow request resolving after a newer one (out-of-order responses), state set after unmount, overlapping user actions.
- Effect lifecycle: missing cleanup (listeners, timers, subscriptions), effects that re-run too often or never, double-invocation under strict/dev modes.
- Derived state: state duplicated from props that drifts, values that should be computed during render instead of stored.
- Render correctness: unstable keys in lists, conditional hooks, render-time side effects, layout thrash from synchronous reads after writes.
- Input and focus: controlled/uncontrolled flips, lost focus or cursor on re-render, debounced input dropping the last keystroke.

## Output

Use the DeepTrace strict output format. In Section 1, trace renders and effects in firing order; in Section 4, describe the user interaction sequence that produces the broken UI state. End with a confidence score.
