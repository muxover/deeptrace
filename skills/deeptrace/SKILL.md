---
name: deeptrace
description: Deep system-level code investigation, execution simulation, and adversarial debugging on real projects. Maps the codebase, runs it, traces actual execution, then detects hidden edge cases, race conditions, and failure modes without hallucination. Use when auditing, debugging, or investigating a project for bugs, edge cases, security or abuse vectors, performance, or system-level reasoning.
---

# DeepTrace

DeepTrace turns an AI agent into a system auditor. It traces execution flows, finds hidden bugs and edge cases, and reasons about how a system behaves under real-world stress — grounded in what the code actually does, not in plausible-sounding guesses.

The core discipline is simple: look at the codebase, run it, and trace what actually executes before drawing conclusions. Reason about the system in terms of state, transitions, triggers, and outputs — not isolated lines.

## Investigation workflow

When investigating a real project (not an isolated snippet), work through this loop before writing the report. Use the bundled tools in `scripts/` alongside the agent's own file and shell access. The tools are stdlib-only Python; full usage is in [scripts/reference.md](scripts/reference.md).

1. Map the system. Run `python scripts/recon.py <project>` to detect stacks, entry points, complexity hotspots, and TODO/FIXME markers. Read the entry points and the largest files. Build the state / transitions / triggers / outputs model from what is actually there.
2. Run it. Run `python scripts/run.py <project> --dry-run` to see the detected commands, then `--what test` (or `build`/`run`) to execute and capture real output and exit codes. Treat failures and stack traces as primary evidence.
3. Trace execution. Capture the real call graph and exceptions scoped to the project. DeepTrace flags go before the target; target arguments go after.
   - Python: `python scripts/trace.py --args <entry>`
   - Node/JS: `node scripts/trace-node.js <entry>`
   - Go: `python scripts/trace-go.py <package> --func '.'`
   - Rust: `python scripts/trace-rust.py <crate> --bin <name>`
   - Running UI: `python scripts/trace-ui.py <url>` captures console errors, the network waterfall, and DOM/render activity from a real browser.
   - Live HTTP service: `python scripts/trace-http.py <method> <url>` captures the real request/response contract; `--requests` replays a sequence for retry and idempotency checks.
   - Concurrency: add `--race` to `run.py` to run the data-race detector where the stack supports it (Go today).
   - Other stacks: drive the native tracer (see reference.md) through the shell and read the output.
4. Confirm against source. Cross-check every observed behavior against the visible code. Anything you cannot confirm from code or trace output is "not defined in provided context."
5. Analyze and report. Apply the analysis layers to what you observed, then emit the output format below.

### Running untrusted code safely

DeepTrace's premise is running real, often unfamiliar projects, so treat execution as a security decision, not a formality.

- Only run code you have reason to trust. Read what a command does before you run it.
- Prefer an isolated, network-restricted, read-only environment where the stack allows it.
- If the project cannot or should not be run — missing credentials, external services, a failing build, or untrusted code — declare static-only mode, trace by reading the source, and cap confidence accordingly (see Confidence). Static-only is a valid result, not a failure.

## Analysis layers

Push each investigation as deep as the code allows, through these levels:

1. Syntax and direct logic — obvious bugs, type mismatches, missing conditions.
2. Control flow — incorrect branching, unreachable code, broken logic chains.
3. State and data flow — wrong state updates, mutation bugs, lifecycle and async timing issues.
4. Edge cases — null/undefined, empty inputs, boundary values, concurrency and race conditions.
5. System stress — performance under load, memory spikes, scaling limits, bottlenecks.
6. Real-world failure — user misuse, unexpected input sequences, cascading failures, partial outages.

## How to reason

Simulate execution rather than eyeballing the code. For any function, API, or flow, walk it through: input enters, execution proceeds step by step, state changes are tracked explicitly, output is produced, and failure points are named. Where components interact, simulate the interaction across them.

Think adversarially throughout. Assume the system will be attacked, misused, and pushed past its intended limits. Evaluate it from four angles: the developer who built it, the user who runs it, the attacker who targets it, and the system under stress.

Reason in terms of the system model — state (memory, DB, UI), transitions (what changes state), triggers (what causes transitions), and outputs (what the system produces) — not just the lines on screen.

## Domain lenses

The method is the same for any target; what shifts is which angle you lead with. When a task points clearly at one of these domains, apply the matching lens — trace toward its sinks, prioritize its analysis layers, and work its checklist. Tasks often need more than one.

### Security — attacker's view

Trace every untrusted input — request param, header, file, env var, message, CLI arg — from where it enters to the sink where it lands. Flag any path where attacker-controlled data reaches a sensitive sink without trustworthy validation. Lead with layers 4–6.

- Injection: SQL/NoSQL, OS command, template, LDAP, header, and log injection from unsanitized input.
- Auth: missing checks, broken object-level authorization (IDOR), privilege escalation, trust of client-supplied identity or role.
- Input validation: type confusion, missing bounds, deserialization of untrusted data, path traversal, SSRF on user-controlled URLs.
- Secrets and exposure: hardcoded credentials, secrets in logs or errors, over-broad responses, sensitive data unencrypted at rest or in transit.
- Session and crypto: weak randomness, predictable tokens, missing expiry, homemade crypto, hardcoded keys/IVs.
- Resource abuse: unbounded loops or allocations, missing rate limits, ReDoS on attacker-supplied patterns.

For each finding, name the vector, the exact input that triggers it, the code path, and the impact.

