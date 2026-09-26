"""Run the model 2.0 engine from the command line, without the database or the web interface.

    python manage.py nrmp_run --params my_params.json --seed 42 --out results/

prints a summary of the diagnostics and, with --out, writes params.json (with the seed used), population.npz,
results.npz (per-agent results) and metrics.json (the diagnostics with version stamps). The same parameters and seed
always give the same files.
"""

import json
import secrets
import time
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser
from pydantic import ValidationError

from nrmps.engine.persistence import population_digest, population_from_npz, population_to_npz, results_to_npz
from nrmps.engine.pipeline import DEFAULT_BLOCK_PAIRS, run_pre_interview
from nrmps.engine.population import PopulationError
from nrmps.params import SimulationParams, canonical_json, load_params
from nrmps.versions import stamps


class Command(BaseCommand):
    """Run the population and pre-interview stages for a parameter file and a seed."""

    help = "Run the model 2.0 engine (population and pre-interview stages) without the database."

    def add_arguments(self, parser: CommandParser) -> None:
        """Declare the options."""
        parser.add_argument("--params", type=Path, help="JSON file of parameters (schema v1); default: the defaults.")
        parser.add_argument(
            "--seed", type=int, help="Root seed; overrides run.seed; drawn at random if neither is set."
        )
        parser.add_argument("--population", type=Path, help="A population.npz from an earlier --out to reuse.")
        parser.add_argument("--block-pairs", type=int, default=DEFAULT_BLOCK_PAIRS, help="Pairs per block (memory).")
        parser.add_argument(
            "--out", type=Path, help="Directory for params.json, population.npz, results.npz and metrics.json."
        )
        parser.add_argument("--json", action="store_true", help="Print the full record as JSON instead of a summary.")

    def handle(self, *args: Any, **options: Any) -> None:
        """Run the engine and report."""
        params = self._params(options["params"])
        seed = options["seed"] if options["seed"] is not None else params.run.seed
        if seed is None:
            seed = secrets.randbits(63)
        try:
            params = params.with_seed(seed)
        except ValidationError as exc:
            raise CommandError(f"Invalid seed: {exc.errors()[0]['msg']}") from exc
        population = population_from_npz(options["population"].read_bytes()) if options["population"] else None
        started = time.perf_counter()
        try:
            result = run_pre_interview(params, seed, population=population, block_pairs=options["block_pairs"])
        except (PopulationError, ValueError) as exc:
            raise CommandError(str(exc)) from exc
        record = {
            "stamps": stamps(),
            "seed": seed,
            "params_hash": params.params_hash(),
            "population_digest": population_digest(result.population),
            "duration_seconds": round(time.perf_counter() - started, 3),
            "metrics": result.metrics,
        }
        if options["out"]:
            out: Path = options["out"]
            out.mkdir(parents=True, exist_ok=True)
            (out / "params.json").write_text(json.dumps(params.to_json_data(), indent=2) + "\n")
            (out / "population.npz").write_bytes(population_to_npz(result.population))
            (out / "results.npz").write_bytes(results_to_npz(result.applicants, result.programs))
            (out / "metrics.json").write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
        if options["json"]:
            self.stdout.write(canonical_json(record))
        else:
            self._summary(record)

    def _params(self, path: Path | None) -> SimulationParams:
        if path is None:
            return SimulationParams()
        try:
            return load_params(json.loads(path.read_text()))
        except (OSError, ValueError) as exc:
            raise CommandError(f"Cannot use {path}: {exc}") from exc

    def _summary(self, record: dict[str, Any]) -> None:
        market = record["metrics"]["market"]
        self.stdout.write(
            f"Seed {record['seed']}: {market['n_applicants']:,} applicants, {market['n_programs']:,} programs, "
            f"{market['n_positions']:,} positions ({market['applicants_per_position']:.3f} applicants per position) "
            f"in {record['duration_seconds']} s."
        )
        for side in ("applicants", "programs"):
            metrics = record["metrics"][side]
            consensus, fidelity = metrics["consensus"], metrics["fidelity"]
            self.stdout.write(
                f"  {side}: agreement {consensus['true_utility_correlation']:.3f}, pre-interview fidelity "
                f"{fidelity['pooled_correlation']:.3f} (expected {fidelity['expected_correlation']:.3f}), "
                f"{metrics['first_choices']['distinct']:,} distinct first choices"
            )
        self.stdout.write(f"  model {record['stamps']['model_version']}, engine {record['stamps']['engine_version']}")
