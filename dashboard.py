import streamlit as st
import pandas as pd
import numpy as np
import importlib
import pkgutil
import inspect
import sys
import base64
import io
import matplotlib.pyplot as plt
from backtesting import Backtest, Strategy
import config
from lib.data_loader import load_data
from strategies.base import BaseStrategy
import json
import os
from strategies.builder import UniversalStrategy, StrategyRecipe

# --- HELPER: AUTO-DISCOVER STRATEGIES ---
def get_strategies():
    strategies = {}
    # 1. Load Python Class Strategies (Existing logic)
    package_name = 'strategies'
    if package_name not in sys.modules:
        import strategies
    package = sys.modules[package_name]
    for _, name, _ in pkgutil.iter_modules(package.__path__):
        if name == 'base': continue
        try:
            module = importlib.import_module(f'{package_name}.{name}')
            for member_name, member_obj in inspect.getmembers(module):
                if (inspect.isclass(member_obj) and issubclass(member_obj, Strategy) and 
                    member_obj is not Strategy and member_obj is not BaseStrategy):
                    strategies[member_name] = member_obj
        except Exception:
            pass

    # 2. Load JSON Strategies (NEW)
    if os.path.exists("saved_strategies"):
        for filename in os.listdir("saved_strategies"):
            if filename.endswith(".json"):
                name = filename.replace(".json", "")
                
                # We create a "proxy" class that Backtesting.py can use
                # This effectively clones the UniversalStrategy class
                class CustomStrat(UniversalStrategy):
                    pass
                
                # Load the JSON recipe
                with open(f"saved_strategies/{filename}", "r") as f:
                    data = json.load(f)
                    recipe = StrategyRecipe(**data)
                
                # Inject the recipe into the class
                CustomStrat.recipe = recipe
                
                # Add to the dictionary with a special prefix
                strategies[f"Custom: {name}"] = CustomStrat
    return strategies

# --- HELPER: GENERATE EQUITY CURVE IMAGE ---
def get_equity_curve_image(equity_data):
    """
    Creates a lightweight PNG image of the equity curve for the report.
    """
    plt.figure(figsize=(6, 3))
    plt.plot(equity_data, color='#00cc44', linewidth=1.5)
    plt.title('Equity Curve', fontsize=10, color='#666')
    plt.grid(True, linestyle='--', alpha=0.3)
    plt.axis('off') # Hide axes for cleaner look
    
    # Save to buffer
    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight', transparent=False)
    plt.close()
    buf.seek(0)
    return base64.b64encode(buf.getvalue()).decode()

