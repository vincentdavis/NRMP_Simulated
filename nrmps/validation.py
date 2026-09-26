"""The validation report (plan step 3.7): the engine checked against matching theory on many random markets.

`validation_report` draws small random markets (random sizes, and a random choice of every stage's policies), runs
the whole pipeline with both proposing sides, and counts per check the markets that fail it:

- the checks every run stores (`engine.validate.run_checks`): no blocking pairs, capacities respected, matches on both
  lists, strict lists of interviewed pairs no longer than 300, the rural hospitals theorem and applicant optimality;
- agreement with an independent solver, the `matching` package, for both proposing sides (skipped where the package
  is not installed: it is a development dependency);
- strategy-proofness: on the first markets, no applicant gets a program they rank higher by submitting another list
  under applicant-proposing deferred acceptance.

`manage.py nrmp_validate` prints the report as Markdown (docs/VALIDATION.md is one); the test suite runs a small one.
"""

import importlib.metadata
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import numpy as np

from .engine import ENGINE_VERSION, MODEL_VERSION
from .engine.match import UNMATCHED, build_lists
from .engine.pipeline import run_pipeline
from .engine.validate import COUNT_CHECKS, FLAG_CHECKS, oracle_match, profitable_misreports
from .params import SimulationParams

MISREPORT_LISTS = 65  # alternative lists tried per applicant (all of them for lists of up to 4 programs)
MISREPORT_APPLICANTS = 80  # applicants checked per market (all of them in these markets)
FAILURES_SHOWN = 10


@dataclass
class Check:
    """One line of the report: what was checked, on how many markets or applicants, and how many failed."""

    title: str
    unit: str = "markets"
    checked: int = 0
    failed: int = 0
    skipped: str = ""


@dataclass
class ValidationReport:
    """The outcome of `validation_report`."""

    seed: int
    markets: int
    applicants: int = 0
    programs: int = 0
    matched: int = 0
    seconds: float = 0.0
    checks: dict[str, Check] = field(default_factory=dict)
    failures: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        """Return True if no check failed."""
        return all(check.failed == 0 for check in self.checks.values())

    def fail(self, key: str, market: int, detail: str) -> None:
        """Count a failure of check `key` on `market` and remember the first few."""
        self.checks[key].failed += 1
        if len(self.failures) < FAILURES_SHOWN:
            self.failures.append(f"Market {market}: {self.checks[key].title} ({detail}).")

    def markdown(self, command: str = "") -> str:
        """Return the report as Markdown."""
        try:
            oracle = f"`matching` {importlib.metadata.version('matching')}"
        except importlib.metadata.PackageNotFoundError:
            oracle = "`matching` (not installed)"
        lines = [
            "# Validation report",
            "",
            f"Model {MODEL_VERSION}, engine {ENGINE_VERSION}, numpy {np.__version__}, oracle {oracle}; generated "
            f"{datetime.now(UTC):%Y-%m-%d}{f' by `{command}`' if command else ''} in {self.seconds:.1f} s.",
            "",
            f"{self.markets:,} random markets from seed {self.seed} (10 to 80 applicants, 2 to 12 programs, a random "
            f"choice of every stage's policies, both proposing sides): {self.applicants:,} applicants, "
            f"{self.programs:,} programs, {self.matched:,} matches.",
            "",
            "| Check | Checked | Failed |",
            "|---|---:|---:|",
        ]
        for check in self.checks.values():
            checked = f"skipped: {check.skipped}" if check.skipped else f"{check.checked:,} {check.unit}"
            lines.append(f"| {check.title} | {checked} | {check.failed:,} |")
        lines += ["", f"**Result: {'passed' if self.passed else 'FAILED'}.**"]
        if self.failures:
            lines += ["", "First failures:", "", *(f"- {failure}" for failure in self.failures)]
        return "\n".join(lines) + "\n"


