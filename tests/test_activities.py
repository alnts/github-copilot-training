import unittest
from copy import deepcopy

from fastapi.testclient import TestClient

from src.app import activities, app


class ActivityRegistrationTests(unittest.TestCase):
    def setUp(self):
        self.original_activities = deepcopy(activities)
        self.client = TestClient(app)
        activities["Test Club"] = {
            "description": "Test activity",
            "schedule": "Fridays",
            "max_participants": 10,
            "participants": ["first@example.com", "second@example.com"],
        }
        self.participants = activities["Test Club"]["participants"]

    def tearDown(self):
        self.client.close()
        activities.clear()
        activities.update(self.original_activities)

    def delete_participant(self, index, email, activity="Test Club"):
        return self.client.delete(
            f"/activities/{activity}/participants/{index}", params={"email": email}
        )

    def test_removes_selected_participant_and_updates_activity_data(self):
        response = self.delete_participant(0, "first@example.com")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"message": "Unregistered first@example.com from Test Club"},
        )
        data = self.client.get("/activities").json()
        self.assertEqual(data["Test Club"]["participants"], ["second@example.com"])
        self.assertEqual(data["Test Club"]["max_participants"], 10)
        for name, activity in self.original_activities.items():
            self.assertEqual(data[name], activity)

    def test_removes_only_clicked_duplicate(self):
        self.participants[:] = [
            "duplicate@example.com", "other@example.com", "duplicate@example.com"
        ]

        response = self.delete_participant(2, "duplicate@example.com")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            self.participants, ["duplicate@example.com", "other@example.com"]
        )

    def test_missing_activity_returns_not_found(self):
        response = self.delete_participant(0, "first@example.com", "Missing Club")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"], "Activity not found")

    def test_invalid_indices_do_not_remove_anyone(self):
        for index in (-1, 2, 100):
            with self.subTest(index=index):
                response = self.delete_participant(index, "first@example.com")
                self.assertEqual(response.status_code, 404)
                self.assertEqual(
                    self.participants, ["first@example.com", "second@example.com"]
                )

    def test_stale_selection_returns_conflict_without_mutation(self):
        response = self.delete_participant(0, "second@example.com")

        self.assertEqual(response.status_code, 409)
        self.assertEqual(
            self.participants, ["first@example.com", "second@example.com"]
        )

    def test_last_participant_removal_and_repeat_request(self):
        self.participants[:] = ["last@example.com"]

        self.assertEqual(self.delete_participant(0, "last@example.com").status_code, 200)
        self.assertEqual(self.participants, [])
        self.assertEqual(self.delete_participant(0, "last@example.com").status_code, 404)

    def test_missing_email_or_invalid_index_is_rejected(self):
        for url in (
            "/activities/Test Club/participants/0",
            "/activities/Test Club/participants/not-an-index?email=first@example.com",
        ):
            with self.subTest(url=url):
                self.assertEqual(self.client.delete(url).status_code, 422)
                self.assertEqual(
                    self.participants, ["first@example.com", "second@example.com"]
                )

    def test_email_query_parameter_preserves_special_characters(self):
        email = "student+club@example.com"
        self.participants.append(email)

        self.assertEqual(self.delete_participant(2, email).status_code, 200)
        self.assertNotIn(email, self.participants)

    def test_signup_still_rejects_duplicates_and_allows_reregistration(self):
        url = "/activities/Test Club/signup"
        params = {"email": "first@example.com"}
        self.assertEqual(self.client.post(url, params=params).status_code, 400)
        self.assertEqual(self.delete_participant(0, params["email"]).status_code, 200)
        self.assertEqual(self.client.post(url, params=params).status_code, 200)
        self.assertEqual(self.participants, ["second@example.com", "first@example.com"])


if __name__ == "__main__":
    unittest.main()
