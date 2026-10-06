"""Convert a CSV transaction export to the API's JSON batch, preserving decimal text."""

import csv
import json
import sys
from pathlib import Path

from traceaml.domain import Transaction

source, output = map(Path, sys.argv[1:])
with source.open(newline="", encoding="utf-8-sig") as stream:
    rows = list(csv.DictReader(stream))
if not 1 <= len(rows) <= 1000:
    raise ValueError("CSV must contain 1–1000 transactions")
records = [Transaction.from_dict(row).to_dict() for row in rows]
with output.open("x", encoding="utf-8") as stream:
    json.dump({"transactions": records}, stream, indent=2)
