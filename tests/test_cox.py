"""
Tests for the Cox model helper functions in src/cox.py. Not meant for students.
"""
import json

import matplotlib.pyplot as plt
import pytest

from src import AGGREGATOR_ORGANISATION, COX_ALGORITHM_IMAGE
from src import cox
from src.descriptive_statistics import send_task
from tests.helpers import get_cox_models

WITH_T_STAGE = ["age_at_diagnosis", "performance_status_ecog", "clin_m", "clin_t"]
WITHOUT_T_STAGE = ["age_at_diagnosis", "performance_status_ecog", "clin_m"]


@pytest.fixture
def models(fake_client):
    """The four models of the Cox notebook, calculated with the stored results."""
    return {
        "A": cox.run_cox_model(fake_client, [1, 2, 3], WITH_T_STAGE, "survival"),
        "B": cox.run_cox_model(fake_client, [1, 2, 3], WITHOUT_T_STAGE, "survival"),
        "C": cox.run_cox_model(fake_client, [1, 2], WITH_T_STAGE, "survival"),
        "D": cox.run_cox_model(fake_client, [1, 2], WITHOUT_T_STAGE, "survival"),
    }


def test_tests_use_the_models_of_the_notebook():
    assert get_cox_models() == [([1, 2, 3], WITH_T_STAGE), ([1, 2, 3], WITHOUT_T_STAGE),
                                ([1, 2], WITH_T_STAGE), ([1, 2], WITHOUT_T_STAGE)]


def test_warning_when_descriptive_statistics_were_not_run(fake_client, capsys):
    cox.check_descriptive_statistics_done(fake_client)
    assert "WARNING" in capsys.readouterr().out


def test_no_warning_after_descriptive_statistics(fake_client, capsys):
    send_task(fake_client, [1], "partial_general_statistics", {}, "survival")
    cox.check_descriptive_statistics_done(fake_client)
    assert "Good" in capsys.readouterr().out


def test_run_cox_model_sends_the_expected_task(fake_client):
    cox.run_cox_model(fake_client, [1, 2], WITH_T_STAGE, "survival")
    task = fake_client.created_tasks[0]
    assert task["image"] == COX_ALGORITHM_IMAGE
    assert task["organizations"] == [AGGREGATOR_ORGANISATION]
    assert task["databases"] == [{"label": "survival"}]
    assert task["input_"] == {"method": "central", "kwargs": {
        "time_col": "overall_survival_in_days", "outcome_col": "event_overall_survival",
        "expl_vars": WITH_T_STAGE, "organization_ids": [1, 2]}}


def test_model_with_different_t_stage_coding_fails_with_an_explanation(fake_client, capsys):
    assert cox.run_cox_model(fake_client, [1, 2, 3], WITH_T_STAGE, "survival") is None
    output = capsys.readouterr().out
    assert "could not be calculated (status: crashed)" in output
    assert "TypeError: unsupported operand type(s) for +: 'int' and 'str'" in output
    assert "descriptive statistics notebook" in output


def test_model_result_remembers_organisations_and_variables(models):
    assert models["C"]["organisations"] == [1, 2]
    assert models["C"]["variables"] == WITH_T_STAGE


def test_compare_models(models):
    table = cox.compare_models(models)
    assert list(table.index) == ["B", "C", "D"]
    assert list(table["T stage in model"]) == ["no", "yes", "no"]
    # On the same patients, the model with the T stage fits better (lower AIC); this answers question 1
    assert table.loc["C", "AIC"] < table.loc["D", "AIC"]


def test_t_stage_increases_the_risk(models):
    ratios = cox.read_hazard_ratios(models["C"]).set_index("variable")
    assert ratios.loc["clin_t", "lowest (95 % CI)"] > 1


def test_leaving_out_an_organisation_widens_the_confidence_intervals(models):
    """Question 2: model C uses fewer patients, so its confidence intervals are wider than those of model B."""
    width = {name: cox.read_hazard_ratios(models[name]).set_index("variable")
             .eval("`highest (95 % CI)` - `lowest (95 % CI)`") for name in ["B", "C"]}
    assert (width["C"][WITHOUT_T_STAGE] > width["B"][WITHOUT_T_STAGE]).all()


def test_show_hazard_ratios(models):
    table = cox.show_hazard_ratios(models)
    assert list(table.index) == WITHOUT_T_STAGE + ["clin_t"]
    assert list(table.columns) == ["B", "C", "D"]
    assert table.loc["clin_t", "B"] == "not in model"
    assert table.loc["clin_t", "C"].startswith("1.86 (")


def test_plot_hazard_ratios(models):
    cox.plot_hazard_ratios(models)
    axis = plt.gcf().axes[0]
    assert [label.get_text() for label in axis.get_yticklabels()] == WITHOUT_T_STAGE + ["clin_t"]
    assert [text.get_text() for text in axis.get_legend().get_texts()] == ["B", "C", "D"]
    lowest, highest = axis.get_xlim()
    assert lowest < 1 < highest


def test_stored_results_are_valid(cox_results):
    for key, result in cox_results.items():
        if result is not None:
            assert json.loads(result)["warnings"] == [], key
