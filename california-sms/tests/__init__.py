# =============================================================================
# Test package marker
#
# Enables explicit imports such as tests.fakes without importing application-side
# simulation code. Tests and their fixtures live outside SAM's src/ CodeUri and
# are not shipped to Lambda. This module intentionally has no setup side effects;
# each test fixture owns its dependency injection and environment cleanup.
# =============================================================================
