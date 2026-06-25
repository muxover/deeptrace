# Example: check-then-act race condition

A worked DeepTrace analysis of a small, realistic bug. The input is a Node.js withdrawal handler; the output follows the DeepTrace format.

## Input code

```js
async function withdraw(userId, amount) {
  const account = await db.getAccount(userId);

  if (account.balance < amount) {
    throw new Error("insufficient funds");
  }

  const newBalance = account.balance - amount;
  await db.updateBalance(userId, newBalance);

  return newBalance;
}
```

The handler is invoked per HTTP request. `db.getAccount` and `db.updateBalance` are independent async calls. No lock or transaction wraps them.

## DeepTrace output

**Verdict:** Critical check-then-act race between read and write allows overdraft and lost updates. **Confidence: 90%** — the race is clear from the code; whether `db.updateBalance` already runs in a transaction or applies an atomic decrement is not defined in provided context.

### Execution trace

Two requests `A` and `B` for the same `userId`, balance = 100, each withdrawing 100:

1. `A` reads account -> balance 100.
2. `B` reads account -> balance 100 (A has not written yet).
3. `A` checks `100 < 100` -> false, proceeds.
4. `B` checks `100 < 100` -> false, proceeds.
5. `A` computes `newBalance = 0`, writes 0.
6. `B` computes `newBalance = 0`, writes 0.

Both withdrawals succeed; 200 leaves the account but balance lands at 0 instead of -100 being rejected.

### Identified issues

- Critical: check-then-act (TOCTOU) race between `getAccount` and `updateBalance`. Concurrent requests read the same balance and both pass the guard, allowing overdraft.
- High: last-writer-wins on `updateBalance`. A's write is silently overwritten by B; the decrement is computed from a stale read, so updates are lost even without an overdraft.
- Medium: no atomicity across the read and write, so a crash between steps 1 and 5 leaves no record that the check ever happened.

### Edge cases

- Exactly concurrent equal withdrawals draining to zero (traced above).
- N concurrent small withdrawals each individually valid but collectively exceeding the balance.
- `amount` negative or zero: not validated, so a negative amount increases the balance.
- `account` undefined when `userId` does not exist: `account.balance` throws. How `getAccount` signals a missing user is not defined in provided context.

### Failure scenarios

- A user fires duplicate requests (double-click, retry, or scripted) and withdraws more than they hold.
- Under load, lost updates cause the stored balance to drift above the true value, compounding the loss over time.

### Security and abuse vectors

- Deliberate exploitation: an attacker sends many parallel withdrawal requests to force overdraft before any write lands. The wider the gap between read and write (network/DB latency), the larger the exploitable window.

### Performance

- The fix (a transaction or atomic conditional update) adds serialization per account. Under high contention on a single hot account this becomes a throughput bottleneck, but correctness requires it.

## Suggested fix

Make the decrement atomic and conditional so the database enforces the guard:

```js
async function withdraw(userId, amount) {
  if (amount <= 0) throw new Error("invalid amount");

  const updated = await db.decrementIfSufficient(userId, amount);
  if (!updated) throw new Error("insufficient funds");

  return updated.balance;
}
```

`decrementIfSufficient` performs a single `UPDATE ... SET balance = balance - amount WHERE id = ? AND balance >= amount`, returning the row only when it applied.
