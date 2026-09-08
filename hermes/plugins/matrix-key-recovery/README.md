# Matrix key recovery

This user plugin protects encrypted delivery to Bryan's four private,
two-member Hermes, SGG, Second Brain, and CairnOS rooms.

For those four exact room IDs and only for `@bryan:snowboardtechie.com`, it:

- creates fresh Olm channels before a newly rotated Megolm room key is shared;
- accepts a missing-room-key request only while Bryan is currently joined and
  the requesting device is not deleted or blacklisted; and
- forwards the retained room key through another fresh Olm channel.

All other users, rooms, devices, and to-device event types retain mautrix's
default authorization and transport behavior. The installer enables this plugin
without granting permission to override Hermes tools.
