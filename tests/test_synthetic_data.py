"""
Tests for the synthetic survival data. Not meant for students.
"""
import pandas as pd
import pytest

import dev_network
from synthetic_datasets import generate_survival_data
from tests.helpers import SURVIVAL_DATA_PATH, get_notebook_setting, split_like_dev_network

# The T stages that each hospital (A, B, C, in the order of the file) uses. Hospital C uses sub-stages on purpose:
# students solve this interoperability problem in the next notebook (run-cox-ph).
# There is no 'x' (unknown), so that the Cox model can use the T stage of nodes 1 and 2 as a number.
SIMPLE_T_STAGES = {"0", "1", "2", "3", "4"}
EXPECTED_T_STAGES = [SIMPLE_T_STAGES, SIMPLE_T_STAGES,
                     {"0", "1a", "1b", "2a", "2b", "2c", "3", "4a", "4b"}]

SAMPLE_SIZE_THRESHOLD = 10


@pytest.fixture(scope="module")
def data():
    return pd.read_csv(SURVIVAL_DATA_PATH, dtype=str, keep_default_na=False, na_values=[""])


@pytest.fixture(scope="module")
def nodes(data):
    return split_like_dev_network(data, dev_network.NUMBER_OF_NODES)


def test_stored_data_matches_generator(tmp_path):
    """The stored CSV must be exactly what the generator produces (regenerate it after changes)."""
    generated_file = tmp_path / "survival.csv"
    generate_survival_data.generate_data().to_csv(generated_file, index=False)
    assert generated_file.read_text() == SURVIVAL_DATA_PATH.read_text(), \
        "Run 'python synthetic_datasets/generate_survival_data.py' to update survival.csv"


def test_one_hospital_per_node():
    assert len(generate_survival_data.HOSPITALS) == dev_network.NUMBER_OF_NODES


def test_every_node_has_enough_records(nodes):
    for node in nodes:
        assert len(node) >= dev_network.MINIMUM_RECORDS_PER_NODE


def test_every_node_receives_exactly_one_hospital(nodes):
    prefixes = [set(node["id"].str[0]) for node in nodes]
    assert all(len(prefix) == 1 for prefix in prefixes)
    assert len(set.union(*prefixes)) == dev_network.NUMBER_OF_NODES


def test_patient_ids_are_unique(data):
    assert data["id"].is_unique


def test_columns_follow_flyover_example_data(data):
    assert list(data.columns) == [
        "id", "biological_sex", "age_at_diagnosis", "performance_status_ecog", "overall_hpv_p16_status",
        "index_tumour_location", "clin_t", "clin_n", "clin_m", "event_overall_survival",
        "overall_survival_in_days",
    ]


def test_intended_interoperability_problem_in_t_stage(nodes):
    """Hospital C must record the T stage with sub-stages; the other hospitals must not."""
    for node, expected_t_stages in zip(nodes, EXPECTED_T_STAGES):
        assert set(node["clin_t"]) == expected_t_stages


def test_other_categorical_variables_use_the_same_labels_at_every_node(nodes):
    for column in ["biological_sex", "index_tumour_location", "overall_hpv_p16_status", "clin_m",
                   "event_overall_survival"]:
        labels = [set(node[column].dropna()) for node in nodes]
        assert all(node_labels == labels[0] for node_labels in labels), column


def test_every_node_has_deaths_and_survivors(nodes):
    for node in nodes:
        assert node["event_overall_survival"].value_counts().min() >= SAMPLE_SIZE_THRESHOLD


def test_ages_are_realistic(data):
    """The notebook does not filter values, so the data must not contain impossible ages."""
    ages = data["age_at_diagnosis"].astype(int)
    assert ages.between(generate_survival_data.AGE_MINIMUM, generate_survival_data.AGE_MAXIMUM).all()


def test_survival_times_are_realistic(data):
    days = data["overall_survival_in_days"].astype(int)
    assert days.min() >= 0
    assert days.max() <= generate_survival_data.MAXIMUM_FOLLOW_UP


def test_privacy_threshold_hides_only_the_intended_group(nodes):
    """
    Only T stage '0' should be below the sample size threshold (at some nodes), to show students
    how the threshold works. No other group should be hidden.
    """
    categorical_variables = [name for name, details in get_notebook_setting("VARIABLES_TO_DESCRIBE").items()
                             if details["datatype"] == "categorical"]
    small_groups = set()
    for node in nodes:
        for variable in categorical_variables:
            counts = node[variable].dropna().value_counts()
            small_groups.update((variable, group) for group in counts[counts < SAMPLE_SIZE_THRESHOLD].index)
    assert small_groups == {("clin_t", "0")}
