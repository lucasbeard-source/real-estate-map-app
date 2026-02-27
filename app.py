import streamlit as st
import requests
import pandas as pd

st.set_page_config(page_title="MLS Status Discovery", layout="wide")

st.title("🕵️‍♂️ Definitive MLS Status Tester")
st.markdown("Testing the 14 official RESO statuses provided by the Slipstream documentation to see exactly what your API key is allowed to access.")

# --- FETCH API KEY ---
if "SLIPSTREAM_API_KEY" in st.secrets:
    api_key = st.secrets["SLIPSTREAM_API_KEY"]
else:
    api_key = None
    st.error("🚨 API Key not found! Please add 'SLIPSTREAM_API_KEY' to your Streamlit Cloud Secrets.")

# --- UI INPUTS ---
st.markdown("---")
market_id = st.text_input("Market ID to Test", value="sfar")

# The exact 14 statuses from the Slipstream documentation screenshot
default_statuses = "Active, Active Under Contract, Canceled, Closed, Coming Soon, Comp, Deleted, Expired, Hold, Incomplete, Off Market, Other, Pending, Withdrawn"
status_input = st.text_area("Official Statuses to Test", value=default_statuses, height=100)

if st.button("Run Definitive Test", type="primary"):
    if not api_key:
        st.error("Missing API Key.")
    else:
        status_list =[s.strip() for s in status_input.split(",") if s.strip()]
        results =[]
        
        progress_text = st.empty()
        progress_bar = st.progress(0)
        
        for i, stat in enumerate(status_list):
            progress_text.text(f"Querying database for '{stat}' ...")
            
            url = "https://slipstream.homejunction.com/ws/listings/search"
            headers = {
                "Authorization": f"Bearer {api_key}",
                "HJI-API-Key": api_key 
            }
            
            # Removed the limit parameter so we get the true "total" database count
            params = {
                "market": market_id,
                "status": stat
            }
            
            try:
                res = requests.get(url, headers=headers, params=params)
                if res.status_code == 200:
                    data = res.json()
                    
                    total = 0
                    if "result" in data and isinstance(data["result"], dict):
                        total = data["result"].get("total", 0)
                    elif "paging" in data and isinstance(data["paging"], dict):
                        total = data["paging"].get("count", 0)
                        
                    results.append({
                        "Tested Status": stat, 
                        "Total Properties in MLS": total, 
                        "API Response": "Success"
                    })
                else:
                    results.append({
                        "Tested Status": stat, 
                        "Total Properties in MLS": 0, 
                        "API Response": f"Error {res.status_code}"
                    })
            except Exception as e:
                results.append({
                    "Tested Status": stat, 
                    "Total Properties in MLS": 0, 
                    "API Response": "Failed Connection"
                })
                
            progress_bar.progress((i + 1) / len(status_list))
            
        progress_text.text("Testing complete!")
        
        # --- DISPLAY RESULTS ---
        st.markdown("### 📊 Database Results")
        
        df = pd.DataFrame(results)
        df = df.sort_values(by="Total Properties in MLS", ascending=False).reset_index(drop=True)
        
        st.dataframe(
            df, 
            use_container_width=True,
            column_config={
                "Total Properties in MLS": st.column_config.NumberColumn("Total Properties in MLS", format="%d")
            }
        )
