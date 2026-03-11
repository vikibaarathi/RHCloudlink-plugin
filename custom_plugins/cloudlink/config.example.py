"""
CloudLink plugin configuration — EXAMPLE FILE.

Copy this to config.py and edit as needed.
config.py is gitignored and will never be committed.
"""
import os

CL_API_ENDPOINT = os.environ.get(
    "CL_API_ENDPOINT",
    "https://api.rhcloudlink.com"
)
