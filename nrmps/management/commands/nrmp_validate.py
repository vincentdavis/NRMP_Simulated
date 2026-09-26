"""Check the engine against matching theory on many random markets and print the validation report (plan step 3.7).

    python manage.py nrmp_validate --markets 200 --output docs/VALIDATION.md

runs `nrmps.validation.validation_report` and prints (or writes) the Markdown report. It fails with a non-zero exit
status if any check fails, so CI can run it.
"""

from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser

from nrmps.validation import validation_report


class Command(BaseCommand):
    """Run the validation report."""

    help = "Check stability, capacity, list rules, the rural hospitals theorem, an oracle and strategy-proofness."

    def add_arguments(self, parser: CommandParser) -> None:
        """Declare the options."""
        parser.add_argument("--markets", type=int, default=200, help="Random markets to check (default 200).")
        parser.add_argument(
            "--misreport-markets",
            type=int,
            default=50,
            help="Markets on which every applicant's alternative lists are tried (default 50).",
        )
        parser.add_argument("--seed", type=int, default=1, help="Seed of the random markets (default 1).")
        parser.add_argument("--output", type=Path, help="Write the Markdown report to this file.")

    def handle(self, *args: Any, **options: Any) -> None:
        """Check the markets and report."""
        if options["markets"] < 1 or options["misreport_markets"] < 0:
            raise CommandError("--markets must be at least 1 and --misreport-markets at least 0.")
        report = validation_report(options["markets"], options["misreport_markets"], options["seed"])
        command = f"manage.py nrmp_validate --markets {options['markets']} --misreport-markets "
        command += f"{options['misreport_markets']} --seed {options['seed']}"
        text = report.markdown(command)
        if options["output"]:
            options["output"].write_text(text)
            self.stdout.write(f"Wrote {options['output']}: {'passed' if report.passed else 'FAILED'}.")
        else:
            self.stdout.write(text, ending="")
        if not report.passed:
            raise CommandError(f"Validation failed: {len(report.failures)} or more failures (see the report).")
