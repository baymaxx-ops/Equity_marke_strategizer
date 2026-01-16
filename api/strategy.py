from __future__ import annotations

from dataclasses import dataclass
import numpy as np
import pandas as pd
import yfinance as yf
import matplotlib.pyplot as plt
from scipy.stats import norm
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import base64
from io import BytesIO
from fredapi import Fred
import ssl
import urllib.request
import time
from datetime import datetime, timedelta

app = FastAPI()

# Cache for financial data
financial_cache = {}
CACHE_DURATION = 3600  # 1 hour in seconds

# Initialize FRED API (get free key at https://fred.stlouisfed.org/docs/api/)
FRED_API_KEY = "28a2040fc9b595e26e33dbb8c3aeac57"
try:
    # Bypass SSL verification for FRED API (workaround for certificate issues)
    ssl._create_default_https_context = ssl._create_unverified_context
    fred = Fred(api_key=FRED_API_KEY)
except Exception as e:
    print(f"FRED initialization error: {e}")
    fred = None

TRADING_DAYS = 252

# ============================================================
# Volatility Regime Helpers
# ============================================================
def _pct_rank(s: pd.Series, window: int) -> pd.Series:
    """
    Rolling percentile rank of the last value in each window.
    Returns 0..1 (NaN until enough history).
    """
    def _rank_last(x):
        x = pd.Series(x)
        return (x.rank(pct=True).iloc[-1])
    return s.rolling(window, min_periods=window).apply(_rank_last, raw=False)

def _zscore(s: pd.Series, window: int) -> pd.Series:
    m = s.rolling(window, min_periods=window).mean()
    sd = s.rolling(window, min_periods=window).std(ddof=0)
    return (s - m) / sd

def _rvol_from_price(px: pd.Series, window: int = 20, ann_factor: int = 252) -> pd.Series:
    """
    Realized volatility from log returns, annualized.
    """
    r = np.log(px).diff()
    return r.rolling(window, min_periods=window).std(ddof=0) * np.sqrt(ann_factor)

def volatility_regime_from_vix(vix_close: pd.Series,
                               lookback_days: int = 252 * 5,
                               low_q: float = 0.33,
                               high_q: float = 0.67):
    """
    Inputs:
      vix_close: VIX close series (e.g., ^VIX Close) from Yahoo
    Outputs:
      dict with:
        - vix_level
        - vix_pct_rank (rolling, 0..1)
        - regime_label: 'LOW_VOL' / 'MID_VOL' / 'HIGH_VOL'
    """
    vix = vix_close.dropna()
    pr = _pct_rank(vix, lookback_days)

    regime = pd.Series(index=vix.index, dtype="object")
    regime[pr < low_q] = "LOW_VOL"
    regime[(pr >= low_q) & (pr <= high_q)] = "MID_VOL"
    regime[pr > high_q] = "HIGH_VOL"

    return {
        "vix_level": vix,
        "vix_pct_rank": pr,
        "regime_label": regime
    }

def volatility_regime_from_realized(stock_close: pd.Series,
                                    rv_window: int = 20,
                                    lookback_days: int = 252 * 5,
                                    low_q: float = 0.33,
                                    high_q: float = 0.67):
    """
    Use realized vol when you don't want VIX.
    """
    rv = _rvol_from_price(stock_close, window=rv_window)
    pr = _pct_rank(rv.dropna(), lookback_days)

    regime = pd.Series(index=rv.index, dtype="object")
    regime[pr < low_q] = "LOW_RVOL"
    regime[(pr >= low_q) & (pr <= high_q)] = "MID_RVOL"
    regime[pr > high_q] = "HIGH_RVOL"

    return {"realized_vol": rv, "rv_pct_rank": pr, "regime_label": regime}

