"""The database schema: the tables the app, engine and SLM read, their columns, keys and allowed values.

A database is a folder: one CSV per table, the score distributions' CDFs in `distributions.parquet`, and
`manifest.json`. The real one is data/db/ (written by `uniadvisor build`); simulated ones live in
data/sim/<name>/ with the same schema. docs/DATA.md explains the tables for people; this module is what
`uniadvisor.db.load` checks.

Every fact (a cutoff, a quota, a fee, a distribution) carries a `provenance`:
  observed   published by a source (`source` names it, `url` links it when there is one)
  derived    a fixed rule applied to observed values (exact distributions from per-candidate scores)
  estimated  a model fills a missing real-world value; its error is measured; students see "ước tính"
  simulated  made up from scratch to train or test; never in the real database
A missing fact has no row (no fee row = tuition unknown), so "missing" is never a provenance.
"""

from __future__ import annotations

from dataclasses import dataclass

SCHEMA_VERSION = 1
PROVENANCE = ("observed", "derived", "estimated", "simulated")
KINDS = ("real", "simulated")
SIM_PREFIX = "SIM-"  # every school_code / program_id in a simulated database starts with it


@dataclass(frozen=True)
class Column:
    name: str
    type: str = "str"                       # str | int | float | bool
    required: bool = True                   # False: the cell may be empty
    values: tuple[str, ...] | None = None   # allowed values (empty allowed when not required)
    doc: str = ""


@dataclass(frozen=True)
class Table:
    name: str
    columns: tuple[Column, ...]
    key: tuple[str, ...]
    refs: tuple[tuple[str, str, str], ...] = ()   # (column, other table, other column)
    doc: str = ""

    @property
    def file(self) -> str:
        return f"{self.name}.csv"

    def column(self, name: str) -> Column:
        return next(c for c in self.columns if c.name == name)


def _provenance() -> Column:
    return Column("provenance", values=PROVENANCE, doc="observed | derived | estimated | simulated")


PROGRAM_KINDS = ("standard", "high_quality", "advanced", "international")
CUTOFF_STATUS = ("confirmed_2_sources", "disputed", "single_source")
DIST_METHODS = ("exact", "observed", "synthesized", "anchored", "year_shift", "simulated")

TABLES: dict[str, Table] = {t.name: t for t in (
    Table("schools", key=("school_code",), doc="universities in scope", columns=(
        Column("school_code", doc="ministry school code, e.g. BKA"),
        Column("name"),
        Column("short_name", required=False),
        Column("city", doc="Hà Nội | TP. Hồ Chí Minh"),
        Column("website", required=False),
        Column("address", required=False),
    )),
    Table("programs", key=("program_id",), refs=(("school_code", "schools", "school_code"), ("reference_combo", "combos", "combo")),
          doc="programs admitting by THPT exam score on the 30-point scale", columns=(
        Column("program_id", doc="<school_code>:<program code>"),
        Column("school_code"),
        Column("program_code", required=False),
        Column("name"),
        Column("major_code", required=False, doc="7-digit ministry major code when known"),
        Column("field", required=False, doc="one of build.fields.FIELDS"),
        Column("kind", values=PROGRAM_KINDS),
        Column("campus", required=False, doc="branch campus, empty = main campus"),
        Column("combos", doc="exam combinations accepted, ';'-separated"),
        Column("reference_combo", doc="the combination whose distribution places the cutoff"),
        Column("conditions", required=False, doc="special conditions, ' | '-separated"),
        Column("source_url", required=False),
    )),
    Table("cutoffs", key=("program_id", "year", "combo"), refs=(("program_id", "programs", "program_id"),),
          doc="admission cutoffs, 30-point scale; combo empty = the program's single cutoff", columns=(
        Column("program_id"),
        Column("year", "int"),
        Column("combo", required=False, doc="empty: applies to every combination of the program"),
        Column("score", "float"),
        Column("status", required=False, values=CUTOFF_STATUS, doc="agreement between sources; empty when simulated"),
        Column("n_sources", "int"),
        Column("lowest_of_several", "bool", doc="the source listed several cutoffs (per combination or campus); the lowest is kept"),
        _provenance(),
        Column("source", doc="source id (config/sources.yaml) or generator name"),
        Column("url", required=False),
    )),
    Table("quotas", key=("program_id", "year"), refs=(("program_id", "programs", "program_id"),),
          doc="admission quotas (chỉ tiêu)", columns=(
        Column("program_id"), Column("year", "int"), Column("quota", "int"), _provenance(), Column("source"),
    )),
    Table("tuition", key=("program_id", "year"), refs=(("program_id", "programs", "program_id"),),
          doc="tuition per academic year in VND; no row = unknown", columns=(
        Column("program_id"),
        Column("year", "int"),
        Column("min_vnd", "float"),
        Column("max_vnd", "float"),
        _provenance(),
        Column("method", required=False, doc="how an estimate was made, e.g. school_median"),
        Column("source", required=False),
    )),
    Table("combos", key=("combo",), doc="exam-only subject combinations (tổ hợp), all weights 1", columns=(
        Column("combo"), Column("subject_1"), Column("subject_2"), Column("subject_3"),
    )),
    Table("distributions", key=("combo", "year"), refs=(("combo", "combos", "combo"),),
          doc="score distribution metadata; the CDFs are in distributions.parquet", columns=(
        Column("combo"),
        Column("year", "int"),
        Column("method", values=DIST_METHODS, doc="how the CDF was built (engine/dist.py)"),
        _provenance(),
        Column("n", "float", required=False, doc="candidates behind it, when known"),
        Column("note", required=False),
        Column("mean", "float"), Column("p50", "float"), Column("p75", "float"), Column("p90", "float"),
    )),
)}

CDF_FILE = "distributions.parquet"   # combo, year, g0..g600: P(total <= 0.05 * i)
MANIFEST_FILE = "manifest.json"
