"""Save the example runs that everyone can see at /examples/ (nrmps.examples).

    python manage.py nrmp_examples

runs each example's market with the code as it is now and writes its files to nrmps/example_runs/<slug>/ if the
saved ones are missing or differ: after a change of the engine, of the example's preset or of its seed. Commit the
files. With --check nothing is written, and the command fails if an example is out of date (the tests check the
same); --force writes the files even when nothing changed. The database is not used.
"""

from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser

from nrmps.examples import DIRECTORY, EXAMPLES, save, saved_run, stale


class Command(BaseCommand):
    """Save the example runs again where the code no longer gives the saved files."""

    help = "Save the public example runs (nrmps/example_runs/) where they are missing or out of date."

    def add_arguments(self, parser: CommandParser) -> None:
        """Declare the options."""
        parser.add_argument("--check", action="store_true", help="Write nothing; fail if an example is out of date.")
        parser.add_argument("--force", action="store_true", help="Write the files even if nothing changed.")

    def handle(self, *args: Any, **options: Any) -> None:
        """Check or save every example and report."""
        outdated = []
        for slug, example in EXAMPLES.items():
            changed = stale(example) if options["check"] else save(example, force=options["force"])
            if options["check"]:
                self.stdout.write(f"{slug}: {'out of date: ' + ', '.join(changed) if changed else 'up to date'}")
                outdated += [slug] if changed else []
                continue
            if not changed and not options["force"]:
                self.stdout.write(f"{slug}: up to date")
                continue
            run = saved_run(slug).run
            match = (run.metrics or {})["outcomes"]["match"]
            self.stdout.write(
                f"{slug}: saved to {DIRECTORY / slug} ({', '.join(changed) or 'nothing had changed'}): "
                f"{run.n_applicants:,} applicants, {run.n_programs:,} programs, {run.n_positions:,} positions, "
                f"match rate {match['match_rate']:.1%}"
            )
        if outdated:
            raise CommandError(f"Out of date: {', '.join(outdated)}. Run `python manage.py nrmp_examples`.")
