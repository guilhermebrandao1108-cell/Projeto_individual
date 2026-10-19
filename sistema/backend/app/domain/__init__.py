"""Pure business rules: no database, no HTTP. Tested directly in tests/test_domain.py."""


class DomainError(Exception):
    """A rule of the ticket workflow was violated (HTTP 409)."""


class PermissionDenied(Exception):
    """The user's role does not allow this action (HTTP 403)."""
