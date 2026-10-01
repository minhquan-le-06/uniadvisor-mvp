"""Module 1, data: the database every other module reads (`unidata.db`), and how it is collected and built.

collect/   one scraper per source -> data/collected/
build/     cleaning, cross-source cutoffs, distributions, MOET codes and fields -> data/db/
db/        the schema, the loader and its checks (get_db, load, write)
sim/       simulated databases with the same schema (tiny, season)
dist.py    score distributions (CDFs) and their methods
paths.py   where everything lives (both packages take folder paths from here)

This package never imports the backend (`uniadvisor`): other modules depend on it, not the other way round.
"""
