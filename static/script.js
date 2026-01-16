// Store latest result for advanced metrics
let lastResult = null;
let lastTicker = null;

// Remove splash screen after animation completes
window.addEventListener('load', function() {
    setTimeout(function() {
        const splashScreen = document.querySelector('.splash-screen');
        if (splashScreen) {
            splashScreen.remove();
        }
    }, 2300); // 1.5s animation delay + 0.8s fade out
});

// Text animation for hero title
function animateTitle() {
    const titleElement = document.getElementById('animatedTitle');
    if (!titleElement) return;
    
    const text = titleElement.textContent.trim();
    titleElement.innerHTML = '';
    
    // Create spans for each character with delay
    text.split('').forEach((char, index) => {
        const span = document.createElement('span');
        span.textContent = char;
        span.style.animationDelay = `${index * 40}ms`;
        titleElement.appendChild(span);
    });
}

// Initialize title animation on page load
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', animateTitle);
} else {
    // If DOM is already loaded, run immediately
    animateTitle();
}

// Function to auto-fetch financial data when inputs change
async function autoUpdateFinancials() {
    let ticker = lastTicker || document.getElementById('ticker')?.value;
    
    if (!ticker) {
        console.log('No ticker available for auto-update');
        return;
    }
    
    try {
        // Silently fetch financial data without showing modal
        const response = await fetch(`/api/financials/${ticker}?t=${Date.now()}`);
        if (response.ok) {
            const financialData = await response.json();
            // Update financials only if modal is visible or store for when it opens
            console.log('Auto-updating financials for', ticker);
        } else {
            console.log('Failed to fetch financials:', response.status);
        }
    } catch (error) {
        // Silently fail - don't disrupt user experience
        console.log('Auto-update financials failed (silent):', error);
    }
}

// Company selector dropdown - ensure DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    const companyDropdown = document.getElementById('companyDropdown');
    const formSection = document.getElementById('formSection');
    
    console.log('DOM ready - companyDropdown:', companyDropdown);
    console.log('DOM ready - formSection:', formSection);
    
    if (companyDropdown && formSection) {
        companyDropdown.addEventListener('change', function() {
            const ticker = this.value;
            console.log('Ticker selected:', ticker);
            
            if (ticker) {
                // Update ticker input
                document.getElementById('ticker').value = ticker;
                lastTicker = ticker;
                
                // Show form section - force display
                formSection.style.display = 'block';
                formSection.classList.add('visible');
                console.log('Form classList:', formSection.classList);
                console.log('Form display style:', formSection.style.display);
                
                // Set default dates to last 2 years
                const endDate = new Date();
                const startDate = new Date();
                startDate.setFullYear(startDate.getFullYear() - 2);
                
                document.getElementById('endDate').valueAsDate = endDate;
                document.getElementById('startDate').valueAsDate = startDate;
            } else {
                formSection.style.display = 'none';
                formSection.classList.remove('visible');
            }
        });
        console.log('Event listener attached successfully');
    } else {
        console.error('Could not find companyDropdown or formSection');
    }
});

// Add event listeners to all input fields to auto-update financials
const inputFields = [
    'market',
    'startDate',
    'endDate',
    'riskFreeRate',
    'window',
    'strike',
    'daysToExpiry'
];

// Wait for DOM to be ready before adding listeners
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function() {
        inputFields.forEach(fieldId => {
            const element = document.getElementById(fieldId);
            if (element) {
                element.addEventListener('change', autoUpdateFinancials);
                element.addEventListener('input', autoUpdateFinancials);
            }
        });
    });
} else {
    // DOM already loaded
    inputFields.forEach(fieldId => {
        const element = document.getElementById(fieldId);
        if (element) {
            element.addEventListener('change', autoUpdateFinancials);
            element.addEventListener('input', autoUpdateFinancials);
        }
    });
}

