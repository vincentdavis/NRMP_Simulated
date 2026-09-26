---
title: Help
order: 0
summary: What the simulator does, a quick start, and where to read more.
---

NRMP Simulations models the residency Match: applicants and residency programs with preferences and imperfect
information go through applications, preference signals, interview invitations, interviews and rank order lists to
the match, computed with the same kind of algorithm the NRMP uses. You set the assumptions; the simulator shows what
follows from them. It is an independent educational and research tool, not affiliated with the National Resident
Matching Program, and its results are not predictions of any real applicant's or program's match.

## Quick start

1. Create an account and open **Simulations**, then **New simulation**. Pick a preset to start from; the default is
   an NRMP-like market of {{default_applicants}} applicants for {{default_positions}} positions in
   {{default_programs}} programs. Every simulation gets its own random seed.
2. Press **Run**. The run generates the applicants and programs, their true preferences and their noisy views of
   each other, then runs every stage: applications, signals, interview invitations, interviews, rank order lists and
   the match.
3. Open the run. Its tabs show the summary, the population, the views before interviews, the applications and
   interviews (every application, with filters), the match, and the applicants and programs; any one applicant's or
   program's page follows it through the stages.
4. Change a parameter, press **Save and run**, and compare. While you edit, the panel beside the form shows what the
   parameters give, and the pipeline at the top of the page says which stages a saved change makes out of date.

A run is reproducible: the same parameters and seed always give exactly the same results, and changing one parameter
changes only what depends on it. With a blank seed every run draws a new one (the run page shows which). Every page
has a **Help** button, and "?" buttons explain columns and actions.

## The guide

- [How the Match works](/help/nrmp/): the real process the simulator follows.
- [The simulation model](/help/model/): every stage, with its formulas and a worked example.
- [Reading the results](/help/results/): what each number, table and chart on a run's pages means.
- [Parameter reference](/help/parameters/): every parameter, its range and default.
- [CSV files](/help/csv/): uploading your own applicants or programs, and the downloads.
- [Glossary](/help/glossary/) and [questions](/help/faq/).
- [About and citing](/help/about/): versions, how to cite, the source code.

## Current limitations

- A run is one draw of the random stages. Replicates, with averages and uncertainty bands, are planned; their
  parameters are in the form, marked "Not used yet".
- Couples, supplemental (PGY-1 and advanced) lists, interview date conflicts and SOAP (the process after the Match
  for unfilled positions) are not modelled.
- Markets are limited to {{max_pairs}} applicant × program pairs per run. Accounts also have daily limits on runs
  and pairs.
- Results are simulations under the assumptions you set. They are not predictions of any real applicant's or
  program's match.

## Getting help

Questions, bug reports and ideas: see the [contact page](/contact/), or open an issue in the
[project repository]({{project_url}}).
