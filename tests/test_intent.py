"""Module 2's intent reader, the generator's truth tags, and the simulated students with an always-right judge."""

import json

from uniadvisor.build import majors
from uniadvisor.intent import covers, extract
from uniadvisor.intent.evaluate import evaluate
from uniadvisor.paths import SLM_DATA
from uniadvisor.sim import students as sim_students
from uniadvisor.slm import synth


def test_reader_returns_facts_with_their_sentences():
    i = extract("Em muốn học CNTT. Gia đình em chỉ lo được học phí tầm 2.5 triệu mỗi tháng. Em không thích kinh doanh. "
                "Mẹ em muốn em học Vật lý, còn em thì không thích lắm. Em có IELTS 6.5.")
    assert i.codes("interests") == {"74801", "74802"} and i.interests[0].evidence == "Em muốn học CNTT"
    assert i.codes("dislikes") == {"73401"}
    assert i.family.codes == ("74401",) and i.family_agrees is False
    assert i.budget.value == 25e6 and "2.5 triệu" in i.budget.evidence     # a decimal does not end the sentence
    assert i.english.value == "ielts"


def test_reader_does_not_take_everyday_words_for_majors():
    i = extract("Gia đình em chỉ lo được học phí 20 triệu. Kinh tế gia đình em không khá lắm. Toán là môn mạnh nhất của em.")
    assert i.interests == [] and i.budget.value == 20e6 and i.strong == {"TO": "Toán là môn mạnh nhất của em"}
    assert extract("Em hay tự viết code Python").interests[0].implied
    assert extract("em muon hoc nganh duoc").interests == []                # "dược" needs diacritics ("được")
    assert extract("Em muốn học ngành Dược").codes("interests") == {"77202"}


def test_covers_follows_the_field_mapping():
    assert covers("748", "7480201") and covers("74401", "7440102")
    assert not covers("744", "7440112")        # chemistry is filed under sinh_hoa, not khoa_hoc_tn
    assert covers("7440112", "7440112") and not covers("748", "")


def test_truth_tags_are_moet_codes_and_texts_are_unchanged():
    codes = set(majors.catalog().code)
    bank = {p for f in synth.FIELD_TEXT.values() for k in f.values() for p in k}
    assert set(synth.PHRASE_CODES) <= bank
    assert {c for v in [*synth.PHRASE_CODES.values(), *synth.FIELD_CODES.values()] for c in v} <= codes
    # the frozen gold students still regenerate byte for byte from the dataset's seed
    gold = {json.loads(line)["student_id"]: json.loads(line)["latent"]["free_text"]
            for line in open(SLM_DATA / "gold_frozen.jsonl", encoding="utf-8")}
    gen = synth.ProfileGenerator(13)
    for i in range(max(int(s[1:]) for s in gold) + 1):
        z = gen.latent()
        text = gen.text(z)
        if f"s{i:05d}" in gold:
            assert gold[f"s{i:05d}"] == text


def test_evaluation_runs(tiny_db):
    r = evaluate(60, seed=1, db=tiny_db)
    assert r["single"]["budget"]["stated"] > 0 and r["areas"]["interests"]["precision"] is not None


def test_simulated_students_and_the_oracle_judge(tiny_db):
    from uniadvisor.advisor import advise
    from uniadvisor.engine.forecast import ForecastParams

    students = sim_students.generate(40, seed=2)
    assert students == sim_students.generate(40, seed=2)
    assert all(s["student_id"].startswith("SIM-") for s in students)
    judge = sim_students.OracleJudge(students)
    s = next(x for x in students if x["intent"]["risk"] and x["intent"]["interests"])
    a = advise(sim_students.profile(s), judge=judge, db=tiny_db, params=ForecastParams())
    assert a.judge == "oracle" and a.profile_answers["risk_tolerance"].label == s["intent"]["risk"]
    for ev in a.chosen + a.alternatives:
        fit = ev["answers"]["interest_fit"].label
        assert fit in {"1", "2", "3", "4", "5", "insufficient"}