// Form submission
document.getElementById('analyzeBtn').addEventListener('click', async function(e) {
    e.preventDefault();
    
    const ticker = document.getElementById('ticker').value;
    const market = document.getElementById('market').value;
    const startDate = document.getElementById('startDate').value;
    const endDate = document.getElementById('endDate').value;
    const riskFreeRate = parseFloat(document.getElementById('riskFreeRate').value);
    const window = parseInt(document.getElementById('window').value);
    const strike = document.getElementById('strike').value ? parseFloat(document.getElementById('strike').value) : null;
    const daysToExpiry = parseInt(document.getElementById('daysToExpiry').value);
    
    if (!ticker || !market || !startDate || !endDate || !riskFreeRate || !window || !daysToExpiry) {
        alert('Please fill in all required fields');
        return;
    }
    
    // Show loading
    document.getElementById('loadingSection').classList.add('visible');
    document.getElementById('resultsSection').classList.remove('visible');
    
    try {
        const response = await fetch('/api/calculate', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                ticker: ticker,
                market: market,
                start: startDate,
                end: endDate,
                risk_free: riskFreeRate,
                window: window,
                strike: strike,
                days: daysToExpiry
            })
        });
        
        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(errorText);
        }
        
        const result = await response.json();
        
        // Store result for advanced tools
        lastResult = result;
        
        // Hide loading, show results
        document.getElementById('loadingSection').classList.remove('visible');
        document.getElementById('resultsSection').classList.add('visible');
        
        // Render metrics
        const metricsContainer = document.getElementById('metricsContainer');
        metricsContainer.innerHTML = '';
        
        const metrics = [
            {
                label: 'Strategy Return',
                value: (result.backtest_summary.strategy_return * 100).toFixed(2) + '%'
            },
            {
                label: 'Buy & Hold Return',
                value: (result.backtest_summary.buy_hold_return * 100).toFixed(2) + '%'
            },
            {
                label: 'Beta',
                value: result.capm_summary.beta.toFixed(3)
            },
            {
                label: 'Expected Annual Return',
                value: (result.capm_summary.expected_annual_return * 100).toFixed(2) + '%'
            },
            {
                label: 'Realized Volatility',
                value: (result.volatility_regime.realized_volatility * 100).toFixed(2) + '%'
            },
            {
                label: 'Hit Rate',
                value: (result.backtest_summary.hit_rate * 100).toFixed(2) + '%'
            }
        ];
        
        metrics.forEach(metric => {
            const card = document.createElement('div');
            card.className = 'metric-card';
            card.innerHTML = `
                <div class="metric-label">${metric.label}</div>
                <div class="metric-value">${metric.value}</div>
            `;
            metricsContainer.appendChild(card);
        });
        
        // Render charts
        renderCharts(result);
        
        // Render backtest table
        renderBacktestTable(result.table_data);
        
    } catch (error) {
        alert('Error: ' + error.message);
        document.getElementById('loadingSection').classList.remove('visible');
    }
});

function renderCharts(result) {
    // Use backend-generated matplotlib images for accurate visualization
    const equityChart = document.getElementById('equityCurveChart');
    const drawdownChart = document.getElementById('drawdownChart');
    
    // Set images directly (base64 data URIs don't need cache busting)
    if (equityChart && result.equity_plot) {
        equityChart.src = result.equity_plot;
    }
    
    if (drawdownChart && result.drawdown_plot) {
        drawdownChart.src = result.drawdown_plot;
    }
}

function renderBacktestTable(tableData) {
    const tbody = document.getElementById('backtestBody');
    tbody.innerHTML = '';
    
    tableData.forEach(row => {
        const tr = document.createElement('tr');
        const daysValue = parseInt(row.days) || 0;
        tr.innerHTML = `
            <td>${row.Date}</td>
            <td>${(row.stock_ret * 100).toFixed(2)}%</td>
            <td>${daysValue}</td>
            <td>${(row.strategy_ret * 100).toFixed(2)}%</td>
        `;
        tbody.appendChild(tr);
    });
}

