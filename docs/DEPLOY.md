# Deploying the app

The hosted MVP is the Streamlit chat (`app/streamlit_app.py`) with the **keyword judge**: no SLM, no torch.
That keeps the install small (~650 MB of packages, ~250 MB RAM at runtime, results in ~2 s) and fits free hosting.
The SLM (hybrid 0.864 vs keywords 0.823 on the gold set) is a later step, below.

What the deploy uses, all in the repo:

| File | Role |
|---|---|
| `requirements.txt` | `-e .`: the package with its base dependencies (no `[slm]` extra) |
| `.streamlit/config.toml` | headless server, no usage stats, viewer-only toolbar |
| `data/processed/`, `config/`, `models/forecast_params.json` | everything the app reads; nothing is collected at runtime |

No secrets are needed. The app writes nothing to disk; each browser session keeps its own state.

## Streamlit Community Cloud (recommended, free)

1. Go to https://share.streamlit.io and sign in with the GitHub account that owns the repo.
   If the repo is private, allow Streamlit access to private repos when GitHub asks.
2. **Create app** → **Deploy a public app from GitHub**, then fill in:

   | Field | Value |
   |---|---|
   | Repository | `minhquan-le-06/uniadvisor-mvp` |
   | Branch | `main` |
   | Main file path | `app/streamlit_app.py` |
   | App URL | e.g. `uniadvisor` (gives `uniadvisor.streamlit.app`) |

3. **Advanced settings** → Python **3.12** (anything 3.11+ works). Leave secrets empty.
4. **Deploy**. The first build takes a few minutes; the log shows `pip install -e .`, then the app.
5. Check: the sidebar should read "48 trường, 1666 ngành" and "luật từ khóa (chưa có SLM)". Then run one
   example from the chat through to the list.

After that, every push to `main` redeploys automatically. An app from a private repo may start as private:
open **Share** and make it public if students should open it without being invited.
Free apps sleep after a few days without visitors; the first visitor wakes them (about 30 s).

## Hugging Face Spaces (alternative)

Create a Space with the **Docker** or **Streamlit** SDK and push this repo to it. The Streamlit SDK expects
`app.py` at the root, so either set `app_file: app/streamlit_app.py` in the Space's README front matter or
add a one-line `app.py` that runs the app. Spaces give 16 GB RAM on the free CPU tier, which matters
only for the SLM version.

## Running it like the host does

```bash
python -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/streamlit run app/streamlit_app.py
```

`uniadvisor.paths` finds `config/` and `data/` next to the source checkout, or in the current folder when the
package was installed non-editable; set `UNIADVISOR_ROOT` to point elsewhere.

## Later: the SLM version

1. Commit the trained adapter: un-ignore `models/slm/adapter.pt` (~7 MB) in `.gitignore` and add `models/slm/`.
2. Add CPU torch and transformers to `requirements.txt`
   (`--extra-index-url https://download.pytorch.org/whl/cpu`, then `torch`, `transformers`, `safetensors`).
3. The base model (mmarco-mMiniLMv2-L12-H384, ~470 MB) downloads from Hugging Face at first start, so the host
   needs outbound access there. Expect ~1.5 GB RAM; try it on Spaces first if Streamlit Cloud runs out of memory.
