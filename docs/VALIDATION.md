# Validation report

Model 2.1, engine 2.1.0, numpy 2.5.3, oracle `matching` 1.4.3; generated 2026-09-26 by `manage.py nrmp_validate --markets 500 --misreport-markets 100 --seed 1` in 3.2 s.

500 random markets from seed 1 (10 to 80 applicants, 2 to 12 programs, a random choice of every stage's policies, both proposing sides): 23,099 applicants, 3,345 programs, 15,521 matches.

| Check | Checked | Failed |
|---|---:|---:|
| Blocking pairs: an applicant and a program that rank each other above their match | 500 markets | 0 |
| Programs matched to more applicants than they have positions | 500 markets | 0 |
| Matches that are not on both rank order lists | 500 markets | 0 |
| List entries without an interview | 500 markets | 0 |
| Rank order lists whose ranks are not exactly 1, 2, ..., k | 500 markets | 0 |
| Applicant list entries beyond rank 300 (the NRMP limit) | 500 markets | 0 |
| Both proposing sides match the same applicants and fill each program equally (rural hospitals) | 500 markets | 0 |
| No applicant prefers the program-proposing result (applicant optimality) | 500 markets | 0 |
| Same match as an independent solver, applicants proposing | 500 markets | 0 |
| Same match as an independent solver, programs proposing | 500 markets | 0 |
| No applicant gets a better program by submitting a different list (applicants proposing) | 4,745 applicants | 0 |

**Result: passed.**
