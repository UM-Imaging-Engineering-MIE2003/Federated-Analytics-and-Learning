"""
Regenerate tests/data/descriptive_statistics_results.json and tests/data/cox_results.json with the real algorithms.
Not meant for students.

Run this after changing the synthetic data, VARIABLES_TO_DESCRIBE in the descriptive statistics
notebook, or the model variables in the Cox notebook, in an
environment with tests/requirements-algorithm.txt installed:

    python -m tests.update_test_data
"""
import json
import tempfile
from pathlib import Path

from tests.helpers import (COX_RESULTS_PATH, DESCRIPTIVE_STATISTICS_RESULTS_PATH, get_notebook_setting, run_descriptive_statistics_with_mock_client,
                           run_cox_with_mock_client)


def main() -> None:
    variables_to_describe = get_notebook_setting("VARIABLES_TO_DESCRIBE")
    with tempfile.TemporaryDirectory() as data_folder:
        descriptive_statistics_results = run_descriptive_statistics_with_mock_client(variables_to_describe, Path(data_folder))
        cox_results = run_cox_with_mock_client(Path(data_folder))
    DESCRIPTIVE_STATISTICS_RESULTS_PATH.parent.mkdir(exist_ok=True)
    DESCRIPTIVE_STATISTICS_RESULTS_PATH.write_text(json.dumps(descriptive_statistics_results, indent=2) + "\n", encoding="utf-8")
    print(f"Saved the descriptive statistics results to {DESCRIPTIVE_STATISTICS_RESULTS_PATH}")
    COX_RESULTS_PATH.write_text(json.dumps(cox_results, indent=2) + "\n", encoding="utf-8")
    print(f"Saved the Cox results to {COX_RESULTS_PATH}")


if __name__ == "__main__":
    main()
