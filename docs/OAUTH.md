# OAuth 2.0 / OpenID Connect for the agent API

Memory Fabric can act as an OAuth 2.0 resource server for JWT access tokens.
This is optional; the existing locally issued credentials continue to work.

```console
pip install "memory-fabric[oauth]"
```

Create a server-only `oidc.json`:

```json
{
  "issuer": "https://id.example.com/",
  "audience": "https://memory.example.com/",
  "jwks_uri": "https://id.example.com/.well-known/jwks.json",
  "algorithms": ["RS256"],
  "required_scopes": ["memory-fabric"],
  "leeway_seconds": 30,
  "subjects": {"00u-provider-subject": "research-agent"}
}
```

The mapped agent must also exist in `--agents-file`; that server-side file is
the authority for tenant and roles. Token `roles`, `groups`, `tenant`, and
`entitlements` claims never grant Memory Fabric permissions.

```console
memory-fabric --db fabric.db agent-api --agents-file agents.txt \
  --oidc-config oidc.json --host 127.0.0.1
```

Clients send `Authorization: Bearer eyJ...`. The verifier requires a signed
RFC 9068 `at+jwt`, an explicitly allowed asymmetric algorithm, exact issuer
and audience, `sub`, `exp`, `iat`, and all configured scopes. JWKS and issuer
URLs must use HTTPS. Authentication failures remain opaque `401` responses.
Local whole-agent revocation applies on the next request. Individual OAuth
token revocation remains the identity provider's responsibility, so deployments
should use short access-token lifetimes and provider-side revocation.

Memory Fabric validates access tokens; it does not issue them. Authorization
Code + PKCE, client credentials, device flow, consent, and MFA belong at the
configured identity provider.