function resetAnalysis() {
    document.getElementById('formSection').classList.remove('visible');
    document.getElementById('resultsSection').classList.remove('visible');
    document.getElementById('loadingSection').classList.remove('visible');
    document.getElementById('companyDropdown').value = '';
    document.getElementById('ticker').value = '';
}

// Set initial date values
document.addEventListener('DOMContentLoaded', function() {
    // Set today's date
    const today = new Date().toISOString().split('T')[0];
    document.getElementById('endDate').value = today;
    
    // Set date 2 years ago
    const twoYearsAgo = new Date();
    twoYearsAgo.setFullYear(twoYearsAgo.getFullYear() - 2);
    document.getElementById('startDate').value = twoYearsAgo.toISOString().split('T')[0];
    
    // Set default values
    document.getElementById('riskFreeRate').value = '4.5';
    document.getElementById('window').value = '63';
    document.getElementById('daysToExpiry').value = '30';
});

// ============ ADVANCED TOOLS MODAL ============

// Advanced metrics calculation functions
const TRADING_DAYS = 252;

function calculateAnnualizedReturn(tableData) {
    if (!tableData || tableData.length === 0) return NaN;
    let equity = 1;
    tableData.forEach(row => {
        equity *= (1 + parseFloat(row.strategy_ret));
    });
    const years = tableData.length / TRADING_DAYS;
    return Math.pow(equity, 1 / years) - 1;
}

function calculateAnnualizedVol(tableData) {
    if (!tableData || tableData.length === 0) return NaN;
    const returns = tableData.map(r => parseFloat(r.strategy_ret));
    const mean = returns.reduce((a, b) => a + b, 0) / returns.length;
    const variance = returns.reduce((a, b) => a + Math.pow(b - mean, 2), 0) / returns.length;
    const stdDev = Math.sqrt(variance);
    return stdDev * Math.sqrt(TRADING_DAYS);
}

function calculateDownsideVol(tableData, mar = 0) {
    if (!tableData || tableData.length === 0) return NaN;
    const downside = tableData
        .map(r => parseFloat(r.strategy_ret))
        .filter(r => r < mar);
    if (downside.length === 0) return 0;
    const mean = downside.reduce((a, b) => a + b, 0) / downside.length;
    const variance = downside.reduce((a, b) => a + Math.pow(b - mean, 2), 0) / downside.length;
    return Math.sqrt(variance) * Math.sqrt(TRADING_DAYS);
}

function calculateSharpeRatio(tableData, rfAnnual = 0.045) {
    if (!tableData || tableData.length === 0) return NaN;
    const rfDaily = Math.pow(1 + rfAnnual, 1 / TRADING_DAYS) - 1;
    const excessReturns = tableData.map(r => parseFloat(r.strategy_ret) - rfDaily);
    const mean = excessReturns.reduce((a, b) => a + b, 0) / excessReturns.length;
    const variance = excessReturns.reduce((a, b) => a + Math.pow(b - mean, 2), 0) / excessReturns.length;
    const vol = Math.sqrt(variance);
    if (vol === 0) return NaN;
    return (mean / vol) * Math.sqrt(TRADING_DAYS);
}

function calculateSortinoRatio(tableData, rfAnnual = 0.045) {
    if (!tableData || tableData.length === 0) return NaN;
    const rfDaily = Math.pow(1 + rfAnnual, 1 / TRADING_DAYS) - 1;
    const excessReturns = tableData.map(r => parseFloat(r.strategy_ret) - rfDaily);
    const downside = excessReturns.filter(r => r < 0);
    if (downside.length === 0) return NaN;
    
    const meanExcess = excessReturns.reduce((a, b) => a + b, 0) / excessReturns.length;
    const downsideVariance = downside.reduce((a, b) => a + Math.pow(b, 2), 0) / excessReturns.length;
    const downsideVol = Math.sqrt(downsideVariance);
    
    if (downsideVol === 0) return NaN;
    return (meanExcess * TRADING_DAYS) / downsideVol;
}

