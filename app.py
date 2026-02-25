import streamlit as st
import folium
from streamlit_folium import st_folium
import requests
import pandas as pd

# --- INITIALIZE SESSION STATE ---
# Default map center (e.g., Denver, CO)
if "clicked_lat" not in st.session_state:
    st.session_state.clicked_lat = 39.7392
if "clicked_lng" not in st.session_state:
    st.session_state.clicked_lng = -104.9903
if "listings" not in st.session_state:
    st.session_state.listings =[]

st.set_page_config(page_title="Coming Soon Listings Map", layout="wide")

st.title("🏡 'Coming Soon' Real Estate Map")
st.markdown("Drop a pin on the map below, set your radius, and search the Slipstream API for upcoming listings.")

# --- SIDEBAR: SETTINGS & INPUTS ---
st.sidebar.header("API & Search Settings")
api_key = st.sidebar.text_input("ATTOM / Slipstream API Key", type="password", help="Enter your ATTOM Data API Key")
radius_miles = st.sidebar.slider("Search Radius (miles)", min_value=1, max_value=50, value=5)

def fetch_slipstream_listings(lat, lng, radius, key):
    """
    Connects to the ATTOM / Home Junction Slipstream API to fetch coming soon properties.
    """
    # NOTE: Replace with the actual endpoint URL provided in your Slipstream API Docs
    url = "https://slipstream.homejunction.com/v2/listings/search"
    
    headers = {
        "Content-Type": "application/json",
        # ATTOM typically uses 'apikey', but Home Junction Slipstream might use a Bearer token
        "apikey": key  
    }
    
    # Parameters for geospatial radius search and status filtering
    params = {
        "lat": lat,
        "lon": lng,
        "radius": radius,
        "status": "Coming Soon" # Adjust filter syntax according to ATTOM/Slipstream docs
    }
    
    try:
        # --- UNCOMMENT TO MAKE ACTUAL API CALLS ---
        # response = requests.get(url, headers=headers, params=params)
        # response.raise_for_status()
        # data = response.json()
        # return data.get("result",[]) # Adjust 'result' to match the actual JSON response key
        
        # --- MOCK DATA FOR UI TESTING ---
        return[
            {"address": "123 Maple Dr", "price": 450000, "lat": lat + (radius*0.002), "lng": lng + (radius*0.002), "beds": 3, "baths": 2, "status": "Coming Soon"},
            {"address": "456 Oak Ln", "price": 525000, "lat": lat - (radius*0.003), "lng": lng + (radius*0.004), "beds": 4, "baths": 3, "status": "Coming Soon"},
            {"address": "789 Pine Ave", "price": 399000, "lat": lat + (radius*0.004), "lng": lng - (radius*0.002), "beds": 2, "baths": 1, "status": "Coming Soon"},
        ]
    except Exception as e:
        st.error(f"Error fetching data from API: {e}")
        return[]

# --- MAP RENDERING ---
# 1. Initialize Map
m = folium.Map(location=[st.session_state.clicked_lat, st.session_state.clicked_lng], zoom_start=12)

# 2. Add Center Pin (User's dropped pin)
folium.Marker([st.session_state.clicked_lat, st.session_state.clicked_lng],
    icon=folium.Icon(color="red", icon="crosshairs", prefix='fa'),
    tooltip="Search Center"
).add_to(m)

# 3. Add Radius Circle (Convert miles to meters)
folium.Circle(
    radius=radius_miles * 1609.34,
    location=[st.session_state.clicked_lat, st.session_state.clicked_lng],
    color="blue",
    fill=True,
    fill_opacity=0.1
).add_to(m)

# 4. Plot any fetched listings onto the map
for listing in st.session_state.listings:
    popup_text = f"<b>{listing['address']}</b><br/>${listing['price']:,}<br/>{listing['beds']}B / {listing['baths']}b"
    folium.Marker(
        [listing["lat"], listing["lng"]],
        icon=folium.Icon(color="green", icon="home"),
        tooltip="Coming Soon",
        popup=folium.Popup(popup_text, max_width=250)
    ).add_to(m)

# Render map in Streamlit
map_data = st_folium(m, width=800, height=500, returned_objects=["last_clicked"])

# --- HANDLE MAP CLICKS ---
# Update coordinate state if a user clicks a new location on the map
if map_data and map_data.get("last_clicked"):
    new_lat = map_data["last_clicked"]["lat"]
    new_lng = map_data["last_clicked"]["lng"]
    
    # If click is a new location, reset the pins and redraw
    if new_lat != st.session_state.clicked_lat or new_lng != st.session_state.clicked_lng:
        st.session_state.clicked_lat = new_lat
        st.session_state.clicked_lng = new_lng
        st.session_state.listings =[] # Clear old search results
        st.rerun()

# --- SEARCH ACTION ---
st.write(f"**Current Search Center:** {st.session_state.clicked_lat:.5f}, {st.session_state.clicked_lng:.5f}")

if st.button("Search 'Coming Soon' Listings", type="primary"):
    if not api_key:
        st.warning("Please enter your API Key in the sidebar to fetch actual data.")
        
    with st.spinner("Fetching listings from Slipstream..."):
        # Fetch data and save it in session_state so it survives widget interactions
        st.session_state.listings = fetch_slipstream_listings(
            st.session_state.clicked_lat,
            st.session_state.clicked_lng,
            radius_miles,
            api_key
        )
        
    if st.session_state.listings:
        st.success(f"Found {len(st.session_state.listings)} 'Coming Soon' properties!")
        st.rerun() # Rerun to plot the new green markers on the map
    else:
        st.info("No 'Coming Soon' listings found in this radius.")

# --- RESULTS DATAFRAME ---
if st.session_state.listings:
    st.write("### Listing Details")
    df = pd.DataFrame(st.session_state.listings)
    
    # Format the price column for a cleaner look
    if 'price' in df.columns:
        df['price'] = df['price'].apply(lambda x: f"${x:,.0f}" if pd.notnull(x) else "N/A")
        
    st.dataframe(df, use_container_width=True)
