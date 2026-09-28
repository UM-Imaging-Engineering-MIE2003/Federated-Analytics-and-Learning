# Tests (for maintainers only)

> **Students: you do not need this folder.** These tests are not part of the course.
> They make sure that the course materials keep working over a longer time, for example when
> vantage6, the algorithm or one of the Python packages changes.

The tests run automatically on GitHub for every commit to `main` and every pull request,
and once a week (see `.github/workflows/tests.yml`).

## What is tested

| File | What it checks | Marker |
|---|---|---|
| `test_synthetic_data.py` | The survival data is reproducible, every node receives at least 250 records from one hospital, and the *intended* interoperability problem in `clin_t` (T stage) is still there | – |
| `test_utils.py` | The shared helpers in `src/utils.py` (checking the server, listing organisations, sending tasks) | – |
| `test_descriptive_statistics.py` | The descriptive statistics helpers in `src/descriptive_statistics.py` (collecting, reading, tabulating and plotting results, including the T-stage overview) | – |
| `test_cox.py` | The Cox model helpers in `src/cox.py`, including the answers to the two questions in the Cox notebook | – |
| `test_vantage_client.py` | Logging in with `src/vantage_client.py`, with and without MFA and encryption | – |
| `test_dev_network.py` | The commands that `dev_network.py` sends to the `v6` command line tool, and the random order of the hospitals | – |
| `test_notebooks.py` | Both notebooks are clean (no outputs, no TODOs), are valid, and point to each other | – |
| `test_descriptive_statistics_notebook.py` | The settings of the descriptive statistics notebook match the data, and it runs from top to bottom with a fake vantage6 client | – |
| `test_cox_notebook.py` | The Cox notebook runs with a fake vantage6 client: model A fails, students must change the list of organisations, and the notebook warns when the descriptive statistics were not run | – |
| `test_algorithm.py` | The real algorithms (run with the vantage6 mock client) still give the results in `tests/data/descriptive_statistics_results.json` and `tests/data/cox_results.json` | `algorithm` |
| `test_dev_network_e2e.py` | Both notebooks run, one after the other, against a real, running developer network | `devnetwork` |

## Running the tests

Standard tests (fast, no Docker needed):

```
pip install -r requirements.txt -r tests/requirements.txt
pytest
```

Algorithm tests. The algorithm pins an older `vantage6-algorithm-tools` version, so use a
**separate** environment:

```
pip install -r tests/requirements-algorithm.txt
pytest -m algorithm tests/test_algorithm.py
```

End-to-end test with the developer network (needs Docker, takes several minutes):

```
pip install -r requirements.txt -r tests/requirements.txt
python dev_network.py start
pytest -m devnetwork
python dev_network.py stop
```

## After changing the data or the notebook

If you change the synthetic data (`synthetic_datasets/generate_survival_data.py`),
`VARIABLES_TO_DESCRIBE` in the descriptive statistics notebook or the model variables in the Cox notebook:

1. Regenerate the data: `python synthetic_datasets/generate_survival_data.py`
2. Regenerate the stored algorithm results, in the algorithm environment:
   `python -m tests.update_test_data`
3. If you use a new version of an algorithm, update both the image in `src/__init__.py` and the
   commit in `tests/requirements-algorithm.txt`, so that they match.

## Known issues in the algorithms

- **Cox model (v6-coxph 1.0.0):** the `Z` and `p-value` columns are calculated as
  `(exp(coef) - 1) / SE` instead of `coef / SE`, so they are wrong. The notebook therefore only
  shows the hazard ratios and their 95 % confidence intervals, which are correct.
- **Descriptive statistics:** the `adjusted std` of the aggregate result includes outliers when
  inliers are given. The notebook does not use inliers and does not show this statistic.
- **Descriptive statistics:** the number `3` and the text `'3'` are counted as different groups.
  This happens for `clin_t`, because one organisation stores it as text. `src/utils.read_results`
  adds up groups with the same name.