function calculateInfoRatio(tableData) {
    if (!tableData || tableData.length === 0) return NaN;
    const strategyReturns = tableData.map(r => parseFloat(r.strategy_ret));
    const benchmarkReturns = tableData.map(r => parseFloat(r.market_ret));
    const activeReturns = strategyReturns.map((s, i) => s - benchmarkReturns[i]);
    
    const mean = activeReturns.reduce((a, b) => a + b, 0) / activeReturns.length;
    const variance = activeReturns.reduce((a, b) => a + Math.pow(b - mean, 2), 0) / activeReturns.length;
    const te = Math.sqrt(variance);
    
    if (te === 0) return NaN;
    return (mean / te) * Math.sqrt(TRADING_DAYS);
}

function calculateMaxDrawdown(tableData) {
    if (!tableData || tableData.length === 0) return NaN;
    let equity = 1;
    let maxEquity = 1;
    let maxDD = 0;
    
    tableData.forEach(row => {
        equity *= (1 + parseFloat(row.strategy_ret));
        maxEquity = Math.max(maxEquity, equity);
        const dd = (maxEquity - equity) / maxEquity;
        maxDD = Math.max(maxDD, dd);
    });
    
    return maxDD;
}

function calculateHitRate(tableData) {
    if (!tableData || tableData.length === 0) return NaN;
    const positiveReturns = tableData.filter(r => parseFloat(r.strategy_ret) > 0).length;
    return positiveReturns / tableData.length;
}

// Display advanced metrics in modal
function displayAdvancedMetrics(result) {
    const container = document.getElementById('advancedMetricsContainer');
    container.innerHTML = '';
    
    const tableData = result.table_data;
    const rfRate = result.risk_free_rate ? result.risk_free_rate / 100 : 0.045;
    
    const metrics = [
        {
            label: 'Annualized Return',
            value: (calculateAnnualizedReturn(tableData) * 100).toFixed(2) + '%',
            description: 'Strategy annual return based on compound growth',
            tooltip: 'The compound annual growth rate (CAGR) of your strategy. Higher is better, but should be evaluated with risk metrics.'
        },
        {
            label: 'Annualized Volatility',
            value: (calculateAnnualizedVol(tableData) * 100).toFixed(2) + '%',
            description: 'Standard deviation of daily returns annualized',
            tooltip: 'Measures the variability of returns. Lower volatility means more consistent performance. Compare against market volatility (typically 15-20%).'
        },
        {
            label: 'Sharpe Ratio',
            value: calculateSharpeRatio(tableData, rfRate).toFixed(3),
            description: 'Risk-adjusted return per unit of volatility',
            tooltip: 'Indicates excess return per unit of risk. Higher is better. Above 1 is good, above 2 is excellent, above 3 is exceptional.'
        },
        {
            label: 'Sortino Ratio',
            value: calculateSortinoRatio(tableData, rfRate).toFixed(3),
            description: 'Risk-adjusted return focusing on downside risk',
            tooltip: 'Similar to Sharpe but only penalizes downside volatility. Better measure for strategies with asymmetric risk profiles.'
        },
        {
            label: 'Information Ratio',
            value: calculateInfoRatio(tableData).toFixed(3),
            description: 'Excess return per unit of tracking error vs benchmark',
            tooltip: 'Measures active management skill. Above 0.5 is good, above 1.0 is excellent. Negative means underperformance vs benchmark.'
        },
        {
            label: 'Downside Volatility',
            value: (calculateDownsideVol(tableData, 0) * 100).toFixed(2) + '%',
            description: 'Volatility of negative returns only',
            tooltip: 'Focuses on the variability of losses. Lower downside volatility is preferable. Key for risk management and downside protection.'
        },
        {
            label: 'Maximum Drawdown',
            value: (calculateMaxDrawdown(tableData) * 100).toFixed(2) + '%',
            description: 'Peak-to-trough decline from highest point',
            tooltip: 'The largest peak-to-trough decline experienced. Shows worst-case scenario. Important for understanding recovery time needed.'
        },
        {
            label: 'Hit Rate',
            value: (calculateHitRate(tableData) * 100).toFixed(2) + '%',
            description: 'Percentage of positive return days',
            tooltip: 'Percentage of trading days with positive returns. Higher hit rate provides psychological comfort and consistency, but doesn\'t measure magnitude.'
        }
    ];
    
    metrics.forEach(metric => {
        const card = document.createElement('div');
        card.className = 'metric-modal-card';
        card.innerHTML = `
            <div class="metric-modal-label">
                ${metric.label}
                <span class="metric-tooltip-icon" title="${metric.tooltip}">?</span>
            </div>
            <div class="metric-modal-value">${isNaN(parseFloat(metric.value)) ? 'N/A' : metric.value}</div>
            <div class="metric-modal-description">${metric.description}</div>
            <div class="metric-tooltip-content">${metric.tooltip}</div>
        `;
        container.appendChild(card);
    });
}

