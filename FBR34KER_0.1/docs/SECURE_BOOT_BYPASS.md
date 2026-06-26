# Secure-boot state model

This module is a bounded, in-memory state model for policy and interface
testing. It does not parse or modify Apple Image4 trust data, create valid
signatures or certificates, alter APTicket or SHSH handling, patch iBoot, or
change a device boot manifest.

Release builds keep the model disabled through
`FBR34KER_ENABLE_SECURITY_MODEL`. All mutation functions return failure when
that symbol is absent, and immutable probe images remain locked.

The `secure-boot-bypass status` command reports model state only. It is not
evidence that Apple secure boot has been bypassed.
