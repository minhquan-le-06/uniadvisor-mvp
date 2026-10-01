"""Command line.  `uniadvisor --help`

Yearly refresh:  collect -> build -> backtest -> slm-data -> (train on Kaggle) -> app
"""

from __future__ import annotations

import json
import logging
import subprocess
import sys
from pathlib import Path

import typer

from uniadvisor.paths import ARTIFACTS, REPORTS, ROOT

app = typer.Typer(add_completion=False, help="UniAdvisor: university application advisor (THPT exam-score method).")


@app.callback()
def _startup() -> None:
    from uniadvisor.env import load_dotenv

    load_dotenv()  # .env in the project root (git-ignored): API keys etc.


def _log() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)


SCORE_FILES_URL = "https://media.githubusercontent.com/media/sdgedfegw/du-lieu-diem-thi/main/{name}"
SCORE_FILES = {2023: "du_lieu_diem_thi_2023.csv", 2024: "du_lieu_diem_thi_2024.csv",
               2025: "du-lieu-diem-thi-2025-ct2018.csv", 2026: "du_lieu_diem_thi_2026.csv"}


@app.command("fetch-scores")
def fetch_scores(years: str = typer.Option("2023,2024,2025,2026", help="comma list"), force: bool = False) -> None:
    """Download public per-candidate exam scores (github.com/sdgedfegw/du-lieu-diem-thi) into data/inbox/.
    ~80-100 MB per year; kept out of git. Then run `uniadvisor build` and `uniadvisor backtest`."""
    import httpx

    from uniadvisor.paths import INBOX

    INBOX.mkdir(parents=True, exist_ok=True)
    for year in (int(y) for y in years.split(",") if y.strip()):
        name = SCORE_FILES.get(year)
        if name is None:
            raise typer.BadParameter(f"no known score file for {year}; known: {sorted(SCORE_FILES)}")
        dest = INBOX / name
        if dest.exists() and not force:
            print(f"{dest.name}: already there (use --force to download again)")
            continue
        tmp = dest.with_suffix(".part")
        with httpx.stream("GET", SCORE_FILES_URL.format(name=name), follow_redirects=True, timeout=120) as r:
            r.raise_for_status()
            with open(tmp, "wb") as f:
                for chunk in r.iter_bytes(1 << 20):
                    f.write(chunk)
        tmp.replace(dest)
        print(f"{dest.name}: {dest.stat().st_size / 1e6:.0f} MB")


@app.command()
def collect(refresh: bool = False, only: str = typer.Option("", help="comma list: vietnamnet,vnexpress,distributions,tuyensinh247,ads_final")) -> None:
    """Fetch cutoffs, tuition and score distributions (polite, cached)."""
    _log()
    from uniadvisor.collect.run import collect_all

    print(json.dumps(collect_all(refresh=refresh, only=[x for x in only.split(",") if x] or None), indent=1))


@app.command()
def build() -> None:
    """Rebuild distributions, cutoffs and the database (data/db/) from collected data."""
    _log()
    import pandas as pd

    from uniadvisor.build import catalog, cutoffs, distributions
    from uniadvisor.paths import BUILD, INBOX

    built = BUILD / "distributions.csv"
    if not any(INBOX.glob("*.csv")) and built.exists() and (pd.read_csv(built).method == "exact").any():
        # without the per-candidate files a rebuild would replace exact distributions with approximations
        print("distributions: kept (data/inbox/ is empty; run `uniadvisor fetch-scores` to rebuild them exactly)")
    else:
        print("distributions:", distributions.build()["counts"])
    print("cutoffs:", json.dumps({k: v for k, v in cutoffs.build().items() if k != "by_year_status"}, default=str))
    print("catalog:", json.dumps(catalog.build(), default=str))


@app.command()
def backtest() -> None:
    """Backtest the cutoff forecast, fit its parameters, write artifacts/reports/backtest.json."""
    from uniadvisor.engine.backtest import run

    r = run()
    print(json.dumps({"chosen": r["chosen"], "engine": r["engine_pre_results"]["all"],
                      "calibration": {k: r["calibration_cross_fitted"][k] for k in ("brier", "ece", "buckets")}}, indent=1, default=float))


@app.command()
def report() -> None:
    """Write artifacts/reports/data_report.md (coverage, quality, gaps)."""
    from uniadvisor.build.report import build as build_report

    print(build_report())


