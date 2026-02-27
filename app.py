import streamlit as st
import requests

st.title("Slipstream API Status")

# 1. Retrieve the token from secrets
token = st.secrets["SLIPSTREAM_TOKEN"]

# 2. Define the URL
url = "https://slipstream.homejunction.com/ws/api/status"

# 3. Make the call
# Note: Slipstream typically accepts the token as a query parameter or header
params = {"token": token}

if st.button("Check API Status"):
    try:
        response = requests.get(url, params=params)
        
        if response.status_code == 200:
            data = response.json()
            st.success("Connection Successful!")
            st.json(data)  # Displays the API response nicely
        else:
            st.error(f"Error: {response.status_code}")
            st.write(response.text)
            
    except Exception as e:
        st.error(f"An error occurred: {e}")