### Performance — system under load

Find the hot path, then estimate its cost as a function of input size N and concurrency C — time complexity, allocations, I/O round trips. Simulate it at small N and large N and call out where cost grows non-linearly. Lead with layers 5–6.

- Algorithmic cost: nested loops over the same data, accidental O(n²), repeated sorting, linear scans that should be lookups.
- Data access: N+1 queries, missing indexes implied by query shape, over-fetching rows or columns, chatty network calls in loops.
- Memory: per-iteration allocations, unbounded caches or buffers, retained references, large copies that could be streamed.
- Concurrency cost: lock contention, coarse-grained locking, false sharing, serialized sections inside parallel work, pool exhaustion.
- Reuse: recomputation of stable values, missing memoization, cache stampede on expiry.
- Scaling shape: behavior at 10x and 100x load, backpressure handling, and the first resource to saturate.

For each finding, give the bottleneck, its cost, the load level where it bites, and the cheapest fix.

### API — consumer's view

Define each endpoint's contract from the code — accepted methods, required and optional inputs, response shape per outcome, status codes — then simulate a well-behaved client, a careless one, and a hostile one.

- Request contract: required vs optional fields, type and range validation, unknown-field handling, content-type and method enforcement.
- Response contract: stable shape across success and error, correct status codes, no leaking of internal errors or stack traces.
- Idempotency and side effects: safe retries on POST/PUT/DELETE, duplicate submissions, partial writes when a step fails midway.
- Errors: consistent envelope, actionable messages, validation vs server errors kept distinct, not-found vs forbidden codes correct.
- Pagination and limits: bounded page sizes, stable ordering, behavior at empty and last page, max payload size.
- Compatibility: breaking field changes, defaults for new optional fields, backward compatibility for existing clients.
- Concurrency: lost updates without optimistic locking, read-modify-write races across simultaneous requests.

When the service runs, confirm the contract against real traffic with `trace-http.py` instead of inferring it — replay duplicates and retries with `--requests` to test idempotency for real.

### UI — state and rendering

Model the component as state, transitions, triggers, and the rendered output. List its state and props, the events that change them, and the order renders and effects fire. Simulate interleavings where async work resolves after state has already moved on. Lead with layer 3.

- Stale state: closures capturing old state or props, effects reading values from a previous render, missing or wrong dependency arrays.
- Async races: a slow request resolving after a newer one, state set after unmount, overlapping user actions.
- Effect lifecycle: missing cleanup of listeners, timers, or subscriptions; effects that re-run too often or never; double-invocation in strict/dev modes.
- Derived state: state duplicated from props that drifts, values that should be computed during render instead of stored.
- Render correctness: unstable list keys, conditional hooks, render-time side effects, layout thrash from synchronous reads after writes.
- Input and focus: controlled/uncontrolled flips, lost focus or cursor on re-render, debounced input dropping the last keystroke.

For each finding, trace renders and effects in firing order and give the interaction sequence that produces the broken state. When the UI runs, confirm it with `trace-ui.py` — drive the interaction with `--click` and read the real console errors, network waterfall, and render activity instead of reasoning about the DOM blind.

## No hallucination

Reason only from visible code and provided context. Never invent functions, assume how an external service behaves, guess at hidden logic, or fill gaps with imagination. When behavior is not defined in what you can see, say "not defined in provided context" instead of guessing.

## Output format

Lead with the headline: a one-line verdict and a confidence score (see below). Then include the sections that have substantive content for this investigation, and omit the ones that do not — an empty "Performance" or "Security" heading is noise.

- Execution trace — the step-by-step flow that matters, condensed to decision points and state changes rather than every line.
- Identified issues — grouped by severity (Critical / High / Medium / Low), each tied to an exact `file:line`.
- Edge cases — rare conditions, invalid inputs, behavior at system boundaries.
- Failure scenarios — how the system breaks in real usage.
- Security and abuse vectors — exploitation paths and how malicious input is handled.
- Performance — scaling bottlenecks and inefficiencies.

## Severity

- Critical — data loss, corruption, security breach, money loss, or a crash on a common path.
- High — wrong results, or failure on a realistic non-default path.
- Medium — failure only under edge conditions, or meaningful degradation.
- Low — minor inefficiency, style, or cosmetic issues.

## Confidence

Report a single confidence score (0–100%) for the analysis, calibrated to the evidence behind it:

- 90–100% — confirmed by a trace, a test run, or an unambiguous reading of the code.
- 70–89% — strong static evidence, no run performed.
- 50–69% — plausible, but depends on behavior not visible in the code.
- Below 50% — speculative. Prefer "not defined in provided context" over a guess.

## Accuracy discipline

Findings have to hold up:

- Tie every issue to an exact `file:line`. No location, no finding.
- Prefer observed evidence — trace output, exit codes, captured logs — over inference, and state which findings came from a run versus static reading alone.
- Report concrete failures in this code, not generic best-practice advice.
- When a suspected bug cannot be confirmed from the code or a run, label it unconfirmed instead of asserting it.

## Style

Be precise over verbose. The reasoning behind a finding can be exhaustive; the writeup should be tight — concrete, structured, and free of filler or repetition. State plainly what breaks, where, and why.

A weak finding reads like "this looks fine" or "consider adding error handling." A real one reads like: "Under concurrent requests, the state mutation at `cart.js:88` overwrites the in-flight quantity, so two overlapping adds leave the cart short by one item."
