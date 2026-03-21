# TODO - NRMP Simulation Project

## High Priority - Core Functionality

### Simulation Engine Completion

- [ ] **Implement school invitation logic** (`simulation_engine.py`)
  - Schools select students for interview invitations based on pre-interview rankings
  - Respect `school_interview_limit` from SimulationConfig (percentage of capacity)
  - Respect `applicant_interview_limit` from SimulationConfig
  - Update Interview status from "initialized" to "invited"
  - Students accept/decline invitations; update status to "interviewed"

- [ ] **Wire up post-interview scoring/ranking in UI** (`views.py`)
  - Engine functions exist (`compute_post_interview_scores_and_rankings` etc.) but no views call them
  - Add HTMX endpoints for triggering post-interview scoring and ranking
  - Add buttons/controls in the interview management UI

- [ ] **Implement student final ranking** (`simulation_engine.py:313`)
  - Complete `students_rank()` function
  - Generate final preference lists based on post-interview scores
  - Create Match model instances with student ranking data

- [ ] **Implement school final ranking** (`simulation_engine.py:321`)
  - Complete `schools_rank()` function
  - Generate final preference lists based on post-interview scores
  - Create Match model instances with school ranking data

- [ ] **Implement NRMP matching algorithm** (`simulation_engine.py:326`)
  - Complete `match()` function with deferred acceptance (Gale-Shapley) algorithm
  - Student-proposing variant per NRMP rules
  - Handle unmatched participants
  - Respect school capacity constraints

### Completed Engine Functions
- [x] Interview initialization (full cross-product) - `initialize_interview()`
- [x] Student pre-interview rating of schools - `students_rate_schools_pre_interview()`
- [x] School pre-interview rating of students - `schools_rate_students_pre_interview()`
- [x] Pre-interview ranking computation - `compute_students_pre_rankings()`, `compute_schools_pre_rankings()`
- [x] Complete pre-interview workflow - `compute_pre_interview_scores_and_rankings()`
- [x] Student post-interview rating of schools - `students_rate_schools_post_interview()`
- [x] School post-interview rating of students - `schools_rate_students_post_interview()`
- [x] Post-interview ranking computation - `compute_students_post_rankings()`, `compute_schools_post_rankings()`
- [x] Complete post-interview workflow - `compute_post_interview_scores_and_rankings()`

## Medium Priority - User Experience

### UI/UX Improvements
- [ ] **Simulation workflow UI**
  - Add progress indicators for simulation stages
  - Create step-by-step simulation wizard
  - Add simulation status dashboard

- [ ] **Data visualization**
  - Add charts for population statistics
  - Create match outcome visualizations
  - Implement ranking distribution graphs

- [ ] **Bulk operations UI**
  - Improve CSV upload/download experience
  - Add data validation feedback
  - Create bulk edit capabilities

### Performance Optimizations
- [ ] **Database query optimization**
  - Refactor engine functions to use `bulk_update()` instead of per-row `.save()` calls
  - Add database indexes for common queries
  - Implement query result caching

## Low Priority - Enhancement Features

### Advanced Simulation Features
- [ ] **Multiple matching rounds**
  - Support for SOAP (post-match) rounds
  - Implement couples matching
  - Add specialty-specific matching rules

- [ ] **Preference modeling improvements**
  - Add more sophisticated preference generation models
  - Implement preference correlation modeling
  - Add geographic preference constraints

- [ ] **Simulation analysis tools**
  - Add statistical analysis of match outcomes
  - Implement scenario comparison tools
  - Create reproducible simulation reports

### Administrative Features
- [ ] **User management**
  - Add user roles (admin, researcher, student)
  - Implement simulation sharing permissions

## Technical Debt & Code Quality

### Bug Fixes
- [ ] **Fix typo in `_score()` parameter** (`simulation_engine.py:4`)
  - Rename `meta_preferances` to `meta_preferences`

### Testing
- [ ] **Unit tests** (currently `nrmps/tests.py` is empty)
  - Add tests for `_score()`, population generation, scoring, ranking functions
  - Test model validation and constraints
  - Add form validation tests

- [ ] **Integration tests**
  - Test complete simulation workflows end-to-end
  - Test CSV upload/download round-trip
  - Test HTMX endpoint responses

### Code Organization
- [ ] **Refactoring**
  - Extract business logic from views into service layers
  - Improve error handling consistency

## Deployment & Infrastructure
- [ ] **Containerization**
  - Add `entrypoint.sh` referenced by Dockerfile (or update Dockerfile)
  - Add docker-compose for local development
  - Create deployment documentation

- [ ] **Production setup**
  - Configure PostgreSQL for production
  - Implement proper logging configuration

---

## Notes
- Items marked with line numbers reference specific locations in the codebase
- Priority levels are suggestions and can be adjusted based on project needs
- The simulation pipeline order is: create populations -> initialize interviews -> pre-interview scoring/ranking -> school invitations -> interview phase -> post-interview scoring/ranking -> final ranking -> match
