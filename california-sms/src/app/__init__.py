# =============================================================================
# Application package: California SMS service
#
# This package contains the deployed FastAPI application, the SNS Lambda entry
# point, AWS messaging logic, and DynamoDB persistence. SAM packages src/, so this
# marker is included in both Lambda functions. It intentionally performs no work:
# importing the package must not retrieve secrets, create clients, or send SMS.
# Entry points are app.main.handler (HTTP) and app.inbound.handler (incoming SMS).
# =============================================================================
