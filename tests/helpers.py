"""
Shared helpers for the maintainer tests. Not meant for students.
"""
import ast
import json
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).parent.parent
DESCRIPTIVE_STATISTICS_NOTEBOOK_PATH = PROJECT_ROOT / "run-descriptive-statistics.ipynb"
SURVIVAL_DATA_PATH = PROJECT_ROOT / "synthetic_datasets" / "survival.csv"
DESCRIPTIVE_STATISTICS_RESULTS_PATH = Path(__file__).parent / "data" / "descriptive_statistics_results.json"
COX_NOTEBOOK_PATH = PROJECT_ROOT / "run-cox-ph.ipynb"
COX_RESULTS_PATH = Path(__file__).parent / "data" / "cox_results.json"

NUMBER_OF_NODES = 3


def read_notebook(path: Path = DESCRIPTIVE_STATISTICS_NOTEBOOK_PATH) -> dict:
    """Read a course notebook as a dictionary."""
    return json.loads(path.read_text(encoding="utf-8"))


def get_code_cells(path: Path = DESCRIPTIVE_STATISTICS_NOTEBOOK_PATH) -> list[str]:
    """Return the source of every code cell of a course notebook."""
    return ["".join(cell["source"]) for cell in read_notebook(path)["cells"] if cell["cell_type"] == "code"]


def get_notebook_setting(name: str, path: Path = DESCRIPTIVE_STATISTICS_NOTEBOOK_PATH):
    """
    Return the value of a setting in the notebook (e.g. VARIABLES_TO_DESCRIBE), so that the tests always
    use the same settings as the notebook. The setting must be a plain value (a list, dictionary, text, ...).
    """
    for source in get_code_cells(path):
        for statement in ast.parse(source).body:
            if isinstance(statement, ast.Assign) and any(
                    isinstance(target, ast.Name) and target.id == name for target in statement.targets):
                return ast.literal_eval(statement.value)
    raise KeyError(f"No cell in the notebook defines {name}")


def cox_model_key(organisations, variables) -> str:
    """The key of a Cox model in tests/data/cox_results.json, e.g. '1,2|age_at_diagnosis,clin_t'."""
    return ",".join(str(organisation) for organisation in organisations) + "|" + ",".join(variables)


def get_cox_models() -> list[tuple[list[int], list[str]]]:
    """The Cox models (organisations and variables) that the Cox notebook calculates."""
    variables = get_notebook_setting("MODEL_VARIABLES", COX_NOTEBOOK_PATH)
    variables_without_t_stage = get_notebook_setting("VARIABLES_WITHOUT_T_STAGE", COX_NOTEBOOK_PATH)
    return [([1, 2, 3], variables), ([1, 2, 3], variables_without_t_stage),
            ([1, 2], variables), ([1, 2], variables_without_t_stage)]


def load_cox_results() -> dict:
    """Load the stored Cox results; a value of None means that the algorithm crashed."""
    return json.loads(COX_RESULTS_PATH.read_text(encoding="utf-8"))


def _write_node_files(data_folder: Path) -> list:
    """Write the data of each node to a file, split as in the developer network."""
    datasets = []
    for number, node_data in enumerate(split_like_dev_network(pd.read_csv(SURVIVAL_DATA_PATH)), start=1):
        node_file = data_folder / f"node_{number}.csv"
        node_data.to_csv(node_file, index=False)
        datasets.append([{"database": str(node_file), "db_type": "csv", "input_data": {}}])
    return datasets


def run_cox_with_mock_client(data_folder: Path) -> dict:
    """
    Run the Cox algorithm with the vantage6 mock client for every model in the Cox notebook.

    Requires the algorithm packages (see tests/requirements-algorithm.txt).

    Returns:
        Dictionary with cox_model_key(...) as key, and the result as JSON text (or None if it crashed)
    """
    from vantage6.algorithm.tools.mock_client import MockAlgorithmClient

    client = MockAlgorithmClient(datasets=_write_node_files(data_folder), module="coxph")
    # The mock client numbers the organisations 0, 1, 2 instead of 1, 2, 3
    mock_ids = [organisation["id"] for organisation in client.organization.list()]

    results = {}
    for organisations, variables in get_cox_models():
        selected = [mock_ids[organisation - 1] for organisation in organisations]
        try:
            task = client.task.create(input_={"method": "central", "kwargs": {
                "time_col": "overall_survival_in_days", "outcome_col": "event_overall_survival",
                "expl_vars": variables, "organization_ids": selected}}, organizations=[selected[0]])
            result = client.wait_for_results(task["id"])[0]
            result["included_organizations"] = organisations
            results[cox_model_key(organisations, variables)] = json.dumps(result)
        except TypeError:
            results[cox_model_key(organisations, variables)] = None
    return results


def split_like_dev_network(data: pd.DataFrame, number_of_nodes: int = NUMBER_OF_NODES) -> list[pd.DataFrame]:
    """Split the data over the nodes in the same way as 'v6 dev create-demo-network'."""
    length = len(data)
    return [data[i * length // number_of_nodes:(i + 1) * length // number_of_nodes]
            for i in range(number_of_nodes)]


def load_descriptive_statistics_results() -> dict:
    """Load the stored descriptive statistics results; the keys are organisation IDs (int) and 'aggregate'."""
    stored = json.loads(DESCRIPTIVE_STATISTICS_RESULTS_PATH.read_text(encoding="utf-8"))
    return {int(key) if key.isdigit() else key: value for key, value in stored.items()}


def run_descriptive_statistics_with_mock_client(variables_to_describe: dict, data_folder: Path) -> dict:
    """
    Run the descriptive statistics algorithm with the vantage6 mock client on the synthetic data,
    split over the nodes as in the developer network.

    Requires the algorithm package (see tests/requirements-algorithm.txt).

    Returns:
        The descriptive statistics results in the same form as src.descriptive_statistics.collect_results: JSON text per organisation
        ID (1, 2, 3) and under the key 'aggregate'
    """
    from vantage6.algorithm.tools.mock_client import MockAlgorithmClient

    client = MockAlgorithmClient(datasets=_write_node_files(data_folder), module="v6-descriptive-statistics")
    mock_ids = [organisation["id"] for organisation in client.organization.list()]

    descriptive_statistics_results = {}
    for number, mock_id in enumerate(mock_ids, start=1):
        task = client.task.create(input_={"method": "partial_general_statistics",
                                          "kwargs": {"variables_to_describe": variables_to_describe}},
                                  organizations=[mock_id])
        descriptive_statistics_results[number] = json.dumps(client.wait_for_results(task["id"])[0])

    task = client.task.create(input_={"method": "central",
                                      "kwargs": {"variables_to_describe": variables_to_describe,
                                                 "organisations_to_include": mock_ids}},
                              organizations=[mock_ids[0]])
    descriptive_statistics_results["aggregate"] = json.dumps(client.wait_for_results(task["id"])[0])
    return descriptive_statistics_results
