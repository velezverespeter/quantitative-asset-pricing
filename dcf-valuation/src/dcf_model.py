"""
Discounted Cash Flow (DCF) Valuation Model
--------------------------------------------
Values a company by projecting its unlevered free cash flow (FCF) forward,
discounting each year back to present value at the Weighted Average Cost of
Capital (WACC), and adding a terminal value for cash flows beyond the
explicit forecast period.

Usage:
    python dcf_model.py --ticker AAPL

Data source:
    Live inputs are pulled via yfinance (Yahoo Finance) at runtime.
    If the API is unreachable, the model falls back to the sourced reference
    values in FALLBACK_DATA below (Apple, dated 2026-07-19 — see comments for
    original sources: SEC 10-K FY2025, StockAnalysis.com, Morningstar).

Author: Peter Velez Vereš
"""

import argparse
from dataclasses import dataclass

import matplotlib.pyplot as plt

# ── Reference fallback data (used only if the live API call fails) ──────────
# Sourced 2026-07-19. Replace/update when re-running for accuracy.
#   - Base FCF ($98.8B): SEC 10-K FY2025 (fiscal year ended 2025-09-30),
#     computed as Operating Cash Flow ($111.48B) − CapEx ($12.72B)
#   - Share price ($333.55), shares outstanding (14.69B), market cap ($4.90T):
#     Morningstar quote, snapshot 2026-07-19
#   - Beta (1.10), total debt ($84.71B), cash & marketable securities
#     ($146.60B): StockAnalysis.com statistics page
FALLBACK_DATA = {
    "ticker": "AAPL",
    "company_name": "Apple Inc.",
    "share_price": 333.55,
    "shares_outstanding_b": 14.69,      # billions
    "base_fcf_b": 98.8,                 # billions, FY2025 actual
    "total_debt_b": 84.71,              # billions
    "cash_b": 146.60,                   # billions
    "beta": 1.10,
    "effective_tax_rate": 0.15,
    "pretax_cost_of_debt": 0.045,       # approx. yield on Apple's outstanding bonds
}

# ── Macro / market assumptions (update periodically) ─────────────────────────
RISK_FREE_RATE = 0.043      # ~10-year US Treasury yield
EQUITY_RISK_PREMIUM = 0.05  # long-run US equity risk premium estimate


@dataclass
class DCFAssumptions:
    forecast_years: int = 5
    fcf_growth_rates: tuple = (0.08, 0.07, 0.06, 0.05, 0.04)  # Year 1–5
    terminal_growth_rate: float = 0.025


def fetch_live_data(ticker: str) -> dict:
    """Attempt to pull live inputs via yfinance. Raises on failure so the
    caller can fall back to sourced reference data instead of silently
    using stale numbers."""
    import yfinance as yf

    t = yf.Ticker(ticker)
    info = t.info
    cashflow = t.cashflow

    operating_cf = cashflow.loc["Operating Cash Flow"].iloc[0]
    capex = abs(cashflow.loc["Capital Expenditure"].iloc[0])
    base_fcf = (operating_cf - capex) / 1e9

    return {
        "ticker": ticker,
        "company_name": info.get("longName", ticker),
        "share_price": info["currentPrice"],
        "shares_outstanding_b": info["sharesOutstanding"] / 1e9,
        "base_fcf_b": base_fcf,
        "total_debt_b": info.get("totalDebt", 0) / 1e9,
        "cash_b": info.get("totalCash", 0) / 1e9,
        "beta": info.get("beta", 1.0),
        "effective_tax_rate": 0.15,  # not reliably available via yfinance; override if known
        "pretax_cost_of_debt": 0.045,
    }


def get_data(ticker: str, use_fallback: bool = False) -> dict:
    if use_fallback:
        print(f"Using sourced fallback data for {ticker} (dated 2026-07-19).\n")
        return FALLBACK_DATA
    try:
        data = fetch_live_data(ticker)
        print(f"Pulled live data for {ticker} via yfinance.\n")
        return data
    except Exception as e:
        print(f"Live data fetch failed ({e}).")
        print("Falling back to sourced reference data (dated 2026-07-19).\n")
        return FALLBACK_DATA


