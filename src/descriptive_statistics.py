"""
Helper functions for the descriptive statistics notebook (run-descriptive-statistics.ipynb).
"""
import json
from io import StringIO

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

from . import DESCRIPTIVE_STATISTICS_ALGORITHM_IMAGE
from . import utils

# The name of the tasks with the descriptive statistics algorithm
DESCRIPTIVE_STATISTICS_TASK_NAME = "Descriptive statistics retrieval"

# Fixed colours per organisation (in order) and for the aggregate result; checked for colour blindness
ORGANISATION_COLOURS = ["#2a78d6", "#eb6834", "#1baf7a"]
AGGREGATE_COLOUR = "#4a3aa7"
AGGREGATE_NAME = "Aggregate"

# The numerical statistics that are shown, in this order. The notebook does not use inliers, so the
# 'outliers' are left out; so is the 'adjusted std' of the aggregate result, to keep the tables simple.
STATISTICS_TO_SHOW = ["count", "na", "mean", "std", "q1", "median", "q3"]

# The row with missing values in the categorical results; it is shown after the real groups
MISSING_GROUP = "na"
# The row with outliers in the categorical results; it is left out because the notebook does not use inliers
OUTLIER_GROUP = "outliers"


def send_task(client, organisations, method, arguments, database_label):
    """
    Send a task with the descriptive statistics algorithm to one or more organisations.

    Args:
        client: An authenticated vantage6 client
        organisations: List of IDs of the organisations that should run the task
        method: The function of the algorithm to run, e.g. 'partial_general_statistics' or 'central'
        arguments: Dictionary with the input for that function, e.g. the variables to describe
        database_label: The label of the data set on the nodes

    Returns:
        A dictionary with the details of the created task, including its 'id'
    """
    return utils.send_task(client, organisations, method, arguments, database_label,
                           image=DESCRIPTIVE_STATISTICS_ALGORITHM_IMAGE, name=DESCRIPTIVE_STATISTICS_TASK_NAME)


def collect_results(client, partial_tasks, central_task):
    """
    Wait for the tasks to finish and collect their raw (JSON) results.

    Args:
        client: An authenticated vantage6 client
        partial_tasks: Dictionary with the organisation ID as key and the partial task as value
        central_task: The central (aggregating) task

    Returns:
        Dictionary with the organisation ID as key and the raw result as value;
        the aggregate result is stored under the key 'aggregate'
    """
    tasks = dict(partial_tasks)
    tasks["aggregate"] = central_task

    raw_results = {}
    for key, task in tasks.items():
        print(f"Waiting for the result of {_get_source_name(key)}")
        result = client.wait_for_results(task["id"])
        raw_results[key] = result["data"][0]["result"]
    print("All results have arrived.")
    return raw_results


def _get_source_name(key):
    """Give each result a readable name, for example, 'Organisation 1' or 'Aggregate'."""
    return AGGREGATE_NAME if key == "aggregate" else f"Organisation {key}"


def read_results(raw_results):
    """
    Read the raw results into two tables (pandas DataFrames): one for numerical and one for
    categorical variables. The column 'source' shows where each row comes from.

    The partial results and the aggregate result do not use exactly the same names
    (e.g. 'Q2' versus 'median'); this function makes them the same so that they can be compared.

    Args:
        raw_results: Dictionary as returned by collect_results

    Returns:
        A tuple with the numerical results and the categorical results
    """
    numerical_tables = []
    categorical_tables = []
    for key, raw_result in raw_results.items():
        # The result is a JSON text; each value inside it is again a table in JSON format
        result = json.loads(raw_result) if isinstance(raw_result, str) else raw_result
        for table_name, table_json in result.items():
            table = pd.read_json(StringIO(table_json))
            table.insert(0, "source", _get_source_name(key))
            if table_name.startswith("numerical"):
                numerical_tables.append(table)
            elif table_name.startswith("categorical"):
                categorical_tables.append(table)

    # Keep the order of the sources: the organisations first and the aggregate result last
    sources = [_get_source_name(key) for key in raw_results]

    numerical_results = pd.concat(numerical_tables, ignore_index=True)
    numerical_results["source"] = pd.Categorical(numerical_results["source"], categories=sources)
    numerical_results["statistic"] = numerical_results["statistic"].str.lower().replace({"q2": "median"})
    numerical_results = numerical_results[numerical_results["statistic"].isin(STATISTICS_TO_SHOW)].copy()
    numerical_results["statistic"] = pd.Categorical(numerical_results["statistic"],
                                                    categories=STATISTICS_TO_SHOW, ordered=True)

    categorical_results = pd.concat(categorical_tables, ignore_index=True)
    # Groups can be numbers (e.g. a stage); use text so that all groups are treated the same way
    categorical_results["value"] = categorical_results["value"].astype(str)
    categorical_results = categorical_results[categorical_results["value"] != OUTLIER_GROUP]
    # The algorithm sees the number 3 and the text '3' as different groups (this happens when one
    # organisation stores a column as text); add up groups that have the same name
    categorical_results = categorical_results.groupby(["source", "variable", "value"], as_index=False,
                                                      observed=True, sort=False)["count"].sum()
    categorical_results["source"] = pd.Categorical(categorical_results["source"], categories=sources)
    # The percentage of records in each group, so that sources of different sizes can be compared
    categorical_results["percentage"] = (categorical_results["count"]
                                         / categorical_results.groupby(["source", "variable"], observed=True)[
                                             "count"].transform("sum")
                                         * 100).round(1)

    return numerical_results, categorical_results


