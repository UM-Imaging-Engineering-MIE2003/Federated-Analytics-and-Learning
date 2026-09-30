# Federated-Analytics-and-Learning
Materials for the Federated Learning topic

## Getting started
1. Install [Docker Desktop](https://www.docker.com/products/docker-desktop/) and make sure it is running.
   On Linux, your user must be in the `docker` group.
2. Create a Python environment with **Python 3.10** and install the packages. vantage6 4.15.1
   does not work with newer versions of Python, even though it installs without errors.
   ```
   python3.10 -m venv .venv         # Windows: py -3.10 -m venv .venv
   source .venv/bin/activate        # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```
   If you do not have Python 3.10, [uv](https://docs.astral.sh/uv/) can install it for you:
   replace the first line with `uv venv --python 3.10 --seed .venv`.
3. Start the vantage6 (version 4.15.1) developer network in a terminal:
   ```
   python dev_network.py start
   ```
4. Open the notebooks in this order, and run the cells from top to bottom:
   1. `run-descriptive-statistics.ipynb`: explore the data of the three hospitals;
   2. `run-cox-ph.ipynb`: study survival with a federated Cox model.
5. Stop the network when you have finished: `python dev_network.py stop`
   (or delete it completely with `python dev_network.py remove`).

Any CSV files that you put in `synthetic_datasets/` before the network is created for the
first time are added to the nodes as extra data sets; the file name is used as the label.

## For maintainers
The `tests` folder and the GitHub Actions workflow check that these materials keep working over
time. Students do not need them; see `tests/README.md`.
