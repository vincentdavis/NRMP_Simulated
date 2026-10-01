---
title: Reading the results
order: 3
summary: What each number, table and chart on a run's pages means.
---

A run's pages are tabs: Summary, Population, Before interviews, Applications and interviews, Match, Applicants and
Programs. Each tab opens with its key numbers, and "?" buttons explain the columns of every table.

## Summary

The run's key numbers, whether its checks passed, who got an interview and a match (the applicants' flow from the
Applications and interviews tab, with **Colour by strength** on unless you turned it off), the downloads, how long
each stage took, the version stamps and the exact parameters (with the seed) the run used, so it can be repeated.

On sites where a background worker computes runs, a run first waits in a queue. Its population is built as soon as
you press **Run** (so a market that is too large, or an upload that does not fit, is reported at once) and the other
stages follow when the worker picks the run up. Meanwhile the summary shows which stages have finished and which are
waiting, how many runs are ahead of it, and a warning if no worker is running or the run has waited unusually long.

## Population

The applicants and programs as generated, next to what the parameters asked for: group shares and strength, tier
shares and quality, how closely each attribute follows strength or quality, and the average weights. In the
histograms of strength and quality, the line is the distribution the parameters ask for; the bars should follow it,
and the text under each chart gives the largest deviation in standard errors (more than 4 would point to a problem).

## Before interviews

Agreement
: The average correlation between two agents' true utilities; it should be close to the agreement you set.

Fidelity
: How well the pre-interview view matches the truth, over all pairs (the correlation of true and observed utility)
  and per agent (the rank correlation of its true and pre-interview orderings).

First choices
: How concentrated the pre-interview first choices are: with high agreement many applicants want the same few
  programs. The Gini coefficient measures it (0: every program is someone's first choice equally often; near 1: a few
  programs get nearly all).

The scatter plots show true against observed utility for a sample of pairs before interviews and of interviews after
them; the dashed line is observed = true.

## Applications and interviews

The funnel from applications through invitations, interviews and rank order lists to matches, with how many
applications drop out at each step; the same flow for applicants, each counted once (who gets an interview and who
matches), which **Colour by strength** splits into five groups by strength percentile to follow the quality of the
applicants through the stages and see who makes up each drop-off; applications, signals, invitations, interviews
and list entries per applicant;
the signals' effect on interview rates; and, over matched applicants:

Regret
: How much better (in SD units) the best program an applicant interviewed at turned out to be than the one they
  matched to, judged by the utility the interview revealed.

Post-interview fidelity
: The correlation of the realised utility and the post-interview view over all interviews: 1 means interviews reveal
  everything.

The table lists every application with filters: the stage it reached, whether it carried a signal, and applicant
and program names.

## Match

Match rate
: The share of applicants with a rank order list who matched, as NRMP reports count it. Applicants without an
  interview have no list and are not counted.

Positions filled
: The share of positions the match filled.

Matched to their first choice
: The share of matched applicants who matched to the program they ranked first; the chart beside it shows every
  choice, from the first to the tenth, and lower ones together.

Sorting
: Whether stronger applicants match to better programs: the rank correlation between an applicant's strength and the
  quality of the program they matched to, over matched applicants. Close to 1, the strongest applicants are at the
  best programs, in order; at 0, strength has nothing to do with where applicants match. It is the summary of the
  chart under **Who matched where**, which shows where each fifth of applicants by strength ended up: not matched,
  or matched to a program in each fifth of programs by quality. Beside it, a chart shows which programs filled
  their positions, by quality.

Checks
: Every run checks that the match is stable (no blocking pairs), within capacity, only between pairs on both lists,
  and that the lists follow the rules. With *Compare both sides proposing* on, it also runs program-proposing
  deferred acceptance and checks that the same applicants match and every program fills the same number of
  positions.

"Who matched" starts with a chart of each strength decile (1 is the weakest tenth of applicants, 10 the strongest):
the share who matched, who had a rank order list but did not match, and who had no list. Its tables break the match
rate, the mean choice matched and interviews down by applicant group and by strength decile.

## Applicants, programs and one agent's page

The lists show every applicant or program with its attributes, weights, pre-interview results and outcome, and sort
by any column. An applicant's page shows how far each of their applications got, as a network (one point per
program) and as a funnel like the one on the Applications and interviews tab, then follows them through the stages
in a table: every program they applied to, the signal they sent, the invitation and its wave, whether they
interviewed, both sides' views after the interview, where each side put the other on its list, and the match. Its
second tab shows how the applicant sees every program before interviews and how every program sees them. Program
pages are the same from the program's side, and a program's funnel has **Colour by strength** too: it splits the
applications by the applicant's strength percentile among all applicants, so you can see whom the program invites,
ranks and matches.

## Charts

Every chart answers one question, written as its caption, and its "?" button explains how to read it. Each has a
summary sentence underneath, and most have a table of their numbers ("The numbers"), so nothing depends on seeing
the drawing. The colours mean the same thing on every chart unless its key says otherwise: blue is applicants,
orange is programs, green is a match and grey is everything else; shades of blue order the stages, darker (lighter
in the dark theme) the further a stage. With **Colour by strength** on, the applicants' flow colours applicants by
strength percentile instead, drop-offs included: red for the bottom 20%, grey for the middle and blue for the top 20%,
as the key under it shows.
**Patterns as well as colours** in the display settings (the button beside the account menu) adds patterns to the
bars and areas, for colour-blind readers and printing.

[[chart_catalog]]

## Downloads

Every run's parameters (with the seed) and diagnostics download as JSON, and its population as CSV in the upload
format, so it can be reproduced or uploaded elsewhere. The match (one row per applicant), the programs' results and
every application (from signal to match, with both sides' true, pre-interview, realised and post-interview values)
download as CSV; see [CSV files](/help/csv/).
