import pytest
import csv
import os

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


@pytest.fixture
def ae_spec_path():
    return os.path.join(FIXTURES_DIR, "sample_ae_spec.csv")


@pytest.fixture
def dm_spec_path():
    return os.path.join(FIXTURES_DIR, "sample_dm_spec.csv")


@pytest.fixture
def ae_raw_rows():
    rows = []
    path = os.path.join(FIXTURES_DIR, "sample_ae_spec.csv")
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return rows
