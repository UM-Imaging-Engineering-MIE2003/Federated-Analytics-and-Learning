# Organisation that runs the aggregation (central) task.
# This is intentionally defined here (and not in the notebook) so that
# users cannot accidentally change it while configuring their own runs.
# In the vantage6 developer network, organisation 1 is the organisation of the dev_admin user.
AGGREGATOR_ORGANISATION = 1

# The collaboration in which the tasks are created; the developer network has one collaboration
COLLABORATION_ID = 1

# The descriptive statistics algorithm of STRONG AYA (https://github.com/STRONGAYA/v6-descriptive-statistics);
# the '@sha256:...' part makes sure that always exactly the same version is used
DESCRIPTIVE_STATISTICS_ALGORITHM_IMAGE = "ghcr.io/strongaya/v6-descriptive-statistics@sha256:8c1340b0d2564b1d50e467c14e47ccc979d4c84ba9219b4bfce669083b557178"

# The federated Cox proportional hazards algorithm (https://github.com/MaastrichtU-CDS/v6-coxph, version 1.0.0)
COX_ALGORITHM_IMAGE = "ghcr.io/maastrichtu-cds/v6-coxph-standard-coxph@sha256:c3036a08b206dca23ee40aa0a8c1b5c1d9c19618dda743b2c38012f64d97f938"
