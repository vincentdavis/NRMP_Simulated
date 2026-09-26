"""Interviews and the post-interview view (model_spec.md §7.4)."""

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from nrmps.params import SimulationParams

from .applications import Applications
from .invitations import Invitations
from .rng import Stream, pair_normals
from .utility import MarketModel

F64 = NDArray[np.float64]


@dataclass(frozen=True, eq=False)
class Interviews:
    """True, realised and post-interview utilities of every application (NaN where no interview took place)."""

    applicant_true: F64  # u
    applicant_realised: F64  # u* = u + fit shock
    applicant_post: F64  # the applicant's post-interview view
    program_true: F64  # v
    program_realised: F64  # v*
    program_post: F64  # the program's post-interview view


def interview(
    params: SimulationParams,
    model: MarketModel,
    applications: Applications,
    invitations: Invitations,
    seed: int,
    replicate: int = 0,
) -> Interviews:
    """Reveal the fit shocks and shrink each side's pre-interview error for every interview (§7.4)."""
    n_pairs = applications.size
    arrays = [np.full(n_pairs, np.nan) for _ in range(6)]
    held = np.flatnonzero(invitations.accepted)
    if held.size:
        i = applications.i[held].astype(np.int64)
        j = applications.j[held].astype(np.int64)
        sigma_fit = params.info.fit_shock_sd
        kappa = params.info.interview_informativeness
        u = model.applicants.pair_utilities(i, j)
        u_star = u + sigma_fit * pair_normals(seed, Stream.FIT, replicate, i, j)
        u_post = u_star + (1.0 - kappa) * model.applicant_view.pair_error(i, j)
        v = model.programs.pair_utilities(j, i)
        v_star = v + sigma_fit * pair_normals(seed, Stream.FIT_P, replicate, i, j)
        v_post = v_star + (1.0 - kappa) * model.program_view.pair_error(j, i)
        for target, values in zip(arrays, (u, u_star, u_post, v, v_star, v_post), strict=True):
            target[held] = values
    return Interviews(*arrays)
