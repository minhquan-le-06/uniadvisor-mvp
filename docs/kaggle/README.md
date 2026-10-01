# Training the SLM on Kaggle

The SLM (multilingual MiniLM cross-encoder + LoRA + typed heads) trains in about 30 minutes on a Kaggle
GPU (both T4s are used); on a laptop CPU it takes hours. Everything it needs is in one zip.

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
3. Import `docs/kaggle/train_slm.ipynb` (or paste its cells) and run all. For long runs prefer
   **Save Version → Save & Run All**, so an idle browser tab cannot stop the session; the result is then
   in the version's Output tab.

**Both GPUs.** Cell 3 starts one training process per GPU with `torchrun` (PyTorch DDP): each GPU trains on
its own share of every epoch and gradients are averaged, so "GPU T4 x2" is about twice as fast as one GPU.
`--bs` is per GPU (effective batch = bs x GPUs); evaluation, calibration and saving run on GPU 0.

**VRAM.** About 20 steps in, the log prints `VRAM peak: GPU0 x/15 GB, GPU1 x/15 GB`. Raise `--bs` while that stays
under ~85% (and raise `--lr` a little with it, e.g. bs 128 -> lr 1e-3, bs 256 -> 1.4e-3); lower it on
"CUDA out of memory". Filling VRAM makes epochs faster, not the model better: a larger batch means fewer update
steps, so if validation accuracy drops compared with a run at a smaller batch, go back to the smaller one.

Useful knobs (`python -m uniadvisor.slm.train --help`):
`--epochs 5 --bs 128 --lr 1e-3 --lora-r 16 --max-len 320 --target-acc 0.9 --eval-bs 512`.
The loss should fall steadily in the first epoch and flatten later.
To use LLM-teacher labels instead of the rubric teacher, rename `train.llm.jsonl` → `train.jsonl`
(and the same for val) before training.

## 3. Bring the model back

Download `/kaggle/working/slm_model.zip` and unzip it into `artifacts/models/slm/` so that
`artifacts/models/slm/adapter.pt` and `artifacts/models/slm/config.json` exist. The app and API pick it up automatically
and use the hybrid judge (SLM for its best questions, keyword rules for the rest; see the README).

Compare the judges on the same rows (on CPU the full test split takes 5–20 min, so use a limit):

```bash
uniadvisor slm-eval --judge slm --limit 3000
uniadvisor slm-eval --judge heuristic --limit 3000
uniadvisor slm-eval --judge hybrid --limit 3000
```

If a question flips (the SLM now beats the rules or the other way round), update `SLM_QUESTIONS` in
`src/uniadvisor/slm/infer.py` or put `"route": [...]` in `artifacts/models/slm/config.json`.

The load report printed on first use (`classifier.*` UNEXPECTED, `pooler.*` MISSING) is expected: the
model uses its own pooling and heads, which come from `adapter.pt`.

The adapter is small (~7 MB): only LoRA weights, heads and temperatures are saved; the base model is
downloaded from Hugging Face on first use (or found in the local HF cache).
