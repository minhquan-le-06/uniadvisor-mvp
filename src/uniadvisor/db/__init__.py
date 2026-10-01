"""The database every module reads: load it, check it, write it.

    from uniadvisor.db import get_db
    db = get_db()                 # data/db/, or the folder in UNIADVISOR_DB
    db.catalog                    # one row per program, joined with its school, latest cutoff, quota and fee
    db.history["BKA:IT1"]         # {year: cutoff}
    db.combos["A00"]              # ["TO", "LI", "HO"]
    db.distributions              # engine.dist.ScoreDistributions

Tests build a small simulated database (uniadvisor.sim.tiny) and pass it in, or make it the default with
`set_default`. The schema is in db/schema.py; docs/DATA.md explains it.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path

import numpy as np
import pandas as pd

from uniadvisor.db.schema import (CDF_FILE, KINDS, MANIFEST_FILE, PROVENANCE, SCHEMA_VERSION, SIM_PREFIX, TABLES,
                                  Table)

__all__ = ["Database", "DatabaseError", "load", "write", "from_tables", "validate", "get_db", "set_default", "require_real",
           "TABLES", "PROVENANCE", "SCHEMA_VERSION", "SIM_PREFIX"]


class DatabaseError(ValueError):
    def __init__(self, where: str, problems: list[str]):
        self.problems = problems
        shown = "\n  ".join(problems[:20]) + (f"\n  ... and {len(problems) - 20} more" if len(problems) > 20 else "")
        super().__init__(f"{where}: {len(problems)} problem(s)\n  {shown}")


# ------------------------------------------------------------------ the database object
@dataclass
class Database:
    tables: dict[str, pd.DataFrame]
    cdfs: pd.DataFrame                       # combo, year, g0..g600
    manifest: dict
    path: Path | None = None

    @property
    def kind(self) -> str:
        return self.manifest["kind"]

    @property
    def name(self) -> str:
        return self.manifest.get("name", "")

    @property
    def simulated(self) -> bool:
        return self.kind == "simulated"

    def __getitem__(self, table: str) -> pd.DataFrame:
        return self.tables[table]

    @cached_property
    def combos(self) -> dict[str, list[str]]:
        c = self.tables["combos"]
        return {r.combo: [r.subject_1, r.subject_2, r.subject_3] for r in c.itertuples(index=False)}

    @cached_property
    def history(self) -> dict[str, dict[int, float]]:
        """Program-wide cutoffs per program: {program_id: {year: score}}."""
        c = self.tables["cutoffs"]
        c = c[c.combo == ""]
        return {pid: dict(zip(g.year.astype(int), g.score.astype(float))) for pid, g in c.groupby("program_id")}

    @cached_property
    def distributions(self):  # noqa: ANN201 - engine.dist.ScoreDistributions (imported late: engine imports db)
        from uniadvisor.engine.dist import ScoreDistributions

        return ScoreDistributions.from_frames(self.cdfs, self.tables["distributions"])

    @cached_property
    def catalog(self) -> pd.DataFrame:
        """One row per program with what the advisor shows and judges: school, city, field name, latest
        cutoff and its status, years of history, latest quota, latest fee and whether it is observed,
        estimated or missing. Empty cells are None."""
        from uniadvisor.build.fields import FIELDS

        t = self.tables
        p = t["programs"].rename(columns={"name": "program_name"})
        s = t["schools"][["school_code", "name", "city"]].rename(columns={"name": "school_name"})
        p = p.merge(s, on="school_code", how="left")
        cut = t["cutoffs"][t["cutoffs"].combo == ""].sort_values(["program_id", "year"])
        last = cut.groupby("program_id").tail(1).set_index("program_id")
        p["latest_year"] = p.program_id.map(last.year)
        p["latest_cutoff"] = p.program_id.map(last.score)
        p["latest_status"] = p.program_id.map(last.status)
        p["years_with_cutoff"] = p.program_id.map(cut.groupby("program_id").year.nunique()).fillna(0).astype(int)
        q = t["quotas"].sort_values(["program_id", "year"]).groupby("program_id").tail(1).set_index("program_id")
        p["quota"] = p.program_id.map(q.quota)
        fee = t["tuition"].sort_values(["program_id", "year"]).groupby("program_id").tail(1).set_index("program_id")
        p["tuition_min"] = p.program_id.map(fee.min_vnd)
        p["tuition_max"] = p.program_id.map(fee.max_vnd)
        p["tuition_provenance"] = p.program_id.map(fee.provenance).fillna("missing")
        p["field_name"] = p.field.map(FIELDS).fillna("")
        # MOET's names for the program's ngành, nhóm ngành and lĩnh vực
        names = dict(zip(t["majors"].code, t["majors"].name))
        p["major_name"] = p.major_code.map(names)
        p["moet_group_code"] = p.major_code.str[:5].where(p.major_code != "", "")
        p["moet_group"] = p.moet_group_code.map(names)
        p["moet_field_code"] = p.major_code.str[:3].where(p.major_code != "", "")
        p["moet_field"] = p.moet_field_code.map(names)
        p = p.replace("", np.nan)
        return p.astype(object).where(p.notna(), None)


# ------------------------------------------------------------------ reading
def _convert(df: pd.DataFrame, t: Table) -> tuple[pd.DataFrame, list[str]]:
    """CSV strings -> typed columns. Empty cells: '' for str, NaN for numbers. Returns problems found."""
    problems = []
    out = df.copy()
    for c in t.columns:
        if c.name not in out.columns:
            continue
        s = out[c.name].fillna("").astype(str).str.strip()
        blank = s == ""
        if c.required and blank.any():
            problems.append(f"{t.name}.{c.name}: {int(blank.sum())} empty cell(s) in a required column")
        if c.type in ("int", "float"):
            v = pd.to_numeric(s.where(~blank), errors="coerce")
            bad = v.isna() & ~blank
            if bad.any():
                problems.append(f"{t.name}.{c.name}: not a number: {s[bad].head(3).tolist()}")
            if c.type == "int" and not blank.any() and not bad.any():
                v = v.astype(int)
            out[c.name] = v
        elif c.type == "bool":
            m = s.str.lower().map({"true": True, "false": False, "1": True, "0": False})
            if (m.isna() & ~blank).any():
                problems.append(f"{t.name}.{c.name}: not true/false: {s[m.isna() & ~blank].head(3).tolist()}")
            out[c.name] = m.fillna(False).astype(bool)
        else:
            out[c.name] = s
    return out, problems


def _read_folder(path: Path) -> tuple[dict, dict[str, pd.DataFrame], pd.DataFrame | None, list[str]]:
    problems = []
    mpath = path / MANIFEST_FILE
    manifest = json.loads(mpath.read_text(encoding="utf-8")) if mpath.exists() else {}
    if not manifest:
        problems.append(f"{MANIFEST_FILE} is missing")
    tables = {}
    for name, t in TABLES.items():
        f = path / t.file
        if not f.exists():
            problems.append(f"{t.file} is missing")
            tables[name] = pd.DataFrame(columns=[c.name for c in t.columns])
            continue
        raw = pd.read_csv(f, dtype=str, keep_default_na=False, encoding="utf-8")
        tables[name], p = _convert(raw, t)
        problems += p
    cdfs = pd.read_parquet(path / CDF_FILE) if (path / CDF_FILE).exists() else None
    if cdfs is None:
        problems.append(f"{CDF_FILE} is missing")
    return manifest, tables, cdfs, problems


def default_path() -> Path:
    from uniadvisor.paths import DB

    return Path(os.environ.get("UNIADVISOR_DB") or DB)


def load(path: Path | str | None = None, *, allow_simulated: bool = True) -> Database:
    """Read and check a database folder. Raises DatabaseError listing every problem found."""
    path = Path(path) if path else default_path()
    if not path.is_dir():
        raise DatabaseError(str(path), ["folder does not exist (run `uniadvisor build`, or `uniadvisor sim tiny` for a test database)"])
    manifest, tables, cdfs, problems = _read_folder(path)
    if not problems:
        problems = validate(tables, cdfs, manifest)
    if problems:
        raise DatabaseError(str(path), problems)
    db = Database(tables, cdfs, manifest, path)
    if db.simulated and not allow_simulated:
        raise DatabaseError(str(path), ["this is a simulated database; this step needs the real one (data/db/)"])
    return db


_DEFAULT: list[Database] = []


def get_db() -> Database:
    """The database the app, API and CLI use: the one given to `set_default`, else data/db/ (or UNIADVISOR_DB)."""
    if not _DEFAULT:
        _DEFAULT.append(load())
    return _DEFAULT[0]


def set_default(db: Database | None) -> None:
    """Make `db` what get_db() returns (None: go back to reading data/db/ on next use). For tests and demos."""
    _DEFAULT.clear()
    if db is not None:
        _DEFAULT.append(db)


def require_real(db: Database, what: str) -> None:
    if db.simulated:
        raise DatabaseError(str(db.path or db.name), [f"{what} needs the real database, not the simulated '{db.name}'"])


# ------------------------------------------------------------------ checking
def validate(tables: dict[str, pd.DataFrame], cdfs: pd.DataFrame | None, manifest: dict) -> list[str]:
    """Every rule the schema states, on typed tables. Empty list = valid."""
    problems: list[str] = []
    if manifest.get("schema_version") != SCHEMA_VERSION:
        problems.append(f"manifest schema_version {manifest.get('schema_version')!r}, expected {SCHEMA_VERSION}")
    kind = manifest.get("kind")
    if kind not in KINDS:
        problems.append(f"manifest kind {kind!r}, expected one of {KINDS}")
    if kind == "simulated" and not {"name", "seed"} <= set(manifest.get("generator") or {}):
        problems.append("a simulated database's manifest needs generator.name and generator.seed")

    for name, t in TABLES.items():
        df = tables.get(name)
        if df is None:
            problems.append(f"table {name} is missing")
            continue
        cols = [c.name for c in t.columns]
        if missing := [c for c in cols if c not in df.columns]:
            problems.append(f"{name}: missing column(s) {missing}")
            continue
        if extra := [c for c in df.columns if c not in cols]:
            problems.append(f"{name}: unknown column(s) {extra} (add them to db/schema.py first)")
        for c in t.columns:
            if c.values:
                bad = sorted({v for v in df[c.name] if v != "" and v not in c.values})
                if bad:
                    problems.append(f"{name}.{c.name}: not allowed {bad[:5]}; allowed {list(c.values)}")
        dup = df.duplicated(list(t.key), keep=False)
        if dup.any():
            problems.append(f"{name}: {int(dup.sum())} rows share a key {t.key}, e.g. {df[dup][list(t.key)].head(2).to_dict('records')}")
        for col, other, ocol in t.refs:
            target = tables.get(other)
            if target is None or ocol not in target.columns:
                continue
            vals = df[col][df[col] != ""]
            bad = sorted(set(vals) - set(target[ocol]))
            if bad:
                problems.append(f"{name}.{col}: {len(bad)} value(s) not in {other}.{ocol}, e.g. {bad[:3]}")
        if "provenance" in df.columns:
            sim = df.provenance == "simulated"
            if kind == "real" and sim.any():
                problems.append(f"{name}: {int(sim.sum())} simulated row(s) in the real database")
        for idcol in ("school_code", "program_id"):
            if idcol in df.columns and name in ("schools", "programs"):
                marked = df[idcol].str.startswith(SIM_PREFIX)
                if kind == "real" and marked.any():
                    problems.append(f"{name}.{idcol}: {int(marked.sum())} {SIM_PREFIX} id(s) in the real database")
                if kind == "simulated" and (~marked).any():
                    problems.append(f"{name}.{idcol}: every id in a simulated database starts with {SIM_PREFIX}, "
                                    f"e.g. not {df[idcol][~marked].head(2).tolist()}")
    if problems:
        return problems

    p, c = tables["programs"], tables["cutoffs"]
    known = set(tables["combos"].combo)
    for r in p.itertuples(index=False):
        combos = [x for x in r.combos.split(";") if x]
        if r.reference_combo not in combos:
            problems.append(f"programs {r.program_id}: reference_combo {r.reference_combo} is not in its combos")
        if unknown := [x for x in combos if x not in known]:
            problems.append(f"programs {r.program_id}: combos not in the combos table: {unknown}")
    if not c.score.between(0, 30).all():
        problems.append(f"cutoffs: {int((~c.score.between(0, 30)).sum())} score(s) outside 0-30")
    real_rows = c[c.provenance != "simulated"]
    if (real_rows.status == "").any():
        problems.append("cutoffs: status is empty on rows that are not simulated")
    f = tables["tuition"]
    if ((f.min_vnd <= 0) | (f.max_vnd < f.min_vnd)).any():
        problems.append("tuition: need 0 < min_vnd <= max_vnd")
    if (tables["quotas"].quota <= 0).any():
        problems.append("quotas: quota must be positive")
    m = tables["majors"]
    lengths = {"linh_vuc": 3, "nganh": 7, "nhom_nganh": 5}
    if (bad := m[(m.code.str.len() != m.level.map(lengths)) | ~m.code.str.fullmatch(r"\d+")]).size:
        problems.append(f"majors: code length does not match its level, e.g. {bad.code.head(3).tolist()}")
    if (bad := m[(m.parent != "") & (m.code.str[:-2] != m.parent)]).size:
        problems.append(f"majors: parent is not the code minus its last 2 digits, e.g. {bad.code.head(3).tolist()}")
    nganh = set(m.code[m.level == "nganh"])
    if bad := sorted(set(p.major_code[p.major_code != ""]) - nganh):
        problems.append(f"programs.major_code: not a ngành (7-digit) code: {bad[:3]}")
    if (p[(p.major_code == "") != (p.major_code_provenance == "")]).size:
        problems.append("programs: major_code_provenance must be set exactly when major_code is")
    no_cut = sorted(set(p.program_id) - set(c.program_id))
    if no_cut:
        problems.append(f"programs: {len(no_cut)} program(s) without any cutoff, e.g. {no_cut[:3]}")

    if cdfs is not None:
        d = tables["distributions"]
        keys = set(zip(d.combo, d.year.astype(int)))
        ckeys = set(zip(cdfs.combo, cdfs.year.astype(int)))
        if keys != ckeys:
            problems.append(f"distributions: {len(keys ^ ckeys)} (combo, year) pairs differ between "
                            f"distributions.csv and {CDF_FILE}")
        grid = cdfs[[g for g in cdfs.columns if g not in ("combo", "year")]].to_numpy(float)
        if grid.size and ((grid < -1e-9).any() or (grid > 1 + 1e-9).any() or (np.diff(grid, axis=1) < -1e-9).any()
                          or not np.allclose(grid[:, -1], 1.0)):
            problems.append(f"{CDF_FILE}: every row must be a CDF (0..1, non-decreasing, ends at 1)")
        if missing := sorted(set(p.reference_combo) - {combo for combo, _ in ckeys}):
            problems.append(f"distributions: no CDF for reference combo(s) {missing[:5]}")
    return problems


# ------------------------------------------------------------------ writing
def from_tables(tables: dict[str, pd.DataFrame], cdfs: pd.DataFrame, manifest: dict) -> Database:
    """A checked database in memory, from plain DataFrames (any dtypes; None/NaN = empty). Rows are sorted by
    key. Raises DatabaseError listing every problem. `write` saves one; simulations use this directly."""
    manifest = {"schema_version": SCHEMA_VERSION, **{k: v for k, v in manifest.items() if k != "counts"}}
    typed, problems = {}, []
    for name, t in TABLES.items():
        cols = [c.name for c in t.columns]
        df = tables.get(name, pd.DataFrame(columns=cols))
        if missing := [c for c in cols if c not in df.columns]:
            problems.append(f"{name}: missing column(s) {missing}")
            continue
        df = df[cols].astype(object)
        df = df.where(df.notna(), "").astype(str)
        df, p = _convert(df, t)
        typed[name] = df.sort_values(list(t.key), kind="stable").reset_index(drop=True)
        problems += p
    cdfs = cdfs.sort_values(["combo", "year"]).reset_index(drop=True)
    problems = problems or validate(typed, cdfs, manifest)
    if problems:
        raise DatabaseError(f"database '{manifest.get('name', '?')}'", problems)
    manifest["counts"] = {name: len(typed[name]) for name in TABLES}
    return Database(typed, cdfs, manifest)


def write(path: Path | str, tables: dict[str, pd.DataFrame] | Database, cdfs: pd.DataFrame | None = None,
          manifest: dict | None = None) -> Database:
    """Check, then write a database folder (rows sorted by key, so rebuilds diff cleanly). Returns it loaded.
    Pass either a Database or (tables, cdfs, manifest)."""
    path = Path(path)
    db = tables if isinstance(tables, Database) else from_tables(tables, cdfs, manifest)
    path.mkdir(parents=True, exist_ok=True)
    for name, t in TABLES.items():
        db.tables[name].to_csv(path / t.file, index=False, encoding="utf-8", lineterminator="\n")
    db.cdfs.to_parquet(path / CDF_FILE, index=False)
    (path / MANIFEST_FILE).write_text(json.dumps(db.manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    return load(path)
