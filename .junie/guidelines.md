# NRMP Simulations

## Package overview
This app allows configurable simulations of the National Resident matching program (NRMP) https://www.nrmp.org/.
Researchers are able to upload or configure the students (Applicant), schools (Programs) and the matching algorithm (Matching Algorithm).
It includes a interview stage before the matching stage.

## User account:
- Basic user account system, no email verification required.
- Users can configure and save configurations.
- Users can import student and or school population data.
- Users can run simulations and save and export the results.

### Core development technologies
- Python 3.13+
- Django 5.2+
- PostgreSQL 14+ (sqlite for local development)
- Boostrap5

### Development tools
- pytest
- ruff
- ty
- mypy
- logging

## Code Style and Development Guidelines

### Code Style

1. **Linting and Formating**:
   The project uses Ruff for linting. Configuration is in `ruff.toml`.
   ```bash
   # Run linter
   ruff check .

   # Run linter with auto-fix
   ruff check --fix .
   ```

2. **Style Guidelines**:
   - Line length: 120 characters
   - Indentation: 4 spaces
   - String quotes: Double quotes
   - Docstrings: Required for all public functions, classes, and methods
   - Also see the `ruff.toml` file.