@app.command("slm-data")
def slm_data(students: int = 4000, programs_per_student: int = 4, seed: int = 13) -> None:
    """Build the synthetic SLM dataset (data/slm/)."""
    from uniadvisor.slm.dataset import build as build_ds

    s = build_ds(students, programs_per_student, seed)
    print(json.dumps({k: (v["examples"] if isinstance(v, dict) and "examples" in v else v) for k, v in s.items()}, indent=1, ensure_ascii=False))


@app.command("slm-train", context_settings={"allow_extra_args": True, "ignore_unknown_options": True})
def slm_train(ctx: typer.Context) -> None:
    """Fine-tune the SLM (all options are passed to uniadvisor.slm.train)."""
    from uniadvisor.slm.train import main

    main(ctx.args)


@app.command("slm-relabel")
def slm_relabel(split: str = "train", limit: int = 2000, samples: int = 3) -> None:
    """Relabel SLM examples with an LLM teacher (Gemini; needs GEMINI_API_KEYS)."""
    from uniadvisor.slm.llm_teacher import relabel

    print(json.dumps(relabel(split, limit, samples), indent=1))


@app.command("slm-eval")
def slm_eval(judge: str = "auto", gold: Path | None = None, limit: int | None = None) -> None:
    """Evaluate a judge on the test split or a human gold file: auto (what the app uses), hybrid, slm or heuristic."""
    from uniadvisor.slm.evaluate import evaluate
    from uniadvisor.slm.infer import LOAD_ERROR, HeuristicJudge, HybridJudge, get_judge, load_slm

    if judge == "heuristic":
        j = HeuristicJudge()
    elif judge in ("slm", "hybrid"):
        slm = load_slm()
        if slm is None and LOAD_ERROR:
            raise typer.BadParameter(f"the SLM files were found but loading failed: {LOAD_ERROR[0]}")
        if slm is None:
            import os

            from uniadvisor.paths import MODELS

            d = Path(os.environ.get("UNIADVISOR_SLM_DIR", MODELS / "slm"))
            found = sorted(str(f.relative_to(d)) for f in d.rglob("*") if f.is_file())[:8] if d.is_dir() else []
            hint = (f"folder does not exist" if not d.is_dir() else
                    f"it contains: {', '.join(found) or 'nothing'}" + (" (unzipped one level too deep?)" if any("/" in f or "\\" in f for f in found) else ""))
            raise typer.BadParameter(f"no trained SLM: need adapter.pt and config.json directly in {d.resolve()}; {hint}"
                                     + (" [UNIADVISOR_SLM_DIR is set]" if "UNIADVISOR_SLM_DIR" in os.environ else ""))
        j = slm if judge == "slm" else HybridJudge(slm)
    elif judge == "auto":
        j = get_judge()
    else:
        raise typer.BadParameter("--judge must be auto, hybrid, slm or heuristic")
    r = evaluate(j, gold=gold, limit=limit)
    out = REPORTS / f"slm_eval_{r['judge']}_{r['split']}.json"
    out.write_text(json.dumps(r, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"judge": r["judge"], "n": r["n"], "overall_accuracy": r["overall_accuracy"], "per_question": r["per_question"]}, indent=1, ensure_ascii=False))


@app.command()
def advise(scores: str = typer.Option(..., help="e.g. TO=8.4,VA=7,LI=8,N1=8.2"), text: str = "", province: str = "",
           area: str = "KV3", category: str = "none", gender: str = "", mock: bool = False, k: int = 10) -> None:
    """Print an application list for one student."""
    from uniadvisor.advisor import advise as run_advise
    from uniadvisor.explain import DISCLAIMER
    from uniadvisor.slm.state import StudentProfile

    sc = {kv.split("=")[0].strip().upper(): float(kv.split("=")[1]) for kv in scores.split(",") if "=" in kv}
    p = StudentProfile(scores=sc, province=province or None, area=area, category=category, gender=gender or None,
                       score_kind="mock" if mock else "actual", free_text=text)
    a = run_advise(p, k_max=k)
    import pandas as pd

    pd.set_option("display.width", 220)
    pd.set_option("display.max_colwidth", 40)
    print(a.table()[["NV", "Mã", "Ngành", "Điểm xét", "Dự báo điểm chuẩn", "P(đỗ)", "Nhóm", "Độ phù hợp (u)", "Độ tin cậy"]].to_string(index=False))
    print("\n" + a.summary)
    for q in a.clarify:
        print("? " + q["ask"])
    print("\n" + DISCLAIMER)


