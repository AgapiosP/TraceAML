"""Load and validate packaged jurisdiction metadata."""

from __future__ import annotations

import json
from dataclasses import dataclass
from importlib.resources import files


@dataclass(frozen=True, slots=True)
class JurisdictionPack:
    pack_id: str
    name: str
    version: str
    reviewed_on: str
    authorities: tuple[str, ...]
    review_topics: tuple[str, ...]
    sources: tuple[str, ...]
    disclaimer: str


def load_pack(pack_id: str) -> JurisdictionPack:
    normalized = pack_id.lower()
    if normalized not in {"eu", "uk", "us", "au"}:
        raise ValueError(f"unsupported jurisdiction pack: {pack_id}")
    resource = files("traceaml").joinpath("packs", f"{normalized}.json")
    value = json.loads(resource.read_text(encoding="utf-8"))
    required = {
        "pack_id",
        "name",
        "version",
        "reviewed_on",
        "authorities",
        "review_topics",
        "sources",
        "disclaimer",
    }
    if missing := required.difference(value):
        raise ValueError(f"pack is missing fields: {sorted(missing)}")
    return JurisdictionPack(
        pack_id=value["pack_id"],
        name=value["name"],
        version=value["version"],
        reviewed_on=value["reviewed_on"],
        authorities=tuple(value["authorities"]),
        review_topics=tuple(value["review_topics"]),
        sources=tuple(value["sources"]),
        disclaimer=value["disclaimer"],
    )

