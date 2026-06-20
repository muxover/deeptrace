---
name: deeptrace-api-audit
description: API contract audit built on the DeepTrace method. Checks request/response shapes, status codes, idempotency, and error contracts against real client usage. Use when explicitly named to review an endpoint, handler, or API surface.
disable-model-invocation: true
---

# DeepTrace API Audit

Applies the DeepTrace method with the API consumer as the primary perspective. The focus is the contract: what a caller can send, what they get back, and how the endpoint behaves when they deviate from the happy path.

## Method

For each endpoint, define the contract from the code: accepted methods, required and optional inputs, response shape per outcome, and status codes. Then simulate a well-behaved client, a careless client, and a hostile client, and check that the response is correct, consistent, and safe in each case. Mark behavior of downstream services as "not defined in provided context" unless visible.

## Checklist

- Request contract: required vs optional fields, type and range validation, unknown-field handling, content-type and method enforcement.
- Response contract: stable shape across success and error, correct status codes (2xx/4xx/5xx), no leaking of internal errors or stack traces.
- Idempotency and side effects: safe retries on POST/PUT/DELETE, duplicate submissions, partial writes when a step fails midway.
- Errors: consistent error envelope, actionable messages, validation errors vs server errors not conflated, correct codes for not-found vs forbidden.
- Pagination and limits: bounded page sizes, stable ordering, behavior at empty and last page, max payload size.
- Versioning and compatibility: breaking changes to fields, default values for new optional fields, backward compatibility for existing clients.
- Concurrency: lost updates without optimistic locking, read-modify-write races across simultaneous requests.

## Output

Use the DeepTrace strict output format. In Section 1, trace one request through validation, handling, and response; in Section 4, cover malformed, duplicate, and concurrent requests. End with a confidence score.
