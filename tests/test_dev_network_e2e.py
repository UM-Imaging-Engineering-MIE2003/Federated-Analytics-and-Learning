"""
End-to-end test: run both notebooks against a running vantage6 developer network.
Not meant for students.

Start the network first ('python dev_network.py start'), then run 'pytest -m devnetwork'.
"""
import nbformat
import pytest
import requests

import dev_network
from tests.helpers import COX_NOTEBOOK_PATH, DESCRIPTIVE_STATISTICS_NOTEBOOK_PATH, PROJECT_ROOT

pytestmark = pytest.mark.devnetwork

SERVER_VERSION_URL = "http://localhost:7601/api/version"

# The notebook waits for the nodes, which first need to download the algorithm image
NOTEBOOK_TIMEOUT_SECONDS = 1800


@pytest.fixture(scope="module")
def executed_notebook():
    from nbclient import NotebookClient

    try:
        requests.get(SERVER_VERSION_URL, timeout=10).raise_for_status()
    except requests.exceptions.RequestException:
        pytest.fail("The developer network is not running; start it with 'python dev_network.py start'")

    notebook = nbformat.read(DESCRIPTIVE_STATISTICS_NOTEBOOK_PATH, as_version=4)
    NotebookClient(notebook, timeout=NOTEBOOK_TIMEOUT_SECONDS, kernel_name="python3",
                   resources={"metadata": {"path": str(PROJECT_ROOT)}}).execute()
    return notebook


def get_text_output(notebook, cell_id):
    cell = next(cell for cell in notebook.cells if cell.get("id") == cell_id)
    texts = []
    for output in cell.outputs:
        texts.append(output.get("text", ""))
        texts.append(output.get("data", {}).get("text/plain", ""))
    return "".join(texts)


def test_notebook_runs_without_errors(executed_notebook):
    for cell in executed_notebook.cells:
        if cell.cell_type == "code":
            assert all(output.output_type != "error" for output in cell.outputs)


def test_all_results_arrive(executed_notebook):
    assert "All results have arrived." in get_text_output(executed_notebook, "bc983da302cfb8ed")


def test_aggregate_result_describes_all_patients(executed_notebook):
    numerical_table = get_text_output(executed_notebook, "c0ffee0000000007")
    # The aggregate result counts the 1200 patients of the three hospitals
    assert "1200.0" in numerical_table


def find_organisation_with_different_t_stage_coding() -> int:
    """Look in the data files of the nodes which organisation stores the T stage as text (e.g. '2b')."""
    import pandas as pd
    from vantage6.cli.context.node import NodeContext

    network = dev_network.NETWORK_NAME
    data_folder = NodeContext.instance_folders("node", f"{network}_node_1", False)["dev"] / network
    different = []
    for organisation in range(1, dev_network.NUMBER_OF_NODES + 1):
        # In the developer network, node N belongs to organisation N
        node_data = pd.read_csv(data_folder / f"df_survival_{network}_node_{organisation}.csv")
        if pd.to_numeric(node_data["clin_t"], errors="coerce").isna().any():
            different.append(organisation)
    assert len(different) == 1, f"Expected exactly one organisation with T sub-stages, found {different}"
    return different[0]


@pytest.fixture(scope="module")
def executed_cox_notebook(executed_notebook):
    """Run the Cox notebook after the descriptive statistics notebook, with the answer that students should find."""
    from nbclient import NotebookClient

    from tests.test_cox_notebook import STUDENT_LINE

    # The hospitals are given to the nodes in a random order, so find the right answer first
    different = find_organisation_with_different_t_stage_coding()
    same_coding = [organisation for organisation in range(1, dev_network.NUMBER_OF_NODES + 1)
                   if organisation != different]
    notebook = nbformat.read(COX_NOTEBOOK_PATH, as_version=4)
    for cell in notebook.cells:
        cell.source = cell.source.replace(STUDENT_LINE, f"ORGANISATIONS_WITH_SAME_CODING = {same_coding}")
    NotebookClient(notebook, timeout=NOTEBOOK_TIMEOUT_SECONDS, kernel_name="python3",
                   resources={"metadata": {"path": str(PROJECT_ROOT)}}).execute()
    return notebook


def test_cox_notebook_runs_without_errors(executed_cox_notebook):
    for cell in executed_cox_notebook.cells:
        if cell.cell_type == "code":
            assert all(output.output_type != "error" for output in cell.outputs)


def test_cox_notebook_finds_the_descriptive_statistics(executed_cox_notebook):
    assert "Good: you have already explored the data" in get_text_output(executed_cox_notebook, "cox-check-code")


def test_cox_model_with_different_coding_fails(executed_cox_notebook):
    output = get_text_output(executed_cox_notebook, "cox-model-a-code")
    assert "could not be calculated (status: crashed)" in output
    assert "'int' and 'str'" in output


def test_cox_models_match_the_stored_results(executed_cox_notebook):
    """The real network must give the same AIC as the mock client (tests/data/cox_results.json)."""
    table = get_text_output(executed_cox_notebook, "cox-compare-table")
    for aic in ["4873.9", "2340.7", "2417.3"]:
        assert aic in table
