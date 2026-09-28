"""
Tests for the Cox model notebook (run-cox-ph.ipynb). Not meant for students.
"""
import pandas as pd

import src.utils
import src.vantage_client
from src import COX_ALGORITHM_IMAGE
from tests.conftest import FakeClient
from tests.helpers import (COX_NOTEBOOK_PATH, SURVIVAL_DATA_PATH, get_code_cells, get_notebook_setting,
                           load_cox_results, load_descriptive_statistics_results)

# The line that students must change in option 2, and the answer that they should find
STUDENT_LINE = "ORGANISATIONS_WITH_SAME_CODING = [1, 2, 3]"
STUDENT_ANSWER = "ORGANISATIONS_WITH_SAME_CODING = [1, 2]"


def run_notebook(monkeypatch, student_answer=None, descriptive_statistics_done=True):
    """Run all code cells of the Cox notebook with a fake vantage6 client instead of a real server."""
    client = FakeClient(load_descriptive_statistics_results(), load_cox_results())
    if descriptive_statistics_done:
        client.task.create(name="Descriptive statistics retrieval", image="", input_={}, organizations=[1])
    monkeypatch.setattr(src.vantage_client, "authenticate", lambda config, **kwargs: client)
    monkeypatch.setattr(src.utils, "check_server", lambda config: None)

    namespace = {}
    for source in get_code_cells(COX_NOTEBOOK_PATH):
        if student_answer:
            source = source.replace(STUDENT_LINE, student_answer)
        namespace["_"] = None
        exec(source, namespace)
    return client, namespace


def test_students_must_change_the_organisations_themselves():
    assert any(STUDENT_LINE in source for source in get_code_cells(COX_NOTEBOOK_PATH))


def test_default_model_uses_all_organisations_and_the_t_stage():
    assert get_notebook_setting("ORGANISATIONS_TO_RUN_TASK", COX_NOTEBOOK_PATH) == [1, 2, 3]
    assert "clin_t" in get_notebook_setting("MODEL_VARIABLES", COX_NOTEBOOK_PATH)
    assert "clin_t" not in get_notebook_setting("VARIABLES_WITHOUT_T_STAGE", COX_NOTEBOOK_PATH)


def test_model_variables_are_numbers_at_the_first_two_nodes():
    data = pd.read_csv(SURVIVAL_DATA_PATH)
    first_two_nodes = data[data["id"].str[0].isin(["A", "B"])]
    for variable in get_notebook_setting("MODEL_VARIABLES", COX_NOTEBOOK_PATH):
        assert pd.to_numeric(first_two_nodes[variable], errors="coerce").notna().all(), variable


def test_notebook_with_the_right_answer(monkeypatch, capsys):
    client, namespace = run_notebook(monkeypatch, STUDENT_ANSWER)
    output = capsys.readouterr().out

    models = namespace["models"]
    assert list(models) == ["A: all organisations, with T stage", "B: all organisations, without T stage",
                            "C: same T stage coding, with T stage", "D: same T stage coding, without T stage"]
    assert models["A: all organisations, with T stage"] is None
    assert all(model is not None for name, model in models.items() if not name.startswith("A"))
    assert "Good: you have already explored the data" in output
    assert "could not be calculated" in output

    cox_tasks = [task for task in client.created_tasks if task["image"] == COX_ALGORITHM_IMAGE]
    assert [task["input_"]["kwargs"]["organization_ids"] for task in cox_tasks] == [
        [1, 2, 3], [1, 2, 3], [1, 2], [1, 2]]


def test_notebook_without_changing_the_organisations(monkeypatch, capsys):
    """If students do not change the list, model C fails and model D is not calculated."""
    _, namespace = run_notebook(monkeypatch)
    output = capsys.readouterr().out
    assert namespace["models"]["C: same T stage coding, with T stage"] is None
    assert "D: same T stage coding, without T stage" not in namespace["models"]
    assert "Model C is missing" in output


def test_notebook_warns_when_descriptive_statistics_were_not_run(monkeypatch, capsys):
    run_notebook(monkeypatch, STUDENT_ANSWER, descriptive_statistics_done=False)
    assert "WARNING: you have not run the descriptive statistics notebook yet" in capsys.readouterr().out

