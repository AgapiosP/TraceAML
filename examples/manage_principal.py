"""Operator-only creation/renewal of an individual expiring access token."""

import json
import secrets
import sys
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path

from traceaml.operations import write_private
from traceaml.service import Principal, secret_file

config, subject, tenant, role, output = sys.argv[1:]
path = Path(config)
records = json.loads(secret_file(config))
token = secrets.token_urlsafe(32)
p = Principal(
    subject,
    tenant,
    role,
    sha256(token.encode()).hexdigest(),
    datetime.now(UTC) + timedelta(days=30),
)
write_private(Path(output), token.encode() + b"\n")
records = [r for r in records if not (r["subject"] == subject and r["tenant_id"] == tenant)]
records.append({**asdict(p), "expires_at": p.expires_at.isoformat()})
temporary = path.with_name(path.name + ".new")
write_private(temporary, json.dumps(records, indent=2).encode())
temporary.replace(path)
print(
    json.dumps(
        {
            "principal_file": config,
            "token_file": output,
            "expires_at": p.expires_at.isoformat(),
            "restart_required": True,
        }
    )
)
