# Security policy

## Supported versions

Only the latest version on the default branch is currently supported.

## Reporting a vulnerability

Please do not disclose security vulnerabilities in a public issue. Use GitHub
Security Advisories if enabled for the repository, or contact the maintainers
privately through the repository's security contact.

This project is intended for trusted local networks. The standalone server
requires a user-chosen room phrase and isolates each phrase into a separate
room. This is protection against accidental or casual cross-device access, not
strong identity authentication; short or common phrases can be guessed.
The bundled server limits room-entry attempts to 10 per client address per
minute and upload requests to 1 GB and 1,000 files by default. These are
defense-in-depth limits, not a substitute for authentication or capacity
planning; room throttling depends on the configured Django cache being shared
when multiple workers or hosts are used.

Do not expose it directly to the public internet. A room phrase alone is not a
replacement for authentication, authorization, rate limiting, trusted TLS,
monitoring, and a reviewed production deployment configuration.
