from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path
from types import SimpleNamespace

PLUGIN = Path(__file__).with_name("plugins") / "matrix-key-recovery" / "__init__.py"
SPEC = importlib.util.spec_from_file_location("matrix_key_recovery", PLUGIN)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class FakeContext:
    def __init__(self) -> None:
        self.factory = None

    def register_platform_handler(self, platform: str, factory) -> None:
        self.platform = platform
        self.factory = factory


class FakeStore:
    def __init__(self, devices: dict) -> None:
        self.devices = devices

    async def get_devices(self, user_id):
        return self.devices


class FakeCrypto:
    def __init__(self, devices: dict) -> None:
        self.crypto_store = FakeStore(devices)
        self.trust_name = "CROSS_SIGNED_TOFU"
        self.trust_names = {}
        self.created = []
        self.shared = []
        self.sent = []

        async def original_allow(device, request):
            return False

        self.allow_key_share = original_allow

    async def _create_outbound_sessions(self, users, _force_recreate_session=False):
        self.created.append((users, _force_recreate_session))

    async def resolve_trust(self, device):
        return SimpleNamespace(name=self.trust_names.get(device.device_id, self.trust_name))

    async def share_group_session(self, room_id, users):
        self.shared.append((room_id, users))

    async def send_encrypted_to_device(
        self, device, event_type, content, _force_recreate_session=False
    ):
        self.sent.append((device, event_type, content, _force_recreate_session))


class MatrixKeyRecoveryPluginTest(unittest.IsolatedAsyncioTestCase):
    def wire(self):
        device = SimpleNamespace(
            user_id=MODULE.AUTHORIZED_USER,
            device_id="DEVICE",
            identity_key="identity",
            deleted=False,
        )
        crypto = FakeCrypto({"DEVICE": device})

        async def get_joined_members(room_id):
            return {MODULE.AUTHORIZED_USER: object()}

        client = SimpleNamespace(crypto=crypto, get_joined_members=get_joined_members)
        context = FakeContext()
        MODULE.register(context)
        self.assertEqual(context.platform, "matrix")
        factory = context.factory
        self.assertTrue(callable(factory))
        assert factory is not None
        factory(client, SimpleNamespace())
        return client, crypto, device

    async def test_new_group_session_uses_fresh_olm_channel(self) -> None:
        _, crypto, _ = self.wire()
        room = next(iter(MODULE.AUTHORIZED_ROOMS))

        await crypto.share_group_session(room, [MODULE.AUTHORIZED_USER])

        self.assertEqual(len(crypto.created), 1)
        self.assertTrue(crypto.created[0][1])
        self.assertEqual(crypto.shared, [(room, [MODULE.AUTHORIZED_USER])])

    async def test_missing_key_request_is_authorized_and_replayed_fresh(self) -> None:
        _, crypto, device = self.wire()
        room = next(iter(MODULE.AUTHORIZED_ROOMS))
        request = SimpleNamespace(room_id=room)

        self.assertTrue(await crypto.allow_key_share(device, request))
        await crypto.send_encrypted_to_device(
            device, "m.forwarded_room_key", SimpleNamespace(room_id=room)
        )

        self.assertEqual(len(crypto.sent), 1)
        self.assertTrue(crypto.sent[0][3])

    async def test_other_rooms_keep_mautrix_default_policy(self) -> None:
        _, crypto, device = self.wire()
        request = SimpleNamespace(room_id="!other:example.org")

        self.assertFalse(await crypto.allow_key_share(device, request))

    async def test_other_users_keep_mautrix_default_policy(self) -> None:
        _, crypto, device = self.wire()
        device.user_id = "@other:example.org"
        request = SimpleNamespace(room_id=next(iter(MODULE.AUTHORIZED_ROOMS)))

        self.assertFalse(await crypto.allow_key_share(device, request))

    async def test_nonmember_and_untrusted_devices_keep_default_policy(self) -> None:
        client, crypto, device = self.wire()
        room = next(iter(MODULE.AUTHORIZED_ROOMS))
        request = SimpleNamespace(room_id=room)

        async def no_members(_room_id):
            return {}

        client.get_joined_members = no_members
        self.assertFalse(await crypto.allow_key_share(device, request))

        async def joined(_room_id):
            return {MODULE.AUTHORIZED_USER: object()}

        client.get_joined_members = joined
        for trust_name in ("UNVERIFIED", "BLACKLISTED"):
            with self.subTest(trust_name=trust_name):
                crypto.trust_name = trust_name
                self.assertFalse(await crypto.allow_key_share(device, request))

    async def test_unmanaged_key_events_and_group_sessions_are_unchanged(self) -> None:
        _, crypto, device = self.wire()

        await crypto.share_group_session("!other:example.org", [MODULE.AUTHORIZED_USER])
        await crypto.send_encrypted_to_device(
            device,
            "m.room_key",
            SimpleNamespace(room_id=next(iter(MODULE.AUTHORIZED_ROOMS))),
        )

        self.assertEqual(crypto.created, [])
        self.assertEqual(len(crypto.sent), 1)
        self.assertFalse(crypto.sent[0][3])

    async def test_pre_share_refresh_excludes_untrusted_devices(self) -> None:
        _, crypto, trusted_device = self.wire()
        untrusted_device = SimpleNamespace(
            user_id=MODULE.AUTHORIZED_USER,
            device_id="UNTRUSTED",
            identity_key="untrusted-identity",
            deleted=False,
        )
        crypto.crypto_store.devices = {
            "DEVICE": trusted_device,
            "UNTRUSTED": untrusted_device,
        }

        crypto.trust_names["UNTRUSTED"] = "UNVERIFIED"
        await crypto.share_group_session(
            next(iter(MODULE.AUTHORIZED_ROOMS)), [MODULE.AUTHORIZED_USER]
        )

        refreshed_devices = next(iter(crypto.created[0][0].values()))
        self.assertEqual(set(refreshed_devices), {"DEVICE"})


if __name__ == "__main__":
    unittest.main()
