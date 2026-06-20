---
name: deeptrace-security
description: Adversarial security audit built on the DeepTrace method. Traces untrusted input from entry point to sink, hunting injection, auth bypass, and data exposure. Use when explicitly named to audit code for vulnerabilities, abuse vectors, or attacker-controlled input.
disable-model-invocation: true
---

# DeepTrace Security

Applies the DeepTrace method with the attacker as the primary perspective. Prioritize Analysis Levels 4–6 and trace every untrusted input from its entry point to the sink where it is used.

## Method

For each entry point (request param, header, file, env, message, CLI arg), trace the value: where it enters, what validates or sanitizes it, what transforms it, and where it lands. Flag any path where attacker-controlled data reaches a sensitive sink without trustworthy validation. Reason only from visible code; mark anything external as "not defined in provided context".

## Checklist

- Injection: SQL/NoSQL, OS command, template, LDAP, header, and log injection from unsanitized input.
- AuthN/AuthZ: missing checks, broken object-level authorization (IDOR), privilege escalation, trust of client-supplied identity or role.
- Input validation: type confusion, missing bounds, deserialization of untrusted data, path traversal, SSRF on user-controlled URLs.
- Secrets and data exposure: hardcoded credentials, secrets in logs or errors, over-broad responses, sensitive data without encryption at rest or in transit.
- Session and crypto: weak randomness, predictable tokens, missing expiry, homemade crypto, hardcoded keys/IVs.
- Resource abuse: unbounded loops/allocations, missing rate limits, ReDoS on attacker-supplied patterns.

## Output

Use the DeepTrace strict output format. Section 5 (Security / Abuse Vectors) is mandatory here: state the vector, the exact input that triggers it, the code path, and the impact. End with a confidence score.
