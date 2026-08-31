# Engineering Review

Review for:

- Functional correctness.
- Architecture and design consistency.
- Error handling.
- Performance and resource use.
- Concurrency and race conditions.
- Backward compatibility.
- API contracts and serialization.
- Data integrity and migration safety.
- Maintainability.
- Unnecessary complexity.
- Regression risk.
- Oversized or multi-concern changes that should be split.

For PR size and scope:

- Use the authoritative `PR Change Scope` metrics when available. Do not
  estimate or invent line, file, or concern counts.
- Identify distinct concern clusters from the diff and suggest concrete split
  boundaries when that would improve reviewability.
- Treat an oversized PR as non-blocking unless repository policy explicitly
  promotes `change-scope` to `enforced`.
- Do not override the mechanical result. AI explains risk and proposes a
  reviewable sequence; the deterministic provider owns the measurements.

Require the reviewer to explain:

1. What changed.
2. What could break.
3. Whether there are blocking findings.
4. Any meaningful non-blocking recommendations.
