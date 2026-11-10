# Synthetic examples

Identifiers, dates, budgets and observations are illustrative. No real evidence corresponds to these identifiers. The fingerprint made of 64 letters "a" is a syntactic example, not the fingerprint of a test result.

`decision-proposal.json` is a proposal before authorization. `decision-response.json` is a later response in the same scenario; the identifiers P-0042 and D-0042 differ because the kernel assigns the identifier of a published decision.

Schema validation checks structure only: not whether evidence exists, how fresh dates are, the requester's authority, budget availability or the relevance of the action. Those checks belong to the kernel.

The business test is identified as `ORD-IDEMPOTENCY-01`. Identifiers `T-01` to `T-24` name the fault tests of the specification; `T-17` covers budget exhaustion. Keeping them apart avoids confusing business evidence with protocol acceptance.

`contracts/` holds seven valid examples and `contracts/invalid/` three counterexamples: a usurped role, PROPOSE without a proposal, and quiescence incompatible with an effect in flight. Validate with `principalloop validate <contract-name> <json-path>`; counterexamples must return 1. These files are fixtures, not active missions or real evidence.
