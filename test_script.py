#!/usr/bin/env python3
import os

print("Testing environment...")
print(f"ADVBOX_TOKEN exists: {'ADVBOX_TOKEN' in os.environ}")
print(f"ADVBOX_TOKEN length: {len(os.environ.get('ADVBOX_TOKEN', ''))}")

# Test imports
try:
    import requests
    print(f"requests module loaded: {requests.__version__}")
except ImportError as e:
    print(f"Failed to import requests: {e}")

print("All tests passed!")
