# NRMP Simulations

Simulate the residency Match: build a market of applicants and residency programs, give each side preferences and
imperfect information, and see how their ratings and rankings form. For students, program directors, educators and
researchers.

Live site: <https://nrmp-simulated.heteroskedastic.org>

> An independent educational and research simulator. Not affiliated with, sponsored or endorsed by the National
> Resident Matching Program® (NRMP®). Simulated outcomes are not predictions of any real applicant's or program's
> match.

## What works today

1. Create a simulation; it starts with working default parameters (model 2.0: NRMP-like applicant groups, 1.08
   applicants per position, moderate agreement on both sides) and its own random seed.
2. Adjust the parameters: market size and tightness, applicant groups, the attributes each side evaluates and how
   much they agree, and the pre-interview noise. The parameter editor and the help page are generated from one typed
   schema.
3. Run it: applicants and programs are generated (or taken from uploaded CSV files), with true preferences, noisy
   pre-interview views and strict rankings on both sides. The same parameters and seed always give the same results,
   and the pipeline shows which stages a change makes out of date.
4. Explore the run: diagnostics (agreement, fidelity, first choices, the realised population against the request),
   applicants and programs, and one applicant's or program's view of the other side. Download everything as CSV or
   JSON; a downloaded population uploads back unchanged.

Applications, signals, invitations, interviews, rank order lists and the match itself are being built: see the
[phased plan](docs/PROJECT_REVIEW.md#9-phased-implementation-plan) and
[implementation status](docs/IMPLEMENTATION_STATUS.md). The in-app help page (`/help/`) explains the model, every
parameter and the CSV formats; `docs/model_spec.md` is the full specification.

## Development

Requirements: Python 3.14 and [uv](https://docs.astral.sh/uv/); Node.js for the CSS.

```bash
uv sync                         # dependencies (dev and prod groups)
cp .env.example .env            # DEBUG=True for local development
uv run python manage.py migrate
cd theme/static_src && npm ci && npm run build && cd ../..   # Tailwind CSS + daisyUI
uv run python manage.py runserver
```

With `DEBUG` off (production), the app refuses to start without `SECRET_KEY` and `DATABASE_URL`. Every setting is in
[`.env.example`](.env.example).

### Checks and tests

```bash
uv run ruff check . && uv run ruff format --check .   # lint and format
uv run mypy .                                         # types (django-stubs)
uv run codespell .                                    # spelling
uv run pytest                                         # tests (production settings, SQLite in memory)
NRMP_TEST_DATABASE_URL=postgres://... uv run pytest   # the same tests on PostgreSQL
uv run pytest -m e2e                                  # browser tests: Playwright + axe (needs the built CSS)
```

The engine also runs without the web interface: `uv run python manage.py nrmp_run --seed 42 --out results/` writes
the parameters, population, per-agent results and diagnostics; `manage.py seed_demo` creates a demo simulation.

CI runs all of these, builds the Docker image and checks its health endpoint. `uvx pre-commit install` runs the fast
checks before each commit.

## Deployment

Railway, from the `Dockerfile` (see [docs/DEPLOY.md](docs/DEPLOY.md)). `railway.json` runs migrations before each
deploy and health-checks `/healthz`; `railway.worker.json` adds an optional worker for background runs and
`railway.cron.json` a daily clean-up. `docker compose up --build` runs the production image locally with PostgreSQL
and a worker.

## Documentation

- [docs/PROJECT_REVIEW.md](docs/PROJECT_REVIEW.md): the project review and the phased plan.
- [docs/IMPLEMENTATION_STATUS.md](docs/IMPLEMENTATION_STATUS.md): what has been done, step by step.
- [docs/DEPLOY.md](docs/DEPLOY.md): deployment and operations.
- [docs/model_spec.md](docs/model_spec.md): the model 2.0 specification (normative since Phase 2).
- [CLAUDE.md](CLAUDE.md): notes for AI coding assistants (commands, architecture, conventions).

## License

[MIT](LICENSE).
