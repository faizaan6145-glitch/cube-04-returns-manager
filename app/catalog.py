"""Seller catalogue lookups, scoped per organisation.

Built once from data/returns_sample.csv by scripts/build_catalog.py (see that file
for how to regenerate data/catalog.json). This stands in for "the seller's own
catalogue" mentioned in README.md; real deployments would replace this with a
call to the seller's actual product catalogue.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path


class CatalogItem:
    def __init__(self, org_id: str, sku: str, asin: str, title: str, expected_parts: list[str]):
        self.org_id = org_id
        self.sku = sku
        self.asin = asin
        self.title = title
        self.expected_parts = expected_parts


class Catalog:
    def __init__(self, data: dict):
        self._by_org_sku: dict[tuple[str, str], CatalogItem] = {}
        for org_id, entries in data.get("orgs", {}).items():
            for e in entries:
                item = CatalogItem(org_id, e["sku"], e["asin"], e["title"], e["expected_parts"])
                self._by_org_sku[(org_id, e["sku"])] = item

    def lookup(self, org_id: str, sku: str) -> CatalogItem | None:
        return self._by_org_sku.get((org_id, sku))

    def list_for_org(self, org_id: str) -> list[CatalogItem]:
        return [v for (org, _), v in self._by_org_sku.items() if org == org_id]


@lru_cache(maxsize=1)
def _load(path_str: str) -> Catalog:
    data = json.loads(Path(path_str).read_text(encoding="utf-8"))
    return Catalog(data)


def load_catalog(path: Path) -> Catalog:
    return _load(str(path))
