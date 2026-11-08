from __future__ import annotations

from memory_fabric.transport import Peer, PeerRegistry, sign_body, verify_body


def test_peer_rotation_overlap_switch_and_retirement_contract():
    body = {"event": "retraction", "sequence": 7}
    k1, k2 = b"old-peer-key", b"new-peer-key"
    registry = PeerRegistry({"store-origin": Peer("store-origin", "unused", k1, "k1")})

    sig1 = sign_body(body, k1, "k1")
    assert verify_body(body, sig1, registry.key_for("store-origin", sig1["key_id"]))

    # Recipient overlap phase: K2 is current while K1 remains accepted.
    registry.add(Peer("store-origin", "unused", k2, "k2", accepted={"k1": k1}))
    sig2 = sign_body(body, k2, "k2")
    assert verify_body(body, sig1, registry.key_for("store-origin", sig1["key_id"]))
    assert verify_body(body, sig2, registry.key_for("store-origin", sig2["key_id"]))

    # Retirement removes K1; an unknown key id never falls back to K2.
    registry.add(Peer("store-origin", "unused", k2, "k2"))
    assert registry.key_for("store-origin", "k1") is None
    assert registry.key_for("store-origin", "k-unknown") is None
    assert verify_body(body, sig2, registry.key_for("store-origin", "k2"))
