# genai-nvidia

Source-grounded extraction with NVIDIA Nemotron models, a human review queue, and Zetaris storage.

## Setup

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# Unix: source .venv/bin/activate
pip install -e .
cp .env.example .env
```

Fill `.env` with real values. Never commit it.

## Run tests

```bash
pytest -q
```
