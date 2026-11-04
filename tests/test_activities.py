from copy import deepcopy

import pytest


def test_root_redirects_to_static_index(client):
    response = client.get("/", follow_redirects=False)

    assert response.status_code == 307
    assert response.headers["location"] == "/static/index.html"


def test_root_serves_html_after_redirect(client):
    response = client.get("/")

    assert response.status_code == 200
    assert response.url.path == "/static/index.html"
    assert response.headers["content-type"].startswith("text/html")
    assert "Mergington High School" in response.text


def test_get_activities_returns_data_without_mutation(client, activity_data):
    expected = deepcopy(activity_data)

    response = client.get("/activities")

    assert response.status_code == 200
    assert response.json() == expected
    assert activity_data == expected


def test_get_activities_handles_empty_data(client, activity_data):
    activity_data.clear()

    response = client.get("/activities")

    assert response.status_code == 200
    assert response.json() == {}
    assert activity_data == {}


@pytest.mark.parametrize("email", ["new@example.com", "student+club@example.com"])
def test_signup_adds_participant(client, activity_data, email):
    expected = deepcopy(activity_data)
    expected["Test Club"]["participants"].append(email)

    response = client.post("/activities/Test Club/signup", params={"email": email})

    assert response.status_code == 200
    assert response.json() == {"message": f"Signed up {email} for Test Club"}
    assert activity_data == expected
    assert client.get("/activities").json() == expected


@pytest.mark.parametrize(
    ("activity", "params", "status", "detail"),
    [
        ("Test Club", {"email": "first@example.com"}, 400, "Student is already registered"),
        ("Missing Club", {"email": "new@example.com"}, 404, "Activity not found"),
        ("Test Club", {}, 422, None),
    ],
)
def test_signup_rejects_invalid_requests_without_mutation(
    client, activity_data, activity, params, status, detail
):
    original = deepcopy(activity_data)

    response = client.post(f"/activities/{activity}/signup", params=params)

    assert response.status_code == status
    if detail is not None:
        assert response.json()["detail"] == detail
    else:
        assert any(
            error["loc"] == ["query", "email"] for error in response.json()["detail"]
        )
    assert activity_data == original


def test_removes_selected_participant_and_updates_activity_data(client, activity_data):
    expected = deepcopy(activity_data)
    expected["Test Club"]["participants"].pop(0)

    response = client.delete(
        "/activities/Test Club/participants/0", params={"email": "first@example.com"}
    )

    assert response.status_code == 200
    assert response.json() == {
        "message": "Unregistered first@example.com from Test Club"
    }
    assert activity_data == expected
    assert client.get("/activities").json() == expected


def test_removes_only_clicked_duplicate(client, activity_data):
    participants = activity_data["Test Club"]["participants"]
    participants[:] = [
        "duplicate@example.com", "other@example.com", "duplicate@example.com"
    ]

    response = client.delete(
        "/activities/Test Club/participants/2",
        params={"email": "duplicate@example.com"},
    )

    assert response.status_code == 200
    assert participants == ["duplicate@example.com", "other@example.com"]


@pytest.mark.parametrize(
    ("activity", "index", "email", "status", "detail"),
    [
        ("Missing Club", 0, "first@example.com", 404, "Activity not found"),
        ("Test Club", -1, "first@example.com", 404, "Participant not found"),
        ("Test Club", 2, "first@example.com", 404, "Participant not found"),
        ("Test Club", 100, "first@example.com", 404, "Participant not found"),
        (
            "Test Club", 0, "second@example.com", 409,
            "Participant list has changed. Please refresh and try again.",
        ),
    ],
)
def test_unregister_rejects_missing_or_stale_selection(
    client, activity_data, activity, index, email, status, detail
):
    original = deepcopy(activity_data)

    response = client.delete(
        f"/activities/{activity}/participants/{index}", params={"email": email}
    )

    assert response.status_code == status
    assert response.json()["detail"] == detail
    assert activity_data == original


def test_last_participant_removal_and_repeat_request(client, activity_data):
    participants = activity_data["Test Club"]["participants"]
    participants[:] = ["last@example.com"]
    url = "/activities/Test Club/participants/0"
    params = {"email": "last@example.com"}

    assert client.delete(url, params=params).status_code == 200
    assert participants == []
    assert client.get("/activities").json()["Test Club"]["participants"] == []

    repeated = client.delete(url, params=params)
    assert repeated.status_code == 404
    assert repeated.json()["detail"] == "Participant not found"
    assert participants == []


@pytest.mark.parametrize(
    ("index", "params", "location"),
    [
        ("0", {}, ["query", "email"]),
        ("not-an-index", {"email": "first@example.com"}, ["path", "participant_index"]),
    ],
)
def test_unregister_validation_errors_do_not_mutate_data(
    client, activity_data, index, params, location
):
    original = deepcopy(activity_data)

    response = client.delete(
        f"/activities/Test Club/participants/{index}", params=params
    )

    assert response.status_code == 422
    assert any(
        error["loc"] == location for error in response.json()["detail"]
    )
    assert activity_data == original


def test_unregister_preserves_special_characters_in_email(client, activity_data):
    email = "student+club@example.com"
    participants = activity_data["Test Club"]["participants"]
    participants.append(email)

    response = client.delete(
        "/activities/Test Club/participants/2", params={"email": email}
    )

    assert response.status_code == 200
    assert participants == ["first@example.com", "second@example.com"]


def test_signup_allows_reregistration_after_removal(client, activity_data):
    params = {"email": "first@example.com"}
    assert client.delete(
        "/activities/Test Club/participants/0", params=params
    ).status_code == 200

    response = client.post("/activities/Test Club/signup", params=params)

    assert response.status_code == 200
    assert activity_data["Test Club"]["participants"] == [
        "second@example.com", "first@example.com"
    ]
