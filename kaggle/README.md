# Training the SLM on Kaggle

The SLM (multilingual MiniLM cross-encoder + LoRA + typed heads) trains in about 30 minutes on a Kaggle
GPU (3 epochs); on a laptop CPU it takes hours. Everything it needs is in one zip.

## 1. Make the bundle (on your machine, from the project root)

```bash
.venv/Scripts/uniadvisor slm-data            # rebuild data/slm/ if the catalog changed
.venv/Scripts/uniadvisor kaggle-bundle       # -> dist/uniadvisor_kaggle_bundle.zip
```

(On Linux/macOS use `.venv/bin/`.)

## 2. Upload and run

1. Kaggle → Datasets → New dataset → upload `dist/uniadvisor_kaggle_bundle.zip` (name it `uniadvisor-bundle`).
   Kaggle unzips it into a folder; the notebook handles both the folder and a raw zip.
2. New notebook → Add input → your dataset. Settings: **Accelerator GPU T4 x2 or P100**, **Internet on**
   (the base model `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1` is downloaded from Hugging Face).
3. Import `kaggle/train_slm.ipynb` (or paste its cells) and run all. For long runs prefer
   **Save Version → Save & Run All**, so an idle browser tab cannot stop the session; the result is then
   in the version's Output tab.

Useful knobs (`python -m uniadvisor.slm.train --help`):
`--epochs 3 --bs 64 --lr 5e-4 --lora-r 16 --max-len 320 --target-acc 0.9`.
With bs 64 one epoch is about 960 steps (about 8 min on a T4). The loss should fall steadily
(about 1.2 → 0.8 in the first half epoch).
To use LLM-teacher labels instead of the rubric teacher, rename `train.llm.jsonl` → `train.jsonl`
(and the same for val) before training.

## 3. Bring the model back

Download `/kaggle/working/slm_model.zip` and unzip it into `models/slm/` so that
`models/slm/adapter.pt` and `models/slm/config.json` exist. The app and API pick it up automatically
and use the hybrid judge (SLM for its best questions, keyword rules for the rest; see the README).

Compare the judges on the same rows (on CPU the full test split takes 5–20 min, so use a limit):

```bash
uniadvisor slm-eval --judge slm --limit 3000
uniadvisor slm-eval --judge heuristic --limit 3000
uniadvisor slm-eval --judge hybrid --limit 3000
```

If a question flips (the SLM now beats the rules or the other way round), update `SLM_QUESTIONS` in
`src/uniadvisor/slm/infer.py` or put `"route": [...]` in `models/slm/config.json`.

The load report printed on first use (`classifier.*` UNEXPECTED, `pooler.*` MISSING) is expected: the
model uses its own pooling and heads, which come from `adapter.pt`.

The adapter is small (~7 MB): only LoRA weights, heads and temperatures are saved; the base model is
downloaded from Hugging Face on first use (or found in the local HF cache).
