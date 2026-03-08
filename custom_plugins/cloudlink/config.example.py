"""
CloudLink plugin configuration — EXAMPLE FILE.

Copy this to config.py and edit as needed.
config.py is gitignored and will never be committed.
"""
import os

# Production:
# CL_API_ENDPOINT = "https://api.rhcloudlink.com"

# Staging:
# CL_API_ENDPOINT = "https://fz5emenwfi.execute-api.ap-southeast-1.amazonaws.com"

CL_API_ENDPOINT = os.environ.get(
    "CL_API_ENDPOINT",
    "https://api.rhcloudlink.com"
)
