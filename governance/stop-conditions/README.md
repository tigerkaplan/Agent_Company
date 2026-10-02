# GOV-01 Stop Conditions

Canonical implementation: `runtime/core/task_contract.py`. Contract stops include
no_execution, deadline and on_blocker. no_execution and expired deadlines reject
at execution boundaries before effects; deadline is checked again before completion.
on_blocker prevents DONE when canonical execution blockers exist. Existing failure,
budget, review, approval, scope, sandbox and recovery stops remain authoritative.

Stale contracts, changed work, malformed or missing anchors, weakened review,
missing evidence, unsupported tools/actions and opaque provider native tools fail
closed. These checks do not retry, reset budgets, release recovery holds or grant
new authority. Provider/agent output cannot remove stop conditions. An already
accepted receipt records the acceptance time; restart verifies that immutable
observation rather than inventing a new acceptance time.
