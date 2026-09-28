"""
Tests with the real algorithms (descriptive statistics and Cox model), run with the vantage6 mock client.
Not meant for students.

Run in a separate environment with tests/requirements-algorithm.txt:
'pytest -m algorithm tests/test_algorithm.py'
"""
import json
from io import StringIO

import pandas as pd
import pytest

from src import descriptive_statistics
from tests.helpers import get_notebook_setting, load_cox_results, load_descriptive_statistics_results, run_descriptive_statistics_with_mock_client

pytestmark = pytest.mark.algorithm


@pytest.fixture(scope="module")
def descriptive_statistics_algorithm_results(tmp_path_factory):
    pytest.importorskip("vantage6.algorithm.tools.mock_client")
    descriptive_statistics_results = run_descriptive_statistics_with_mock_client(get_notebook_setting("VARIABLES_TO_DESCRIBE"),
                                                 tmp_path_factory.mktemp("nodes"))
    return descriptive_statistics.read_results(descriptive_statistics_results)


def test_algorithm_still_gives_the_stored_results(descriptive_statistics_algorithm_results):
    """If this fails, the algorithm changed: check the notebook, then run 'python -m tests.update_test_data'."""
    stored_results = descriptive_statistics.read_results(load_descriptive_statistics_results())
    for new, stored in zip(descriptive_statistics_algorithm_results, stored_results):
        pd.testing.assert_frame_equal(descriptive_statistics.make_table(new), descriptive_statistics.make_table(stored), atol=0.01)


def test_interoperability_problem_is_visible_in_the_aggregate(descriptive_statistics_algorithm_results):
    _, categorical_results = descriptive_statistics_algorithm_results
    aggregate = categorical_results[(categorical_results["source"] == descriptive_statistics.AGGREGATE_NAME)
                                    & (categorical_results["variable"] == "clin_t")
                                    & (categorical_results["value"] != descriptive_statistics.MISSING_GROUP)]
    assert set(aggregate["value"]) == {"0", "1", "1a", "1b", "2", "2a", "2b", "2c", "3", "4", "4a", "4b"}


def test_privacy_threshold_hides_small_groups(descriptive_statistics_algorithm_results):
    _, categorical_results = descriptive_statistics_algorithm_results
    table = descriptive_statistics.make_table(categorical_results)
    assert table.loc[("clin_t", "0"), ["Organisation 1", "Organisation 3"]].isna().all()
    assert table.loc[("clin_t", "0"), "Organisation 2"] >= 10


def test_aggregate_counts_all_patients(descriptive_statistics_algorithm_results):
    numerical_results, _ = descriptive_statistics_algorithm_results
    table = descriptive_statistics.make_table(numerical_results)
    assert table.loc[("age_at_diagnosis", "count"), "Aggregate"] == 1200


@pytest.fixture(scope="module")
def cox_results(tmp_path_factory):
    pytest.importorskip("coxph")
    from tests.helpers import run_cox_with_mock_client
    return run_cox_with_mock_client(tmp_path_factory.mktemp("cox_nodes"))


def test_cox_algorithm_still_gives_the_stored_results(cox_results):
    """If this fails, the Cox algorithm changed: check the notebook, then run 'python -m tests.update_test_data'."""
    stored = load_cox_results()
    assert set(cox_results) == set(stored)
    for key, result in cox_results.items():
        if stored[key] is None:
            assert result is None, f"{key} should fail because of the different T stage coding"
            continue
        new, old = json.loads(result), json.loads(stored[key])
        assert new["aic"] == pytest.approx(old["aic"], abs=0.1), key
        pd.testing.assert_frame_equal(pd.read_json(StringIO(new["model"])), pd.read_json(StringIO(old["model"])),
                                      atol=0.001)
