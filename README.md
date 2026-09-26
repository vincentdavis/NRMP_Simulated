# NRMP Simulations

Simulate the residency Match: build a market of applicants and residency programs, give each side preferences and
imperfect information, and see how their ratings and rankings form. For students, program directors, educators and
researchers.

Live site: <https://nrmp-simulated.heteroskedastic.org>

> An independent educational and research simulator. Not affiliated with, sponsored or endorsed by the National
> Resident Matching Program® (NRMP®). Simulated outcomes are not predictions of any real applicant's or program's
> match.

## What works today

1. Create a simulation; it starts with a working default configuration.
2. Generate applicant (student) and program (school) populations, or upload them as CSV (a download uploads back
   unchanged; sample files are linked in the app).
3. Create one interview row per applicant-program pair.
4. Compute true utilities, noisy pre-interview ratings and strict pre-interview ranks for both sides.
5. Browse, sort and download the results.

Applications, signals, invitations, interviews, rank order lists and the match itself are being built: see the
[phased plan](docs/PROJECT_REVIEW.md#9-phased-implementation-plan) and
[implementation status](docs/IMPLEMENTATION_STATUS.md).

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

CI runs all of these, builds the Docker image and checks its health endpoint. `uvx pre-commit install` runs the fast
checks before each commit.

## Deployment

Railway, from the `Dockerfile` (see [docs/DEPLOY.md](docs/DEPLOY.md)). `railway.json` runs migrations before each
deploy and health-checks `/healthz`. `docker compose up --build` runs the production image locally with PostgreSQL.

## Documentation

- [docs/PROJECT_REVIEW.md](docs/PROJECT_REVIEW.md): the project review and the phased plan.
- [docs/IMPLEMENTATION_STATUS.md](docs/IMPLEMENTATION_STATUS.md): what has been done, step by step.
- [docs/DEPLOY.md](docs/DEPLOY.md): deployment and operations.
- [docs/model_spec.md](docs/model_spec.md): the proposed model 2.0 for the next engine.
- [CLAUDE.md](CLAUDE.md): notes for AI coding assistants (commands, architecture, conventions).

## License

[MIT](LICENSE).
