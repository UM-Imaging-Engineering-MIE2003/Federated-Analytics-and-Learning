"""
Create the synthetic survival data set used in the course.

The data describes patients with head and neck cancer who were treated at three
(made-up) hospitals. None of the records belongs to a real person. The columns follow
the English example data of Flyover:
https://github.com/MaastrichtU-CDS/Flyover/tree/main/example_data

The vantage6 developer network divides every CSV file over the nodes in order:
node 1 receives the first third of the rows, node 2 the second third, and so on.
The rows are therefore written per hospital (A, B, C), so that each node receives the
patients of exactly one hospital. dev_network.py puts the hospitals in a random order
before it creates the network, so each network gives the hospitals to different nodes.
Keep NUMBER_OF_NODES in dev_network.py equal to the number of hospitals below.

On purpose, hospital C records the T stage ('clin_t') in more detail than the
other hospitals: it uses sub-stages such as '1a', '1b' and '2c' instead of '1' and '2'.
This data interoperability problem is solved by the students in the next notebook
(run-cox-ph); do not fix it here.

Run this script from the main folder of the course:

    python synthetic_datasets/generate_survival_data.py
"""
from pathlib import Path

import numpy as np
import pandas as pd

# Fixed seed, so that everyone gets exactly the same data
RANDOM_SEED = 2026

# The number of patients per hospital; every node should receive at least 250 records
PATIENTS_PER_HOSPITAL = 400

OUTPUT_FILE = Path(__file__).parent / "survival.csv"

ECOG_STATUSES = [0, 1, 2, 3, 4]
HPV_STATUSES = ["positive", "negative"]
TUMOUR_LOCATIONS = ["oropharynx", "larynx", "hypopharynx"]
# No 'x' (unknown) for the T stage: the Cox model needs the T stage as a number at every hospital
T_STAGES = ["0", "1", "2", "3", "4"]
N_STAGES = ["0", "1", "2", "3", "x"]

# Every hospital treats a different group of patients
HOSPITALS = [
    {
        # Hospital A: a general hospital
        "id_prefix": "A",
        "age_mean": 64, "age_sd": 8,
        "female_fraction": 0.30,
        "ecog_probabilities": [0.25, 0.35, 0.22, 0.12, 0.06],
        "hpv_probabilities": [0.35, 0.55], "missing_hpv_fraction": 0.10,
        "location_probabilities": [0.45, 0.40, 0.15],
        # Stage '0' is rare on purpose: it is hidden by the privacy threshold of the algorithm
        "t_stage_probabilities": [0.02, 0.21, 0.34, 0.28, 0.15],
        "n_stage_probabilities": [0.30, 0.30, 0.25, 0.12, 0.03],
        "metastasis_fraction": 0.08,
    },
    {
        # Hospital B: a university hospital with more HPV-positive (better prognosis) patients
        "id_prefix": "B",
        "age_mean": 57, "age_sd": 7,
        "female_fraction": 0.35,
        "ecog_probabilities": [0.40, 0.35, 0.15, 0.07, 0.03],
        "hpv_probabilities": [0.65, 0.30], "missing_hpv_fraction": 0.05,
        "location_probabilities": [0.70, 0.20, 0.10],
        "t_stage_probabilities": [0.03, 0.31, 0.36, 0.20, 0.10],
        "n_stage_probabilities": [0.25, 0.40, 0.25, 0.08, 0.02],
        "metastasis_fraction": 0.05,
    },
    {
        # Hospital C: a Dutch regional hospital with older patients and more advanced tumours
        "id_prefix": "C",
        "age_mean": 67, "age_sd": 9,
        "female_fraction": 0.30,
        "ecog_probabilities": [0.15, 0.30, 0.25, 0.20, 0.10],
        "hpv_probabilities": [0.25, 0.50], "missing_hpv_fraction": 0.25,
        "location_probabilities": [0.35, 0.40, 0.25],
        "t_stage_probabilities": [0.02, 0.11, 0.26, 0.34, 0.27],
        "n_stage_probabilities": [0.20, 0.25, 0.30, 0.20, 0.05],
        "metastasis_fraction": 0.15,
        # This hospital records sub-stages of the T stage (the interoperability problem, see above)
        "t_sub_stages": {"1": ["1a", "1b"], "2": ["2a", "2b", "2c"], "4": ["4a", "4b"]},
    },
]

