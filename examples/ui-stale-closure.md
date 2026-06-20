# Example: stale closure in a React effect

A DeepTrace UI Simulation analysis of a counter that auto-increments. Output follows the strict seven-part format.

## Input code

```jsx
function Counter() {
  const [count, setCount] = useState(0);

  useEffect(() => {
    const id = setInterval(() => {
      setCount(count + 1);
    }, 1000);
    return () => clearInterval(id);
  }, []);

  return <span>{count}</span>;
}
```

## DeepTrace output

### 1. Execution Trace

1. Mount: `count = 0`. The effect runs once (empty dependency array) and starts an interval.
2. The interval callback closes over `count` from the first render, where `count` is 0.
3. Tick 1: `setCount(0 + 1)` -> 1. Component re-renders, but the interval still holds the original closure.
4. Tick 2: the callback again computes `0 + 1` -> 1. State stays at 1.
5. Every subsequent tick recomputes `0 + 1`. The displayed value freezes at 1.

### 2. Identified Issues

- High: stale closure. The interval captures `count` from the mount render and never sees updates, so the counter sticks at 1 instead of incrementing.
- Medium: the empty dependency array hides the bug from the linter only if the exhaustive-deps rule is disabled; it is a missing-dependency defect.

### 3. Edge Case Analysis

- Fast unmount/remount: cleanup clears the interval correctly, so the leak is avoided, but the freeze remains on each mount.
- Strict mode double-invoke in development sets up and tears down the effect twice; the visible bug is the same but timing differs.
- If other state triggers re-renders, the span still shows the frozen value because the interval owns the stale `count`.

### 4. Failure Scenarios

- A user watching the counter sees it jump to 1 and stop, reporting "the timer is broken."
- Any logic derived from `count` (progress bars, expiry) silently stops advancing.

### 5. Security / Abuse Vectors

- Not applicable to this component.

### 6. Performance Concerns

- Minor: the interval keeps firing and calling `setCount` with the same value; React bails out of re-render on identical state, so cost is low but non-zero.

### 7. Confidence Score

93%. The stale-closure behavior is determined by React's render and closure semantics. Surrounding app state is not defined in provided context.

## Suggested fix

Use the functional updater so the callback never depends on a captured value:

```jsx
useEffect(() => {
  const id = setInterval(() => setCount((c) => c + 1), 1000);
  return () => clearInterval(id);
}, []);
```