@app.command("kaggle-bundle")
def kaggle_bundle(out: Path = ARTIFACTS / "uniadvisor_kaggle_bundle.zip") -> None:
    """Zip the code + SLM dataset for upload as a Kaggle Dataset (see docs/kaggle/README.md)."""
    import zipfile

    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(ROOT / "pyproject.toml", "uniadvisor/pyproject.toml")
        for base in (ROOT / "src", ROOT / "config", ROOT / "data" / "slm"):
            for f in base.rglob("*"):
                if f.is_file() and "__pycache__" not in f.parts and "llm_cache" not in f.parts and f.name != "gemini_keys.txt":
                    z.write(f, "uniadvisor/" + f.relative_to(ROOT).as_posix())
    print(f"wrote {out} ({out.stat().st_size / 1e6:.1f} MB)")


@app.command()
def serve(port: int = 8000) -> None:
    """Run the HTTP API."""
    subprocess.run([sys.executable, "-m", "uvicorn", "uniadvisor.api:app", "--port", str(port)], check=False)


@app.command("app")
def run_app(port: int = 8501) -> None:
    """Run the Vietnamese chat UI (Streamlit)."""
    subprocess.run([sys.executable, "-m", "streamlit", "run", str(ROOT / "app" / "streamlit_app.py"), "--server.port", str(port)], check=False)


@app.command()
def label(port: int = 8502) -> None:
    """Label the SLM gold set by hand (writes data/slm/gold_labeled.csv after every answer)."""
    subprocess.run([sys.executable, "-m", "streamlit", "run", str(ROOT / "app" / "label_gold.py"), "--server.port", str(port)], check=False)


@app.command("gold-llm")
def gold_llm(models: str = typer.Option("gemini-3.5-flash,gemini-3.5-flash-lite", help="tried in order, each with every key"),
             delay: float = typer.Option(4.0, help="seconds between requests"),
             limit: int | None = typer.Option(None, help="at most this many requests (2 rows each)"),
             redo: str = typer.Option("", help="comma list of questions to relabel if labelled before rubric versions "
                                               "were recorded (e.g. ability_fit); rows with an old version tag are redone anyway")) -> None:
    """Label the gold set with Gemini -> data/slm/gold_llm.csv (keys: GEMINI_API_KEYS=k1,k2 or data/slm/gemini_keys.txt)."""
    _log()
    from uniadvisor.slm import llm_label

    stats = llm_label.run(llm_label.load_keys(), models=tuple(m.strip() for m in models.split(",") if m.strip()),
                          delay=delay, limit=limit, redo=tuple(q.strip() for q in redo.split(",") if q.strip()))
    print(json.dumps(stats, indent=1))
    table = llm_label.agreement() if llm_label.OUT.exists() else None
    if table is not None and len(table):
        print(table.to_string(index=False))


@app.command("check-db")
def check_db(path: Path | None = typer.Argument(None, help="database folder (default: data/db/ or UNIADVISOR_DB)")) -> None:
    """Load a database, check it against the schema, and print what it holds."""
    from uniadvisor.db import load

    db = load(path)
    cat = db.catalog
    print(json.dumps({"path": str(db.path), "kind": db.kind, "name": db.name, "counts": db.manifest.get("counts"),
                      "tuition": cat.tuition_provenance.value_counts().to_dict(),
                      "provenance": {name: db[name].provenance.value_counts().to_dict()
                                     for name in ("cutoffs", "quotas", "tuition", "distributions")}},
                     indent=1, ensure_ascii=False))


sim_app = typer.Typer(help="Simulated databases in data/sim/<name>/ (same schema, SIM- ids; never the real data).")
app.add_typer(sim_app, name="sim")


@sim_app.command("tiny")
def sim_tiny(seed: int = 0, out: Path | None = typer.Option(None, help="default: data/sim/tiny")) -> None:
    """A hand-sized world (3 schools, 12 programs) for tests. Try the app on it:
    UNIADVISOR_DB=data/sim/tiny uniadvisor app"""
    from uniadvisor.paths import SIM
    from uniadvisor.sim import tiny

    db = tiny.build(out or SIM / "tiny", seed)
    print(f"wrote {db.path}: {db.manifest['counts']}")


@sim_app.command("season")
def sim_season(seed: int = 0, reform: bool = typer.Option(False, help="add the 2025-like reform-year drop"),
               out: Path | None = typer.Option(None, help="default: data/sim/<generated name>")) -> None:
    """The real database plus one simulated admission season (correlated shocks), for engine checks."""
    from uniadvisor.db import get_db, write
    from uniadvisor.paths import SIM
    from uniadvisor.sim import season

    sim = season.simulate(get_db(), seed=seed, reform=reform)
    db = write(out or SIM / sim.name, sim)
    print(f"wrote {db.path}: {db.manifest['generator']}")


if __name__ == "__main__":
    app()