# The lowest and highest realistic age at diagnosis
AGE_MINIMUM = 18
AGE_MAXIMUM = 95

# Risk of dying per day, and how the patient characteristics change that risk
DAILY_RISK = 0.0002
T_STAGE_EFFECT = {"0": 0.5, "1": 0.6, "2": 1.0, "3": 1.8, "4": 3.0}
HPV_EFFECT = {"positive": 0.5, "negative": 1.2, None: 1.0}
ECOG_EFFECT = 1.3
METASTASIS_EFFECT = 3.0

# The shortest and longest follow-up in days (half a year and five years)
MINIMUM_FOLLOW_UP = 180
MAXIMUM_FOLLOW_UP = 1826


def generate_hospital(hospital: dict, number_of_patients: int, generator: np.random.Generator) -> pd.DataFrame:
    """Generate the patients of one hospital."""
    age = generator.normal(hospital["age_mean"], hospital["age_sd"], number_of_patients)
    age = np.clip(np.round(age), AGE_MINIMUM, AGE_MAXIMUM).astype(int)

    sex = np.where(generator.random(number_of_patients) < hospital["female_fraction"], "female", "male")
    ecog = generator.choice(ECOG_STATUSES, number_of_patients, p=hospital["ecog_probabilities"])
    location = generator.choice(TUMOUR_LOCATIONS, number_of_patients, p=hospital["location_probabilities"])
    t_stage = generator.choice(T_STAGES, number_of_patients, p=hospital["t_stage_probabilities"])
    n_stage = generator.choice(N_STAGES, number_of_patients, p=hospital["n_stage_probabilities"])
    m_stage = (generator.random(number_of_patients) < hospital["metastasis_fraction"]).astype(int)

    # The HPV status is not known for some patients
    hpv_probabilities = np.array(hospital["hpv_probabilities"] + [hospital["missing_hpv_fraction"]])
    hpv = generator.choice(HPV_STATUSES + [None], number_of_patients, p=hpv_probabilities / hpv_probabilities.sum())

    # Time until death, based on the patient characteristics
    daily_risk = np.array([
        DAILY_RISK * T_STAGE_EFFECT[t] * HPV_EFFECT[h] * ECOG_EFFECT ** e * (METASTASIS_EFFECT if m else 1.0)
        for t, h, e, m in zip(t_stage, hpv, ecog, m_stage)
    ])
    time_to_death = generator.exponential(1 / daily_risk)

    # Patients were diagnosed at different moments, so the follow-up time differs per patient
    time_to_end_of_follow_up = generator.uniform(MINIMUM_FOLLOW_UP, MAXIMUM_FOLLOW_UP, number_of_patients)

    died = time_to_death <= time_to_end_of_follow_up

    # Write the T stage as this hospital records it; sub-stages are chosen at random
    sub_stages = hospital.get("t_sub_stages", {})
    recorded_t_stage = [generator.choice(sub_stages[t]) if t in sub_stages else t for t in t_stage]
    survival_days = np.round(np.minimum(time_to_death, time_to_end_of_follow_up)).astype(int)

    data = pd.DataFrame({
        "id": [f"{hospital['id_prefix']}{number:04d}" for number in range(1, number_of_patients + 1)],
        "biological_sex": sex,
        "age_at_diagnosis": age,
        "performance_status_ecog": ecog,
        "overall_hpv_p16_status": hpv,
        "index_tumour_location": location,
        "clin_t": recorded_t_stage,
        "clin_n": n_stage,
        "clin_m": m_stage,
        "event_overall_survival": died.astype(int),
        "overall_survival_in_days": survival_days,
    })

    # Shuffle the rows within the hospital
    return data.sample(frac=1, random_state=int(generator.integers(1_000_000))).reset_index(drop=True)


def generate_data(patients_per_hospital: int = PATIENTS_PER_HOSPITAL, seed: int = RANDOM_SEED) -> pd.DataFrame:
    """Generate the data of all hospitals, written one hospital after the other."""
    generator = np.random.default_rng(seed)
    hospitals = [generate_hospital(hospital, patients_per_hospital, generator) for hospital in HOSPITALS]
    return pd.concat(hospitals, ignore_index=True)


def main() -> None:
    data = generate_data()
    data.to_csv(OUTPUT_FILE, index=False)
    print(f"Saved {len(data)} records ({PATIENTS_PER_HOSPITAL} per hospital) to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
