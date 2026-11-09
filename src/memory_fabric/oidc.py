"""Optional OAuth 2.0 JWT access-token authentication for the agent API.

This is a resource-server verifier, not an authorization server or browser
login flow. It follows RFC 9068 and maps ``(issuer, subject)`` to an already
registered Memory Fabric agent. Token tenant and role claims never create
local privilege.
"""
from __future__ import annotations

__stability__ = "beta"

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Protocol
from urllib.parse import urlparse

from .identity import IdentityError


class TokenVerifier(Protocol):
    def authenticate(self, token: str) -> str: ...


@dataclass(frozen=True)
class OidcConfig:
    issuer: str
    audience: str
    jwks_uri: str
    subjects: Mapping[str, str]
    algorithms: tuple[str, ...] = ("RS256",)
    required_scopes: tuple[str, ...] = ()
    leeway_seconds: int = 30

    @staticmethod
    def load(path: str) -> "OidcConfig":
        try:
            raw = json.loads(Path(path).read_text(encoding="utf-8"))
            config = OidcConfig(
                issuer=str(raw["issuer"]), audience=str(raw["audience"]),
                jwks_uri=str(raw["jwks_uri"]),
                subjects={str(k): str(v) for k, v in raw["subjects"].items()},
                algorithms=tuple(str(v) for v in raw.get("algorithms", ["RS256"])),
                required_scopes=tuple(str(v) for v in raw.get("required_scopes", [])),
                leeway_seconds=int(raw.get("leeway_seconds", 30)),
            )
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise IdentityError(f"invalid OIDC configuration: {exc}") from None
        config.validate()
        return config

    def validate(self) -> None:
        for label, value in (("issuer", self.issuer), ("jwks_uri", self.jwks_uri)):
            parsed = urlparse(value)
            if parsed.scheme != "https" or not parsed.netloc or parsed.username:
                raise IdentityError(f"OIDC {label} must be an HTTPS URL without userinfo")
        if not self.audience or not self.subjects:
            raise IdentityError("OIDC audience and subjects must not be empty")
        allowed = {"RS256", "RS384", "RS512", "ES256", "ES384", "ES512"}
        if not self.algorithms or not set(self.algorithms) <= allowed:
            raise IdentityError("OIDC algorithms must be an explicit asymmetric allow-list")
        if not 0 <= self.leeway_seconds <= 300:
            raise IdentityError("OIDC leeway_seconds must be between 0 and 300")


class OidcJwtVerifier:
    """Verify RFC 9068 access tokens using the issuer's configured JWKS."""

    def __init__(self, config: OidcConfig) -> None:
        config.validate()
        self.config = config
        try:
            import jwt
        except ImportError:
            raise IdentityError(
                "OAuth support needs: pip install 'memory-fabric[oauth]'"
            ) from None
        self._jwt = jwt
        self._keys = jwt.PyJWKClient(config.jwks_uri, cache_keys=True)

    def authenticate(self, token: str) -> str:
        if token.count(".") != 2:
            raise IdentityError("OAuth access token is not a compact JWT")
        try:
            header = self._jwt.get_unverified_header(token)
            if str(header.get("typ", "")).lower() not in {"at+jwt", "application/at+jwt"}:
                raise IdentityError("OAuth token typ must be at+jwt")
            if header.get("alg") not in self.config.algorithms:
                raise IdentityError("OAuth token algorithm is not allowed")
            key = self._keys.get_signing_key_from_jwt(token).key
            claims: dict[str, Any] = self._jwt.decode(
                token, key, algorithms=list(self.config.algorithms),
                audience=self.config.audience, issuer=self.config.issuer,
                leeway=self.config.leeway_seconds,
                options={"require": ["iss", "sub", "aud", "exp", "iat"]},
            )
        except IdentityError:
            raise
        except Exception as exc:
            raise IdentityError(f"OAuth token validation failed: {type(exc).__name__}") from None
        subject = claims.get("sub")
        if not isinstance(subject, str) or subject not in self.config.subjects:
            raise IdentityError("OAuth subject is not mapped")
        scope = claims.get("scope", "")
        granted = set(scope.split()) if isinstance(scope, str) else set()
        if not set(self.config.required_scopes) <= granted:
            raise IdentityError("OAuth token lacks a required scope")
        return self.config.subjects[subject]
