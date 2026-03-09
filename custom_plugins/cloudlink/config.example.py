"""
CloudLink plugin configuration — EXAMPLE FILE.

Copy this to config.py and edit as needed.
config.py is gitignored and will never be committed.
"""
import os

# Production:
# CL_API_ENDPOINT = "https://api.rhcloudlink.com"

# Staging:
# CL_API_ENDPOINT = "https://u9d3pvkmii.ap-southeast-1.awsapprunner.com"

CL_API_ENDPOINT = os.environ.get(
    "CL_API_ENDPOINT",
    "https://api.rhcloudlink.com"
)
