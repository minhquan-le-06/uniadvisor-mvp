"""Simulated databases: same schema as the real one (unidata.db), made up to train or test.

tiny     a hand-sized world (3 schools, 12 programs) for fast tests of the advisor, API and app
season   the real database plus one simulated admission season, for testing the engine against a known truth

Rules every simulated database keeps (db.validate checks them):
- manifest.json says kind=simulated and names the generator and its seed, so it can be rebuilt exactly;
- every school_code / program_id starts with SIM-, so it can never be mistaken for or joined to a real one;
- it lives in data/sim/<name>/ (git-ignored: rebuild it from the seed), never in data/db/.
"""
