---
title: About and citing
order: 8
summary: Versions, how to cite the simulator, and the source code.
seo_title: About the simulator and how to cite it
description: The versions of the residency Match simulator, how to cite it in research and reproduce a run, and its open-source code and licence.
---

NRMP Simulations is an independent educational and research simulator of the residency Match. It is not affiliated
with, sponsored or endorsed by the National Resident Matching Program® (NRMP®). Simulated outcomes are not
predictions of any real applicant's or program's match.

## Versions

This site runs model {{model_version}}, engine {{engine_version}} and app {{app_version}}. Every run stores the
versions it used (with the git commit, numpy and Python), and every download repeats them: a result can always be
traced to the code that produced it. A new model version means results can differ for the same parameters and seed.

## How to cite

Please cite the simulator with its version and the model version of your runs. The repository's `CITATION.cff`
file has the details; for example:

> Davis, V. NRMP Simulations (version {{app_version}}), model {{model_version}}. {{project_url}}

Report the parameters and seed of the runs you use (download them from each run), so others can reproduce them.

## Source code and licence

The code is open source under the MIT licence: [{{project_url}}]({{project_url}}). The model specification is
`docs/model_spec.md`, the implementation plan and status are in `docs/`, and issues and ideas are welcome.
