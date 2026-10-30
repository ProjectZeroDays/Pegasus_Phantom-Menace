"""Catalog discovery and payload build tests."""

from __future__ import annotations

import struct
from pathlib import Path

import pytest
from pegasus.modules.access_workflow import catalog


def test_catalog_discovers_vendored_vectors():
    vectors = catalog.list_vectors()
    assert len(vectors) >= 50
    assert any(vector["category"] == "messaging" for vector in vectors)


def test_whatsapp_mp4_builds_valid_container(tmp_path):
    result = catalog.build("cve_2023_2569_whatsapp_mp4", output_dir=str(tmp_path))
    data = Path(result["path"]).read_bytes()
    assert result["size"] == len(data)
    assert struct.unpack(">I", data[:4])[0] == 8 + len(b"isom\x00\x00\x02\x00isomiso2avc1mp41")


def test_build_by_cve_alias(tmp_path):
    result = catalog.build("CVE-2019-3568", output_dir=str(tmp_path))
    assert result["cve"] == "CVE-2019-3568"


def test_unknown_vector_raises():
    with pytest.raises(catalog.CatalogError):
        catalog.build("CVE-0000-0000")


def test_categories_are_known():
    cats = set(catalog.categories())
    assert {"messaging", "bluetooth", "browser"} & cats
    assert "other" in cats or len(cats) > 3
