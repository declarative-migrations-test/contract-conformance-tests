# Infrastructure and migration sequencing contract

Database migrations must not become an implicit infrastructure deployment mechanism.

## Ordered admission

1. Validate reusable Terraform modules and each environment root with backend disabled.
2. Confirm provider-native sync roots point at the canonical module directories.
3. Confirm remote services/databases are healthy using read-only probes.
4. Only then run migration planning/admission.
5. Run migration apply tests against disposable test resources, never production resources from this sibling org.
6. Promote routing/edge changes only after the migration compatibility suite is green.

## Failure semantics

- Terraform formatting/validation failure blocks migration execution.
- Missing provider credentials or inaccessible private source is an admission failure, not a successful skip.
- Migration rollback tests cannot substitute for Terraform state isolation.
- A successful migration test cannot certify a different infra SHA.

This ordering keeps infrastructure state, schema authority, and migration history separately auditable.
