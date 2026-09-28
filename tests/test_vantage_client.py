"""
Tests for logging in with src/vantage_client.py. Not meant for students.
"""
import pytest

from src import vantage_client

CONFIG = {"server_url": "http://localhost", "server_port": 7601, "server_api": "/api"}


class RecordingClient:
    """Records how the vantage6 client is created and used."""
    instances = []

    def __init__(self, *args, **kwargs):
        self.args, self.kwargs = args, kwargs
        self.authenticated_with = None
        self.private_key_file = "not set"
        RecordingClient.instances.append(self)

    def authenticate(self, **kwargs):
        self.authenticated_with = kwargs

    def setup_encryption(self, private_key_file):
        self.private_key_file = private_key_file


@pytest.fixture(autouse=True)
def recording_client(monkeypatch):
    RecordingClient.instances = []
    monkeypatch.setattr(vantage_client, "Client", RecordingClient)


def fail_when_asked(*args, **kwargs):
    raise AssertionError("The user should not be asked for input")


def test_developer_network_login_asks_nothing(monkeypatch):
    monkeypatch.setattr(vantage_client.getpass, "getpass", fail_when_asked)
    monkeypatch.setattr("builtins.input", fail_when_asked)

    client = vantage_client.authenticate(CONFIG, username="dev_admin", password="password",
                                         use_mfa=False, use_encryption=False, log_level="warn")

    assert client.args == ("http://localhost", 7601, "/api")
    assert client.kwargs == {"log_level": "warn"}
    assert client.authenticated_with == {"username": "dev_admin", "password": "password", "mfa_code": None}
    assert client.private_key_file is None


def test_real_network_login_asks_for_missing_details(monkeypatch):
    answers = iter(['"C:\\keys\\private_key.pem"', "secret", "123456"])
    monkeypatch.setattr(vantage_client.getpass, "getpass", lambda prompt: next(answers))
    monkeypatch.setattr("builtins.input", lambda prompt: "researcher")

    client = vantage_client.authenticate(CONFIG)

    assert client.kwargs == {"log_level": "debug"}
    assert client.authenticated_with == {"username": "researcher", "password": "secret", "mfa_code": "123456"}
    # Quotes around the path (e.g. from 'Copy as path' on Windows) are removed
    assert client.private_key_file == "C:\\keys\\private_key.pem"
