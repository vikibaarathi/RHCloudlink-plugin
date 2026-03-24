"""Centralized constants for the CloudLink plugin."""

DEFAULT_API_ENDPOINT = "https://api.rhcloudlink.com"
CL_VERSION = "1.5.0"

# Timeouts (seconds)
API_TIMEOUT = 10
S3_TIMEOUT = 30

# Allowed image types for upload
ALLOWED_IMAGE_TYPES = frozenset({'image/jpeg', 'image/png', 'image/webp'})

# RH option keys
OPT_ENABLED = "cl-enable-plugin"
OPT_EVENT_ID = "cl-event-id"
OPT_EVENT_KEY = "cl-event-key"
