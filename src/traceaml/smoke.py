"""Exercise a real running server without external test dependencies."""

import json
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

base = "http://127.0.0.1:8000"
for attempt in range(30):
    try:
        with urlopen(base + "/health/ready", timeout=5) as response:
            assert json.load(response)["status"] == "ready"
        break
    except (URLError, HTTPError):
        if attempt == 29:
            raise
        time.sleep(1)
token = Path(sys.argv[1]).read_text().strip()
try:
    urlopen(base + "/v1/cases", timeout=5)
    raise AssertionError("unauthenticated case access succeeded")
except HTTPError as error:
    assert error.code == 401
headers = {"Authorization": "Bearer " + token}
with urlopen(Request(base + "/v1/cases", headers=headers), timeout=5) as response:
    assert len(json.load(response)["items"]) == 3
with urlopen(base + "/", timeout=5) as response:
    assert b"Open your workspace" in response.read()
with urlopen(base + "/workspace.js", timeout=5) as response:
    assert response.status == 200
try:
    urlopen(Request(base + "/v1/cases", data=b"x" * 1_048_577, headers=headers), timeout=5)
    raise AssertionError("oversized body accepted")
except HTTPError as error:
    assert error.code == 413
print("Authenticated container smoke check passed")