def random_params(rng: np.random.Generator) -> dict[str, Any]:
    """Return the parameters of a small random market with a random choice of every stage's policies."""

    def pick(*options: Any) -> Any:
        return options[int(rng.integers(len(options)))]

    def uniform(low: float, high: float) -> float:
        return round(float(rng.uniform(low, high)), 2)

    n_applicants = int(rng.integers(10, 81))
    applicants_per_position = uniform(0.8, 1.6)
    n_programs = int(rng.integers(2, min(12, int(n_applicants / 1.6)) + 1))
    tiers = pick([], [{"name": "gold", "count": int(rng.integers(1, 3)), "boost": uniform(0, 1.5)}])
    return {
        "schema_version": 1,
        "run": {"seed": int(rng.integers(2**62))},
        "market": {
            "n_applicants": n_applicants,
            "applicants_per_position": applicants_per_position,
            "n_programs": n_programs,
        },
        "prefs": {"applicant_pref_correlation": uniform(0, 1), "program_pref_correlation": uniform(0, 1)},
        "info": {
            "applicant_pre_noise_sd": uniform(0, 1.5),
            "program_pre_noise_sd": uniform(0, 1.5),
            "interview_informativeness": uniform(0, 1),
            "fit_shock_sd": uniform(0, 1),
        },
        "apps": {
            "strategy": pick("top_n", "portfolio", "all", "random"),
            "count_dist": pick("fixed", "poisson", "negbin"),
            "mean": int(rng.integers(1, n_programs + 3)),
        },
        "signals": {
            "tiers": tiers,
            "allocation": pick("top_utility", "realistic", "random"),
            "program_use_share": uniform(0, 1),
            "use_in_ranking": bool(rng.integers(2)),
        },
        "invites": {
            "strategy": pick("top_score", "threshold_then_top", "threshold_then_random", "signal_first"),
            "interviews_per_position": uniform(1, 8),
            "rounds": int(rng.integers(1, 5)),
        },
        "interview": {"applicant_cap": int(rng.integers(1, 10)), "acceptance_order": pick("best_first", "first_come")},
        "rol": {
            "applicant_policy": pick(
                "all_interviewed", "top_k", "above_reservation", "truncate_k", "likelihood_weighted"
            ),
            "applicant_top_k": int(rng.integers(1, 8)),
            "program_policy": pick("all_interviewed", "dnr_quantile", "dnr_threshold"),
            "program_dnr_quantile": uniform(0, 0.5),
            "reservation_utility": uniform(-1.5, 0.5),
        },
        "match": {"algorithm": pick("applicant_proposing", "program_proposing"), "compare_both": True},
    }


def validation_report(markets: int = 200, misreport_markets: int = 20, seed: int = 1) -> ValidationReport:
    """Check `markets` random markets (strategy-proofness on the first `misreport_markets`) and return the report."""
    started = time.perf_counter()
    rng = np.random.default_rng(seed)
    report = ValidationReport(seed=seed, markets=markets)
    report.checks = {key: Check(title) for key, title in (COUNT_CHECKS | FLAG_CHECKS).items()}
    report.checks["oracle_applicants"] = Check("Same match as an independent solver, applicants proposing")
    report.checks["oracle_programs"] = Check("Same match as an independent solver, programs proposing")
    report.checks["misreports"] = Check(
        "No applicant gets a better program by submitting a different list (applicants proposing)", unit="applicants"
    )
    for market in range(1, markets + 1):
        params = SimulationParams.model_validate(random_params(rng))
        result = run_pipeline(params, int(params.run.seed or 0))
        population, match = result.population, result.match
        report.applicants += population.n_applicants
        report.programs += population.n_programs
        report.matched += int(np.count_nonzero(match.program != UNMATCHED))
        checks = result.metrics["outcomes"]["checks"]
        for key in [*COUNT_CHECKS, *FLAG_CHECKS]:
            report.checks[key].checked += 1
            if (checks[key] != 0) if key in COUNT_CHECKS else (checks[key] is not True):
                report.fail(key, market, f"{key} = {checks[key]}, seed {params.run.seed}")
        lists = build_lists(result.applications, result.lists, population.programs.capacity)
        other = match.alternative
        if other is None:  # compare_both is on, so the other proposing side ran
            raise RuntimeError("The comparison match is missing.")
        by_applicants, by_programs = (
            (match.program, other) if match.algorithm == "applicant_proposing" else (other, match.program)
        )
        for key, optimal, ours in (
            ("oracle_applicants", "resident", by_applicants),
            ("oracle_programs", "hospital", by_programs),
        ):
            expected = oracle_match(lists, optimal)
            if expected is None:
                report.checks[key].skipped = "the matching package is not installed"
                continue
            report.checks[key].checked += 1
            if ours.tolist() != expected:
                report.fail(key, market, f"seed {params.run.seed}")
        if market <= misreport_markets:
            misreports = report.checks["misreports"]
            generator = np.random.default_rng([seed, market])
            for applicant in range(min(population.n_applicants, MISREPORT_APPLICANTS)):
                misreports.checked += 1
                gains = profitable_misreports(lists, applicant, limit=MISREPORT_LISTS, rng=generator)
                if gains:
                    report.fail("misreports", market, f"applicant {applicant + 1}, seed {params.run.seed}")
    report.seconds = time.perf_counter() - started
    return report
