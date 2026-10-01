"""The Streamlit app starts on any database and says so when the data is simulated."""

from streamlit.testing.v1 import AppTest

from unidata.paths import ROOT


def test_app_starts_on_the_tiny_world_and_warns_it_is_simulated(use_tiny):
    at = AppTest.from_file(str(ROOT / "app" / "streamlit_app.py"), default_timeout=120).run()
    assert not at.exception
    assert any("MÔ PHỎNG" in w.value for w in at.sidebar.warning)
    assert any("3 trường, 12 ngành" in m.value for m in at.sidebar.markdown)