# ============================================================
# 2) Interest Rate Regime
# ============================================================
def interest_rate_regime(y10_close: pd.Series,
                         y2_close: pd.Series | None = None,
                         trend_window: int = 126,
                         slope_window: int = 63):
    """
    Yahoo tickers often used:
      - 10Y yield proxy: ^TNX  (quoted in 10x yield; ex: 45.0 ~ 4.5%)
      - 2Y yield proxy:  ^IRX is 13-week, not 2Y. 2Y availability varies.
        If you can get a 2Y series, pass it as y2_close.

    Outputs:
      - rate_level (in decimal, e.g., 0.045)
      - rate_trend: 'FALLING'/'RISING' (based on moving average slope)
      - curve_slope: (10Y - 2Y) if y2 provided, else NaN
      - curve_state: 'INVERTED'/'NORMAL' if y2 provided
    """
    y10 = y10_close.dropna() / 1000.0  # ^TNX is ~10x yield in % -> decimal: (45 / 1000 = 0.045)
    
    # Adaptive window: use min of trend_window or 30% of available data, but at least 20 days
    available_data = len(y10)
    adaptive_window = max(20, min(trend_window, int(available_data * 0.3)))
    
    # Trend via MA slope (simple + robust)
    ma = y10.rolling(adaptive_window, min_periods=1).mean()
    ma_slope = ma.diff()  # day-over-day slope of MA
    rate_trend = pd.Series(index=y10.index, dtype="object")
    rate_trend[ma_slope > 0] = "RISING"
    rate_trend[ma_slope <= 0] = "FALLING"

    curve_slope = pd.Series(index=y10.index, dtype="float64")
    curve_state = pd.Series(index=y10.index, dtype="object")

    if y2_close is not None:
        y2 = y2_close.dropna()
        # If your 2Y series is also in "10x %", adjust accordingly.
        # If it's already in percent (e.g., 4.2), convert to decimal: /100
        # Here we try to infer: if median > 1, assume percent, else already decimal.
        y2_med = y2.median()
        if y2_med > 1:
            # could be like 4.2 (%)
            y2_dec = y2 / 100.0
        else:
            y2_dec = y2

        # Align indexes
        y2_dec = y2_dec.reindex(y10.index).ffill()
        curve_slope = (y10 - y2_dec).rolling(slope_window, min_periods=slope_window).mean()
        curve_state[curve_slope < 0] = "INVERTED"
        curve_state[curve_slope >= 0] = "NORMAL"
    else:
        curve_slope[:] = np.nan
        curve_state[:] = np.nan

    return {
        "y10_rate_decimal": y10,
        "y10_ma": ma,
        "rate_trend": rate_trend,
        "curve_slope": curve_slope,
        "curve_state": curve_state
    }

# ============================================================
# 4) Liquidity Regime
# ============================================================
def liquidity_regime(hyg_close: pd.Series,
                     lqd_close: pd.Series,
                     spx_close: pd.Series | None = None,
                     window: int = 63,
                     z_low: float = -0.5,
                     z_high: float = 0.5):
    """
    Liquidity via HYG vs LQD relative strength (high-yield vs investment-grade credit).
    
    - When HYG/LQD ratio is strong & improving -> liquidity/risk appetite improving.
    - When HYG/LQD ratio falls sharply -> liquidity tightening / risk-off.

    Outputs:
      - ratio: HYG/LQD
      - ratio_z: rolling zscore
      - liquidity_label: 'TIGHT'/'NEUTRAL'/'EASY'
    """
    hyg = hyg_close.dropna()
    lqd = lqd_close.dropna()

    idx = hyg.index.intersection(lqd.index)
    hyg = hyg.reindex(idx).ffill()
    lqd = lqd.reindex(idx).ffill()

    ratio = hyg / lqd
    ratio_z = _zscore(ratio, window)

    liq = pd.Series(index=ratio.index, dtype="object")
    liq[ratio_z <= z_low] = "TIGHT"
    liq[(ratio_z > z_low) & (ratio_z < z_high)] = "NEUTRAL"
    liq[ratio_z >= z_high] = "EASY"

    out = {
        "hyg_lqd_ratio": ratio,
        "ratio_z": ratio_z,
        "liquidity_label": liq
    }

    if spx_close is not None:
        spx = spx_close.reindex(ratio.index).ffill()
        dd = (spx / spx.cummax()) - 1.0
        out["spx_drawdown"] = dd

    return out

@dataclass
class BacktestResult:
    strategy_return: float
    buy_hold_return: float
    hit_rate: float
    total_days: int

class CalculationRequest(BaseModel):
    ticker: str
    market: str
    start: str
    end: str | None = None
    risk_free: float = 0.02
    window: int = 126
    strike: float | None = None
    days: int = 30

