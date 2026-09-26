"""Create a demo simulation with one finished run, for local development, screenshots and onboarding.

    python manage.py seed_demo --username demo

The user is created if missing, with the password from the NRMP_DEMO_PASSWORD environment variable, or with an
unusable password (log in as staff and set one, or use the password reset) when it is not set.
"""

import os
from typing import Any

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError, CommandParser

from nrmps.exceptions import SimulationError
from nrmps.models import Simulation
from nrmps.params import SimulationParams
from nrmps.runs import run_now

DEMO_DESCRIPTION = (
    "A demo market with the default parameters: NRMP-like applicant groups, 1.08 applicants per position and "
    "moderate agreement on both sides. Change a parameter and run it again to compare."
)


class Command(BaseCommand):
    """Create a user (if needed) and a demo simulation with one finished run."""

    help = "Create a demo simulation with one finished run."

    def add_arguments(self, parser: CommandParser) -> None:
        """Declare the options."""
        parser.add_argument("--username", default="demo", help="Owner of the demo (created if missing).")
        parser.add_argument("--email", default="", help="Email address for a new user.")
        parser.add_argument("--name", default="Demo market", help="Name of the demo simulation.")
        parser.add_argument("--seed", type=int, default=2026, help="Seed of the demo run.")

    def handle(self, *args: Any, **options: Any) -> None:
        """Create the user, the simulation and its run."""
        users = get_user_model()
        user = users.objects.filter(username=options["username"]).first()
        if user is None:
            user = users(username=options["username"], email=options["email"])
            password = os.environ.get("NRMP_DEMO_PASSWORD")
            if password:
                user.set_password(password)
            else:
                user.set_unusable_password()
            user.save()
            self.stdout.write(f"Created the user {user.username}{'' if password else ' (no password set)'}.")
        params = SimulationParams().with_seed(options["seed"])
        simulation = Simulation.objects.create(
            owner=user, name=options["name"], description=DEMO_DESCRIPTION, params=params.to_json_data()
        )
        try:
            run = run_now(simulation, None)
        except SimulationError as exc:
            raise CommandError(str(exc)) from exc
        if run.status != run.Status.SUCCEEDED:
            raise CommandError(f"The demo run failed: {run.error}")
        self.stdout.write(
            f"Created “{simulation.name}” (simulation {simulation.pk}) with run {run.number}: "
            f"{run.n_applicants:,} applicants, {run.n_programs:,} programs, {run.duration_ms} ms."
        )
