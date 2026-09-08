"""Keep Bryan's private Matrix room keys recoverable."""

from __future__ import annotations

import logging


logger = logging.getLogger(__name__)

AUTHORIZED_USER = "@bryan:snowboardtechie.com"
AUTHORIZED_ROOMS = frozenset(
    {
        "!USHKqGpzKJq-4PQkLs_aDY_PxB_7AvS-xLSQGcdXVGU",
        "!5hH-Wud0Gd7hS1Z214EwjEMUvqtH8FBVOZhIZj0sqR4",
        "!CsY4wEHn3w715wk78Uz9RQ9lNv2hV9CFPr6T6YgQNgE",
        "!dc6CqGlnIP1ivE6QDrbNedXZlmViaDOK75KjdzQ63_w",
    }
)


def _event_type_name(event_type) -> str:
    serialize = getattr(event_type, "serialize", None)
    return str(serialize() if callable(serialize) else event_type)


def _wire_matrix(client, _adapter) -> None:
    crypto = getattr(client, "crypto", None)
    if crypto is None or getattr(crypto, "_bryan_key_recovery_wired", False):
        return

    original_allow_key_share = crypto.allow_key_share
    original_share_group_session = crypto.share_group_session
    original_send_encrypted_to_device = crypto.send_encrypted_to_device

    async def allow_key_share(device, request):
        user_id = str(getattr(device, "user_id", ""))
        room_id = str(getattr(request, "room_id", ""))
        if (
            user_id != AUTHORIZED_USER
            or room_id not in AUTHORIZED_ROOMS
            or getattr(device, "deleted", False)
        ):
            return await original_allow_key_share(device, request)

        members = await client.get_joined_members(room_id)
        if AUTHORIZED_USER not in {str(member_id) for member_id in members.keys()}:
            return await original_allow_key_share(device, request)

        trust = await crypto.resolve_trust(device)
        if getattr(trust, "name", "").upper() == "BLACKLISTED":
            return await original_allow_key_share(device, request)
        return True

    async def share_group_session(room_id, users):
        room_text = str(room_id)
        authorized_user = next(
            (user for user in users if str(user) == AUTHORIZED_USER), None
        )
        if room_text in AUTHORIZED_ROOMS and authorized_user is not None:
            devices = await crypto.crypto_store.get_devices(authorized_user)
            devices = {
                device_id: device
                for device_id, device in (devices or {}).items()
                if not getattr(device, "deleted", False)
            }
            if devices:
                try:
                    await crypto._create_outbound_sessions(
                        {authorized_user: devices}, _force_recreate_session=True
                    )
                except Exception as exc:
                    # The normal share still runs. A client key request will retry with a
                    # fresh Olm channel after that device replenishes one-time keys.
                    logger.warning(
                        "Matrix key recovery could not refresh every Olm channel before "
                        "sharing %s: %s",
                        room_text,
                        exc,
                    )
        return await original_share_group_session(room_id, users)

    async def send_encrypted_to_device(
        device, event_type, content, _force_recreate_session=False
    ):
        room_id = str(getattr(content, "room_id", ""))
        force_recreate = _force_recreate_session or (
            _event_type_name(event_type) == "m.forwarded_room_key"
            and str(getattr(device, "user_id", "")) == AUTHORIZED_USER
            and room_id in AUTHORIZED_ROOMS
        )
        return await original_send_encrypted_to_device(
            device,
            event_type,
            content,
            _force_recreate_session=force_recreate,
        )

    crypto.allow_key_share = allow_key_share
    crypto.share_group_session = share_group_session
    crypto.send_encrypted_to_device = send_encrypted_to_device
    crypto._bryan_key_recovery_wired = True
    logger.info("Matrix key recovery enabled for Bryan's managed private rooms")


def register(ctx) -> None:
    ctx.register_platform_handler("matrix", _wire_matrix)
