# Example: non-idempotent payment endpoint

A worked DeepTrace analysis of a charge endpoint through the API lens. Output follows the DeepTrace format.

## Input code

```js
// POST /charge
async function charge(req, res) {
  const { userId, amountCents } = req.body;
  const charge = await payments.create({ userId, amountCents });
  await db.insert("charges", { id: charge.id, userId, amountCents });
  res.status(200).json({ chargeId: charge.id });
}
```

The client retries `POST /charge` on network timeout.

## DeepTrace output

**Verdict:** Critical idempotency gap double-charges the user on any retry. **Confidence: 88%** — the gap is clear from the code; provider behavior on bad amounts and multi-statement effects are not defined in provided context.

### Execution trace

1. Client sends `POST /charge`; the request reaches `payments.create`, which charges the card.
2. The network drops the response before the client receives it.
3. The client retries the same `POST /charge`.
4. The server has no record that this logical request already ran, so it calls `payments.create` again.
5. The card is charged twice; two rows land in `charges`.

### Identified issues

- Critical: POST is not idempotent. A retry (client, proxy, or load balancer) double-charges the user. There is no idempotency key and no deduplication.
- High: no input validation. `amountCents` is unchecked, so negative, zero, non-integer, or huge values pass straight through to the payment provider.
- Medium: partial failure between `payments.create` and `db.insert` leaves a real charge with no local record, so reconciliation breaks.

### Edge cases

- `amountCents` missing or `userId` absent: behavior is not defined in provided context; likely a provider-side error after partial work.
- Concurrent duplicate submissions (double-click) race the same way as a retry.
- `payments.create` succeeds but the process crashes before responding: the same double-charge on retry, plus no DB row.

### Failure scenarios

- A user on flaky mobile data is charged two or three times for one purchase, triggering chargebacks and support load.
- A retry storm during an outage multiplies real charges across many users.

### Security and abuse vectors

- Negative `amountCents` could credit an account if the provider or ledger treats it as a refund. Whether it does is not defined in provided context.
- Replay of a captured request repeats the charge with no server-side guard.

### Performance

- Each retry performs a full external payment call; under retry storms this saturates the provider rate limit and the connection pool.

## Suggested fix

Require an idempotency key and enforce it before charging:

```js
async function charge(req, res) {
  const key = req.header("Idempotency-Key");
  if (!key) return res.status(400).json({ error: "Idempotency-Key required" });
  if (!Number.isInteger(req.body.amountCents) || req.body.amountCents <= 0) {
    return res.status(422).json({ error: "invalid amount" });
  }
  const existing = await db.get("charges", { idempotency_key: key });
  if (existing) return res.status(200).json({ chargeId: existing.id });

  const charge = await payments.create({ ...req.body, idempotencyKey: key });
  await db.insert("charges", { id: charge.id, idempotency_key: key, ...req.body });
  res.status(200).json({ chargeId: charge.id });
}
```
