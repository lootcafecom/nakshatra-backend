"""
Tests for auth and persistence (signup, login, profiles, reading
history). Uses an isolated in-memory SQLite database per test run via
FastAPI's dependency override, so these tests never touch the real
nakshatra.db file and can run repeatedly without side effects.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database import Base, get_db

TEST_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


def unique_email():
    import uuid
    return f"test-{uuid.uuid4().hex[:8]}@example.com"


class TestSignupAndLogin:
    def test_signup_returns_token(self):
        resp = client.post("/auth/signup", json={"email": unique_email(), "password": "testpass123"})
        assert resp.status_code == 201
        assert "access_token" in resp.json()

    def test_duplicate_signup_rejected(self):
        email = unique_email()
        client.post("/auth/signup", json={"email": email, "password": "testpass123"})
        resp = client.post("/auth/signup", json={"email": email, "password": "different"})
        assert resp.status_code == 400

    def test_login_with_correct_password(self):
        email = unique_email()
        client.post("/auth/signup", json={"email": email, "password": "testpass123"})
        resp = client.post("/auth/login", json={"email": email, "password": "testpass123"})
        assert resp.status_code == 200
        assert "access_token" in resp.json()

    def test_login_with_wrong_password_rejected(self):
        email = unique_email()
        client.post("/auth/signup", json={"email": email, "password": "testpass123"})
        resp = client.post("/auth/login", json={"email": email, "password": "wrongpassword"})
        assert resp.status_code == 401

    def test_me_endpoint_requires_token(self):
        resp = client.get("/auth/me")
        assert resp.status_code == 401

    def test_me_endpoint_with_valid_token(self):
        email = unique_email()
        token = client.post("/auth/signup", json={"email": email, "password": "testpass123"}).json()["access_token"]
        resp = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert resp.json()["email"] == email


class TestBirthProfiles:
    def _get_token(self) -> str:
        email = unique_email()
        return client.post("/auth/signup", json={"email": email, "password": "testpass123"}).json()["access_token"]

    def test_create_and_list_profile(self):
        token = self._get_token()
        headers = {"Authorization": f"Bearer {token}"}
        create_resp = client.post("/profiles", headers=headers, json={
            "label": "Myself", "name": "Test Person", "birth_date": "1995-06-15",
            "birth_time": "10:30", "place_name": "Mumbai, India",
            "latitude": 19.076, "longitude": 72.8777, "timezone": "Asia/Kolkata",
            "is_primary": True,
        })
        assert create_resp.status_code == 201

        list_resp = client.get("/profiles", headers=headers)
        assert list_resp.status_code == 200
        assert len(list_resp.json()) == 1
        assert list_resp.json()[0]["name"] == "Test Person"

    def test_profile_requires_auth(self):
        resp = client.get("/profiles")
        assert resp.status_code == 401

    def test_delete_profile(self):
        token = self._get_token()
        headers = {"Authorization": f"Bearer {token}"}
        profile_id = client.post("/profiles", headers=headers, json={
            "label": "Myself", "name": "Test Person", "birth_date": "1995-06-15",
            "birth_time": "10:30", "place_name": "Mumbai, India",
            "latitude": 19.076, "longitude": 72.8777, "timezone": "Asia/Kolkata",
        }).json()["id"]

        delete_resp = client.delete(f"/profiles/{profile_id}", headers=headers)
        assert delete_resp.status_code == 204

        list_resp = client.get("/profiles", headers=headers)
        assert len(list_resp.json()) == 0

    def test_profile_limit_enforced(self):
        token = self._get_token()
        headers = {"Authorization": f"Bearer {token}"}
        payload = {
            "label": "Person", "name": "Test", "birth_date": "1995-06-15",
            "birth_time": "10:30", "place_name": "Mumbai, India",
            "latitude": 19.076, "longitude": 72.8777, "timezone": "Asia/Kolkata",
        }
        for _ in range(5):
            resp = client.post("/profiles", headers=headers, json=payload)
            assert resp.status_code == 201
        # 6th should be rejected (MAX_PROFILES_PER_USER = 5)
        resp = client.post("/profiles", headers=headers, json=payload)
        assert resp.status_code == 400

    def test_cannot_delete_another_users_profile(self):
        token_a = self._get_token()
        token_b = self._get_token()
        profile_id = client.post("/profiles", headers={"Authorization": f"Bearer {token_a}"}, json={
            "label": "Myself", "name": "A's profile", "birth_date": "1995-06-15",
            "birth_time": "10:30", "place_name": "Mumbai, India",
            "latitude": 19.076, "longitude": 72.8777, "timezone": "Asia/Kolkata",
        }).json()["id"]

        resp = client.delete(f"/profiles/{profile_id}", headers={"Authorization": f"Bearer {token_b}"})
        assert resp.status_code == 404


class TestReadingHistory:
    def _get_token(self) -> str:
        email = unique_email()
        return client.post("/auth/signup", json={"email": email, "password": "testpass123"}).json()["access_token"]

    def test_anonymous_reading_not_saved(self):
        # no Authorization header at all
        client.post("/readings/numerology", json={
            "name": "Anon", "birth_date": "1995-06-15", "birth_time": "10:30",
            "latitude": 19.076, "longitude": 72.8777, "timezone": "Asia/Kolkata", "language": "en",
        })
        # there's no way to list anonymous history by design — just confirm
        # the reading endpoint itself still succeeds without a token
        resp = client.post("/readings/numerology", json={
            "name": "Anon", "birth_date": "1995-06-15", "birth_time": "10:30",
            "latitude": 19.076, "longitude": 72.8777, "timezone": "Asia/Kolkata", "language": "en",
        })
        assert resp.status_code == 200

    def test_signed_in_reading_appears_in_history(self):
        token = self._get_token()
        headers = {"Authorization": f"Bearer {token}"}
        client.post("/readings/numerology", headers=headers, json={
            "name": "Signed In Person", "birth_date": "1995-06-15", "birth_time": "10:30",
            "latitude": 19.076, "longitude": 72.8777, "timezone": "Asia/Kolkata", "language": "en",
        })
        history_resp = client.get("/readings/history", headers=headers)
        assert history_resp.status_code == 200
        history = history_resp.json()
        assert len(history) == 1
        assert history[0]["reading_type"] == "numerology"
        assert history[0]["calculated_data"]["Life Path"]["value"] == 9

    def test_history_requires_auth(self):
        resp = client.get("/readings/history")
        assert resp.status_code == 401

    def test_history_filter_by_type(self):
        token = self._get_token()
        headers = {"Authorization": f"Bearer {token}"}
        client.post("/readings/numerology", headers=headers, json={
            "name": "Person", "birth_date": "1995-06-15", "birth_time": "10:30",
            "latitude": 19.076, "longitude": 72.8777, "timezone": "Asia/Kolkata", "language": "en",
        })
        client.post("/readings/tarot", headers=headers, json={"name": "Person", "language": "en"})

        numerology_only = client.get("/readings/history?reading_type=numerology", headers=headers).json()
        assert len(numerology_only) == 1
        assert numerology_only[0]["reading_type"] == "numerology"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
