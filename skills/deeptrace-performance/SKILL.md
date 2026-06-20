---
name: deeptrace-performance
description: Performance and scaling audit built on the DeepTrace method. Estimates complexity, allocation pressure, and contention, then simulates behavior under load. Use when explicitly named to find bottlenecks, hot paths, or scaling limits.
disable-model-invocation: true
---

# DeepTrace Performance

Applies the DeepTrace method with system stress as the primary perspective. Prioritize Analysis Levels 5–6 and reason about behavior as input size and concurrency grow, not just correctness on a single call.

## Method

Identify the hot path, then estimate cost in terms of time complexity, allocations, and I/O round trips as a function of input size N and concurrency C. Simulate the path at small N and at large N, and call out where cost grows non-linearly. Distinguish measured facts in the code from assumptions, which must be labelled "not defined in provided context".

## Checklist

- Algorithmic complexity: nested loops over the same data, accidental O(n^2), repeated sorting, linear scans that should be lookups.
- Data access: N+1 queries, missing indexes implied by query shape, fetching more rows/columns than used, chatty network calls in loops.
- Allocation and memory: per-iteration allocations, unbounded caches/buffers, retained references, large copies that could be streamed.
- Concurrency cost: lock contention, coarse-grained locking, false sharing, serialized sections inside parallel work, thread/connection pool exhaustion.
- Caching and reuse: recomputation of stable values, missing memoization, cache stampede on expiry.
- Scaling shape: behavior at 10x and 100x load, backpressure handling, and the first resource to saturate.

## Output

Use the DeepTrace strict output format. Section 6 (Performance Concerns) is mandatory: give the bottleneck, its complexity or cost, the load level where it bites, and the cheapest fix. End with a confidence score.
