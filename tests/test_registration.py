import sqlite3

import pytest
from werkzeug.security import check_password_hash

from database.db import create_user, get_db, get_user_by_email

VALID = {"name": "Jane Doe", "email": "jane@example.com", "password": "secret123"}


def post_register(client, name=VALID["name"], email=VALID["email"],
                  password=VALID["password"]):
    return client.post(
        "/register",
        data={"name": name, "email": email, "password": password},
        follow_redirects=False,
    )


def user_count():
    conn = get_db()
    try:
        return conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    finally:
        conn.close()


def body(response):
    return response.get_data(as_text=True)


# --- GET ---------------------------------------------------------------

def test_get_register_renders_form(client):
    response = client.get("/register")
    assert response.status_code == 200
    assert 'action="/register"' in body(response)


# --- success -----------------------------------------------------------

def test_register_success_redirects_to_login(client):
    response = post_register(client)
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")


def test_register_success_creates_user_row(client):
    before = user_count()
    post_register(client)
    assert user_count() == before + 1
    row = get_user_by_email("jane@example.com")
    assert row["name"] == "Jane Doe"


def test_name_and_email_are_stripped_and_email_lowercased(client):
    post_register(client, name="  Jane  ", email="  Jane@Example.COM ")
    row = get_user_by_email("jane@example.com")
    assert row is not None
    assert row["name"] == "Jane"


def test_password_is_hashed(client):
    post_register(client)
    row = get_user_by_email("jane@example.com")
    assert row["password_hash"] != VALID["password"]
    assert VALID["password"] not in row["password_hash"]
    assert check_password_hash(row["password_hash"], VALID["password"])


def test_password_of_exactly_8_characters_is_accepted(client):
    assert post_register(client, password="12345678").status_code == 302


def test_password_of_7_characters_is_rejected(client):
    before = user_count()
    response = post_register(client, password="1234567")
    assert response.status_code == 200
    assert "at least 8 characters" in body(response)
    assert user_count() == before


# --- duplicates --------------------------------------------------------

def test_duplicate_email_is_rejected(client):
    post_register(client)
    before = user_count()
    response = post_register(client)
    assert response.status_code == 200
    assert "already exists" in body(response)
    assert user_count() == before


def test_duplicate_email_is_case_insensitive(client):
    post_register(client)
    before = user_count()
    response = post_register(client, email="JANE@Example.com")
    assert response.status_code == 200
    assert "already exists" in body(response)
    assert user_count() == before


def test_demo_user_is_unaffected(client):
    demo_before = get_user_by_email("demo@spendly.com")
    post_register(client)
    response = post_register(client, email="demo@spendly.com")
    assert response.status_code == 200
    assert "already exists" in body(response)
    demo_after = get_user_by_email("demo@spendly.com")
    assert demo_after["password_hash"] == demo_before["password_hash"]


# --- validation --------------------------------------------------------

@pytest.mark.parametrize(
    "overrides, message",
    [
        ({"name": ""}, "enter your name"),
        ({"name": "   "}, "enter your name"),
        ({"email": ""}, "enter your email"),
        ({"email": "   "}, "enter your email"),
        ({"email": "abc"}, "valid email"),
        ({"email": "a@"}, "valid email"),
        ({"email": "@b"}, "valid email"),
        ({"password": ""}, "enter a password"),
    ],
)
def test_validation_failures(client, overrides, message):
    before = user_count()
    response = post_register(client, **overrides)
    assert response.status_code == 200
    assert message in body(response)
    assert user_count() == before


def test_validation_reports_name_error_first(client):
    response = post_register(client, name="", email="bad", password="x")
    text = body(response)
    assert "enter your name" in text
    assert "valid email" not in text
    assert "at least 8 characters" not in text


# --- re-population -----------------------------------------------------

def test_failed_submission_keeps_name_and_email(client):
    response = post_register(client, password="short")
    text = body(response)
    assert 'value="Jane Doe"' in text
    assert 'value="jane@example.com"' in text


def test_password_is_never_repopulated(client):
    response = post_register(client, password="short-pw")
    assert "short-pw" not in body(response)


def test_retained_name_is_html_escaped(client):
    response = post_register(client, name="<script>x</script>", password="short")
    assert "<script>x</script>" not in body(response)


# --- db helpers --------------------------------------------------------

def test_create_user_twice_raises_integrity_error(client):
    create_user("A", "a@example.com", "password1")
    with pytest.raises(sqlite3.IntegrityError):
        create_user("B", "a@example.com", "password2")
    assert get_user_by_email("a@example.com")["name"] == "A"


def test_get_user_by_email_returns_none_for_unknown(client):
    assert get_user_by_email("nobody@example.com") is None
