from __future__ import annotations

import json
from pathlib import Path

import pytest

from memory_fabric import MemoryFabric
from memory_fabric.agent_api import AgentApi
from memory_fabric.identity import IdentityError
from memory_fabric.oidc import OidcConfig, OidcJwtVerifier
from memory_fabric.service import MemoryService


class FakeOidc:
    def __init__(self, agent_id: str = "ag_oauth", fail: bool = False) -> None:
        self.agent_id = agent_id
        self.fail = fail

    def authenticate(self, token: str) -> str:
        if self.fail or token != "header.payload.signature":
            raise IdentityError("invalid token")
        return self.agent_id


def service() -> MemoryService:
    current = MemoryService(fabric=MemoryFabric(":memory:"))
    current.register_agent("ag_oauth", b"a" * 32, "tn_oauth")
    return current


def test_oauth_subject_uses_server_side_registration() -> None:
    current = service()
    try:
        api = AgentApi(current, oauth=FakeOidc())
        result = api.handle("remember", "header.payload.signature",
                            {"content": "OAuth-authenticated observation"})
        memory = current._fabric.get(result["memory_id"])
        assert memory.tenant_id == "tn_oauth"
        assert memory.provenance.created_by == "ag_oauth"
    finally:
        current.close()


def test_oauth_failure_has_the_same_opaque_401() -> None:
    current = service()
    try:
        api = AgentApi(current, oauth=FakeOidc(fail=True))
        with pytest.raises(Exception) as caught:
            api.handle("recall", "header.payload.signature", {"query": "x"})
        assert caught.value.status == 401
        assert str(caught.value) == "authentication required"
    finally:
        current.close()


def test_revoking_mapped_agent_stops_oauth_immediately() -> None:
    current = service()
    try:
        api = AgentApi(current, oauth=FakeOidc())
        current.revoke_agent("ag_oauth")
        with pytest.raises(Exception) as caught:
            api.handle("recall", "header.payload.signature", {"query": "x"})
        assert caught.value.status == 401
    finally:
        current.close()


def test_oidc_config_is_fail_closed(tmp_path: Path) -> None:
    path = tmp_path / "oidc.json"
    path.write_text(json.dumps({
        "issuer": "https://id.example.com/",
        "audience": "https://memory.example.com/",
        "jwks_uri": "https://id.example.com/.well-known/jwks.json",
        "subjects": {"provider-subject": "ag_oauth"},
        "algorithms": ["RS256"],
        "required_scopes": ["memory-fabric"],
    }), encoding="utf-8")
    config = OidcConfig.load(str(path))
    assert config.subjects["provider-subject"] == "ag_oauth"
    assert config.required_scopes == ("memory-fabric",)
    path.write_text(path.read_text(encoding="utf-8").replace("https://", "http://"),
                    encoding="utf-8")
    with pytest.raises(IdentityError, match="HTTPS"):
        OidcConfig.load(str(path))


def test_symmetric_and_none_algorithms_are_refused() -> None:
    with pytest.raises(IdentityError, match="asymmetric"):
        OidcConfig("https://id.example/", "aud", "https://id.example/jwks",
                   {"sub": "ag"}, algorithms=("HS256",)).validate()


class FakeKeyClient:
    def get_signing_key_from_jwt(self, token: str):
        return type("Key", (), {"key": "public-key"})()


class FakeJwtLibrary:
    def __init__(self, typ: str = "at+jwt", alg: str = "RS256") -> None:
        self.typ = typ
        self.alg = alg
        self.decode_call: dict = {}

    def get_unverified_header(self, token: str) -> dict:
        return {"typ": self.typ, "alg": self.alg, "kid": "k1"}

    def decode(self, token: str, key: str, **kwargs) -> dict:
        self.decode_call = kwargs
        return {"iss": "https://id.example/", "sub": "sub-1", "aud": "memory-api",
                "exp": 9999999999, "iat": 1, "scope": "memory-fabric read"}


def verifier(library: FakeJwtLibrary) -> OidcJwtVerifier:
    instance = object.__new__(OidcJwtVerifier)
    instance.config = OidcConfig(
        "https://id.example/", "memory-api", "https://id.example/jwks",
        {"sub-1": "ag_oauth"}, required_scopes=("memory-fabric",))
    instance._jwt = library
    instance._keys = FakeKeyClient()
    return instance


def test_verifier_pins_algorithm_issuer_audience_and_required_claims() -> None:
    library = FakeJwtLibrary()
    assert verifier(library).authenticate("header.payload.signature") == "ag_oauth"
    assert library.decode_call["algorithms"] == ["RS256"]
    assert library.decode_call["issuer"] == "https://id.example/"
    assert library.decode_call["audience"] == "memory-api"
    assert library.decode_call["options"]["require"] == ["iss", "sub", "aud", "exp", "iat"]


@pytest.mark.parametrize("typ,alg", [("JWT", "RS256"), ("at+jwt", "none"),
                                      ("at+jwt", "HS256")])
def test_verifier_rejects_cross_jwt_and_algorithm_confusion(typ: str, alg: str) -> None:
    with pytest.raises(IdentityError):
        verifier(FakeJwtLibrary(typ, alg)).authenticate("header.payload.signature")
