import streamlit as st
import folium
from streamlit_folium import st_folium
import requests
import pandas as pd

# --- INITIALIZE SESSION STATE ---
if "clicked_lat" not in st.session_state:
    st.session_state.clicked_lat = 37.7749
if "clicked_lng" not in st.session_state:
    st.session_state.clicked_lng = -122.4194
if "listings" not in st.session_state:
    st.session_state.listings =[]
if "raw_api_response" not in st.session_state:
    st.session_state.raw_api_response = {}

st.set_page_config(page_title="SF Real Estate Map", layout="wide")

st.title("🌉 San Francisco Real Estate Map")
st.markdown("Drop a pin anywhere in the SF area to search the Slipstream API.")

# --- FETCH API KEY FROM SECRETS ---
if "SLIPSTREAM_API_KEY" in st.secrets:
    api_key = st.secrets["SLIPSTREAM_API_KEY"]
else:
    api_key = None
    st.error("🚨 API Key not found! Please add 'SLIPSTREAM_API_KEY' to your Streamlit Cloud Secrets.")

# --- SIDEBAR: SETTINGS & INPUTS ---
st.sidebar.header("Search Settings")
market_id = st.sidebar.text_input("Market ID", value="sfar", help="Your MLS Market ID")

radius_miles = st.sidebar.slider(
    "Search Radius (miles)", 
    min_value=0.1, 
    max_value=25.0, 
    value=0.1, 
    step=0.1
)

listing_status = st.sidebar.selectbox(
    "Listing Status",[
        "Active", 
        "Active Under Contract", 
        "Canceled", 
        "Closed", 
        "Coming Soon", 
        "Comp", 
        "Deleted", 
        "Expired", 
        "Hold", 
        "Incomplete", 
        "Off Market", 
        "Other", 
        "Pending", 
        "Withdrawn"
    ],
    index=0, 
    help="Select the standardized RESO status to query."
)

def fetch_slipstream_listings(lat, lng, radius, key, market, status):
    url = "https://slipstream.homejunction.com/ws/listings/search"
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {key}",
        "HJI-API-Key": key 
    }
    
    params = {
        "market": market,
        "lat": lat,
        "lon": lng,
        "radius": f"{radius}mi", 
        "status": status  
    }
    
    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status() 
        data = response.json()
        
        st.session_state.raw_api_response = data 
        
        raw_listings = []
        if "result" in data and isinstance(data["result"], dict) and "listings" in data["result"]:
            raw_listings = data["result"]["listings"]
        elif "result" in data and isinstance(data["result"], list):
            raw_listings = data["result"]
            
        parsed_listings =[]
        
        for item in raw_listings:
            try:
                # 1. Safely parse the address (handling "withheld" privacy flags)
                addr_info = item.get("address", {})
                if isinstance(addr_info, dict):
                    if addr_info.get("withheld", False) or "deliveryLine" not in addr_info:
                        city = addr_info.get("city", "Unknown City")
                        zip_code = addr_info.get("zip", "")
                        address = f"Address Withheld ({city} {zip_code})".strip()
                    else:
                        address = addr_info.get("deliveryLine", "Unknown Address")
                else:
                    address = str(addr_info)

                # 2. Safely parse Price, Beds, Baths
                price = item.get("listPrice", item.get("price", 0))
                beds = item.get("beds", item.get("bedrooms", 0))
                baths = item.get("baths", item.get("bathrooms", 0))
                
                # 3. FIX: Check for the exact words "latitude" and "longitude"
                coords = item.get("coordinates", {})
                item_lat = coords.get("latitude", coords.get("lat", item.get("lat")))
                item_lng = coords.get("longitude", coords.get("lon", item.get("lon", item.get("lng"))))
                
                # If we successfully found coordinates, add it to our list!
                if item_lat and item_lng:
                    parsed_listings.append({
                        "address": address,
                        "price": price,
                        "beds": beds,
                        "baths": baths,
                        "lat": float(item_lat),
                        "lng": float(item_lng),
                        "status": item.get("status", status)
                    })
            except Exception as e:
                continue
                
        return parsed_listings

    except Exception as e:
        st.error(f"Error fetching data from API: {e}")
        return[]

# --- MAP RENDERING ---
m = folium.Map(location=[st.session_state.clicked_lat, st.session_state.clicked_lng], zoom_start=16)

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
        tooltip=listing["status"],
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

if st.button("Search Actual API", type="primary"):
    if not api_key:
        st.error("Cannot search. The API Key is missing from Streamlit Secrets.")
    else:
        with st.spinner(f"Fetching {listing_status} listings from {market_id.upper()}..."):
            st.session_state.listings = fetch_slipstream_listings(
                st.session_state.clicked_lat,
                st.session_state.clicked_lng,
                radius_miles,
                api_key,
                market_id,
                listing_status 
            )
            
        if st.session_state.listings:
            st.success(f"Found {len(st.session_state.listings)} properties!")
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

with st.expander("🛠️ View Raw API Response (Debug)"):
    if st.session_state.raw_api_response:
        st.json(st.session_state.raw_api_response)
    else:
        st.write("No API calls made yet.")
