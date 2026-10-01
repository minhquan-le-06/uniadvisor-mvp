"""The real database plus one simulated admission season: a known truth to test the engine against.

Next year's cutoff of each program = its latest cutoff + a shock shared by every program that year
+ a shock shared by the programs of one school + the program's own noise:

    c[p, T] = c[p, T-1] + year + school[s(p)] + e[p]

The spreads come from the backtest (artifacts/reports/backtest_residuals.csv, 2,208 forecasts of 2025 and
2026): of the residual variance (3.42 points^2), 1.54 is shared within a school-year, 0.18 of it year-wide.
The engine's optimizer treats programs as independent; a season drawn here, where they are not, shows what
that costs. `reform=True` adds the 2025 reform-year drop (cutoffs fell 0.95 points below forecast on average).

Everything copied from the real database keeps its provenance; only the new season's cutoffs are
`simulated`. Ids get the SIM- prefix (SIM-BKA:IT1), so nothing here can join a real row.

    from unidata.sim import season
    sim = season.simulate(get_db(), seed=3)            # in memory: one draw
    season.simulate(get_db(), seed=3, out=SIM / "season-3")
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from unidata import db as database
from unidata.db.schema import SIM_PREFIX

VERSION = 1


@dataclass(frozen=True)
class SeasonParams:
    year_sd: float = 0.43        # sqrt(0.18): shared by every program in the season
    school_sd: float = 1.16      # sqrt(1.54 - 0.18): shared by the programs of one school
    program_sd: float = 1.37     # sqrt(3.42 - 1.54): each program's own noise
    reform_shift: float = -0.95  # added to the year shock when reform=True (2025: mean residual -0.95)


def _prefix(s: pd.Series) -> pd.Series:
    return SIM_PREFIX + s.astype(str)


def simulate(real: database.Database, seed: int = 0, year: int | None = None, reform: bool = False,
             params: SeasonParams = SeasonParams(), out: Path | str | None = None) -> database.Database:
    database.require_real(real, "simulating a season (it starts from real cutoffs)")
    rng = np.random.default_rng(seed)
    t = {name: df.copy() for name, df in real.tables.items()}
    for name in ("schools", "programs"):
        t[name]["school_code"] = _prefix(t[name].school_code)
    for name in ("programs", "cutoffs", "quotas", "tuition"):
        t[name]["program_id"] = _prefix(t[name].program_id)

    cut = t["cutoffs"]
    latest = cut[cut.combo == ""].sort_values("year").groupby("program_id").tail(1)
    year = year or int(latest.year.max()) + 1
    latest = latest[latest.year == year - 1]          # programs that had a cutoff last year
    schools = latest.program_id.str.split(":").str[0]
    year_shock = rng.normal(params.reform_shift if reform else 0.0, params.year_sd)
    school_shock = {s: rng.normal(0.0, params.school_sd) for s in sorted(schools.unique())}
    noise = rng.normal(0.0, params.program_sd, len(latest))
    new = latest.assign(
        year=year, score=np.round(np.clip(latest.score.to_numpy() + year_shock + schools.map(school_shock).to_numpy() + noise, 0, 30), 2),
        status="", n_sources=0, lowest_of_several=False, provenance="simulated", source="unidata.sim.season", url="")
    t["cutoffs"] = pd.concat([cut, new], ignore_index=True)

    manifest = {"kind": "simulated", "name": f"season-{year}-seed{seed}" + ("-reform" if reform else ""), "latest_year": year,
                "description": f"the real database plus a simulated {year} season ({len(new)} cutoffs)",
                "generator": {"name": "unidata.sim.season", "version": VERSION, "seed": seed, "reform": reform,
                              "params": asdict(params), "year_shock": round(float(year_shock), 4)},
                "based_on": {"name": real.name, "counts": real.manifest.get("counts", {})}}
    if out:
        return database.write(out, t, real.cdfs, manifest)
    return database.from_tables(t, real.cdfs, manifest)
