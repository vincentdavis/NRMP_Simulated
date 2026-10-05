---
title: How the Match works
order: 1
summary: The real process the simulator follows, from applications to Match Day.
seo_title: How the residency Match works
description: The residency Match in brief: who takes part, the timeline from applications to Match Day, the deferred acceptance algorithm, and what the simulator models.
---

The Main Residency Match places graduating medical students and other applicants into residency positions in the
United States. This page describes the process the simulator follows; figures are from the NRMP's 2026 Main Match
and are approximate.

## The participants

Applicants
: US MD and DO seniors, graduates of earlier years, and international medical graduates (IMGs) — about 48,000 in
  2026. They differ in how competitive programs find them.

Programs
: About 6,800 residency programs offering about 44,000 positions, from one or two positions to over a hundred.

Positions
: A program's capacity: the most applicants it can match. With about 1.08 applicants per position the market is
  tight on average, and much tighter in some specialties.

## The timeline

1. **Applications.** Applicants apply to programs through ERAS, often to dozens of them, choosing a mix of
   programs they would love, programs that fit them, and safer choices.
2. **Preference signals.** In many specialties applicants may send a few signals (for example 3 "gold" and 5 "silver")
   to programs they are especially interested in. Programs see them when deciding whom to interview.
3. **Interview invitations.** Programs screen their applications and invite a few applicants per position, often in
   waves as invitations are declined. Applicants accept only as many interviews as they can attend.
4. **Interviews.** Each side learns more about the other: some fits turn out better or worse than they looked.
5. **Rank order lists.** Applicants rank the programs where they interviewed, in order of preference; programs rank
   the applicants they interviewed, leaving out those they would rather not train. An applicant may rank up to 300
   programs.
6. **The match.** The NRMP's algorithm combines the lists; results are released on Match Day. Unfilled positions and
   unmatched applicants then meet in SOAP, which the simulator does not model.

## The algorithm

The NRMP uses the Roth–Peranson algorithm, a version of **applicant-proposing deferred acceptance** extended for
couples and supplemental lists. Without couples it works like this:

1. Every applicant proposes to the first program on their list.
2. Each program holds the best proposals it received, up to its number of positions, by its own list, and rejects the
   rest (and every applicant it did not rank).
3. Each rejected applicant proposes to the next program on their list.
4. This repeats until no one is rejected; the proposals held then are the match.

The result is **stable**: there is no applicant and program that both rank each other above what they got. Among all
stable matches it is the best one for every applicant, and no applicant can get a program they prefer by ranking
programs in a different order than they really prefer them. That is why the NRMP advises applicants to rank
programs in their true order of preference.

## What the simulator models

- Applicants in groups, programs with a number of positions, and attributes each side cares about.
- True preferences that mix what everyone agrees on (for example a program's reputation) with personal tastes and
  fit, and noisy views of them before interviews.
- Application strategies, preference signals, screening with invitation waves, interview caps, interviews that
  reveal fit, rank order list policies, and deferred acceptance.

Not modelled (yet): couples, supplemental lists, interview date conflicts, SOAP, specialty choice, and anything that
happens after the match.
