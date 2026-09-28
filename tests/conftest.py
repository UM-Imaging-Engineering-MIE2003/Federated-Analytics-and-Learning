"""
Shared fixtures for the maintainer tests. Not meant for students.
"""
from types import SimpleNamespace

import matplotlib
import pytest

from src import COX_ALGORITHM_IMAGE
from tests.helpers import cox_model_key, load_cox_results, load_descriptive_statistics_results

# Draw figures without opening windows
matplotlib.use("Agg")

# The end of the log of the Cox algorithm when a variable contains text (as on the real network)
CRASH_LOG = ('  File "/usr/local/lib/python3.10/site-packages/pandas/core/roperator.py", line 11, in radd\n'
             "    return right + left\n"
             "TypeError: unsupported operand type(s) for +: 'int' and 'str'\n")


class FakeClient:
    """
    A stand-in for the vantage6 UserClient that returns stored results instead of contacting a server.
    """

    def __init__(self, descriptive_statistics_results, cox_results=None, organisation_ids=(1, 2, 3)):
        self.descriptive_statistics_results = descriptive_statistics_results
        self.cox_results = cox_results or {}
        self.created_tasks = []
        self.task = SimpleNamespace(create=self._create_task, list=self._list_tasks)
        self.organization = SimpleNamespace(list=self._list_organisations)
        self.run = SimpleNamespace(from_task=self._runs_of_task)
        self._organisation_ids = organisation_ids

    def _list_organisations(self, collaboration=None):
        return {"data": [{"id": organisation_id, "name": f"Hospital {organisation_id}"}
                         for organisation_id in self._organisation_ids]}

    def _create_task(self, **kwargs):
        task = {"id": len(self.created_tasks) + 1, **kwargs}
        self.created_tasks.append(task)
        return {"id": task["id"]}

    def _list_tasks(self, name=None):
        return {"data": [task for task in self.created_tasks if name is None or task["name"] == name]}

    def _get_result(self, task_id):
        task = self.created_tasks[task_id - 1]
        if task["image"] == COX_ALGORITHM_IMAGE:
            kwargs = task["input_"]["kwargs"]
            return self.cox_results[cox_model_key(kwargs["organization_ids"], kwargs["expl_vars"])]
        key = "aggregate" if task["input_"]["method"] == "central" else task["organizations"][0]
        return self.descriptive_statistics_results[key]

    def wait_for_results(self, task_id):
        return {"data": [{"result": self._get_result(task_id) or ""}]}

    def _runs_of_task(self, task_id):
        crashed = self._get_result(task_id) is None
        return {"data": [{"status": "crashed" if crashed else "completed", "log": CRASH_LOG if crashed else ""}]}


@pytest.fixture
def descriptive_statistics_results():
    """The stored results of the descriptive statistics algorithm (see tests/update_test_data.py)."""
    return load_descriptive_statistics_results()


@pytest.fixture
def cox_results():
    """The stored results of the Cox algorithm (see tests/update_test_data.py)."""
    return load_cox_results()


@pytest.fixture
def fake_client(descriptive_statistics_results, cox_results):
    return FakeClient(descriptive_statistics_results, cox_results)


@pytest.fixture(autouse=True)
def no_figure_windows(monkeypatch):
    """Close figures instead of showing them, so that tests do not keep figures in memory."""
    import matplotlib.pyplot as plt
    monkeypatch.setattr(plt, "show", lambda *args, **kwargs: None)
    yield
    plt.close("all")