// Modal event listeners
document.getElementById('advancedToolsBtn').addEventListener('click', function() {
    if (lastResult) {
        displayAdvancedMetrics(lastResult);
        document.getElementById('advancedToolsModal').classList.add('visible');
    } else {
        alert('Please run an analysis first');
    }
});

document.getElementById('closeModalBtn').addEventListener('click', function() {
    document.getElementById('advancedToolsModal').classList.remove('visible');
});

document.getElementById('advancedToolsModal').addEventListener('click', function(e) {
    if (e.target === this) {
        this.classList.remove('visible');
    }
});

// ============ FINANCIALS MODAL ============

document.getElementById('financialsBtn').addEventListener('click', async function() {
    // Use ticker from analysis or from current dropdown selection
    let ticker = lastResult ? lastResult.capm_summary.ticker : (lastTicker || document.getElementById('ticker').value);
    
    console.log('Financials button clicked. Ticker:', ticker, 'lastTicker:', lastTicker, 'lastResult:', lastResult);
    
    if (!ticker) {
        alert('Please select a ticker first');
        return;
    }
    
    document.getElementById('financialsModal').classList.add('visible');
    document.getElementById('financialsLoading').style.display = 'block';
    document.getElementById('financialsContent').style.display = 'none';
    
    try {
        // Force fetch with cache busting to ensure fresh data
        const response = await fetch(`/api/financials/${ticker}?t=${Date.now()}`);
        if (!response.ok) {
            throw new Error('Failed to fetch financial data');
        }
        
        const financialData = await response.json();
        console.log('Financial data fetched for', ticker, ':', financialData);
        displayFinancialData(financialData);
        
    } catch (error) {
        alert('Error fetching financial data: ' + error.message);
        document.getElementById('financialsModal').classList.remove('visible');
    }
});

