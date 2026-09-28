# Synthetic data (for tutors and maintainers)

`survival.csv` contains made-up/synthetic data of 1200 patients with head and neck cancer, 400 per hospital.
The columns follow the English example data of
[Flyover](https://github.com/MaastrichtU-CDS/Flyover/tree/main/example_data).
The file is created by `generate_survival_data.py`.

The vantage6 developer network splits every CSV file in this folder over the nodes in order, so the
rows are written per hospital (A, B, C). `dev_network.py` puts these blocks in a **random order** when
it creates the network: every network (so every student) gets the hospitals at different nodes, and
students cannot know in advance which organisation is different. The order stays the same until the
network is removed (`python dev_network.py remove`). The tests use the order of the file (A, B, C).

The hospitals differ on purpose, so that students can compare the partial results:

| Hospital | Main differences |
|---|---|
| A, general hospital | in between the other two; T stage `0` is hidden by the privacy threshold (also at hospital C) |
| B, university hospital | younger, more HPV-positive and oropharynx tumours |
| C, Dutch regional hospital | older, more advanced tumours, more unknown HPV status; **T stage with sub-stages** |

**Hospital C records the T stage (`clin_t`) with sub-stages (`1a`, `1b`, `2a`, `2b`, `2c`, `4a`, `4b`),
while the other hospitals only use the numbers `0` to `4`. This is an intended data interoperability
problem.** Students notice it in `run-descriptive-statistics.ipynb`. In `run-cox-ph.ipynb`, the Cox
model with the T stage fails at hospital C (the model needs numbers), and students choose between
leaving out the T stage or leaving out hospital C. Do not fix it in the data.

The T stage has no `x` (unknown) on purpose: otherwise the T stage of every hospital would be
text, and the Cox model could not use it at any hospital.
