"""
Tests for the shared helper functions in src/utils.py. Not meant for students.
"""
import requests

from src import COLLABORATION_ID
from src import utils


def test_check_server_reports_running_server(monkeypatch, capsys):
    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {"version": "4.15.1"}

    requested_urls = []
    monkeypatch.setattr(requests, "get", lambda url, timeout: requested_urls.append(url) or Response())
    utils.check_server({"server_url": "http://localhost", "server_port": 7601, "server_api": "/api"})
    assert requested_urls == ["http://localhost:7601/api/version"]
    assert "4.15.1" in capsys.readouterr().out


def test_check_server_reports_unreachable_server(monkeypatch, capsys):
    def fail(url, timeout):
        raise requests.exceptions.ConnectionError()

    monkeypatch.setattr(requests, "get", fail)
    utils.check_server({"server_url": "http://localhost", "server_port": 7601, "server_api": "/api"})
    assert "cannot be reached" in capsys.readouterr().out


def test_show_organisations(fake_client, capsys):
    utils.show_organisations(fake_client)
    assert capsys.readouterr().out.splitlines() == ["1: Hospital 1", "2: Hospital 2", "3: Hospital 3"]


def test_send_task_uses_the_given_algorithm(fake_client):
    utils.send_task(fake_client, [1], "central", {"a": 1}, "survival", image="my-image", name="My task")
    task = fake_client.created_tasks[0]
    assert task["image"] == "my-image"
    assert task["name"] == "My task"
    assert task["collaboration"] == COLLABORATION_ID
    assert task["input_"] == {"method": "central", "kwargs": {"a": 1}}
