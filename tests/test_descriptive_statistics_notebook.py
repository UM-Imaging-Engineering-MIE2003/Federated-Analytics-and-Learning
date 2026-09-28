"""
Tests for the descriptive statistics notebook (run-descriptive-statistics.ipynb). Not meant for students.
"""
import pandas as pd
import pytest

import src.descriptive_statistics
import src.utils
import src.vantage_client
from src import AGGREGATOR_ORGANISATION, DESCRIPTIVE_STATISTICS_ALGORITHM_IMAGE
from tests.conftest import FakeClient
from tests.helpers import SURVIVAL_DATA_PATH, get_code_cells, get_notebook_setting, load_descriptive_statistics_results


def test_database_label_matches_a_synthetic_data_set():
    assert get_notebook_setting("DATABASE_LABEL") == SURVIVAL_DATA_PATH.stem


def test_variables_to_describe_exist_in_the_data():
    columns = pd.read_csv(SURVIVAL_DATA_PATH, nrows=1).columns
    for name, details in get_notebook_setting("VARIABLES_TO_DESCRIBE").items():
        assert name in columns
        assert details == {"datatype": "numerical"} or details == {"datatype": "categorical"}


def test_stored_results_match_the_notebook_variables():
    """If this fails, run 'python -m tests.update_test_data' (see tests/README.md)."""
    numerical_results, categorical_results = src.descriptive_statistics.read_results(load_descriptive_statistics_results())
    stored_variables = set(numerical_results["variable"]) | set(categorical_results["variable"])
    assert stored_variables == set(get_notebook_setting("VARIABLES_TO_DESCRIBE"))


@pytest.fixture
def executed_notebook(monkeypatch):
    """Run all code cells of the notebook with a fake vantage6 client instead of a real server."""
    client = FakeClient(load_descriptive_statistics_results())
    monkeypatch.setattr(src.vantage_client, "authenticate", lambda config, **kwargs: client)
    monkeypatch.setattr(src.utils, "check_server", lambda config: None)

    namespace = {}
    for source in get_code_cells():
        exec(source, namespace)
    return client, namespace


def test_notebook_runs_from_top_to_bottom(executed_notebook):
    client, namespace = executed_notebook
    assert set(namespace["raw_results"]) == {1, 2, 3, "aggregate"}
    assert not namespace["numerical_results"].empty
    assert not namespace["categorical_results"].empty


def test_notebook_sends_the_expected_tasks(executed_notebook):
    client, namespace = executed_notebook
    partial_tasks = [task for task in client.created_tasks if task["input_"]["method"] == "partial_general_statistics"]
    central_tasks = [task for task in client.created_tasks if task["input_"]["method"] == "central"]

    assert [task["organizations"] for task in partial_tasks] == [[1], [2], [3]]
    assert len(central_tasks) == 1
    assert central_tasks[0]["organizations"] == [AGGREGATOR_ORGANISATION]
    assert central_tasks[0]["input_"]["kwargs"]["organisations_to_include"] == [1, 2, 3]
    for task in client.created_tasks:
        assert task["image"] == DESCRIPTIVE_STATISTICS_ALGORITHM_IMAGE
        assert task["databases"] == [{"label": "survival"}]
        assert task["input_"]["kwargs"]["variables_to_describe"] == namespace["VARIABLES_TO_DESCRIBE"]