function displayFinancialData(data) {
    const title = document.getElementById('financialsTitle');
    title.textContent = `${data.company_name} (${data.ticker}) - Quarterly Financials`;
    
    // Display cache info
    const cacheInfo = document.getElementById('cacheInfo');
    if (data.cached) {
        cacheInfo.innerHTML = `<strong>✓ Cached Data:</strong> Last fetched on ${data.cache_timestamp}. Data will refresh after 1 hour.`;
    } else {
        cacheInfo.innerHTML = `<strong>✓ Fresh Data:</strong> Fetched on ${data.fetch_timestamp}`;
    }
    
    // Display key metrics
    const keyMetricsContainer = document.getElementById('keyMetricsContainer');
    keyMetricsContainer.innerHTML = '';
    
    const metricsToDisplay = [
        { key: 'pe_ratio', label: 'P/E Ratio', suffix: '' },
        { key: 'forward_pe', label: 'Forward P/E', suffix: '' },
        { key: 'profit_margin', label: 'Profit Margin', suffix: '%' },
        { key: 'revenue_growth', label: 'Revenue Growth', suffix: '%' },
        { key: 'earnings_growth', label: 'Earnings Growth', suffix: '%' },
        { key: 'roe', label: 'ROE', suffix: '%' },
        { key: 'roa', label: 'ROA', suffix: '%' },
        { key: 'debt_to_equity', label: 'Debt to Equity', suffix: '' },
        { key: 'current_ratio', label: 'Current Ratio', suffix: '' },
        { key: 'dividend_yield', label: 'Dividend Yield', suffix: '%' },
    ];
    
    metricsToDisplay.forEach(metric => {
        const value = data.current_metrics[metric.key];
        const card = document.createElement('div');
        card.className = 'financials-metric-card';
        
        let displayValue = 'N/A';
        if (value !== 'N/A' && value !== null) {
            if (typeof value === 'number') {
                displayValue = (value * 100).toFixed(2) + metric.suffix;
            } else {
                displayValue = value.toFixed(2) + metric.suffix;
            }
        }
        
        card.innerHTML = `
            <div class="financials-metric-label">${metric.label}</div>
            <div class="financials-metric-value">${displayValue}</div>
        `;
        keyMetricsContainer.appendChild(card);
    });
    
    // Display analyst data
    const analystContainer = document.getElementById('analystDataContainer');
    analystContainer.innerHTML = '';
    
    const analystMetrics = [
        { key: 'target_price', label: 'Analyst Target Price', suffix: '$' },
        { key: 'number_of_analysts', label: 'Number of Analysts', suffix: '' },
        { key: 'recommendation', label: 'Recommendation', suffix: '' },
    ];
    
    analystMetrics.forEach(metric => {
        const value = data.analyst_data[metric.key];
        const card = document.createElement('div');
        card.className = 'financials-metric-card';
        
        let displayValue = 'N/A';
        if (value !== 'N/A' && value !== null) {
            displayValue = metric.suffix + (typeof value === 'number' ? value.toFixed(2) : value);
        }
        
        card.innerHTML = `
            <div class="financials-metric-label">${metric.label}</div>
            <div class="financials-metric-value">${displayValue}</div>
        `;
        analystContainer.appendChild(card);
    });
    
    // Display quarterly data
    const quarterlyContainer = document.getElementById('quarterlyDataContainer');
    quarterlyContainer.innerHTML = '';
    
    data.quarterly_data.forEach(quarter => {
        const row = document.createElement('tr');
        
        const revenue = quarter.revenue ? (quarter.revenue / 1e9).toFixed(2) + 'B' : 'N/A';
        const netIncome = quarter.net_income ? (quarter.net_income / 1e9).toFixed(2) + 'B' : 'N/A';
        const ocf = quarter.operating_cash_flow ? (quarter.operating_cash_flow / 1e9).toFixed(2) + 'B' : 'N/A';
        const eps = typeof quarter.eps_ttm === 'number' ? quarter.eps_ttm.toFixed(2) : 'N/A';
        
        row.innerHTML = `
            <td>${quarter.quarter}</td>
            <td>${revenue}</td>
            <td>${netIncome}</td>
            <td>${ocf}</td>
            <td>${eps}</td>
        `;
        quarterlyContainer.appendChild(row);
    });
    
    document.getElementById('financialsLoading').style.display = 'none';
    document.getElementById('financialsContent').style.display = 'block';
}

document.getElementById('closeFinancialsBtn').addEventListener('click', function() {
    document.getElementById('financialsModal').classList.remove('visible');
});

document.getElementById('financialsModal').addEventListener('click', function(e) {
    if (e.target === this) {
        this.classList.remove('visible');
    }
});