def calculate_wacc(data: dict) -> float:
    """Cost of equity via CAPM, cost of debt post-tax, weighted by
    market values of equity and debt."""
    cost_of_equity = RISK_FREE_RATE + data["beta"] * EQUITY_RISK_PREMIUM
    cost_of_debt_after_tax = data["pretax_cost_of_debt"] * (1 - data["effective_tax_rate"])

    market_cap = data["share_price"] * data["shares_outstanding_b"]
    total_debt = data["total_debt_b"]
    total_capital = market_cap + total_debt

    weight_equity = market_cap / total_capital
    weight_debt = total_debt / total_capital

    wacc = weight_equity * cost_of_equity + weight_debt * cost_of_debt_after_tax
    return wacc, cost_of_equity, cost_of_debt_after_tax, weight_equity, weight_debt


def project_fcf(base_fcf: float, assumptions: DCFAssumptions) -> list:
    projected = []
    fcf = base_fcf
    for g in assumptions.fcf_growth_rates:
        fcf = fcf * (1 + g)
        projected.append(fcf)
    return projected


def discount_cash_flows(projected_fcf: list, wacc: float) -> list:
    return [fcf / ((1 + wacc) ** (i + 1)) for i, fcf in enumerate(projected_fcf)]


def calculate_terminal_value(final_year_fcf: float, wacc: float, terminal_growth: float) -> float:
    """Gordon Growth terminal value, discounted to present value."""
    tv_undiscounted = final_year_fcf * (1 + terminal_growth) / (wacc - terminal_growth)
    return tv_undiscounted


def run_dcf(ticker: str, use_fallback: bool = False, assumptions: DCFAssumptions = None):
    if assumptions is None:
        assumptions = DCFAssumptions()

    data = get_data(ticker, use_fallback=use_fallback)
    wacc, cost_of_equity, cost_of_debt, w_equity, w_debt = calculate_wacc(data)

    projected_fcf = project_fcf(data["base_fcf_b"], assumptions)
    discounted_fcf = discount_cash_flows(projected_fcf, wacc)

    terminal_value = calculate_terminal_value(
        projected_fcf[-1], wacc, assumptions.terminal_growth_rate
    )
    discounted_terminal_value = terminal_value / ((1 + wacc) ** assumptions.forecast_years)

    enterprise_value = sum(discounted_fcf) + discounted_terminal_value
    equity_value = enterprise_value - data["total_debt_b"] + data["cash_b"]
    implied_share_price = (equity_value / data["shares_outstanding_b"])

    current_price = data["share_price"]
    upside_pct = (implied_share_price / current_price - 1) * 100

    # ── Console summary ──────────────────────────────────────────────────
    print(f"{'='*60}")
    print(f"DCF VALUATION — {data['company_name']} ({data['ticker']})")
    print(f"{'='*60}\n")

    print("WACC Components")
    print(f"  Cost of equity (CAPM):     {cost_of_equity:.2%}")
    print(f"  Cost of debt (after-tax):  {cost_of_debt:.2%}")
    print(f"  Weight — equity:           {w_equity:.1%}")
    print(f"  Weight — debt:             {w_debt:.1%}")
    print(f"  WACC:                      {wacc:.2%}\n")

    print(f"Projected Free Cash Flow (base: ${data['base_fcf_b']:.1f}B)")
    for i, (fcf, pv) in enumerate(zip(projected_fcf, discounted_fcf), start=1):
        print(f"  Year {i}: ${fcf:6.1f}B  →  PV: ${pv:6.1f}B")
    print()

    print(f"Terminal Value")
    print(f"  Terminal growth rate:      {assumptions.terminal_growth_rate:.2%}")
    print(f"  Undiscounted TV:           ${terminal_value:,.1f}B")
    print(f"  PV of TV:                  ${discounted_terminal_value:,.1f}B\n")

    print("Valuation Bridge")
    print(f"  Enterprise Value:          ${enterprise_value:,.1f}B")
    print(f"  (–) Total Debt:            ${data['total_debt_b']:,.1f}B")
    print(f"  (+) Cash & Equivalents:    ${data['cash_b']:,.1f}B")
    print(f"  Equity Value:              ${equity_value:,.1f}B")
    print(f"  Shares Outstanding:        {data['shares_outstanding_b']:.2f}B\n")

    print(f"{'='*60}")
    print(f"  Implied Share Price:       ${implied_share_price:,.2f}")
    print(f"  Current Market Price:      ${current_price:,.2f}")
    print(f"  Implied Upside/Downside:   {upside_pct:+.1f}%")
    print(f"{'='*60}")

    return {
        "data": data,
        "wacc": wacc,
        "projected_fcf": projected_fcf,
        "discounted_fcf": discounted_fcf,
        "terminal_value": terminal_value,
        "enterprise_value": enterprise_value,
        "equity_value": equity_value,
        "implied_share_price": implied_share_price,
        "current_price": current_price,
        "upside_pct": upside_pct,
    }


