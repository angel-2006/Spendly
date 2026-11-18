from database.db import get_user_by_email, get_user_by_id

DEMO_EMAIL = "demo@spendly.com"
DEMO_PASSWORD = "demo123"


def post_login(client, email=DEMO_EMAIL, password=DEMO_PASSWORD):
    return client.post("/login", data={"email": email, "password": password})


def body(response):
    return response.get_data(as_text=True)


def session_data(client):
    with client.session_transaction() as sess:
        return dict(sess)


# --- GET /login ---

def test_login_page_renders(client):
    response = client.get("/login")
    assert response.status_code == 200
    assert 'action="/login"' in body(response)


# --- success ---

def test_login_success_redirects_to_landing(client):
    response = post_login(client)
    assert response.status_code == 302
    assert response.headers["Location"] == "/"


def test_login_sets_only_user_id_in_session(client, app):
    post_login(client)
    with app.app_context():
        demo = get_user_by_email(DEMO_EMAIL)
    assert session_data(client) == {"user_id": demo["id"]}


def test_email_is_case_and_whitespace_insensitive(client):
    response = post_login(client, email="  DEMO@Spendly.com ")
    assert response.status_code == 302
    assert "user_id" in session_data(client)


def test_registered_user_can_login(client):
    client.post(
        "/register",
        data={"name": "Asha", "email": "asha@example.com", "password": "password1"},
    )
    response = post_login(client, "asha@example.com", "password1")
    assert response.status_code == 302
    assert "user_id" in session_data(client)


# --- failures ---

def test_wrong_password(client):
    response = post_login(client, password="wrong-password")
    assert response.status_code == 200
    assert "Invalid email or password." in body(response)
    assert "user_id" not in session_data(client)


def test_unknown_email_gives_same_error(client):
    wrong_pw = body(post_login(client, password="wrong-password"))
    unknown = body(post_login(client, email="nobody@example.com"))
    assert "Invalid email or password." in unknown
    assert "user_id" not in session_data(client)
    assert wrong_pw.count("Invalid email or password.") == 1
    assert unknown.count("Invalid email or password.") == 1


def test_missing_fields_show_error(client):
    for email, password in [("", DEMO_PASSWORD), (DEMO_EMAIL, ""), ("", "")]:
        response = post_login(client, email, password)
        assert response.status_code == 200
        assert "Please enter your email and password." in body(response)
        assert "user_id" not in session_data(client)


def test_failed_login_repopulates_email_not_password(client):
    response = post_login(client, password="wrong-password")
    html = body(response)
    assert f'value="{DEMO_EMAIL}"' in html
    assert "wrong-password" not in html


# --- navbar ---

def test_navbar_logged_out(client):
    html = body(client.get("/"))
    assert "Sign in" in html
    assert "Get started" in html
    assert "Sign out" not in html


def test_navbar_logged_in(client):
    post_login(client)
    html = body(client.get("/"))
    assert "Demo User" in html
    assert "Sign out" in html
    assert "Get started" not in html


# --- already logged in / stale session ---

def test_login_get_when_logged_in_redirects(client):
    post_login(client)
    response = client.get("/login")
    assert response.status_code == 302
    assert response.headers["Location"] == "/"


def test_stale_session_shows_form_and_logged_out_navbar(client):
    with client.session_transaction() as sess:
        sess["user_id"] = 9999
    assert "Get started" in body(client.get("/"))
    response = client.get("/login")
    assert response.status_code == 200
    assert "user_id" not in session_data(client)


def test_login_clears_previous_session_data(client):
    with client.session_transaction() as sess:
        sess["leftover"] = "x"
    post_login(client)
    assert "leftover" not in session_data(client)


# --- logout ---

def test_logout_clears_session_and_redirects(client):
    post_login(client)
    response = client.get("/logout")
    assert response.status_code == 302
    assert response.headers["Location"] == "/"
    assert "user_id" not in session_data(client)
    assert "Get started" in body(client.get("/"))


def test_logout_when_not_logged_in(client):
    response = client.get("/logout")
    assert response.status_code == 302


# --- db helper ---

def test_get_user_by_id(app):
    with app.app_context():
        demo = get_user_by_email(DEMO_EMAIL)
        assert get_user_by_id(demo["id"])["email"] == DEMO_EMAIL
        assert get_user_by_id(9999) is None
        assert get_user_by_id(None) is None


# --- auth pages are closed to logged-in users ---

def test_register_redirects_when_logged_in(client):
    post_login(client)
    for response in (
        client.get("/register"),
        client.post(
            "/register",
            data={"name": "X", "email": "x@example.com", "password": "password1"},
        ),
    ):
        assert response.status_code == 302
        assert response.headers["Location"] == "/"
    assert get_user_by_email("x@example.com") is None


def test_login_post_redirects_when_logged_in(client):
    post_login(client)
    response = post_login(client, "nobody@example.com", "whatever")
    assert response.status_code == 302
    assert response.headers["Location"] == "/"
