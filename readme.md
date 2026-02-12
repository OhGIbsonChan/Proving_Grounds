## INSTALLATION
Create the new environment (Python 3.11) Run this to create the fresh foundation:
conda create -n proving_grounds python=3.11 -y
conda activate proving_grounds

The Magic Installation Command (Copy-Paste This) We are going to install things in a specific order to pin numpy to a version that works with financial libraries.
# 1. Install the core science stack first, pinning numpy to version 1.x
pip install "numpy<2.0" pandas matplotlib scipy

# 2. Install the UI and Logic tools
pip install streamlit pydantic plotly yfinance pyarrow

# 3. Install Backtesting
pip install backtesting

# 4. Install pandas_ta (The Development Version)
# The version on standard pip is broken/abandoned. We MUST use the GitHub version.
pip install git+https://github.com/twopirllc/pandas-ta.git@development