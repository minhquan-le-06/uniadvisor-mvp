"""Run every collector for the schools in config/scope.yaml and write data/collected/*.csv."""

from __future__ import annotations

import logging

import pandas as pd
import yaml

from uniadvisor.collect import ads_final, moet, tuyensinh247, vietnamnet, vnexpress
from uniadvisor.fetch import BlockedByRobots, PoliteClient
from uniadvisor.paths import COLLECTED, CONFIG, ensure_dirs

log = logging.getLogger(__name__)


def load_scope() -> dict:
    return yaml.safe_load((CONFIG / "scope.yaml").read_text(encoding="utf-8"))


def candidate_codes(scope: dict) -> list[str]:
    return [c for codes in scope["candidates"].values() for c in codes]


def collect_all(refresh: bool = False, only: list[str] | None = None, codes: list[str] | None = None) -> dict[str, int]:
    ensure_dirs()
    scope = load_scope()
    codes = codes or candidate_codes(scope)
    years = scope["history_years"]
    client = PoliteClient(refresh=refresh)
    todo = set(only or ["vietnamnet", "vnexpress", "distributions", "tuyensinh247", "ads_final", "moet"])
    counts: dict[str, int] = {}

    if "distributions" in todo:
        combos = pd.DataFrame(vnexpress.combo_histograms(client))
        subjects = pd.DataFrame(vnexpress.subject_histograms(client))
        combos.to_csv(COLLECTED / "vnexpress_combo_hist.csv", index=False, encoding="utf-8")
        subjects.to_csv(COLLECTED / "vnexpress_subject_hist.csv", index=False, encoding="utf-8")
        counts["combo_hist_rows"], counts["subject_hist_rows"] = len(combos), len(subjects)

    if "vnexpress" in todo:
        rows, ids = [], []
        for i, code in enumerate(codes, 1):
            try:
                vid, name = vnexpress.find_school_id(client, code)
                ids.append({"school_code": code, "vne_id": vid, "vne_name": name})
                if vid is None:
                    log.warning("vnexpress: no id for %s", code)
                    continue
                for y in [y for y in years if y >= 2025]:
                    rows += list(vnexpress.school_year_rows(client, code, vid, y))
            except BlockedByRobots as e:
                log.warning("robots.txt blocks %s", e)
            log.info("vnexpress %d/%d %s rows=%d", i, len(codes), code, len(rows))
        pd.DataFrame(ids).to_csv(COLLECTED / "vnexpress_school_ids.csv", index=False, encoding="utf-8")
        pd.DataFrame(rows).to_csv(COLLECTED / "vnexpress_cutoffs.csv", index=False, encoding="utf-8")
        counts["vnexpress_rows"] = len(rows)

    if "vietnamnet" in todo:
        rows = []
        for i, code in enumerate(codes, 1):
            for y in years:
                try:
                    rows += list(vietnamnet.school_year_rows(client, code, y))
                except BlockedByRobots as e:
                    log.warning("robots.txt blocks %s", e)
            log.info("vietnamnet %d/%d %s rows=%d", i, len(codes), code, len(rows))
        pd.DataFrame(rows).to_csv(COLLECTED / "vietnamnet_cutoffs.csv", index=False, encoding="utf-8")
        counts["vietnamnet_rows"] = len(rows)

    if "tuyensinh247" in todo:
        pages = tuyensinh247.school_pages(codes)
        rows = []
        for i, code in enumerate(codes, 1):
            if code not in pages:
                log.warning("tuyensinh247: no page for %s", code)
                continue
            try:
                rows += list(tuyensinh247.school_rows(client, code, pages[code]))
            except BlockedByRobots as e:
                log.warning("robots.txt blocks %s", e)
            log.info("tuyensinh247 %d/%d %s rows=%d", i, len(codes), code, len(rows))
        pd.DataFrame(rows).to_csv(COLLECTED / "tuyensinh247_cutoffs.csv", index=False, encoding="utf-8")
        counts["tuyensinh247_rows"] = len(rows)

    if "ads_final" in todo:
        rows = list(ads_final.rows(client, codes))
        pd.DataFrame(rows).to_csv(COLLECTED / "ads_final_cutoffs.csv", index=False, encoding="utf-8")
        counts["ads_final_rows"] = len(rows)

    if "moet" in todo:
        counts["moet_majors"] = len(moet.collect(client))

    counts["http_requests"] = client.requests_made
    return counts
