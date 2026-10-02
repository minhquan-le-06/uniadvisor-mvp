"""Module 2's guided chat, without the UI: the questions' closed lists, scores from exact / range / level answers,
the nhóm ngành -> ngành picker and its search, the answers -> JSON document for module 3 with its checks, and the
"Mình hiểu là..." summary. The contract is docs/STUDENT_SCHEMA.md; the Streamlit page is app/pages/hoi_dap.py.

    from uniadvisor.student.form import Answers, ScoreEntry, build, picker, problems
    doc, notices = build(answers, picker())
"""

from uniadvisor.student.form.document import ANYWHERE, NEAR_HOME, Answers, build, problems
from uniadvisor.student.form.picker import Group, Major, Picker, picker, search
from uniadvisor.student.form.scores import MODES, ScoreEntry
from uniadvisor.student.form.summary import SECTIONS, summary

__all__ = ["ANYWHERE", "MODES", "NEAR_HOME", "SECTIONS", "Answers", "Group", "Major", "Picker", "ScoreEntry", "build",
           "picker", "problems", "search", "summary"]
