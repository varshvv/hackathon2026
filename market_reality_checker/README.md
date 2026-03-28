# TruthLayer: The Integrity Terminal

TruthLayer is a finance-track hackathon product built to answer a different question than most market apps. It does not try to predict what comes next. It checks whether the move already happening looks structurally believable.

The result is a lightweight market integrity terminal with a private-bank aesthetic: monochrome, editorial, calm, and severe only when the tape deserves it.

## The Pitch

Most tools try to forecast the next move.

TruthLayer verifies whether the current move even looks real.

## Why It Matters

Market participants often react to momentum before validating whether that motion is natural, unstable, or suspicious. TruthLayer adds a verification layer before trust. It gives judges a clear story:

- explainable quantitative checks
- resilient live demo behavior
- premium product feel
- no prediction-model hand-waving

This is not a trading bot, not a signal generator, and not a claim of institutional surveillance accuracy. It is an explainable market integrity prototype.

## Core Features

- Live forex analysis through Yahoo Finance via `yfinance`
- Silent deterministic fallback to a Geometric Brownian Motion tape if the live feed fails
- Simulator mode for deterministic `Spike Up`, `Spike Down`, `Drift`, and `Jump-Revert` scenarios
- Explainable rule engine with:
  - Return Spike detection
  - Volatility Shock detection
  - Jump-Revert detection
  - Directional Drift detection
- Weighted `0-100` Integrity Score
- Premium monochrome terminal UI with:
  - semi-circular integrity gauge
  - editorial headline section
  - high-contrast metric cards
  - restrained red anomaly overlays
  - boxed “Security Callout” trigger feed

## Stack

- Python 3.10+
- Streamlit
- Pandas
- NumPy
- Plotly
- yfinance

## Project Structure

```text
market_reality_checker/
├── app.py
├── config.py
├── requirements.txt
├── README.md
└── src/
    ├── __init__.py
    ├── data_manager.py
    ├── engine.py
    └── visuals.py
```

## File Overview

- `config.py`
  Centralized product configuration, detection thresholds, symbol mappings, and premium terminal CSS.

- `src/engine.py`
  Contains the `MarketEngine` class with vectorized anomaly detection and weighted scoring.

- `src/data_manager.py`
  Handles market data retrieval through `yfinance`, normalization, deterministic anomaly injection, and the silent GBM fallback.

- `src/visuals.py`
  Builds the monochrome integrity gauge and the main price terminal chart.

- `app.py`
  Streamlit interface, sidebar controls, layout orchestration, and demo flow.

## Detection Logic

TruthLayer favors simple, credible heuristics over opaque ML.

### Return Spike

Computes rolling Z-scores on absolute returns. If a move exceeds the rolling statistical envelope, it is flagged.

### Volatility Shock

Compares short-window realized volatility to its own rolling baseline. If dispersion expands abruptly, the engine marks the tape as unstable.

### Jump-Revert

Looks for a sharp bar followed by an immediate reversal that retraces at least 70 percent. This is especially strong for demo storytelling because it feels visually suspicious and structurally unusual.

### Directional Drift

Captures sustained directional movement that persists beyond what the current short-term regime usually supports.

## Scoring

TruthLayer starts from `100` and deducts points based on weighted rule severity.

- `85-100`: `Natural`
- `65-84`: `Watchlist`
- `0-64`: `Suspicious`

If multiple rules agree, the engine adds a confluence penalty. This makes the verdict feel more coherent during a live walkthrough.

## Setup

```bash
cd market_reality_checker
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run

```bash
streamlit run app.py
```

If Streamlit attempts to write outside the workspace in a restricted environment, you can run:

```bash
HOME="$PWD" streamlit run app.py
```

## Demo Guide For Hacklanta Judges

### Fastest Winning Demo

1. Open the app.
2. Choose `Simulator Mode`.
3. Select `Jump-Revert`.
4. Keep severity near `0.018` to `0.025`.
5. Click `Run Integrity Audit`.

This reliably produces:

- a low Integrity Score
- visible anomaly markers on the chart
- boxed trigger callouts
- a clean “why it was flagged” narrative

### Live Feed Demo

1. Switch to `Live Mode`.
2. Choose `EUR/USD` or `USD/JPY`.
3. Run the audit.
4. If Yahoo Finance is unavailable, TruthLayer silently swaps to a deterministic GBM tape so the demo still completes.

### Story Track

Use this line:

> Everyone else is trying to predict the next move. We built the layer that asks whether the move already on the screen deserves trust.

Then walk judges through:

1. the Integrity Gauge
2. the status label
3. the red anomaly markers
4. the Security Callouts
5. the fact that the product degrades gracefully if live data fails

## Reliability Notes

- No external database
- No auth
- No deployment dependency required for MVP
- Deterministic fallback data path
- Deterministic simulator mode
- Graceful handling for NaNs, malformed timestamps, and missing volume

## Verification

Run:

```bash
python3 -m compileall .
```

The app is designed to handle:

- live feed failure
- empty or malformed market data
- insufficient rolling windows
- NaNs from calculations
- demo-mode anomaly injection without breaking chart structure

## Future Extensions

- More FX pairs and asset classes
- Session-aware regime baselines
- Exportable PDF integrity reports
- Multi-panel microstructure diagnostics
- Better anomaly clustering and regime segmentation

## Closing Positioning

TruthLayer is best presented as:

`A lightweight explainable market integrity terminal.`

That framing is ambitious, credible, and strong for a live finance-track demo.