def plot_valuation_bridge(result: dict, output_path: str = "outputs/dcf_valuation_bridge.png"):
    """Bar chart comparing implied vs. current share price, plus the
    projected FCF path."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.5))

    # Left: implied vs current price
    labels = ["Current Price", "DCF Implied Price"]
    values = [result["current_price"], result["implied_share_price"]]
    colors = ["#888888", "#1672B0"]
    ax1.bar(labels, values, color=colors, width=0.5)
    for i, v in enumerate(values):
        ax1.text(i, v + 2, f"${v:,.2f}", ha="center", fontweight="bold")
    ax1.set_title(f"{result['data']['ticker']} — DCF Implied vs. Current Price")
    ax1.set_ylabel("Price ($)")
    ax1.spines[["top", "right"]].set_visible(False)

    # Right: projected FCF path
    years = list(range(1, len(result["projected_fcf"]) + 1))
    ax2.bar(years, result["projected_fcf"], color="#1672B0", width=0.6)
    ax2.set_title("Projected Free Cash Flow")
    ax2.set_xlabel("Forecast Year")
    ax2.set_ylabel("FCF ($B)")
    ax2.set_xticks(years)
    ax2.spines[["top", "right"]].set_visible(False)

    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    print(f"\nChart saved to {output_path}")


def sensitivity_table(data: dict, assumptions: DCFAssumptions,
                       wacc_range: tuple = None, tg_range: tuple = None) -> None:
    """Print a grid showing how the implied share price changes across a
    range of WACC and terminal growth assumptions — DCF outputs are highly
    sensitive to both, and this makes that sensitivity explicit rather than
    hiding it behind a single point estimate."""
    base_wacc, *_ = calculate_wacc(data)
    if wacc_range is None:
        wacc_range = [base_wacc - 0.02, base_wacc - 0.01, base_wacc,
                       base_wacc + 0.01, base_wacc + 0.02]
    if tg_range is None:
        tg_range = [0.015, 0.020, 0.025, 0.030, 0.035]

    projected_fcf = project_fcf(data["base_fcf_b"], assumptions)

    print(f"\n{'='*60}")
    print("SENSITIVITY: Implied Share Price ($) — WACC (rows) x Terminal Growth (cols)")
    print(f"{'='*60}")
    header = "WACC \\ g   " + "".join(f"{tg:>8.1%}" for tg in tg_range)
    print(header)
    for wacc in wacc_range:
        discounted_fcf = discount_cash_flows(projected_fcf, wacc)
        row = f"{wacc:>8.2%}   "
        for tg in tg_range:
            tv = calculate_terminal_value(projected_fcf[-1], wacc, tg)
            pv_tv = tv / ((1 + wacc) ** assumptions.forecast_years)
            ev = sum(discounted_fcf) + pv_tv
            equity_value = ev - data["total_debt_b"] + data["cash_b"]
            price = equity_value / data["shares_outstanding_b"]
            row += f"{price:>8.2f}"
        print(row)
    print(f"{'='*60}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run a DCF valuation model.")
    parser.add_argument("--ticker", type=str, default="AAPL", help="Stock ticker to value")
    parser.add_argument(
        "--fallback",
        action="store_true",
        help="Use sourced reference data instead of a live API call",
    )
    args = parser.parse_args()

    result = run_dcf(args.ticker, use_fallback=args.fallback)
    plot_valuation_bridge(result)
    sensitivity_table(result["data"], DCFAssumptions())