def black_scholes_call(spot: float, strike: float, time_years: float, rate: float, vol: float) -> float:
    if spot <= 0 or strike <= 0 or time_years <= 0 or vol <= 0:
        raise ValueError("Spot, strike, time, and volatility must be positive.")

    d1 = (np.log(spot / strike) + (rate + 0.5 * vol**2) * time_years) / (vol * np.sqrt(time_years))
    d2 = d1 - vol * np.sqrt(time_years)
    return float(spot * norm.cdf(d1) - strike * np.exp(-rate * time_years) * norm.cdf(d2))

def fetch_prices(ticker: str, start: str, end: str | None) -> pd.Series:
    data = yf.download(ticker, start=start, end=end, auto_adjust=True, progress=False)
    if data.empty:
        raise ValueError(f"No data returned for {ticker}. Check ticker/date range or internet access.")
    close = data["Close"]

    if isinstance(close, pd.DataFrame):
        if close.shape[1] == 1:
            close = close.iloc[:, 0]
        elif ticker in close.columns:
            close = close[ticker]
        else:
            close = close.iloc[:, 0]

    return close.rename(ticker)

def fetch_fred_yield(series_id: str, start: str, end: str | None = None) -> pd.Series:
    """Fetch FRED yield data (e.g., DGS10 for 10-year, DGS2 for 2-year)"""
    if fred is None:
        raise ValueError("FRED API not initialized. Check API key.")
    try:
        data = fred.get_series(series_id, observation_start=start, observation_end=end)
        data = data.dropna()
        if data.empty:
            raise ValueError(f"No FRED data for {series_id}")
        return data / 100.0  # Convert from % to decimal
    except Exception as e:
        raise ValueError(f"FRED fetch error for {series_id}: {str(e)}")

def compute_returns(prices: pd.Series) -> pd.Series:
    return prices.pct_change().dropna()

def rolling_beta(stock_ret: pd.Series, market_ret: pd.Series, window: int) -> pd.Series:
    cov = stock_ret.rolling(window).cov(market_ret)
    var = market_ret.rolling(window).var()
    return cov / var

def backtest_capm_strategy(
    stock_ret: pd.Series,
    market_ret: pd.Series,
    rf_annual: float,
    window: int,
) -> tuple[BacktestResult, pd.DataFrame]:
    rf_daily = (1 + rf_annual) ** (1 / TRADING_DAYS) - 1

    beta = rolling_beta(stock_ret, market_ret, window)
    market_mean = market_ret.rolling(window).mean()

    expected_daily = rf_daily + beta * (market_mean - rf_daily)
    signal = expected_daily > 0

    strategy_returns = signal.shift(1).astype(float).fillna(0) * stock_ret

    equity_strategy = (1 + strategy_returns).cumprod()
    equity_buyhold = (1 + stock_ret).cumprod()

    cumulative_strategy = float(equity_strategy.iloc[-1] - 1)
    cumulative_buy_hold = float(equity_buyhold.iloc[-1] - 1)

    traded_days = (strategy_returns != 0).sum()
    hit_rate = float((strategy_returns > 0).sum() / max(traded_days, 1))

    bt = BacktestResult(
        strategy_return=cumulative_strategy,
        buy_hold_return=cumulative_buy_hold,
        hit_rate=hit_rate,
        total_days=int(strategy_returns.count()),
    )

    # Calculate consecutive days in position - improved logic
    signal_int = signal.astype(int)
    shifted_signal = signal_int.shift(1).fillna(0).astype(int)
    days_in_position = pd.Series(0, index=signal.index)
    counter = 0
    for i in range(len(shifted_signal)):
        if shifted_signal.iloc[i] == 1:
            counter += 1
            days_in_position.iloc[i] = counter
        else:
            counter = 0
            days_in_position.iloc[i] = 0

    df = pd.DataFrame({
        "stock_ret": stock_ret,
        "market_ret": market_ret,
        "beta_roll": beta,
        "expected_daily": expected_daily,
        "signal": signal.astype(int),
        "strategy_ret": strategy_returns,
        "equity_strategy": equity_strategy,
        "equity_buyhold": equity_buyhold,
        "days": days_in_position,
    }).dropna()

    return bt, df

