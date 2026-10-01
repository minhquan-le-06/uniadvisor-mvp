"""Simulated seasons: the real database plus one made-up year, with correlated shocks."""

import numpy as np
import pytest
from conftest import needs_real_db

from uniadvisor.db import DatabaseError, get_db
from uniadvisor.sim import season


def test_a_season_starts_from_real_data_only(tiny_db):
    with pytest.raises(DatabaseError, match="needs the real database"):
        season.simulate(tiny_db)


@needs_real_db
def test_season_adds_one_simulated_year_and_keeps_the_rest():
    real = get_db()
    sim = season.simulate(real, seed=1)
    assert sim.simulated and sim.manifest["generator"]["seed"] == 1
    assert sim["programs"].program_id.str.startswith("SIM-").all()
    c = sim["cutoffs"]
    new = c[c.provenance == "simulated"]
    assert set(new.year) == {2027} and (c[c.year < 2027].provenance == "observed").all()
    assert len(new) == sum(1 for h in real.history.values() if 2026 in h)
    assert len(c) - len(new) == len(real["cutoffs"])                 # every real row is kept
    pid = next(iter(real.history))
    assert sim.history["SIM-" + pid].items() >= real.history[pid].items()  # history kept, one year added
    again = season.simulate(real, seed=1)
    assert again["cutoffs"].equals(c)                                 # same seed, same season


@needs_real_db
def test_reform_shifts_every_cutoff_down_and_school_shocks_are_shared():
    real = get_db()
    calm, reform = season.simulate(real, seed=4), season.simulate(real, seed=4, reform=True)
    a = calm["cutoffs"].query("year == 2027").set_index("program_id").score
    b = reform["cutoffs"].query("year == 2027").set_index("program_id").score
    inside = (a > 1) & (a < 29) & (b > 1) & (b < 29)                 # away from the 0-30 clip
    assert np.allclose((b - a)[inside], -0.95, atol=0.011)
    # no year or program noise: every program of a school moves by the same amount
    only_school = season.simulate(real, seed=4, params=season.SeasonParams(year_sd=0, program_sd=0))
    s = only_school["cutoffs"]
    new = s[s.year == 2027].set_index("program_id").score
    last = {f"SIM-{pid}": h[2026] for pid, h in real.history.items() if 2026 in h}
    moved = (new - new.index.map(last)).round(2)
    per_school = moved.groupby(moved.index.str.split(":").str[0]).nunique()
    assert (per_school <= 2).all()                                    # one value per school (rounding can split it in two)
