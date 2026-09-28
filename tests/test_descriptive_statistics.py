"""
Tests for the descriptive statistics helper functions in src/descriptive_statistics.py. Not meant for students.
"""
import inspect
import json

import matplotlib.pyplot as plt
import pytest

from src import DESCRIPTIVE_STATISTICS_ALGORITHM_IMAGE, COLLABORATION_ID
from src import descriptive_statistics


@pytest.fixture
def results(descriptive_statistics_results):
    return descriptive_statistics.read_results(descriptive_statistics_results)


def test_send_task(fake_client):
    task = descriptive_statistics.send_task(fake_client, organisations=[2], method="partial_general_statistics",
                           arguments={"variables_to_describe": {"age": {"datatype": "numerical"}}},
                           database_label="survival")
    created = fake_client.created_tasks[0]
    assert task["id"] == created["id"]
    assert created["organizations"] == [2]
    assert created["image"] == DESCRIPTIVE_STATISTICS_ALGORITHM_IMAGE
    assert created["collaboration"] == COLLABORATION_ID
    assert created["databases"] == [{"label": "survival"}]
    assert created["input_"] == {"method": "partial_general_statistics",
                                 "kwargs": {"variables_to_describe": {"age": {"datatype": "numerical"}}}}


def test_send_task_explains_when_the_server_refuses(fake_client):
    fake_client.task.create = lambda **kwargs: {"msg": "You lack the permission to do that!"}
    with pytest.raises(RuntimeError, match="permission"):
        descriptive_statistics.send_task(fake_client, [1], "central", {}, "survival")


def test_collect_results(fake_client, descriptive_statistics_results):
    partial_tasks = {organisation: descriptive_statistics.send_task(fake_client, [organisation], "partial_general_statistics",
                                                   {}, "survival") for organisation in (1, 2, 3)}
    central_task = descriptive_statistics.send_task(fake_client, [1], "central", {}, "survival")
    assert descriptive_statistics.collect_results(fake_client, partial_tasks, central_task) == descriptive_statistics_results


def test_read_results_keeps_the_order_of_the_sources(results):
    for table in results:
        assert list(table["source"].cat.categories) == [
            "Organisation 1", "Organisation 2", "Organisation 3", "Aggregate"]


def test_read_results_uses_the_same_statistic_names(results):
    numerical_results, _ = results
    statistics = set(numerical_results["statistic"])
    assert statistics == set(descriptive_statistics.STATISTICS_TO_SHOW)
    for source in numerical_results["source"].cat.categories:
        assert set(numerical_results.loc[numerical_results["source"] == source, "statistic"]) == statistics


def test_read_results_accepts_already_decoded_results(descriptive_statistics_results):
    decoded = {key: json.loads(value) for key, value in descriptive_statistics_results.items()}
    numerical_from_text, _ = descriptive_statistics.read_results(descriptive_statistics_results)
    numerical_from_dict, _ = descriptive_statistics.read_results(decoded)
    assert numerical_from_text.equals(numerical_from_dict)


def test_percentages_add_up_to_100(results):
    _, categorical_results = results
    totals = categorical_results.groupby(["source", "variable"], observed=True)["percentage"].sum()
    assert totals.between(99.5, 100.5).all()


def test_aggregate_counts_are_the_sum_of_the_partial_counts(results):
    _, categorical_results = results
    table = descriptive_statistics.make_table(categorical_results).fillna(0)
    organisations = [column for column in table.columns if column != descriptive_statistics.AGGREGATE_NAME]
    assert (table[organisations].sum(axis=1) == table[descriptive_statistics.AGGREGATE_NAME]).all()


def test_make_table_numerical(results):
    numerical_results, _ = results
    table = descriptive_statistics.make_table(numerical_results)
    assert list(table.columns) == ["Organisation 1", "Organisation 2", "Organisation 3", "Aggregate"]
    assert list(table.index.get_level_values("variable").unique()) == [
        "age_at_diagnosis", "overall_survival_in_days"]
    assert list(table.loc["age_at_diagnosis"].index) == descriptive_statistics.STATISTICS_TO_SHOW
    assert table.loc[("age_at_diagnosis", "count"), "Aggregate"] == 1200


def test_make_table_categorical_puts_missing_values_last(results):
    _, categorical_results = results
    table = descriptive_statistics.make_table(categorical_results)
    assert list(table.loc["performance_status_ecog"].index) == ["0", "1", "2", "3", "4", "na"]
    assert list(table.loc["overall_hpv_p16_status"].index) == ["negative", "positive", "na"]


def test_read_results_leaves_out_outliers(results):
    """The notebook does not use inliers, so the (always empty) outlier rows are not shown."""
    numerical_results, categorical_results = results
    assert "outliers" not in set(numerical_results["statistic"])
    assert descriptive_statistics.OUTLIER_GROUP not in set(categorical_results["value"])


def test_make_table_shows_hidden_groups_as_missing(results):
    _, categorical_results = results
    table = descriptive_statistics.make_table(categorical_results)
    assert table.loc[("clin_t", "0")].isna().sum() >= 1


def test_make_table_percentage(results):
    _, categorical_results = results
    table = descriptive_statistics.make_table(categorical_results, show="percentage")
    assert table.loc[("biological_sex", ["female", "male"]), "Organisation 1"].sum() == pytest.approx(100, abs=0.2)


@pytest.mark.parametrize("plot, table_index", [(descriptive_statistics.plot_numerical, 0), (descriptive_statistics.plot_categorical, 1)])
def test_plots(results, plot, table_index):
    plot(results[table_index])
    figure = plt.gcf()
    variables = results[table_index]["variable"].unique()
    titles = [axis.get_title() for axis in figure.axes]
    assert titles == list(variables)
    legend_texts = [text.get_text() for text in figure.legends[0].get_texts()]
    assert legend_texts == ["Organisation 1", "Organisation 2", "Organisation 3", "Aggregate"]


def test_palette_gives_the_aggregate_its_own_colour(results):
    palette = descriptive_statistics._get_palette(results[0])
    assert palette["Aggregate"] == descriptive_statistics.AGGREGATE_COLOUR
    assert len(set(palette.values())) == len(palette)


def test_fake_client_matches_the_real_client_interface(fake_client):
    """The FakeClient in conftest.py must use the same methods and arguments as the real vantage6 client."""
    UserClient = pytest.importorskip("vantage6.client").UserClient
    assert hasattr(UserClient, "wait_for_results") and hasattr(fake_client, "wait_for_results")
    assert "collaboration" in inspect.signature(UserClient.Organization.list).parameters
    # The arguments that src.descriptive_statistics.send_task passes to client.task.create
    descriptive_statistics.send_task(fake_client, [1], "central", {}, "survival")
    used_arguments = set(fake_client.created_tasks[0]) - {"id"}
    assert used_arguments <= set(inspect.signature(UserClient.Task.create).parameters)


def test_plot_groups_per_source_shows_the_different_t_stages(results):
    _, categorical_results = results
    descriptive_statistics.plot_groups_per_source(categorical_results, "clin_t")
    axis = plt.gcf().axes[0]
    rows = [label.get_text() for label in axis.get_yticklabels()]
    columns = [label.get_text() for label in axis.get_xticklabels()]
    assert rows == ["Organisation 1", "Organisation 2", "Organisation 3", "Aggregate"]
    assert {"1", "1a", "2", "2c", "4b"} <= set(columns)