def make_table(results, show="count"):
    """
    Make a readable table with one column per source.

    Args:
        results: The numerical or categorical results from read_results
        show: For categorical results only; show the 'count' or the 'percentage' per group

    Returns:
        A pandas DataFrame with the variables as rows and the sources as columns
    """
    # Keep the variables in the order in which they were described
    order_of_variables = {name: order for order, name in enumerate(results["variable"].unique())}
    results = results.assign(variable_order=results["variable"].map(order_of_variables))

    if "statistic" in results.columns:
        index, values = ["variable", "statistic"], "value"
        results = results.sort_values(["variable_order", "statistic"])
    else:
        index, values = ["variable", "value"], show
        # Show the groups in alphabetical order, followed by the missing values
        results = results.assign(is_missing=results["value"] == MISSING_GROUP)
        results = results.sort_values(["variable_order", "is_missing", "value"])

    table = results.pivot_table(index=index, columns="source", values=values, observed=True).round(2)
    # Put the rows in the order that was determined above
    row_order = pd.MultiIndex.from_frame(results[index].astype(str).drop_duplicates())
    return table.reindex(row_order)


def _get_palette(results):
    """Give each source a fixed colour, with the aggregate result always in the same colour."""
    organisations = [source for source in results["source"].cat.categories if source != AGGREGATE_NAME]
    palette = dict(zip(organisations, ORGANISATION_COLOURS))
    palette[AGGREGATE_NAME] = AGGREGATE_COLOUR
    return palette


def plot_numerical(numerical_results, statistics=("mean", "median")):
    """
    Plot a bar chart per numerical variable that compares the sources.

    Args:
        numerical_results: The numerical results from read_results
        statistics: The statistics to show
    """
    data = numerical_results[numerical_results["statistic"].isin(statistics)].copy()
    data["statistic"] = data["statistic"].astype(str).str.capitalize()
    sns.set_theme(style="whitegrid")
    figure = sns.catplot(data=data, kind="bar", x="statistic", y="value",
                         hue="source", palette=_get_palette(numerical_results),
                         col="variable", col_wrap=3, sharey=False, height=3.5, aspect=1.0)
    figure.set_axis_labels("", "Value")
    figure.set_titles("{col_name}")
    figure.legend.set_title("Result from")
    plt.show()


def plot_categorical(categorical_results):
    """
    Plot a bar chart per categorical variable with the percentage of records in each group.
    Missing values ('na') are left out of the figure.

    Args:
        categorical_results: The categorical results from read_results
    """
    data = categorical_results[categorical_results["value"] != MISSING_GROUP].sort_values("value")
    sns.set_theme(style="whitegrid")
    figure = sns.catplot(data=data, kind="bar", x="value", y="percentage",
                         hue="source", palette=_get_palette(categorical_results),
                         col="variable", col_order=categorical_results["variable"].unique(),
                         col_wrap=2, sharex=False, height=3.5, aspect=1.3)
    figure.set_axis_labels("", "Percentage of records (%)")
    figure.set_titles("{col_name}")
    figure.tick_params(axis="x", rotation=30)
    figure.tight_layout()
    figure.legend.set_title("Result from")
    plt.show()


def plot_groups_per_source(categorical_results, variable):
    """
    Show which groups of one categorical variable each source uses, as a grid with one row per
    source and one column per group. The number in a cell is the percentage of records in that group;
    an empty cell means that the source does not use (or does not share) that group.

    This makes it easy to see when organisations record the same variable in different ways.

    Args:
        categorical_results: The categorical results from read_results
        variable: The name of the categorical variable, e.g. 'clin_t'
    """
    data = categorical_results[(categorical_results["variable"] == variable)
                               & (categorical_results["value"] != MISSING_GROUP)]
    grid = data.pivot_table(index="source", columns="value", values="percentage", observed=True)
    grid = grid.reindex(index=data["source"].cat.categories, columns=sorted(grid.columns))

    sns.set_theme(style="white")
    figure, axis = plt.subplots(figsize=(1.0 + 0.8 * len(grid.columns), 1.0 + 0.6 * len(grid.index)))
    sns.heatmap(grid, annot=True, fmt=".0f", cmap="Blues", vmin=0, cbar=False,
                linewidths=2, linecolor="white", ax=axis)
    # Show empty cells in light grey so that they are easy to spot
    axis.set_facecolor("#e8e8e6")
    axis.set_title(f"Groups of {variable} per source (percentage of records)")
    axis.set_xlabel("Group")
    axis.set_ylabel("")
    axis.tick_params(axis="y", rotation=0)
    plt.show()
