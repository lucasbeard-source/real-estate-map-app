import streamlit as st
import requests
import pandas as pd

st.set_page_config(page_title="MLS Taxonomy Tester", layout="wide")

st.title("🕵️‍♂️ MLS Status Discovery Tool")
st.markdown("Different MLS boards use different spellings for statuses. This tool will ping the API with various status variations and tell you exactly how many properties exist for each one.")

# --- FETCH API KEY ---
if "SLIPSTREAM_API_KEY" in st.secrets:
    api_key = st.secrets["SLIPSTREAM_API_KEY"]
else:
    api_key = None
    st.error("🚨 API Key not found! Please add 'SLIPSTREAM_API_KEY' to your Streamlit Cloud Secrets.")

# --- UI INPUTS ---
st.markdown("---")
market_id = st.text_input("Market ID to Test", value="sfar")

# A massive list of every possible variation MLS boards use
default_statuses = "Active, Coming Soon, ComingSoon, CS, Active Under Contract, Contingent, Active Contingent, Pending, Closed, Sold, Hold, Withdrawn, Canceled, Expired"
status_input = st.text_area("Status strings to test (comma separated)", value=default_statuses)

if st.button("Run Status Discovery", type="primary"):
    if not api_key:
        st.error("Missing API Key.")
    else:
        status_list =[s.strip() for s in status_input.split(",") if s.strip()]
        results =[]
        
        progress_text = st.empty()
        progress_bar = st.progress(0)
        
        # Loop through every status and ask the API how many exist
        for i, stat in enumerate(status_list):
            progress_text.text(f"Testing status: '{stat}' ...")
            
            url = "https://slipstream.homejunction.com/ws/listings/search"
            headers = {
                "Authorization": f"Bearer {api_key}",
                "HJI-API-Key": api_key 
            }
            params = {
                "market": market_id,
                "status": stat,
                "limit": 1 # We only need 1 property because we just want the 'total' count!
            }
            
            try:
                res = requests.get(url, headers=headers, params=params)
                if res.status_code == 200:
                    data = res.json()
                    
                    # Dig into the JSON to find the "total" properties available
                    total = 0
                    if "result" in data and isinstance(data["result"], dict):
                        total = data["result"].get("total", 0)
                    elif "paging" in data and isinstance(data["paging"], dict):
                        total = data["paging"].get("count", 0)
                        
                    results.append({
                        "Tested Status String": stat, 
                        "Properties Found": total, 
                        "API Response": "Success"
                    })
                else:
                    results.append({
                        "Tested Status String": stat, 
                        "Properties Found": 0, 
                        "API Response": f"Error {res.status_code}"
                    })
            except Exception as e:
                results.append({
                    "Tested Status String": stat, 
                    "Properties Found": 0, 
                    "API Response": "Failed Connection"
                })
                
            # Update the loading bar
            progress_bar.progress((i + 1) / len(status_list))
            
        progress_text.text("Testing complete!")
        
        # --- DISPLAY RESULTS ---
        st.markdown("### 📊 Discovery Results")
        
        df = pd.DataFrame(results)
        
        # Sort so the statuses with the most properties jump to the top
        df = df.sort_values(by="Properties Found", ascending=False).reset_index(drop=True)
        
        st.dataframe(
            df, 
            use_container_width=True,
            column_config={
                "Properties Found": st.column_config.NumberColumn("Properties Found", format="%d")
            }
        )
        
        st.info("💡 **How to use this:** Look at the table above. If 'Coming Soon' has 0 properties, but 'CS' has 45, then you know 'CS' is the exact string you need to use in the Main App's dropdown. Note those exact spellings, and then swap your `app.py` back to the Main Dashboard code!")
