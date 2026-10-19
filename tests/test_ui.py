from pathlib import Path
from streamlit.testing.v1 import AppTest


def test_demo_one_window_flow():
    app = AppTest.from_file(Path(__file__).resolve().parents[1] / 'app.py', default_timeout=20).run()
    assert not app.exception
    start = next(b for b in app.button if b.label == 'Start collaboration')
    start.click().run()
    assert not app.exception
    assert app.session_state['result']['status'] == 'needs_changes'
    assert app.session_state['result']['calls'] == 2
    assert any('SCRIPTED DEMO' in w.value for w in app.warning)


def test_live_requires_explicit_consent_before_start():
    app = AppTest.from_file(Path(__file__).resolve().parents[1] / 'app.py', default_timeout=20).run()
    app.radio[0].set_value('live').run()
    start = next(b for b in app.button if b.label == 'Start collaboration')
    assert start.disabled
    assert not app.exception