def summarize_capm(stock_ret: pd.Series, market_ret: pd.Series, rf_annual: float) -> dict:
    beta = float(stock_ret.cov(market_ret) / market_ret.var())
    expected_market = float(market_ret.mean() * TRADING_DAYS)
    expected_stock = float(rf_annual + beta * (expected_market - rf_annual))
    vol = float(stock_ret.std() * np.sqrt(TRADING_DAYS))
    return {"beta": beta, "expected_market": expected_market, "expected_stock": expected_stock, "vol": vol}

def generate_plot(bt_df: pd.DataFrame) -> str:
    plt.figure(figsize=(10, 5))
    plt.plot(bt_df.index, bt_df["equity_strategy"], label="Strategy", linewidth=2.5, color='#667eea')
    plt.plot(bt_df.index, bt_df["equity_buyhold"], label="Buy & Hold", linewidth=2, alpha=0.6, color='#764ba2', linestyle='--')
    plt.title("Equity Curves: Strategy vs Buy & Hold")
    plt.xlabel("Date")
    plt.ylabel("Growth of $1")
    plt.legend(loc='best')
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    
    buf = BytesIO()
    plt.savefig(buf, format='png')
    buf.seek(0)
    img_base64 = base64.b64encode(buf.read()).decode('utf-8')
    plt.close()
    return f"data:image/png;base64,{img_base64}"

def generate_drawdown_plot(bt_df: pd.DataFrame) -> str:
    drawdown = (bt_df["equity_strategy"] / bt_df["equity_strategy"].cummax() - 1) * 100
    plt.figure(figsize=(10, 4))
    plt.fill_between(bt_df.index, drawdown, 0, alpha=0.3, color='red')
    plt.plot(bt_df.index, drawdown, color='darkred', linewidth=2)
    plt.title("Strategy Drawdown")
    plt.xlabel("Date")
    plt.ylabel("Drawdown (%)")
    plt.axhline(y=0, color='black', linestyle='-', linewidth=0.5)
    plt.tight_layout()
    
    buf = BytesIO()
    plt.savefig(buf, format='png')
    buf.seek(0)
    img_base64 = base64.b64encode(buf.read()).decode('utf-8')
    plt.close()
    return f"data:image/png;base64,{img_base64}"

