---
title: The simulation model
order: 2
summary: Every stage of model {{model_version}}, with its formulas and a worked example.
seo_title: The simulation model of the residency Match
description: How the simulator models the Match: preferences, noisy information, applications, signals, interviews, rank order lists and the match, with formulas.
---

This is model {{model_version}} (engine {{engine_version}}). Values such as strength, quality and utility are on a
z-scale: 0 is average and 1 is one standard deviation above it. The full specification, with every formula and the
random-number recipe, is `docs/model_spec.md` in the [project repository]({{project_url}}).

## Applicants and programs

Applicants belong to groups (for example US MD seniors or international graduates), each with its share of the
applicants and a normal distribution of latent strength. Programs have a latent quality, optionally in tiers:

$$a_i = \mu_{g} + \sigma_{g}\, z_i, \qquad q_j = \mu_{t} + \sigma_q\, z'_j$$

The number of positions follows from the applicants per position you choose, $P = N / \text{applicants per position}$
(rounded), and the positions are spread over the programs so that every program has at least one: evenly, or with
right-skewed sizes as in the real Match.

Each applicant has a value for every *applicant attribute* programs evaluate (for example board_scores), and each
program one for every *program attribute* applicants evaluate (for example reputation). You set how closely each
attribute follows overall strength or quality, $\rho_k$:

$$x_{ik} = \rho_k\, \text{std}(a)_i + \sqrt{1-\rho_k^2}\; e_{ik}$$

The attribute program_size is the program's number of positions (on a log scale).

## Preferences

Everyone weighs the other side's attributes. You set the average weights; each agent's weights are drawn around
them (a Dirichlet distribution), and the weight concentration sets how much they vary.

An applicant's **true utility** for a program has three parts: a view everyone shares (mostly the program's quality,
with some of its average-weighted attributes), $C_j$; the applicant's personal taste for the program's attributes,
$T_{ij}$; and a random personal fit, $\varepsilon_{ij}$. Each part has mean 0 and standard deviation 1:

$$u_{ij} = \sqrt{\rho}\; C_j + \sqrt{1-\rho}\,\left(\sqrt{\tau}\; T_{ij} + \sqrt{1-\tau}\; \varepsilon_{ij}\right)$$

- $\rho$, the **agreement**, is the average correlation between two applicants' utilities: 1 means everyone ranks
  programs the same way, 0 that preferences are purely personal.
- $\tau$ is the share of the personal part that comes from attribute taste rather than pure fit.

Programs value applicants the same way, with their own agreement: $v_{ji} = \sqrt{\rho_P}\, S_i + \dots$

## What each side sees before interviews

Before interviews each side sees the other with error:

$$\hat u_{ij} = u_{ij} + \sigma\, e_{ij}$$

$\sigma$ is the noise in utility SD units: 0 is perfect information, 0.5 keeps a correlation of about 0.89 with the
truth, since the correlation is $1/\sqrt{1+\sigma^2}$. Optionally less-known programs and applicants are seen with
more error (visibility), and part of the error can be shared by everyone judging the same program or applicant
(herding). Each side ranks everyone on the other side by these views; exact ties are broken by seeded random keys.

## Applications and signals

Each applicant applies to $k_i$ programs: a fixed number, or a number drawn around the mean you set. They choose
from their pre-interview ranking: the best $k_i$ programs, every program, random ones, or a **portfolio** of reach,
target and safety programs. For the portfolio, each applicant judges their own standing with some error, and a
program is a reach if its prestige is above that standing by more than the target band, a safety if it is below by
more than the band, and a target otherwise.

Applicants can send preference signals in tiers (for example 3 gold and 5 silver) to programs they applied to: to
their favourites, to realistic choices first, or at random. A share of programs read signals.

## Invitations

Each program has $s_j = \lceil m\, c_j \rceil$ interview slots, where $c_j$ is its number of positions and $m$ the
interviews per position. It screens its applications with a score: its pre-interview view of the applicant, plus
the signal's boost when the applicant signalled it and it reads signals, or minus a **yield protection** penalty for
applicants who look too strong for it (who might go elsewhere).

Programs invite in waves: in each wave a program with open slots invites up to 20% more applicants than it has open
slots, by screening score (or signalled applicants first, or at random above a threshold, depending on the strategy).
Applicants go through their new invitations, the best ones or the first ones first, and accept while they are under
their interview cap and the program still has an open slot; otherwise they decline and the slot goes to a later wave.

## Interviews

An interview reveals a fit neither side knew about, and shrinks each side's pre-interview error:

$$u^*_{ij} = u_{ij} + \sigma_{\text{fit}}\, f_{ij}, \qquad \tilde u_{ij} = u^*_{ij} + (1-\kappa)\, e_{ij}$$

$u^*$ is the **realised utility**, which includes the fit; $\tilde u$ is the **post-interview view**. The interview
informativeness $\kappa$ sets how much of the old error disappears: 0 leaves it all, 1 removes it (the applicant then
knows $u^*$ exactly). Programs are symmetric.

## Rank order lists

Applicants rank the programs where they interviewed by their post-interview view: all of them, the top $k$, those
above a reservation utility, or all of them with the ones they are less likely to match moved down
(likelihood weighted). Programs rank the applicants they interviewed, leaving out a bottom share (do not rank) or
those below a threshold. Applicant lists hold at most 300 programs; applicants with a list take part in the match.

## The match

Applicant-proposing deferred acceptance, as the NRMP (see [How the Match works](/help/nrmp/)), or program-proposing
for comparison. Every run checks that the match is stable, respects capacities and lists and, when both proposing
sides run, that they match the same applicants and fill each program equally (the rural hospitals theorem). The
[validation report]({{project_url}}/blob/main/docs/VALIDATION.md) repeats the checks on hundreds of random markets
against an independent solver.

## Randomness and reproducibility

Every random draw comes from its own stream, derived from the seed, so the same parameters and seed give exactly the
same results, and changing one parameter changes only what depends on it: changing the noise before interviews does
not change the applicants or programs; changing interview informativeness does not change who applied or who was
invited. Pair-level draws use a counter-based generator, so any pair's values can be recomputed on their own.

## A worked example

With the default parameters and seed 42, the engine gives these values for the first applicant and the first
program. The sum below is the engine's own utility, not a recomputation.

[[worked_example]]
