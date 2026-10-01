"""The database: schema checks, the real/simulated boundary, and the catalog view."""

import pandas as pd
import pytest
from conftest import needs_real_db

from uniadvisor import db as database
from uniadvisor.db import DatabaseError
from uniadvisor.sim import tiny


def _tables():
    t, cdfs, manifest = tiny.tables(seed=0)
    return {k: v.copy() for k, v in t.items()}, cdfs, dict(manifest)


@pytest.mark.parametrize("break_it, message", [
    (lambda t, m: t.update(cutoffs=pd.concat([t["cutoffs"], t["cutoffs"].head(1)])), "rows share a key"),
    (lambda t, m: t["programs"].loc.__setitem__((0, "school_code"), "SIM-NOPE"), "not in schools.school_code"),
    (lambda t, m: t["cutoffs"].loc.__setitem__((0, "provenance"), "guessed"), "provenance: not allowed"),
    (lambda t, m: t["cutoffs"].loc.__setitem__((0, "score"), 31.0), "outside 0-30"),
    (lambda t, m: t.update(quotas=t["quotas"].drop(columns="source")), "missing column"),
    (lambda t, m: t["programs"].loc.__setitem__((0, "reference_combo"), "D01"), "reference_combo"),
    (lambda t, m: t["schools"].loc.__setitem__((0, "school_code"), "HN1"), "starts with SIM-"),
    (lambda t, m: m.update(kind="real"), "simulated row(s) in the real database"),
    (lambda t, m: m.update(kind="real"), "SIM- id(s) in the real database"),
    (lambda t, m: m.pop("generator"), "generator.name and generator.seed"),
    (lambda t, m: t["programs"].loc.__setitem__((0, "major_code"), "74802"), "not a ngành"),
    (lambda t, m: t["programs"].loc.__setitem__((0, "major_code"), "7999999"), "not in majors.code"),
    (lambda t, m: t["programs"].loc.__setitem__((0, "major_code_provenance"), ""), "major_code_provenance must be set"),
    (lambda t, m: t["programs"].loc.__setitem__((0, "field"), "robotics"), "field: not allowed"),
    (lambda t, m: t["majors"].loc.__setitem__((0, "level"), "nganh"), "code length does not match its level"),
])
def test_validation_names_each_problem(break_it, message):
    t, cdfs, manifest = _tables()
    break_it(t, manifest)
    with pytest.raises(DatabaseError, match=message.replace("(", r"\(").replace(")", r"\)")):
        database.from_tables(t, cdfs, manifest)


def test_tiny_round_trips_and_is_reproducible(tmp_path):
    a = tiny.build(tmp_path / "a", seed=1)
    b = tiny.build(tmp_path / "b", seed=1)
    c = tiny.build(tmp_path / "c", seed=2)
    for f in ("programs.csv", "cutoffs.csv", "tuition.csv", "manifest.json"):
        assert (tmp_path / "a" / f).read_bytes() == (tmp_path / "b" / f).read_bytes()
    assert (tmp_path / "a" / "cutoffs.csv").read_bytes() != (tmp_path / "c" / "cutoffs.csv").read_bytes()
    assert a.simulated and a.manifest["generator"] == {"name": "uniadvisor.sim.tiny", "version": tiny.VERSION, "seed": 1}
    assert database.load(tmp_path / "a").catalog.equals(a.catalog)


def test_a_simulated_database_is_refused_where_real_data_is_needed(tmp_path, tiny_db):
    tiny.build(tmp_path / "t")
    with pytest.raises(DatabaseError, match="simulated database"):
        database.load(tmp_path / "t", allow_simulated=False)
    with pytest.raises(DatabaseError, match="needs the real database"):
        database.require_real(tiny_db, "the backtest")
    from uniadvisor.engine.backtest import run
    with pytest.raises(DatabaseError):
        run(save=True, db=tiny_db)


def test_catalog_view(tiny_db):
    cat = tiny_db.catalog.set_index("program_id")
    assert cat.loc["SIM-HN1:IT", "school_name"] == "Trường Đại học Mô phỏng Kỹ thuật"
    assert cat.loc["SIM-HN1:IT", "city"] == "Hà Nội" and cat.loc["SIM-HC1:MD", "city"] == "TP. Hồ Chí Minh"
    assert cat.loc["SIM-HN1:IT", "latest_year"] == 2026 and cat.loc["SIM-HN1:IT", "latest_cutoff"] == 25.5
    assert cat.loc["SIM-HN1:EE", "latest_status"] == "disputed"
    assert cat.loc["SIM-HN2:MKT", "years_with_cutoff"] == 1 and cat.loc["SIM-HN1:IT", "years_with_cutoff"] == 5
    # a fee is simulated, estimated (school median) or missing, and missing means no number at all
    assert cat.loc["SIM-HN1:IT", "tuition_provenance"] == "simulated"
    assert cat.loc["SIM-HN1:CE", "tuition_provenance"] == "estimated" and cat.loc["SIM-HN1:CE", "tuition_min"] == 30e6
    assert cat.loc["SIM-HC1:EDU-MATH", "tuition_provenance"] == "missing" and cat.loc["SIM-HC1:EDU-MATH", "tuition_min"] is None
    assert cat.loc["SIM-HN1:IT", "campus"] is None  # empty cells are None, never "" or NaN
    assert tiny_db.history["SIM-HN2:MKT"] == {2026: 26.0}
    assert tiny_db.combos["D01"] == ["TO", "VA", "N1"]
    assert tiny_db.distributions.method("A00", 2026) == "simulated"


@needs_real_db
def test_real_database_is_valid_and_contains_nothing_simulated():
    db = database.load(allow_simulated=False)
    assert db.kind == "real"
    for name in ("cutoffs", "quotas", "tuition", "distributions"):
        assert "simulated" not in set(db[name].provenance)
    cat = db.catalog
    assert set(cat.tuition_provenance) <= {"observed", "estimated", "missing"}
    assert cat[cat.tuition_provenance == "missing"].tuition_min.isna().all()
    assert db.manifest["counts"]["programs"] == len(cat)