@app.post("/api/calculate")
async def calculate_strategy(request: CalculationRequest):
    try:
        args = {
            "ticker": request.ticker,
            "market": request.market,
            "start": request.start,
            "end": request.end,
            "risk_free": request.risk_free,
            "window": request.window,
            "strike": request.strike,
            "days": request.days,
        }

        # ===== DATA SOURCES =====
        # PRICES: Yahoo Finance (stocks, ETFs)
        # YIELDS: FRED (Treasury data, more accurate)
        
        # Fetch prices from Yahoo Finance
        stock_prices = fetch_prices(args["ticker"], args["start"], args["end"])
        market_prices = fetch_prices(args["market"], args["start"], args["end"])

        combined = pd.concat([stock_prices, market_prices], axis=1, join="inner")
        stock_ret = compute_returns(combined[args["ticker"]])
        market_ret = compute_returns(combined[args["market"]])

        aligned = pd.concat([stock_ret, market_ret], axis=1, join="inner")
        stock_ret = aligned[args["ticker"]]
        market_ret = aligned[args["market"]]

        capm = summarize_capm(stock_ret, market_ret, args["risk_free"])

        spot = float(combined[args["ticker"]].iloc[-1])
        strike = float(args["strike"] if args["strike"] is not None else spot * 1.05)
        time_years = float(args["days"] / TRADING_DAYS)
        call_price = black_scholes_call(spot, strike, time_years, args["risk_free"], capm["vol"])

        backtest, bt_df = backtest_capm_strategy(stock_ret, market_ret, args["risk_free"], args["window"])

        # Calculate volatility regime (prices from Yahoo)
        try:
            rv = _rvol_from_price(combined[args["ticker"]], window=20)
            rv = rv.dropna()
            
            if len(rv) > 0:
                current_rv = float(rv.iloc[-1])
                # Determine regime based on percentile
                median_rv = rv.median()
                q75 = rv.quantile(0.75)
                q25 = rv.quantile(0.25)
                
                if current_rv > q75:
                    current_regime = "HIGH_VOL"
                elif current_rv < q25:
                    current_regime = "LOW_VOL"
                else:
                    current_regime = "MID_VOL"
            else:
                current_regime = "N/A"
                current_rv = 0.0
        except Exception as e:
            current_regime = "N/A"
            current_rv = 0.0

        # Calculate interest rate regime (yields from FRED - more accurate)
        try:
            y10_prices = fetch_fred_yield("DGS10", args["start"], args["end"])
            rate_regime = interest_rate_regime(y10_prices)
            rate_trend_series = rate_regime["rate_trend"].dropna()
            y10_rate_series = rate_regime["y10_rate_decimal"].dropna()
            
            current_rate_trend = rate_trend_series.iloc[-1] if len(rate_trend_series) > 0 else "N/A"
            current_y10_rate = float(y10_rate_series.iloc[-1]) if len(y10_rate_series) > 0 else 0.0
        except Exception as e:
            current_rate_trend = "N/A"
            current_y10_rate = 0.0

        # Calculate liquidity regime (prices from Yahoo: HYG & LQD ETFs)
        try:
            hyg_prices = fetch_prices("HYG", args["start"], args["end"])
            lqd_prices = fetch_prices("LQD", args["start"], args["end"])
            liq_regime = liquidity_regime(hyg_prices, lqd_prices)
            liq_label_series = liq_regime["liquidity_label"].dropna()
            hyg_lqd_ratio_series = liq_regime["hyg_lqd_ratio"].dropna()
            
            current_liquidity = liq_label_series.iloc[-1] if len(liq_label_series) > 0 else "N/A"
            current_ratio = float(hyg_lqd_ratio_series.iloc[-1]) if len(hyg_lqd_ratio_series) > 0 else 0.0
        except Exception as e:
            current_liquidity = "N/A"
            current_ratio = 0.0

        capm_summary = {
            "ticker": args["ticker"],
            "market": args["market"],
            "beta": round(capm["beta"], 3),
            "expected_annual_return": round(capm["expected_stock"], 4),
        }

        bs_call = {
            "spot": round(spot, 2),
            "strike": round(strike, 2),
            "volatility": round(capm["vol"], 4),
            "days_to_expiry": args["days"],
            "call_price": round(call_price, 2),
        }

        backtest_summary = {
            "strategy_return": round(backtest.strategy_return, 4),
            "buy_hold_return": round(backtest.buy_hold_return, 4),
            "hit_rate": round(backtest.hit_rate, 4),
            "total_trading_days": backtest.total_days,
        }

        volatility_regime = {
            "regime": str(current_regime),
            "realized_volatility": round(current_rv, 4),
        }

        interest_rate = {
            "rate_trend": str(current_rate_trend),
            "y10_rate": round(current_y10_rate * 100, 2),
        }

        liquidity = {
            "regime": str(current_liquidity),
            "hyg_lqd_ratio": round(current_ratio, 4),
        }

        equity_plot = generate_plot(bt_df)
        drawdown_plot = generate_drawdown_plot(bt_df)

        # Reset index to convert dates to column, filter for active positions, then convert to dict
        bt_df_with_dates = bt_df.reset_index()
        bt_df_with_dates['Date'] = bt_df_with_dates['Date'].astype(str)
        
        # Filter for rows where signal is 1 (in position) OR show last 10 rows regardless
        active_rows = bt_df_with_dates[bt_df_with_dates['signal'] == 1]
        if len(active_rows) >= 5:
            table_data = active_rows.tail(10).to_dict(orient="records")
        else:
            # If less than 5 active positions, show all data with last 10 rows
            table_data = bt_df_with_dates.tail(10).to_dict(orient="records")

        return {
            "capm_summary": capm_summary,
            "black_scholes_call": bs_call,
            "backtest_summary": backtest_summary,
            "volatility_regime": volatility_regime,
            "interest_rate": interest_rate,
            "liquidity": liquidity,
            "equity_plot": equity_plot,
            "drawdown_plot": drawdown_plot,
            "table_data": table_data,
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/")
async def root():
    return FileResponse("static/index.html")

def get_financial_data(ticker: str):
    """Fetch quarterly financial data from Yahoo Finance with caching"""
    try:
        # Check cache
        if ticker in financial_cache:
            cache_time, cached_data = financial_cache[ticker]
            if time.time() - cache_time < CACHE_DURATION:
                cached_data['cached'] = True
                cached_data['cache_timestamp'] = datetime.fromtimestamp(cache_time).strftime('%Y-%m-%d %H:%M:%S')
                return cached_data
        
        # Fetch fresh data
        stock = yf.Ticker(ticker)
        
        # Get quarterly financials and cashflow
        quarterly_financials = stock.quarterly_financials
        quarterly_balance_sheet = stock.quarterly_balance_sheet
        quarterly_cashflow = stock.quarterly_cashflow
        
        if quarterly_financials is None:
            raise Exception(f"No financial data available for {ticker}")
        
        # Get analyst data (estimates)
        info = stock.info if hasattr(stock, 'info') else {}
        
        # Extract latest quarters
        quarters_data = []
        max_quarters = min(4, len(quarterly_financials.columns))  # Last 4 quarters
        
        for i, date in enumerate(quarterly_financials.columns[:max_quarters]):
            quarter_date = date.strftime('%Y-Q%q')
            
            revenue = quarterly_financials.loc['Total Revenue', date] if 'Total Revenue' in quarterly_financials.index else None
            net_income = quarterly_financials.loc['Net Income', date] if 'Net Income' in quarterly_financials.index else None
            
            # Get operating cash flow from cashflow statement
            operating_cash_flow = None
            if quarterly_cashflow is not None and date in quarterly_cashflow.columns:
                if 'Operating Cash Flow' in quarterly_cashflow.index:
                    operating_cash_flow = quarterly_cashflow.loc['Operating Cash Flow', date]
                elif 'Total Cash From Operating Activities' in quarterly_cashflow.index:
                    operating_cash_flow = quarterly_cashflow.loc['Total Cash From Operating Activities', date]
            
            eps_ttm = info.get('trailingEps', 'N/A')
            forward_eps = info.get('forwardEps', 'N/A')
            
            quarters_data.append({
                'quarter': quarter_date,
                'revenue': revenue,
                'net_income': net_income,
                'operating_cash_flow': operating_cash_flow,
                'eps_ttm': eps_ttm,
                'forward_eps': forward_eps,
            })
        
        # Get key metrics
        financials = {
            'ticker': ticker,
            'company_name': info.get('longName', ticker),
            'quarterly_data': quarters_data,
            'current_metrics': {
                'pe_ratio': info.get('trailingPE', 'N/A'),
                'forward_pe': info.get('forwardPE', 'N/A'),
                'profit_margin': info.get('profitMargins', 'N/A'),
                'revenue_growth': info.get('revenueGrowth', 'N/A'),
                'earnings_growth': info.get('earningsGrowth', 'N/A'),
                'roe': info.get('returnOnEquity', 'N/A'),
                'roa': info.get('returnOnAssets', 'N/A'),
                'debt_to_equity': info.get('debtToEquity', 'N/A'),
                'current_ratio': info.get('currentRatio', 'N/A'),
                'dividend_yield': info.get('dividendYield', 'N/A'),
            },
            'analyst_data': {
                'target_price': info.get('targetMeanPrice', 'N/A'),
                'number_of_analysts': info.get('numberOfAnalysts', 'N/A'),
                'recommendation': info.get('recommendationKey', 'N/A'),
            },
            'cached': False,
            'fetch_timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        }
        
        # Cache the data
        financial_cache[ticker] = (time.time(), financials)
        return financials
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error fetching financial data: {str(e)}")

@app.get("/api/financials/{ticker}")
async def get_financials(ticker: str):
    """API endpoint to fetch financial data"""
    return get_financial_data(ticker.upper())

# Mount static files - robust for Vercel serverless
import os
import pathlib

# Try multiple paths to find static directory
static_dir = None
current_dir = pathlib.Path(__file__).parent.parent
possible_paths = [
    current_dir / "static",
    pathlib.Path("/vercel/path0/static"),
    pathlib.Path.cwd() / "static",
]

for path in possible_paths:
    if path.exists():
        static_dir = str(path)
        break

# Fallback to relative path
if static_dir is None:
    static_dir = str(current_dir / "static")

try:
    app.mount("/static", StaticFiles(directory=static_dir), name="static")
except Exception as e:
    print(f"Warning: Could not mount static files from {static_dir}: {e}")