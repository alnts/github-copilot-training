from copy import deepcopy

import pytest
from fastapi.testclient import TestClient

from src.app import activities, app


@pytest.fixture
def activity_data():
    original = deepcopy(activities)
    activities.clear()
    activities.update({
        "Test Club": {
            "description": "Test activity",
            "schedule": "Fridays",
            "max_participants": 10,
            "participants": ["first@example.com", "second@example.com"],
        },
        "Other Club": {
            "description": "Another activity",
            "schedule": "Mondays",
            "max_participants": 5,
            "participants": [],
        },
    })
    try:
        yield activities
    finally:
        activities.clear()
        activities.update(original)


@pytest.fixture
def client(activity_data):
    with TestClient(app) as test_client:
        yield test_client