# --- HELPER: MOBILE REPORT GENERATOR ---
def create_mobile_report(stats, strategy_name, grade, grade_color, equity_img_b64):
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body {{ font-family: -apple-system, sans-serif; background: #f0f2f6; padding: 20px; }}
            .card {{ background: white; padding: 20px; border-radius: 15px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); margin-bottom: 20px; }}
            h1 {{ font-size: 20px; margin: 0 0 10px 0; color: #333; }}
            .grade {{ float: right; padding: 5px 15px; border-radius: 20px; color: white; font-weight: bold; background: {grade_color}; }}
            .metric {{ display: flex; justify-content: space-between; padding: 10px 0; border-bottom: 1px solid #eee; }}
            .metric:last-child {{ border-bottom: none; }}
            .label {{ color: #666; }}
            .value {{ font-weight: bold; color: #333; }}
            .chart-container {{ text-align: center; margin-top: 15px; border-top: 1px solid #eee; padding-top: 15px; }}
            img {{ max-width: 100%; height: auto; border-radius: 10px; }}
            .footer {{ text-align: center; color: #888; font-size: 12px; }}
        </style>
    </head>
    <body>
        <div class="card">
            <span class="grade">{grade.split(' ')[0]}</span>
            <h1>{strategy_name}</h1>
            <p style="color: #666; font-size: 14px; margin-top: -5px;">Performance Report</p>
            
            <div class="metric"><span class="label">Total Return</span><span class="value">{stats['Return [%]']:.2f}%</span></div>
            <div class="metric"><span class="label">Win Rate</span><span class="value">{stats['Win Rate [%]']:.2f}%</span></div>
            <div class="metric"><span class="label">Profit Factor</span><span class="value">{stats['Profit Factor']:.2f}</span></div>
            <div class="metric"><span class="label">Max Drawdown</span><span class="value">{stats['Max. Drawdown [%]']:.2f}%</span></div>
            
            <div class="chart-container">
                <img src="data:image/png;base64,{equity_img_b64}" alt="Equity Curve">
            </div>
        </div>

        <div class="card">
            <h3>Advanced Metrics</h3>
            <div class="metric"><span class="label">Sharpe Ratio</span><span class="value">{stats['Sharpe Ratio']:.2f}</span></div>
            <div class="metric"><span class="label">Sortino Ratio</span><span class="value">{stats['Sortino Ratio']:.2f}</span></div>
            <div class="metric"><span class="label">Kelly Criterion</span><span class="value">{stats['Kelly Criterion']:.2f}</span></div>
            <div class="metric"><span class="label">SQN</span><span class="value">{stats['SQN']:.2f}</span></div>
            <div class="metric"><span class="label">Total Trades</span><span class="value">{stats['# Trades']}</span></div>
        </div>
        
        <div class="footer">Generated by Proving Grounds</div>
    </body>
    </html>
    """
    return html

def calculate_grade(stats):
    pf = stats['Profit Factor']
    dd = abs(stats['Max. Drawdown [%]'])
    if stats['# Trades'] < 30: return "N/A", "gray"
    if pf < 1.0: return "F (Fail)", "red"
    
    score = 0
    if pf > 2.0: score += 3
    elif pf > 1.5: score += 2
    
    if dd < 10: score += 3
    elif dd < 20: score += 2
    
    if score >= 5: return "A (Excellent)", "green"
    if score >= 3: return "B (Good)", "orange"
    return "C (Mediocre)", "gray"

# --- MAIN ---
st.set_page_config(page_title="Proving Grounds", layout="wide")
st.title("🧪 Proving Grounds: Strategy Lab")

# Sidebar
STRAT_MAP = get_strategies()
selected_strat_name = st.sidebar.selectbox("Select Strategy", list(STRAT_MAP.keys()))
SelectedStrategy = STRAT_MAP[selected_strat_name]

# Load data once to get the global date range
@st.cache_data
def get_data_bounds():
    df = load_data(config.DATA_PATH, timeframe="1h") # Use 1h for speed just to get dates
    return df.index.min(), df.index.max()

min_data_date, max_data_date = get_data_bounds()

# --- SIDEBAR UPDATES ---
st.sidebar.header("⏱️ Timeframe & Data Split")
selected_tf = st.sidebar.selectbox("Select Timeframe", ["1min", "5min", "15min", "1h"], index=0)
initial_cash = st.sidebar.number_input("Starting Cash ($)", value=100000)
leverage = st.sidebar.slider("Leverage", 1, 50, 20)
comm = st.sidebar.number_input("Comm ($)", value=1.25) / 30000 
# NEW: Slippage Input (as a percentage of price)
slippage_pct = st.sidebar.number_input("Slippage (%)", value=0.01, step=0.01) / 100
total_friction = comm + slippage_pct

# Dynamic Date Range for OSS
# We use the min/max from the actual data file here
col_start, col_end = st.sidebar.columns(2)
start_date = col_start.date_input(
    "Start Date", 
    value=min_data_date.date(),
    min_value=min_data_date.date(),
    max_value=max_data_date.date()
)
end_date = col_end.date_input(
    "End Date", 
    value=max_data_date.date(),
    min_value=min_data_date.date(),
    max_value=max_data_date.date()
)

params = {}
# Check if the strategy has a Config class (Pydantic model)
if hasattr(SelectedStrategy, 'Config'):
    st.sidebar.markdown("### ⚙️ Strategy Parameters")
    
    # Support Pydantic V1 and V2
    fields = getattr(SelectedStrategy.Config, 'model_fields', {}) or getattr(SelectedStrategy.Config, '__fields__', {})
    
    for name, field in fields.items():
        # Get metadata (Default value, Title, Limits)
        default_val = field.default
        title = field.title if hasattr(field, 'title') and field.title else name
        
        # Render appropriate input widget
        if isinstance(default_val, float):
            params[name] = st.sidebar.number_input(f"{title}", value=float(default_val))
        elif isinstance(default_val, int):
            params[name] = st.sidebar.number_input(f"{title}", value=int(default_val), step=1)
        elif isinstance(default_val, bool):
            params[name] = st.sidebar.checkbox(f"{title}", value=default_val)

    # --- SMART TIME ESTIMATOR ---
    # 1. Load full data ONLY if we haven't already (Streamlit caches this)
    full_df = load_data(config.DATA_PATH, timeframe=selected_tf)
    
    # 2. Filter by the dates user selected to get TRUE count
    tz = "America/New_York"
    # Convert inputs to Timestamps (matching the dataframe index timezone)
    # Note: We assume the DF is loaded with a timezone, usually UTC or NY. 
    # If the logic inside load_data is complex, we just do a rough estimate using dates.
    
    mask = (full_df.index.date >= start_date) & (full_df.index.date <= end_date)
    filtered_len = len(full_df[mask])
    
    # 3. Calculate Estimate (10s per 500k rows is a rough baseline for Python backtesting)
    est_seconds = (filtered_len / 500000) * 10 
    if est_seconds < 1: est_seconds = 1
    
    st.info(f"📊 Selected Data: {filtered_len:,.0f} candles. Estimated Run Time: ~{est_seconds:.0f} seconds.")

    if st.button("🚀 Run Backtest"):
        # Create a progress placeholder
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        try:
            # STEP 1: LOAD DATA
            status_text.text("📂 Loading Data...")
            progress_bar.progress(10)
            df = load_data(config.DATA_PATH, timeframe=selected_tf)
            
            # STEP 2: PREPARE TIMEZONES
            status_text.text("🌍 Aligning Timezones...")
            progress_bar.progress(30)
            
            tz = "America/New_York"
            start_ts = pd.Timestamp(start_date).tz_localize(tz)
            end_ts = pd.Timestamp(end_date).tz_localize(tz).replace(hour=23, minute=59, second=59)
            
            # Handle timezone naive/aware mismatch if needed
            if df.index.tz is None:
                df.index = df.index.tz_localize('UTC').tz_convert(tz)
            else:
                df.index = df.index.tz_convert(tz)
                
            df = df.loc[start_ts:end_ts]
            
            if df.empty:
                st.error("No data available for the selected date range.")
                progress_bar.empty()
            else:
                # STEP 3: INITIALIZE BACKTEST
                status_text.text("⚙️ Initializing Engine...")
                progress_bar.progress(50)
                
                bt = Backtest(
                    df, 
                    SelectedStrategy, 
                    cash=initial_cash, 
                    commission=total_friction, 
                    margin=1/leverage, 
                    trade_on_close=False
                )
                
                # STEP 4: RUN SIMULATION
                status_text.text("🏃 Running Simulation... (This may take a moment)")
                progress_bar.progress(70)
                
                stats = bt.run(**params)
                
                progress_bar.progress(100)
                status_text.text("✅ Complete!")
                
                # --- Generate Assets ---
                # ... (Rest of your existing code below this line remains the same) ...
                grade, color = calculate_grade(stats)
                equity_curve = stats['_equity_curve']['Equity']
                
                # Downsample for PNG generation (speed up)
                if len(equity_curve) > 2000:
                    equity_curve_img_data = equity_curve.iloc[::len(equity_curve)//2000]
                else:
                    equity_curve_img_data = equity_curve
                    
                img_b64 = get_equity_curve_image(equity_curve_img_data)
                report_html = create_mobile_report(stats, selected_strat_name, grade, color, img_b64)
                
                # --- Display ---
                st.markdown(f"<h2 style='color:{color}'>Grade: {grade}</h2>", unsafe_allow_html=True)
                
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Return", f"{stats['Return [%]']:.2f}%")
                col2.metric("Profit Factor", f"{stats['Profit Factor']:.2f}")
                col3.metric("Sortino", f"{stats['Sortino Ratio']:.2f}")
                col4.metric("Kelly", f"{stats['Kelly Criterion']:.2f}")
                
                b64 = base64.b64encode(report_html.encode()).decode()
                href = f'<a href="data:text/html;base64,{b64}" download="report_mobile.html"><button style="background:#ff4b4b;color:white;padding:10px;border:none;border-radius:5px;cursor:pointer;">📱 Download Mobile Report</button></a>'
                st.markdown(href, unsafe_allow_html=True)

                # --- 5. DESKTOP DETAILED VIEW ---
                st.markdown("---")
                st.subheader("🖥️ Desktop Dashboard")

                # A. Interactive Equity Curve (Downsampled for Speed)
                st.caption("Equity Curve (Interactive)")
                equity_curve = stats['_equity_curve']['Equity']
                
                # Downsample: If > 5000 points, show every Nth point to prevent crashing
                if len(equity_curve) > 5000: 
                    downsample_rate = len(equity_curve) // 5000
                    st.line_chart(equity_curve.iloc[::downsample_rate])
                else:
                    st.line_chart(equity_curve)

                # B. Full Statistics Table (Sanitized)
                # We convert to string to prevent the "PyArrow/Streamlit" error
                clean_stats = stats.drop(['_equity_curve', '_trades', '_strategy'], errors='ignore')
                clean_stats_df = clean_stats.to_frame(name="Value").astype(str)

                with st.expander("📊 View Full Statistics", expanded=True):
                    st.dataframe(clean_stats_df, use_container_width=True)

                # --- NEW: MONTE CARLO SIMULATION SECTION ---
                st.markdown("---")
                st.subheader("🎲 Monte Carlo Risk Analysis")

                # Sidebar settings for Monte Carlo
                n_simulations = st.sidebar.slider("MC Iterations", 100, 1000, 500)
                sample_size = len(stats['_trades'])

                if sample_size > 10:
                    trades_pnl = stats['_trades']['PnL'].values
                    
                    # Run Simulations
                    mc_results = []
                    for _ in range(n_simulations):
                        # Shuffle the trades with replacement
                        sim_trades = np.random.choice(trades_pnl, size=sample_size, replace=True)
                        # Calculate equity curve for this simulation
                        sim_equity = np.cumsum(sim_trades) + initial_cash
                        mc_results.append(sim_equity)
                    
                    # Plotting
                    fig, ax = plt.subplots(figsize=(10, 5))
                    for run in mc_results[:100]: # Plot first 100 paths for clarity
                        ax.plot(run, color='gray', alpha=0.1, linewidth=0.5)
                    
                    # Highlight the 5th and 95th percentile paths
                    mc_array = np.array(mc_results)
                    ax.plot(np.percentile(mc_array, 95, axis=0), color='green', label='95th Percentile', linewidth=2)
                    ax.plot(np.percentile(mc_array, 5, axis=0), color='red', label='5th Percentile (Worst Case)', linewidth=2)
                    ax.plot(np.mean(mc_array, axis=0), color='blue', label='Average Path', linestyle='--')
                    
                    ax.set_title(f"Monte Carlo: {n_simulations} Shuffled Equity Paths")
                    ax.set_ylabel("Account Balance ($)")
                    ax.set_xlabel("Trade Number")
                    ax.legend()
                    st.pyplot(fig)

                    # Risk Metrics
                    final_balances = mc_array[:, -1]
                    ruin_count = np.sum(final_balances < initial_cash)
                    
                    m_col1, m_col2, m_col3 = st.columns(3)
                    m_col1.metric("Prob. of Profit", f"{(1 - ruin_count/n_simulations)*100:.1f}%")
                    m_col2.metric("Median Final Equity", f"${np.median(final_balances):,.0f}")
                    m_col3.metric("Max MC Drawdown", f"${(np.max(mc_array) - np.min(mc_array)):,.0f}")
                else:
                    st.warning("Not enough trades to run a reliable Monte Carlo simulation.")

                # C. Trade Log (Sanitized & Limited)
                trades = stats['_trades'].copy()
                
                # Fix Duration formatting
                if 'Duration' in trades.columns:
                    trades['Duration'] = trades['Duration'].astype(str)
                
                # Limit to last 2000 trades to prevent "Out of Memory"
                if len(trades) > 2000:
                    st.warning(f"⚠️ Showing last 2,000 trades (Total: {len(trades)}) to save memory.")
                    trades = trades.iloc[-2000:]
                    
                with st.expander("📝 View Trade Log"):
                    st.dataframe(trades.astype(str), use_container_width=True)

        except Exception as e:
            st.error(f"Error: {e}")
            import traceback
            st.code(traceback.format_exc())