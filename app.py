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
if "raw_api_response" not in st.session_state:
    st.session_state.raw_api_response = {}

st.set_page_config(page_title="SF Coming Soon Listings", layout="wide")

st.title("🌉 San Francisco 'Coming Soon' Map")
st.markdown("Drop a pin anywhere in the SF area to search the Slipstream API for upcoming listings.")

# --- FETCH API KEY FROM SECRETS ---
if "SLIPSTREAM_API_KEY" in st.secrets:
    api_key = st.secrets["SLIPSTREAM_API_KEY"]
else:
    api_key = None
    st.error("🚨 API Key not found! Please add 'SLIPSTREAM_API_KEY' to your Streamlit Cloud Secrets.")

# --- SIDEBAR: SETTINGS & INPUTS ---
st.sidebar.header("Search Settings")
# The "market" parameter as required by Slipstream documentation
market_id = st.sidebar.text_input("Market ID", value="sfar", help="Your MLS Market ID (e.g., 'sfar' for San Francisco)")
radius_miles = st.sidebar.slider("Search Radius (miles)", min_value=1, max_value=25, value=3)

def fetch_slipstream_listings(lat, lng, radius, key, market):
    """
    Connects to the Home Junction Slipstream API to fetch properties.
    """
    # Base endpoint based on Slipstream WS API docs
    url = "https://slipstream.homejunction.com/ws/listings/search"
    
    headers = {
        "Content-Type": "application/json",
        # Home Junction APIs typically accept the key as a Bearer token or HJI-API-Key
        "Authorization": f"Bearer {key}",
        "HJI-API-Key": key 
    }
    
    # Payload formatted for the Slipstream endpoint
    params = {
        "market": market,          # Explicitly identifying the SFAR market
        "lat": lat,
        "lon": lng,
        "radius": f"{radius}mi",   # Adding 'mi' as HJ often requires units for radius
        "status": "Coming Soon"    # Note: Double check if SFAR uses "Coming Soon", "CS", or "Active Under Contract"
    }
    
    try:
        # 1. Make the live API Call
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status() # This will raise an error if your API key is rejected
        
        data = response.json()
        
        # Save raw data for debugging in the UI
        st.session_state.raw_api_response = data 
        
        # 2. Parse the returned JSON
        # Slipstream usually nests listings under result -> listings
        raw_listings =[]
        if "result" in data and isinstance(data["result"], dict) and "listings" in data["result"]:
            raw_listings = data["result"]["listings"]
        elif "result" in data and isinstance(data["result"], list):
            raw_listings = data["result"]
            
        parsed_listings =[]
        
        # 3. Standardize the data for our map
        for item in raw_listings:
            try:
                # Safely extract values accounting for HJ's specific JSON structure
                address = item.get("address", {}).get("deliveryLine", item.get("address", "Unknown Address"))
                price = item.get("listPrice", item.get("price", 0))
                beds = item.get("beds", item.get("bedrooms", 0))
                baths = item.get("baths", item.get("bathrooms", 0))
                
                # Coordinates are usually nested in a coordinates object or straight on the item
                item_lat = item.get("coordinates", {}).get("lat", item.get("lat"))
                item_lng = item.get("coordinates", {}).get("lon", item.get("lon", item.get("lng")))
                
                # Only add if we successfully found coordinates
                if item_lat and item_lng:
                    parsed_listings.append({
                        "address": address,
                        "price": price,
                        "beds": beds,
                        "baths": baths,
                        "lat": float(item_lat),
                        "lng": float(item_lng),
                        "status": item.get("status", "Coming Soon")
                    })
            except Exception as parse_err:
                # Skip items that are missing critical geographic data
                continue
                
        return parsed_listings

    except requests.exceptions.HTTPError as http_err:
        st.error(f"HTTP Error: API returned status code {response.status_code}. (Check your API key and Market ID)")
        st.session_state.raw_api_response = {"error": str(http_err), "details": response.text}
        return[]
    except Exception as e:
        st.error(f"Error fetching data from API: {e}")
        return[]

# --- MAP RENDERING ---
m = folium.Map(location=[st.session_state.clicked_lat, st.session_state.clicked_lng], zoom_start=13)

folium.Marker([st.session_state.clicked_lat, st.session_state.clicked_lng],
    icon=folium.Icon(color="red", icon="crosshairs", prefix='fa'),
    tooltip="Search Center"
).add_to(m)

folium.Circle(
    radius=radius_miles * 1609.34,
    location=[st.session_state.clicked_lat, st.session_state.clicked_lng],
    color="blue",
    fill=True,
    fill_opacity=0.1
).add_to(m)

for listing in st.session_state.listings:
    popup_text = f"<b>{listing['address']}</b><br/>${listing['price']:,}<br/>{listing['beds']}B / {listing['baths']}b"
    folium.Marker(
        [listing["lat"], listing["lng"]],
        icon=folium.Icon(color="green", icon="home"),
        tooltip="Coming Soon",
        popup=folium.Popup(popup_text, max_width=250)
    ).add_to(m)

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

if st.button("Search Actual API for 'Coming Soon' Listings", type="primary"):
    if not api_key:
        st.error("Cannot search. The API Key is missing from Streamlit Secrets.")
    else:
        with st.spinner(f"Fetching live listings from {market_id.upper()}..."):
            st.session_state.listings = fetch_slipstream_listings(
                st.session_state.clicked_lat,
                st.session_state.clicked_lng,
                radius_miles,
                api_key,
                market_id 
            )
            
        if st.session_state.listings:
            st.success(f"Found {len(st.session_state.listings)} live properties!")
            st.rerun() 
        else:
            st.warning("No listings found. Check the Debug Expander below to see what the API returned.")

# --- RESULTS DATAFRAME ---
if st.session_state.listings:
    st.write("### Listing Details")
    df = pd.DataFrame(st.session_state.listings)
    
    if 'price' in df.columns:
        df['price'] = df['price'].apply(lambda x: f"${x:,.0f}" if pd.notnull(x) else "N/A")
        
    st.dataframe(df, use_container_width=True)

# --- DEBUGGING TOOLS ---
# This is incredibly helpful when working with new APIs!
with st.expander("🛠️ View Raw API Response (Debug)"):
    st.write("If your map isn't plotting correctly or you aren't finding results, check the exact JSON the API returned below:")
    if st.session_state.raw_api_response:
        st.json(st.session_state.raw_api_response)
    else:
        st.write("No API calls made yet.")
