---
title: Questions
order: 7
summary: Common questions about runs, results and data.
---

## Why do two runs give the same results?

A simulation has a fixed seed, so runs repeat exactly until you change the seed or a parameter. Clear the seed to
draw a new one for every run; the run page shows the seed each run used.

## I changed a parameter, but some stages still say Done. Why?

Each stage depends only on some parameters. Changing the noise before interviews, for example, does not change the
applicants or programs, so the Population stage stays done, while the later stages become out of date. The pipeline
names what changed.

## Why did an applicant with interviews not match?

The match is stable, not generous: an applicant stays unmatched when every program on their list filled its positions
with applicants it ranked higher. Their page shows where each program ranked them.

## Why is the match rate not the share of all applicants who matched?

Like the NRMP, the simulator counts applicants who submitted a rank order list. Applicants without an interview have
no list; the run's pages report how many there were.

## Could an applicant have done better by ranking programs differently?

Not under applicant-proposing deferred acceptance: ranking programs in true order of preference is always best for
applicants. The [validation report]({{project_url}}/blob/main/docs/VALIDATION.md) checks this on random markets.

## How big can a market be?

Up to {{max_pairs}} applicant × program pairs per run on this site. A 10,000 × 1,000 market takes a few seconds.

## Can I use real applicant data?

Please don't: upload made-up or anonymised data only. Uploaded files are stored with your account, and you can
download or delete everything from your account page.

## How do I reproduce a run elsewhere?

Download its parameters (with the seed): the same parameters and seed give the same results with the same model
version. The population CSVs upload back unchanged, and `manage.py nrmp_run` runs the engine without the website.
