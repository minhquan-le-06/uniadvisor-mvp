# Training the SLM on Kaggle

The SLM (multilingual MiniLM cross-encoder + LoRA + typed heads) trains in minutes on a Kaggle GPU;
on a laptop CPU it takes hours. Everything it needs is in one zip.

## 1. Make the bundle (on your machine)

```bash
.venv/Scripts/uniadvisor slm-data            # rebuild data/slm/ if the catalog changed
.venv/Scripts/uniadvisor kaggle-bundle       # -> dist/uniadvisor_kaggle_bundle.zip
```

## 2. Upload and run

1. Kaggle → Datasets → New dataset → upload `dist/uniadvisor_kaggle_bundle.zip` (name it `uniadvisor-bundle`).
2. New notebook → Add input → your dataset. Settings: **Accelerator GPU T4 x2 or P100**, **Internet on**
   (the base model `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1` is downloaded from Hugging Face).
3. Import `kaggle/train_slm.ipynb` (or paste its cells) and run all.

Useful knobs (`python -m uniadvisor.slm.train --help`):
`--epochs 3 --bs 64 --lr 5e-4 --lora-r 16 --max-len 320 --target-acc 0.9`.
To use LLM-teacher labels instead of the rubric teacher, rename `train.llm.jsonl` → `train.jsonl`
(and the same for val) before training.

## 3. Bring the model back

Download `/kaggle/working/slm_model.zip` and unzip it into `models/slm/` so that
`models/slm/adapter.pt` and `models/slm/config.json` exist. The app and API pick it up automatically
(`uniadvisor slm-eval --judge slm` compares it with the keyword baseline).

The adapter is small (~7 MB): only LoRA weights, heads and temperatures are saved; the base model is
downloaded from Hugging Face on first use (or found in the local HF cache).
