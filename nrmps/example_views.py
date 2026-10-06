"""The saved example runs (nrmps.examples): pages for everyone, at /examples/.

An example's pages are the pages of a run (nrmps.run_views), read-only: its summary, population, views before
interviews, applications and interviews, match, applicants and programs, each applicant's and program's own page,
and the downloads. They show the files saved in the repository and never read the database, so nothing of any
account can appear on them (only the downloads touch it, to count the requests of a client address).
"""

from django.contrib.auth.decorators import login_not_required
from django.http import Http404
from django.shortcuts import render
from django.views.decorators.http import require_GET

from . import run_views
from .examples import EXAMPLES, saved_run
from .ratelimit import over_limit, too_many_requests
from .run_views import RunPages


def example_pages(slug: str) -> RunPages:
    """Return the pages of example `slug`, or raise Http404."""
    if slug not in EXAMPLES:
        raise Http404("No such example")
    saved = saved_run(slug)
    return RunPages(saved.run, saved)


@login_not_required
@require_GET
def examples(request):
    """The saved example runs: what each market is, its key numbers and where to start reading."""
    items = []
    for slug in EXAMPLES:
        pages = example_pages(slug)
        items.append({"pages": pages, "run": pages.run, "highlights": run_views.highlights(pages)})
    return render(request, "nrmps/examples/index.html", {"items": items})


@login_not_required
@require_GET
def example_detail(request, slug: str):
    """An example's summary: key numbers, the applicants' flow, downloads, stages, checks and parameters."""
    return run_views.summary_page(request, example_pages(slug))


@login_not_required
@require_GET
def example_population(request, slug: str):
    """An example's population: the market as generated, with its distributions."""
    return run_views.population_page(request, example_pages(slug))


@login_not_required
@require_GET
def example_pre_interview(request, slug: str):
    """An example before interviews: agreement, fidelity, first choices and first-choice demand."""
    return run_views.pre_interview_page(request, example_pages(slug))


@login_not_required
@require_GET
def example_applications(request, slug: str):
    """An example's applications, invitations and interviews: the funnel, and every application with filters."""
    return run_views.applications_page(request, example_pages(slug))


@login_not_required
@require_GET
def example_match(request, slug: str):
    """An example's match: headline numbers, which choice applicants got, who matched where, and the checks."""
    return run_views.match_page(request, example_pages(slug))


@login_not_required
@require_GET
def example_applicants(request, slug: str):
    """An example's applicants with their attributes, weights and results."""
    return run_views.applicants_page(request, example_pages(slug))


@login_not_required
@require_GET
def example_applicant(request, slug: str, index: int):
    """One applicant of an example through the stages, and its view of every program before interviews."""
    return run_views.agent_page(request, example_pages(slug), index, applicant=True)


@login_not_required
@require_GET
def example_programs(request, slug: str):
    """An example's programs with their attributes, weights, positions and results."""
    return run_views.programs_page(request, example_pages(slug))


@login_not_required
@require_GET
def example_program(request, slug: str, index: int):
    """One program of an example with its applicants through the stages, and its view of every applicant."""
    return run_views.agent_page(request, example_pages(slug), index, applicant=False)


@login_not_required
@require_GET
def example_download(request, slug: str, name: str):
    """Download a file of an example: the applicants, the programs, the results, the parameters or the diagnostics.

    Files are computed when asked for, so each client address gets a limited number per hour; search engines are
    asked to leave them alone (robots.txt, and the header here).
    """
    pages = example_pages(slug)
    if over_limit(request, "example_download", by="ip"):
        return too_many_requests(request)
    response = run_views.download(request, pages, name)
    response["X-Robots-Tag"] = "noindex"
    return response
