# Quantitative Asset Pricing

A collection of independent valuation and pricing models, each in its own subfolder with a dedicated README, dataset, and source code. Built with public market data and open-source tools for applied learning and demonstration purposes.

## Analyses

| Analysis | Description | Status |
|---|---|---|
| [`dcf-valuation`](./dcf-valuation) | 5-year discounted cash flow model with CAPM-derived WACC and sensitivity analysis — applied to Apple Inc. (AAPL) | Complete |
| `comparable-company-analysis` | Trading multiples benchmarking (EV/EBITDA, P/E, EV/Revenue) against a peer group | Planned |
| `options-pricing` | Black-Scholes options pricing with payoff diagrams and Greeks | Planned |
| `bond-pricing` | Bond valuation from cash flows, duration and convexity | Planned |

Each subfolder is self-contained: its own `README.md`, `requirements.txt`, and `src/` directory, so any analysis can be run independently without needing the others installed.

## Repository Structure

```
quantitative-asset-pricing/
├── README.md              (this file)
├── LICENSE
├── .gitignore
└── dcf-valuation/
    ├── README.md
    ├── requirements.txt
    ├── src/
    ├── notebooks/
    ├── data/
    └── outputs/
```

## License

MIT (see LICENSE) — applies repo-wide unless a subfolder specifies otherwise.

---

<sub>This repository contains independent academic and demonstration work using publicly available data. It does not constitute investment research, financial advice, or a recommendation to buy, hold, or sell any security.</sub>
