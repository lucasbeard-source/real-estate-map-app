import streamlit as st
import folium
from streamlit_folium import st_folium
import requests
import pandas as pd

# --- INITIALIZE SESSION STATE ---
# Default map center: San Francisco, CA
if "clicked_lat" not in st.session_state:
    st.session_state.clicked_lat = 37.7749
if "clicked_lng" not in st.session_state:
    st.session_state.clicked_lng = -122.4194
if "listings" not in st.session_state:
    st.session_state.listings =[]

st.set_page_config(page_title="SF Coming Soon Listings", layout="wide")

st.title("🌉 San Francisco 'Coming Soon' Map")
st.markdown("Drop a pin anywhere in the SF area to search the Slipstream API for upcoming listings.")

# --- FETCH API KEY FROM SECRETS ---
# Streamlit will look in its secure vault for this exact name
if "SLIPSTREAM_API_KEY" in st.secrets:
    api_key = st.secrets["SLIPSTREAM_API_KEY"]
else:
    api_key = None
    st.error("🚨 API Key not found! Please add 'SLIPSTREAM_API_KEY' to your Streamlit Cloud Secrets.")

# --- SIDEBAR: SETTINGS & INPUTS ---
st.sidebar.header("Search Settings")
market_id = st.sidebar.text_input("Market ID", value="sfar", help="Your MLS Market ID (e.g. 'sfar' for San Francisco)")
radius_miles = st.sidebar.slider("Search Radius (miles)", min_value=1, max_value=25, value=3)

def fetch_slipstream_listings(lat, lng, radius, key, market):
    """
    Connects to the Home Junction Slipstream API to fetch coming soon properties.
    """
    url = "https://slipstream.homejunction.com/v2/listings/search"
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {key}" 
    }
    
    params = {
        "market": market,
        "lat": lat,
        "lon": lng,
        "radius": radius, 
        "status": "Coming Soon" 
    }
    
    try:
        # --- UNCOMMENT TO MAKE ACTUAL API CALLS ---
        # response = requests.get(url, headers=headers, params=params)
        # response.raise_for_status()
        # data = response.json()
        # return data.get("result",[]) 
        
        # --- MOCK DATA CENTERED AROUND SF FOR UI TESTING ---
        return[
            {"address": "123 Lombard St", "price": 1450000, "lat": lat + (radius*0.002), "lng": lng + (radius*0.002), "beds": 3, "baths": 2, "status": "Coming Soon"},
            {"address": "456 Mission St", "price": 925000, "lat": lat - (radius*0.003), "lng": lng + (radius*0.004), "beds": 2, "baths": 2, "status": "Coming Soon"},
            {"address": "789 Castro St", "price": 2100000, "lat": lat + (radius*0.004), "lng": lng - (radius*0.002), "beds": 4, "baths": 3, "status": "Coming Soon"},
        ]
    except Exception as e:
        st.error(f"Error fetching data from API: {e}")
        return[]

# --- MAP RENDERING ---
m = folium.Map(location=[st.session_state.clicked_lat, st.session_state.clicked_lng], zoom_start=13)

# Add Center Pin 
folium.Marker([st.session_state.clicked_lat, st.session_state.clicked_lng],
    icon=folium.Icon(color="red", icon="crosshairs", prefix='fa'),
    tooltip="Search Center"
).add_to(m)

# Add Radius Circle 
folium.Circle(
    radius=radius_miles * 1609.34,
    location=[st.session_state.clicked_lat, st.session_state.clicked_lng],
    color="blue",
    fill=True,
    fill_opacity=0.1
).add_to(m)

# Plot Fetched Listings
for listing in st.session_state.listings:
    popup_text = f"<b>{listing['address']}</b><br/>${listing['price']:,}<br/>{listing['beds']}B / {listing['baths']}b"
    folium.Marker(
        [listing["lat"], listing["lng"]],
        icon=folium.Icon(color="green", icon="home"),
        tooltip="Coming Soon",
        popup=folium.Popup(popup_text, max_width=250)
    ).add_to(m)

# Render map
map_data = st_folium(m, width=800, height=500, returned_objects=["last_clicked"])

# --- HANDLE MAP CLICKS ---
if map_data and map_data.get("last_clicked"):
    new_lat = map_data["last_clicked"]["lat"]
    new_lng = map_data["last_clicked"]["lng"]
    
    if new_lat != st.session_state.clicked_lat or new_lng != st.session_state.clicked_lng:
        st.session_state.clicked_lat = new_lat
        st.session_state.clicked_lng = new_lng
        st.session_state.listings =[] 
        st.rerun()

# --- SEARCH ACTION ---
st.write(f"**Current SF Search Center:** {st.session_state.clicked_lat:.5f}, {st.session_state.clicked_lng:.5f}")

if st.button("Search 'Coming Soon' Listings", type="primary"):
    if not api_key:
        st.error("Cannot search. The API Key is missing from Streamlit Secrets.")
    else:
        with st.spinner(f"Fetching listings from {market_id.upper()}..."):
            st.session_state.listings = fetch_slipstream_listings(
                st.session_state.clicked_lat,
                st.session_state.clicked_lng,
                radius_miles,
                api_key,
                market_id 
            )
            
        if st.session_state.listings:
            st.success(f"Found {len(st.session_state.listings)} 'Coming Soon' properties!")
            st.rerun() 
        else:
            st.info("No 'Coming Soon' listings found in this radius.")

# --- RESULTS DATAFRAME ---
if st.session_state.listings:
    st.write("### Listing Details")
    df = pd.DataFrame(st.session_state.listings)
    
    if 'price' in df.columns:
        df['price'] = df['price'].apply(lambda x: f"${x:,.0f}" if pd.notnull(x) else "N/A")
        
    st.dataframe(df, use_container_width=True)
