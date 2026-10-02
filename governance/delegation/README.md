# GOV-01 Delegation

Canonical definition: `runtime/core/task_contract.py`; contract schema:
`schemas/task-contract.schema.json`. This document grants no authority.

| Level | Ceiling | Enforcement |
| --- | --- | --- |
| L0 Observe | Observation | No declared deliverables or provider production; returned deliverables block DONE |
| L1 Produce | Produce within read-only execution | No controlled write scope |
| L2 Local Write | Explicit controlled local scope | Existing approval, review, exact paths and sandbox required |
| L3 External Draft | Produce draft | No external send/publication authority |
| L4 External Action | Explicit external boundary required | High-risk approval/review required; unsupported external action fails closed |
| L5 Financial/Irreversible | Explicit sensitive boundary required | High-risk approval/review required; local deletion additionally requires L5 plus existing deletion scope; unsupported finance actions fail closed |

A higher label does not allocate a tool. Contract tools are local_executor,
provider_call, controlled_write, tests and git_read. Native CLI execution is
blocked because existing adapters cannot prove a confined tool surface. Existing
Git action approvals remain separate. No label grants deployment, purchase,
financial transfer or external send authority. Tool/capability/scope ceilings,
risk, blast radius, reversibility, budget and existing approvals all apply together.
