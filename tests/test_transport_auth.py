import unittest

from memory_fabric.protocol import Retraction
from memory_fabric.transport import retraction_signer, verify_retraction_signature


def make_retraction(**changes: object) -> Retraction:
    values: dict[str, object] = {
        "retraction_id": "ret-1", "origin_store_id": "origin",
        "origin_memory_id": "memory-1", "origin_memory_version": 1,
        "origin_sequence": 7, "reason_code": "contradicted",
        "requested_by": "operator", "issued_at": "2026-11-08T00:00:00Z",
    }
    values.update(changes)
    return Retraction(**values)  # type: ignore[arg-type]


class TestTransportAuthentication(unittest.TestCase):
    def test_direct_retraction_uses_origin_signer(self) -> None:
        self.assertEqual(retraction_signer(make_retraction()), "origin")

    def test_forwarded_retraction_uses_forwarding_peer_signer(self) -> None:
        self.assertEqual(retraction_signer(make_retraction(forwarded_by="forwarder")),
                         "forwarder")

    def test_signature_verification_requires_configured_key_and_valid_mac(self) -> None:
        message, key = make_retraction(), b"peer key"
        signature = message.sign(key, "peer-k1")
        self.assertTrue(verify_retraction_signature(message, signature, key))
        self.assertFalse(verify_retraction_signature(message, signature, b"wrong key"))
        self.assertFalse(verify_retraction_signature(message, signature, None))

    def test_signature_verification_binds_message_contents(self) -> None:
        message, key = make_retraction(), b"peer key"
        signature = message.sign(key, "peer-k1")
        changed = make_retraction(origin_sequence=8)
        self.assertFalse(verify_retraction_signature(changed, signature, key))
