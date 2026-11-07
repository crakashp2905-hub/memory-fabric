# Exact action grant binding

`ActionGate.issue_grant` binds a short-lived grant to the tool, agent, tenant, canonical action target and parameters, and the certificate's evidence IDs and versions. The event log is authoritative for grant expiry; changing a caller's copied `Grant.expires_ms` cannot extend the grant. Execution checks the stored expiry and binding before the effect, and the first allowed use consumes the grant.

`tests/test_authority.py` checks changes to each bound field, target and argument mutation through authorization, expiry, revocation, and single-use behavior. The tests are local contract evidence; they do not prove an external tool honors the idempotency key or that a remote identity provider has no revocation delay.
