# Seed - Advanced Equity Strategy Analysis Platform

A powerful, intelligent platform for analyzing equity strategies with real-time market regime detection and predictive performance insights.

## 🌱 About the Project

**Seed** is a comprehensive equity analysis platform designed to help traders and investors make data-driven decisions. It combines advanced technical analysis with machine learning-powered market regime detection to identify optimal trading opportunities and evaluate strategy performance across different market conditions.

### Key Features

✨ **Market Regime Detection** - Intelligent identification of market trends (Uptrend, Downtrend, Sideways)

📊 **Performance Analytics** - Comprehensive metrics including Sharpe Ratio, Sortino Ratio, Maximum Drawdown, and Win Rate

💹 **Real-Time Data** - Live stock data from Yahoo Finance and macroeconomic data from FRED API

🎯 **Strategy Backtesting** - Test your trading strategies against historical data

📈 **Advanced Visualizations** - Interactive charts showing performance, drawdowns, and market regimes

⚡ **Fast Analysis** - Quick calculations using optimized pandas and NumPy operations

## 🛠️ Tech Stack

### Backend
- **FastAPI** - Modern, fast web framework for building APIs
- **Python 3.8+** - Core programming language
- **yfinance** - Fetching stock market data
- **pandas & NumPy** - Data manipulation and numerical computing
- **scipy** - Statistical calculations
- **fredapi** - Federal Reserve economic data

### Frontend
- **HTML5** - Semantic markup
- **CSS3** - Modern styling with animations
- **JavaScript (Vanilla)** - Interactive features and data visualization
- **Plotly.js** - Interactive charts and graphs

## 📋 System Requirements

- Python 3.8 or higher
- pip (Python package manager)
- Modern web browser (Chrome, Firefox, Safari, Edge)
- Internet connection (for fetching real-time data)

## 🚀 Installation & Setup

### Step 1: Clone or Download the Project

```bash
git clone https://github.com/yourusername/Equitystrategy.git
cd Equitystrategy
```

Or download as ZIP and extract to your desired location.

### Step 2: Create a Virtual Environment (Recommended)

```bash
# Create virtual environment
python3 -m venv .venv

# Activate virtual environment
# On macOS/Linux:
source .venv/bin/activate

# On Windows:
.venv\Scripts\activate
```

### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

Or install manually:

```bash
pip install fastapi uvicorn yfinance pandas numpy scipy plotly fredapi
```

## 🎯 How to Use

### Step 1: Start the Server

```bash
python3 -m uvicorn api.strategy:app --host 0.0.0.0 --port 8000
```

The server will start and display:
```
INFO:     Uvicorn running on http://0.0.0.0:8000
```

### Step 2: Open in Browser

Navigate to: **http://localhost:8000**

### Step 3: Run an Analysis

1. **Select a Ticker** - Choose a stock from the dropdown (AAPL, MSFT, GOOGL, etc.)
2. **Configure Parameters**:
   - **Market** - Select benchmark index (SPY, QQQ, IWM)
   - **Start Date** - Historical data starting point
   - **End Date** - Analysis end date
   - **Risk-Free Rate** - Annual risk-free rate for CAPM calculations
   - **Lookback Window** - Days for moving average calculation
   - **Strike Price** (optional) - For options pricing
   - **Days to Expiry** (optional) - For options valuation

3. **Run Analysis** - Click the "Run Analysis" button
4. **View Results**:
   - Performance charts
   - Key metrics (Sharpe Ratio, Sortino Ratio, Drawdown)
   - Market regime analysis
   - Advanced performance analytics

## 📁 Project Structure

```
Equitystrategy/
├── api/
│   └── strategy.py          # Main FastAPI application & analysis engine
├── static/
│   ├── index.html           # Frontend interface
│   └── script.js            # Client-side JavaScript
├── requirements.txt         # Python dependencies
└── README.md               # This file
```

## 🔧 Configuration

### Modifying Available Stocks

Edit the dropdown options in `static/index.html` to add or remove stocks:

```html
<option value="TICKER">Company Name (TICKER)</option>
```

### Adjusting Analysis Parameters

Default ranges can be modified in `static/script.js`:
- Lookback window range: 20-126 days
- Risk-free rate: Default 3.0%

## 📊 Available Metrics

### Performance Metrics
- **Cumulative Return** - Total return over the period
- **Annual Return** - Annualized performance
- **Sharpe Ratio** - Risk-adjusted returns
- **Sortino Ratio** - Downside risk-adjusted returns
- **Maximum Drawdown** - Largest peak-to-trough decline
- **Win Rate** - Percentage of winning days
- **Profit Factor** - Gross profit / Gross loss

### Market Regimes
- 🟢 **UPTREND** - Bullish market conditions
- 🔴 **DOWNTREND** - Bearish market conditions
- 🟡 **SIDEWAYS** - Range-bound market

## 🚨 Troubleshooting

### Port Already in Use
If port 8000 is already in use:
```bash
python3 -m uvicorn api.strategy:app --host 0.0.0.0 --port 8001
```

### Browser Cache Issues
If changes don't appear:
- **Mac**: Press Cmd+Shift+R
- **Windows/Linux**: Press Ctrl+Shift+R

### Connection Errors
- Ensure the server is running
- Check if firewall is blocking port 8000
- Verify internet connection (needed for fetching data)

### Missing Data
Some stocks may not have sufficient historical data. Try major stocks like AAPL, MSFT, GOOGL, etc.

## 📡 API Endpoints

### Analyze Strategy
```
POST /api/calculate
Body: {
    "ticker": "AAPL",
    "market": "SPY",
    "start_date": "2022-01-01",
    "end_date": "2024-01-01",
    "risk_free_rate": 3.0,
    "window": 63,
    "strike": null,
    "days_to_expiry": null
}
```

### Get Financial Data
```
GET /api/financials/{ticker}
```

## 🔐 Privacy & Data

- No user data is stored on the server
- All data comes from public APIs (Yahoo Finance, FRED)
- Analysis is performed on your browser/server only
- No personal information is collected

## 📈 Future Enhancements

- [ ] Portfolio optimization
- [ ] Options strategy analysis
- [ ] Real-time alerts
- [ ] Export analysis reports
- [ ] Machine learning predictions
- [ ] Multi-asset class support

## 📄 License

This project is open source. Feel free to use, modify, and distribute.

## 👤 Author

**Smit Patel**
- LinkedIn: [smitpatel22052002abcd](https://linkedin.com/in/smitpatel22052002abcd)

## 🤝 Support

For issues, questions, or suggestions:
1. Check the Troubleshooting section above
2. Review the code comments
3. Verify all dependencies are installed
4. Reach out via LinkedIn

## ⭐ Tips for Best Results

- Use 2+ years of historical data for reliable analysis
- Test with major liquid stocks first
- Verify market conditions before making trading decisions
- Combine with other analysis tools for better insights
- Monitor results regularly as markets evolve

---

**Disclaimer**: This tool is for educational and analytical purposes only. Always conduct thorough research and consult with financial advisors before making investment decisions.

**Happy Analyzing! 🚀**
