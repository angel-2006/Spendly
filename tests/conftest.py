import pytest


@pytest.fixture
def app(tmp_path, monkeypatch):
    """Flask app bound to a fresh temporary database for each test.

    DB_PATH is patched before app is imported, because importing app runs
    init_db()/seed_db() against whichever path is active at that moment.
    """
    monkeypatch.setattr("database.db.DB_PATH", str(tmp_path / "test.db"))

    import app as app_module
    from database.db import init_db, seed_db

    app_module.app.config["TESTING"] = True
    with app_module.app.app_context():
        init_db()
        seed_db()
    yield app_module.app


@pytest.fixture
def client(app):
    return app.test_client()
