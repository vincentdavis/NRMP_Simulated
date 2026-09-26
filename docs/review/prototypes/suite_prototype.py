"""Starter test-suite prototype from the project review (2026-09-24); see README.md before moving it into nrmps/tests/."""
import random
import pytest
from hypothesis import given, settings, strategies as st
from django.urls import reverse
from nrmps.models import SimulationConfig, Simulation, User
from nrmps import simulation_engine as se


@pytest.fixture
def owner(db):
    return User.objects.create_user("owner", password="Pw-123456789!")


@pytest.fixture
def sim(owner):
    s = Simulation.objects.create(owner=owner, name="t")
    SimulationConfig.objects.create(simulation=s, number_of_applicants=20, number_of_schools=4,
                                    school_score_mean=0.5, school_meta_preference_stddev=0.5, school_meta_scores_stddev=0.5)
    s.create_students(); s.create_schools()
    return s


def test_default_config_is_valid(db):
    """Model defaults must satisfy the model's own validators (currently fails)."""
    SimulationConfig(simulation=Simulation(owner=User(username="u"), name="x")).full_clean(exclude=["simulation"])


@pytest.mark.parametrize("name", ["simulation_manage", "simulation_students", "simulation_interviews",
                                  "simulation_download_students"])
def test_non_owner_gets_404(client, sim, name, django_user_model):
    intruder = django_user_model.objects.create_user("intruder", password="Pw-123456789!")
    client.force_login(intruder)
    assert client.get(reverse(f"nrmps:{name}", kwargs={"pk": sim.pk})).status_code == 404


def test_htmx_create_students_returns_partial(client, sim):
    client.force_login(sim.owner)
    r = client.post(reverse("nrmps:simulation_create_students", kwargs={"pk": sim.pk}), HTTP_HX_REQUEST="true")
    assert r.status_code == 200 and b'id="population-counts"' in r.content and b"<html" not in r.content


def test_pre_interview_rating_adds_noise_not_scales(sim):
    """Observed score should be true utility + N(0, err) noise (currently multiplied -> fails)."""
    se.initialize_interview(sim)
    se.students_rate_schools_pre_interview(sim)
    obs = list(sim.interviews.values_list("student_pre_observed_score_of_school", flat=True))
    assert max(obs) > 0.2, f"observed scores look scaled by rating_error: max={max(obs):.3f}"


# --- property-based tests for the (future) match(): demonstrated against a reference DA ---
def deferred_acceptance(s_prefs, h_prefs, cap):
    rank = {h: {s: i for i, s in enumerate(p)} for h, p in h_prefs.items()}
    nxt = {s: 0 for s in s_prefs}; held = {h: [] for h in h_prefs}; free = list(s_prefs)
    while free:
        s = free.pop()
        if nxt[s] >= len(s_prefs[s]): continue
        h = s_prefs[s][nxt[s]]; nxt[s] += 1
        if s not in rank[h]: free.append(s); continue
        held[h].append(s); held[h].sort(key=rank[h].get)
        if len(held[h]) > cap[h]: free.append(held[h].pop())
    return {s: h for h, ss in held.items() for s in ss}


@st.composite
def markets(draw):
    ns, nh = draw(st.integers(1, 12)), draw(st.integers(1, 5))
    S, H = list(range(ns)), [f"h{i}" for i in range(nh)]
    s_prefs = {s: draw(st.permutations(H))[: draw(st.integers(0, nh))] for s in S}
    h_prefs = {h: [s for s in draw(st.permutations(S)) if draw(st.booleans()) or True] for h in H}
    cap = {h: draw(st.integers(0, 4)) for h in H}
    return s_prefs, h_prefs, cap


@settings(max_examples=300, deadline=None)
@given(markets())
def test_match_is_stable_and_respects_capacity(m):
    s_prefs, h_prefs, cap = m
    match = deferred_acceptance(s_prefs, h_prefs, cap)
    for h in h_prefs:
        assert sum(1 for v in match.values() if v == h) <= cap[h]
    for s, h in match.items():
        assert h in s_prefs[s] and s in h_prefs[h]          # individual rationality
    for s, prefs in s_prefs.items():                          # no blocking pair
        cur = prefs.index(match[s]) if s in match else len(prefs)
        for h in prefs[:cur]:
            held = [x for x, v in match.items() if v == h]
            worst = max((h_prefs[h].index(x) for x in held), default=None)
            assert s not in h_prefs[h] or (len(held) >= cap[h] and (worst is None or h_prefs[h].index(s) > worst))
