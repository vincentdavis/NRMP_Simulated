"""Account services: email verification links and the personal data export."""

import io
import json
import tempfile
import zipfile

from django.conf import settings
from django.core import signing
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify

from .engine.population import PopulationError
from .models import User
from .population_csv import UploadedSide, plain_csv_lines, population_csv_lines, uploaded_csv_lines
from .runs import MATCH_COLUMNS, RunData

VERIFY_SALT = "nrmps.accounts.verify-email"


def verification_token(user: User) -> str:
    """Return a signed token that confirms `user`'s current email address."""
    return signing.dumps({"user": user.pk, "email": user.email}, salt=VERIFY_SALT)


def verify_token(token: str) -> User | None:
    """Mark the email address in a verification token as confirmed; return the user, or None if the token is bad.

    A token is bad when its signature is wrong, it is older than PASSWORD_RESET_TIMEOUT, or the account's email has
    changed since it was sent.
    """
    try:
        data = signing.loads(token, salt=VERIFY_SALT, max_age=settings.PASSWORD_RESET_TIMEOUT)
    except signing.BadSignature:
        return None
    user = User.objects.filter(pk=data.get("user"), is_active=True).first()
    if user is None or not user.email or user.email != data.get("email"):
        return None
    if user.email_verified_at is None:
        user.email_verified_at = timezone.now()
        user.save(update_fields=["email_verified_at"])
    return user


def send_verification_email(request, user: User) -> None:
    """Email `user` a link that confirms their address."""
    link = request.build_absolute_uri(reverse("nrmps:verify_email", kwargs={"token": verification_token(user)}))
    days = settings.PASSWORD_RESET_TIMEOUT // (24 * 60 * 60)
    context = {"user": user, "link": link, "days": days}
    send_mail(
        subject="Confirm your email address for NRMP Simulations",
        message=render_to_string("emails/verify_email.txt", context),
        from_email=None,
        recipient_list=[user.email],
    )


def export_user_data(user: User):
    """Return a file object with a ZIP of everything stored for `user`, positioned at the start.

    The archive holds account.json, presets.json (the saved presets) and, per simulation: simulation.json (fields
    and draft parameters), the uploaded populations as CSV, and per run run.json (parameters with the seed, versions,
    status, diagnostics). The latest successful run's applicants, programs and match are included as CSV; other runs
    can be reproduced from their parameters and seed.
    """
    archive = tempfile.SpooledTemporaryFile(max_size=20 * 1024 * 1024)  # noqa: SIM115 (returned to the caller)
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        account = {
            "username": user.username,
            "full_name": user.full_name,
            "email": user.email,
            "email_verified_at": user.email_verified_at.isoformat() if user.email_verified_at else None,
            "date_joined": user.date_joined.isoformat(),
            "exported_at": timezone.now().isoformat(),
        }
        zf.writestr("account.json", json.dumps(account, indent=2))
        presets = [
            {
                "name": preset.name,
                "description": preset.description,
                "created_at": preset.created_at.isoformat(),
                "params": preset.params,
            }
            for preset in user.presets.all()
        ]
        zf.writestr("presets.json", json.dumps(presets, indent=2))
        for sim in user.simulations.order_by("id"):
            folder = f"simulations/{sim.pk}-{slugify(sim.name) or 'simulation'}"
            info = {
                "name": sim.name,
                "description": sim.description,
                "public": sim.public,
                "created_at": sim.created_at.isoformat(),
                "params": sim.params,
            }
            zf.writestr(f"{folder}/simulation.json", json.dumps(info, indent=2))
            for upload in sim.uploads.all():
                lines = uploaded_csv_lines(UploadedSide.from_npz(bytes(upload.data)))
                _write_lines(zf, f"{folder}/uploaded-{upload.side}.csv", lines)
            latest = sim.latest_run(succeeded=True)
            for run in sim.runs.order_by("number"):
                record = {
                    "number": run.number,
                    "status": run.status,
                    "created_at": run.created_at.isoformat(),
                    "seed": run.seed,
                    "params": run.params,
                    "population_source": run.population_source,
                    "stamps": run.stamps(),
                    "duration_ms": run.duration_ms,
                    "error": run.error,
                    "metrics": run.metrics,
                }
                zf.writestr(f"{folder}/runs/{run.number}/run.json", json.dumps(record, indent=2))
                if latest is not None and run.pk == latest.pk:
                    _write_run_files(zf, f"{folder}/runs/{run.number}", run)
    archive.seek(0)
    return archive


def _write_run_files(zf: zipfile.ZipFile, folder: str, run) -> None:
    """Write a run's applicants, programs and (for runs with the match) the match as CSV."""
    try:
        data = RunData(run)
    except PopulationError:
        return
    _write_lines(zf, f"{folder}/applicants.csv", population_csv_lines(data.population.applicants))
    _write_lines(zf, f"{folder}/programs.csv", population_csv_lines(data.population.programs))
    if data.stages is not None:
        _write_lines(zf, f"{folder}/match.csv", plain_csv_lines(MATCH_COLUMNS, data.match_rows()))


def _write_lines(zf: zipfile.ZipFile, name: str, lines) -> None:
    with zf.open(name, "w") as handle, io.TextIOWrapper(handle, encoding="utf-8", newline="") as text:
        for line in lines:
            text.write(line)
