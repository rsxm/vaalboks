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

Do not expose it directly to the public internet. A room phrase alone is not a
replacement for authentication, authorization, rate limiting, trusted TLS,
monitoring, and a reviewed production deployment configuration.
