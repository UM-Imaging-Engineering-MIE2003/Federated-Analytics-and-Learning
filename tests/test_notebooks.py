"""
Tests that apply to both course notebooks. Not meant for students.
"""
import nbformat
import pytest

from tests.helpers import COX_NOTEBOOK_PATH, DESCRIPTIVE_STATISTICS_NOTEBOOK_PATH, get_code_cells, read_notebook

ALL_NOTEBOOKS = pytest.mark.parametrize("path", [DESCRIPTIVE_STATISTICS_NOTEBOOK_PATH, COX_NOTEBOOK_PATH],
                                       ids=lambda path: path.stem)


@ALL_NOTEBOOKS
def test_notebook_is_valid(path):
    nbformat.validate(nbformat.read(path, as_version=4))


@ALL_NOTEBOOKS
def test_notebook_is_stored_without_outputs(path):
    """Students should start with a clean notebook."""
    for cell in read_notebook(path)["cells"]:
        if cell["cell_type"] == "code":
            assert cell["outputs"] == [] and cell["execution_count"] is None


@ALL_NOTEBOOKS
def test_notebook_has_no_todos(path):
    for cell in read_notebook(path)["cells"]:
        assert "TODO" not in "".join(cell["source"])


@ALL_NOTEBOOKS
def test_every_code_cell_is_valid_python(path):
    for source in get_code_cells(path):
        compile(source, "<notebook cell>", "exec")


def test_notebooks_point_to_each_other():
    """Students must do the descriptive statistics notebook first, and then continue with the Cox notebook."""
    descriptive_text = DESCRIPTIVE_STATISTICS_NOTEBOOK_PATH.read_text(encoding="utf-8")
    cox_text = COX_NOTEBOOK_PATH.read_text(encoding="utf-8")
    assert COX_NOTEBOOK_PATH.name in descriptive_text
    assert DESCRIPTIVE_STATISTICS_NOTEBOOK_PATH.name in cox_text
