"""
Helper functions for the Cox model notebook (run-cox-ph.ipynb).
"""
import json
from io import StringIO

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.ticker import FixedLocator, FuncFormatter, NullLocator
import seaborn as sns

from . import AGGREGATOR_ORGANISATION, COX_ALGORITHM_IMAGE
from .descriptive_statistics import DESCRIPTIVE_STATISTICS_TASK_NAME
from .utils import send_task

# Fixed colours for the models (in the order in which they were calculated); checked for colour blindness
MODEL_COLOURS = ["#2a78d6", "#eb6834", "#1baf7a", "#4a3aa7"]


def check_descriptive_statistics_done(client):
    """
    Check that the descriptive statistics notebook has been run on this server, and print a warning if not.

    Args:
        client: An authenticated vantage6 client
    """
    tasks = client.task.list(name=DESCRIPTIVE_STATISTICS_TASK_NAME)["data"]
    if tasks:
        print("Good: you have already explored the data with the descriptive statistics notebook.")
    else:
        print("WARNING: you have not run the descriptive statistics notebook yet.\n"
              "Please do that first (run-descriptive-statistics.ipynb). "
              "You will need what you learn there to finish this notebook.")


def run_cox_model(client, organisations, variables, database_label,
                  time_column="overall_survival_in_days", event_column="event_overall_survival"):
    """
    Calculate a Cox model with the data of the selected organisations, and wait for the result.

    Args:
        client: An authenticated vantage6 client
        organisations: List of IDs of the organisations whose data is used
        variables: List of the variables (columns) in the model; they must be numbers
        database_label: The label of the data set on the nodes
        time_column: The column with the follow-up time
        event_column: The column that shows whether the event (death) happened: 1 (yes) or 0 (no)

    Returns:
        A dictionary with the result of the model, or None if the model could not be calculated
    """
    task = send_task(
        client,
        organisations=[AGGREGATOR_ORGANISATION],
        method="central",
        arguments={"time_col": time_column,
                   "outcome_col": event_column,
                   "expl_vars": list(variables),
                   "organization_ids": list(organisations)},
        database_label=database_label,
        image=COX_ALGORITHM_IMAGE,
        name="Cox model",
    )
    result = client.wait_for_results(task["id"])["data"][0]["result"]

    # The status and the log of the run show whether (and why) the algorithm failed
    run = client.run.from_task(task["id"])["data"][0]
    if run["status"] != "completed" or not result:
        _explain_failure(run)
        return None

    result = json.loads(result) if isinstance(result, str) else result
    result["variables"] = list(variables)
    result["organisations"] = list(organisations)
    print("The model is ready.")
    return result


def _explain_failure(run):
    """Print a short explanation of why the model could not be calculated."""
    log_lines = [line.strip() for line in (run.get("log") or "").splitlines() if line.strip()]
    error_lines = [line for line in log_lines if "Error" in line and not line.startswith("File")]
    last_error = error_lines[-1] if error_lines else "(no error message found)"

    print(f"The model could not be calculated (status: {run['status']}).")
    print(f"The last error message is:\n    {last_error}\n")
    if "str" in last_error:
        print("This usually means that a variable contains text (for example '2b') where the model\n"
              "expects a number. Do all organisations record the variables in the model in the same way?\n"
              "Go back to the descriptive statistics notebook and look at the variables in your model.")


def read_hazard_ratios(result):
    """
    Read the hazard ratios and their 95 % confidence intervals from the result of a model.

    Returns:
        A pandas DataFrame with one row per variable
    """
    model = pd.read_json(StringIO(result["model"]))
    return pd.DataFrame({
        "variable": model.index,
        "hazard ratio": model["Exp(coef)"].values,
        "lowest (95 % CI)": model["lower_CI"].values,
        "highest (95 % CI)": model["upper_CI"].values,
    })


def compare_models(models):
    """
    Make a table that compares models: which organisations and variables they use, and their AIC.

    Args:
        models: Dictionary with a name for each model as key and the result of run_cox_model as value

    Returns:
        A pandas DataFrame with one row per model
    """
    rows = []
    for name, result in models.items():
        if result is None:
            continue
        rows.append({
            "model": name,
            "organisations": ", ".join(str(organisation) for organisation in result["organisations"]),
            "number of variables": len(result["variables"]),
            "T stage in model": "yes" if "clin_t" in result["variables"] else "no",
            "AIC": round(result["aic"], 1),
        })
    return pd.DataFrame(rows).set_index("model")


def show_hazard_ratios(models):
    """
    Make a table with the hazard ratio and its 95 % confidence interval for each variable and model.

    Args:
        models: Dictionary with a name for each model as key and the result of run_cox_model as value

    Returns:
        A pandas DataFrame with one row per variable and one column per model
    """
    columns = {}
    variables = []
    for name, result in models.items():
        if result is None:
            continue
        ratios = read_hazard_ratios(result).set_index("variable")
        variables += [variable for variable in ratios.index if variable not in variables]
        columns[name] = pd.Series(
            [f"{row['hazard ratio']:.2f} ({row['lowest (95 % CI)']:.2f} to {row['highest (95 % CI)']:.2f})"
             for _, row in ratios.iterrows()],
            index=ratios.index)
    # Keep the variables in the order of the models
    return pd.DataFrame(columns).reindex(variables).fillna("not in model")


def plot_hazard_ratios(models):
    """
    Plot the hazard ratio (dot) and its 95 % confidence interval (line) for each variable and model.

    Args:
        models: Dictionary with a name for each model as key and the result of run_cox_model as value
    """
    names = [name for name, result in models.items() if result is not None]
    variables = list(dict.fromkeys(variable for name in names for variable in models[name]["variables"]))

    sns.set_theme(style="whitegrid")
    figure, axis = plt.subplots(figsize=(8, 1.0 + 0.9 * len(variables)))
    # Put the models slightly above each other so that their lines do not overlap
    offsets = [(index - (len(names) - 1) / 2) * 0.18 for index in range(len(names))]
    for name, offset, colour in zip(names, offsets, MODEL_COLOURS):
        ratios = read_hazard_ratios(models[name])
        positions = [variables.index(variable) + offset for variable in ratios["variable"]]
        axis.hlines(positions, ratios["lowest (95 % CI)"], ratios["highest (95 % CI)"], color=colour, linewidth=2)
        axis.plot(ratios["hazard ratio"], positions, "o", color=colour, markersize=8, label=name)

    axis.axvline(1, color="#52514e", linewidth=1, linestyle="--")
    # A log scale shows 'half the risk' and 'twice the risk' at the same distance from 1
    axis.set_xscale("log")
    lowest, highest = axis.get_xlim()
    axis.set_xlim(min(lowest, 0.8), max(highest, 1.25))
    ticks = [tick for tick in [0.25, 0.5, 0.8, 1, 1.25, 1.5, 2, 3, 4, 6, 8, 10, 15, 20]
             if axis.get_xlim()[0] <= tick <= axis.get_xlim()[1]]
    axis.xaxis.set_major_locator(FixedLocator(ticks))
    axis.xaxis.set_minor_locator(NullLocator())
    axis.xaxis.set_major_formatter(FuncFormatter(lambda value, position: f"{value:g}"))
    axis.set_yticks(range(len(variables)), variables)
    axis.invert_yaxis()
    axis.set_xlabel("Hazard ratio (log scale); left of the dashed line: lower risk, right: higher risk")
    axis.set_title("Hazard ratios with 95 % confidence intervals")
    axis.legend(title="Model", loc="upper left", bbox_to_anchor=(1.02, 1), frameon=False)
    plt.show()
