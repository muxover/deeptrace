# Example: SQL injection via string-built query

A worked DeepTrace analysis of a login lookup through the security lens. Output follows the DeepTrace format.

## Input code

```js
async function findUser(username) {
  const query = `SELECT id, role FROM users WHERE name = '${username}'`;
  const rows = await db.query(query);
  return rows[0] || null;
}

// route: POST /login -> findUser(req.body.username)
```

`username` comes straight from the request body. No parameterization, no escaping.

## DeepTrace output

**Verdict:** Critical SQL injection allows authentication bypass and data exfiltration. **Confidence: 92%** — injection is certain from the visible concatenation; multi-statement and exact driver behavior are not defined in provided context.

### Execution trace

1. Request body `{ username }` enters the route handler unvalidated.
2. `findUser` interpolates `username` directly into the SQL string.
3. With `username = "' OR '1'='1' --"`, the query becomes `SELECT id, role FROM users WHERE name = '' OR '1'='1' --'`.
4. The `OR '1'='1'` matches every row; `--` comments out the rest.
5. `rows[0]` returns the first user in the table, which is often an admin.

### Identified issues

- Critical: SQL injection. Attacker-controlled `username` is concatenated into the query, allowing authentication bypass and arbitrary data access.
- High: returning `role` from an attacker-selected row enables privilege escalation downstream if the caller trusts it.
- Medium: no input validation on `username` (length, charset) before it reaches the data layer.

### Edge cases

- `username` containing a single quote breaks the query even without malice, surfacing the vulnerability as ordinary errors.
- Stacked queries (`'; DROP TABLE users; --`) succeed if the driver allows multiple statements. Whether `db.query` allows that is not defined in provided context.
- Unicode or encoded quotes that bypass naive filters.

### Failure scenarios

- An attacker logs in as any user without a password, or dumps the table via a UNION-based payload.
- A benign user with an apostrophe in their name triggers a 500, masking attacks in the noise.

### Security and abuse vectors

- Authentication bypass: `' OR '1'='1' --`.
- Data exfiltration: `' UNION SELECT password, role FROM users --`.
- Blind extraction via boolean or time-based payloads if errors are suppressed.

### Performance

- UNION and time-based payloads can run expensive scans, turning the endpoint into a cheap DoS lever.

## Suggested fix

Use a parameterized query so input is never parsed as SQL:

```js
async function findUser(username) {
  const rows = await db.query("SELECT id, role FROM users WHERE name = $1", [username]);
  return rows[0] || null;
}
```
