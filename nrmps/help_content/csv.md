---
title: CSV files
order: 5
summary: Uploading your own applicants or programs, and the files a run downloads.
seo_title: CSV files: uploading populations, downloading results
description: Upload your own applicants or programs as CSV files and download a run's population, match and applications: the file formats and their columns.
---

## Uploading a population

You can upload your own applicants or programs (or both) instead of generating them; runs then use the file. A run's
downloaded applicants or programs can be uploaded again unchanged. The whole file is checked first: if any row has a
problem, nothing changes and the problems are listed with their line and column.

With the default parameters the columns are:

- **Applicants:** `{{applicant_columns}}` ([sample file]({{applicant_sample}}))
- **Programs:** `{{program_columns}}` ([sample file]({{program_sample}}))

The rules:

- The first row names the columns. The attribute columns are the attributes in your parameters, so the simulation
  page lists the exact columns for your settings.
- `strength`, `quality` and the attributes are on the z-scale (0 = average). `capacity` is a whole number of
  positions (1 or more); program_size is computed from it, so it is not a column.
- `group` and `tier` are optional names made of lowercase letters, digits and underscores.
- The `weight:…` columns are optional; give all of them or none. Each row's weights are rescaled to add up to 1.
  Without them the model draws the weights when the run starts.
- Names must be unique within a file. Files may be up to {{max_upload_mb}} MB and {{max_upload_rows}} rows, in UTF-8
  (Excel's "CSV UTF-8" works).

Please use made-up or anonymised data only (see the [terms](/terms/)).

## A run's downloads

`match.csv`
: One row per applicant: group, strength, applications, signals, interviews, list length, the matched program, where
  the applicant ranked it, where the program ranked the applicant, and (with *Compare both sides proposing*) the
  program they would get if programs proposed.

`program_results.csv`
: One row per program: tier, quality, positions, applications and signals received, invitations, interviews, list
  length and positions filled.

`applications.csv`
: One row per application: the applicant's pre-interview rank of the program, reach/target/safety (portfolio
  strategy), the signal, the invitation wave, whether the interview took place, both sides' true utility,
  pre-interview view, realised utility and post-interview view, both list ranks, and whether it ended in the match.

`pairs.csv`
: Every applicant–program pair before interviews: both sides' true utility, pre-interview view and ranks (offered
  for markets small enough to recompute every pair).

`metrics.json` and `params.json`
: The run's diagnostics with its version stamps, and its parameters with the seed used.
