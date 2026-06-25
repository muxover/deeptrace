# Example: N+1 query in a list endpoint

A worked DeepTrace analysis of an endpoint that lists posts with their authors, through the performance lens. Output follows the DeepTrace format.

## Input code

```js
async function listPosts() {
  const posts = await db.query("SELECT id, title, author_id FROM posts");
  for (const post of posts) {
    post.author = await db.query("SELECT name FROM users WHERE id = $1", [post.author_id]);
  }
  return posts;
}
```

## DeepTrace output

**Verdict:** High-severity N+1 query makes latency scale with result size, not data volume. **Confidence: 90%** — the N+1 shape is unambiguous; exact DB latency and pool size are not defined in provided context.

### Execution trace

1. One query fetches N posts.
2. The loop issues one additional query per post to fetch its author.
3. Total queries = 1 + N. Each is a separate round trip to the database.
4. With N = 500 posts, the endpoint runs 501 sequential queries before responding.

### Identified issues

- High: classic N+1 query pattern. Query count grows linearly with result size; latency is dominated by per-query round-trip time, not data volume.
- Medium: queries run sequentially with `await` inside the loop, so round trips are not even overlapped.
- Low: repeated author lookups are not deduplicated; the same author is fetched once per post.

### Edge cases

- N = 0: one query, fine.
- Many posts sharing few authors: the redundancy multiplies (e.g. 500 posts, 5 authors -> 500 author queries for 5 distinct rows).
- A slow or contended `users` table makes every iteration pay the tail latency.

### Failure scenarios

- Under load the endpoint exhausts the DB connection pool with bursts of small queries, slowing unrelated requests.
- Response time scales with content, so the page that "worked in dev" (10 rows) times out in production (thousands).

### Security and abuse vectors

- If page size is caller-controlled and unbounded, an attacker requests a huge list to amplify the query count into a denial-of-service.

### Performance

- Cost: O(N) queries, O(N) round trips, sequential. Fix collapses it to 2 queries (or 1 with a join), turning round-trip-bound latency into a single batch.

## Suggested fix

Batch the author lookup into one query, then map in memory:

```js
async function listPosts() {
  const posts = await db.query("SELECT id, title, author_id FROM posts");
  const ids = [...new Set(posts.map((p) => p.author_id))];
  const authors = await db.query("SELECT id, name FROM users WHERE id = ANY($1)", [ids]);
  const byId = new Map(authors.map((a) => [a.id, a.name]));
  for (const post of posts) post.author = byId.get(post.author_id) || null;
  return posts;
}
```
