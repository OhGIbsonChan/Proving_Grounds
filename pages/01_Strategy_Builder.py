# pages/01_Strategy_Builder.py
import streamlit as st
import json
import os
import sys

# Add the root directory to sys.path so we can import 'strategies'
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from strategies.builder import StrategyRecipe, Rule, IndicatorConfig

# --- FIX: Use 'page_icon' instead of 'icon' ---
st.set_page_config(page_title="Strategy Builder", page_icon="🛠️")
st.title("🛠️ No-Code Strategy Builder")

# --- 1. SESSION STATE INIT ---
if "current_recipe" not in st.session_state:
    st.session_state.current_recipe = {
        "name": "My New Strategy",
        "entry_rules": [],
        "exit_rules": [],
        "stop_loss_atr": 2.0,
        "take_profit_atr": 3.0
    }

# --- 2. SIDEBAR HELPER ---
def rule_creator(key_prefix):
    col1, col2, col3 = st.columns([2, 1, 2])
    with col1:
        ind_a = st.selectbox("Indicator A", ["RSI", "SMA", "EMA", "Close"], key=f"{key_prefix}_a")
        # If it needs params, show them
        param_a = {}
        if ind_a in ["RSI", "SMA", "EMA"]:
            length = st.number_input("Length", value=14, key=f"{key_prefix}_a_len")
            param_a = {"length": length}
            
    with col2:
        op = st.selectbox("Operator", [">", "<", "=="], key=f"{key_prefix}_op")
        
    with col3:
        type_b = st.radio("Compare to:", ["Number", "Indicator"], horizontal=True, key=f"{key_prefix}_type")
        val_b = None
        ind_b = None
        
        if type_b == "Number":
            val_b = st.number_input("Value", value=50.0, key=f"{key_prefix}_val")
        else:
            ind_b_name = st.selectbox("Indicator B", ["SMA", "EMA", "Close"], key=f"{key_prefix}_b")
            param_b = {}
            if ind_b_name in ["SMA", "EMA"]:
                l_b = st.number_input("Length", value=50, key=f"{key_prefix}_b_len")
                param_b = {"length": l_b}
            # Construct the config object
            ind_b = {"name": ind_b_name, "params": param_b}

    return {
        "indicator_a": {"name": ind_a, "params": param_a},
        "operator": op,
        "indicator_b": val_b if type_b == "Number" else ind_b
    }

# --- 3. MAIN UI ---
st.subheader("Entry Rules (Buy)")
with st.expander("Add Entry Rule", expanded=True):
    new_rule = rule_creator("entry")
    if st.button("➕ Add Entry Rule"):
        st.session_state.current_recipe["entry_rules"].append(new_rule)

# --- REPLACEMENT BLOCK: Display Rules with Delete Capability ---
if st.session_state.current_recipe["entry_rules"]:
    st.markdown("#### Current Rules")
    # Iterate with index to allow deletion
    for i, r in enumerate(st.session_state.current_recipe["entry_rules"]):
        col_info, col_del = st.columns([5, 1])
        
        with col_info:
            # Format friendly text
            ind_a = r['indicator_a']['name']
            op = r['operator']
            target = r['indicator_b']
            target_str = target['name'] if isinstance(target, dict) else str(target)
            st.info(f"Rule {i+1}: {ind_a} {op} {target_str}")
            
        with col_del:
            # Unique key is crucial here
            if st.button("🗑️", key=f"del_rule_{i}", help="Remove this rule"):
                st.session_state.current_recipe["entry_rules"].pop(i)
                st.rerun() # Refresh immediately
else:
    st.caption("No entry rules yet.")

st.markdown("---")
st.subheader("Risk Management")
c1, c2 = st.columns(2)
# Update session state when these inputs change
st.session_state.current_recipe["stop_loss_atr"] = c1.number_input("Stop Loss (ATR)", 1.0, 10.0, float(st.session_state.current_recipe["stop_loss_atr"]))
st.session_state.current_recipe["take_profit_atr"] = c2.number_input("Take Profit (ATR)", 1.0, 20.0, float(st.session_state.current_recipe["take_profit_atr"]))

# --- 4. SAVE SYSTEM ---
st.markdown("---")
strat_name = st.text_input("Strategy Name", value=st.session_state.current_recipe["name"])

if st.button("💾 Save Strategy"):
    # Ensure directory exists
    os.makedirs("saved_strategies", exist_ok=True)
    
    # Update name in recipe
    st.session_state.current_recipe["name"] = strat_name
    
    # Save to JSON
    # We replace spaces with underscores for the filename
    safe_name = strat_name.replace(" ", "_")
    filepath = f"saved_strategies/{safe_name}.json"
    
    with open(filepath, "w") as f:
        json.dump(st.session_state.current_recipe, f, indent=4)
    
    st.success(f"Strategy saved to {filepath}! Go to the Main Dashboard to test it.")

# --- NEW SECTION: Manage Saved Strategies ---
st.markdown("---")
with st.expander("🗑️ Manage Saved Strategies"):
    # List all JSON files
    if not os.path.exists("saved_strategies"):
        st.caption("No saved strategies found.")
    else:
        files = [f for f in os.listdir("saved_strategies") if f.endswith(".json")]
        
        if not files:
            st.caption("No saved strategies found.")
        else:
            # Select strategy to delete
            selected_file = st.selectbox("Select Strategy to Delete", files)
            
            # Delete button with confirmation safety
            if st.button(f"❌ Delete '{selected_file}'", type="primary"):
                try:
                    os.remove(f"saved_strategies/{selected_file}")
                    st.success(f"Deleted {selected_file}!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error deleting file: {e}")