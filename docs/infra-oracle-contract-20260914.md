# Independent infrastructure oracle contract

Infrastructure checks in this sibling org certify an exact production revision, never a moving branch name.

- Record the production `*-infra` head SHA.
- If production source is private, copy only the required contract surface and pin every file by Git blob SHA.
- Verify mirrored bytes with `git hash-object` before running tests.
- Run Terraform without a backend and never apply infrastructure from the test org.
- Treat preview, staging, and production as isolated composition roots.
- Reject committed Terraform state/cache and duplicate provider-native configuration beneath `environments/`.

For migrations specifically, infrastructure validation must remain independent from schema/data migration execution: provisioning/layout checks happen first; database migration tests run only after the infrastructure contract is admitted.

Any source-head change invalidates previous sibling certification until the oracle is repinned and rerun.
