import streamlit as st
import folium
from streamlit_folium import st_folium
import requests
import pandas as pd
from datetime import datetime, timedelta

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

radius_miles = st.sidebar.number_input(
    "Search Radius (miles)", 
    min_value=0.01, 
    max_value=50.0, 
    value=0.5, 
    step=0.1,
    help="Type an exact number or use the arrows."
)

listing_status = st.sidebar.selectbox(
    "Listing Status",[
        "Active", "Active Under Contract", "Canceled", "Closed", "Coming Soon", 
        "Comp", "Deleted", "Expired", "Hold", "Incomplete", "Off Market", 
        "Other", "Pending", "Withdrawn"
    ],
    index=0
)

# --- API LIMITER ---
st.sidebar.markdown("---")
st.sidebar.subheader("API Limits")
max_results = st.sidebar.number_input(
    "Max Results per Request",
    min_value=1,
    max_value=500,
    value=200,
    step=25,
    help="Limits the data payload to protect your API usage quota."
)

# --- PROPERTY & AGENT FILTERS ---
st.sidebar.markdown("---")
st.sidebar.subheader("Additional Filters")

property_type = st.sidebar.selectbox(
    "Property Type",["All", "Residential", "Commercial", "Land", "Multi-Family", "Condo"],
    index=0,
    help="Note: Different MLS boards use different terms (e.g., SFR vs Residential). If your results disappear, switch this back to 'All'."
)

agent_name_filter = st.sidebar.text_input(
    "Agent Name", 
    value="", 
    help="Leave blank for all agents, or type a first or last name to filter."
)

# --- DATE FILTER ---
st.sidebar.markdown("---")
st.sidebar.subheader("Date Filter")
apply_date_filter = st.sidebar.checkbox("Enable Date Filter", value=False)
filter_date = st.sidebar.date_input(
    "On or After Date", 
    value=datetime.today() - timedelta(days=30),
    help="Filters Listing Date (if Active) or Closed Date (if Closed)."
)

def fetch_slipstream_listings(lat, lng, radius, key, market, status, apply_date, since_date, prop_type_filter, agent_filter, limit_size):
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
        "status": status,
        "size": limit_size
    }
    
    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status() 
        data = response.json()
        
        st.session_state.raw_api_response = data 
        
        raw_listings =[]
        if "result" in data and isinstance(data["result"], dict) and "listings" in data["result"]:
            raw_listings = data["result"]["listings"]
        elif "result" in data and isinstance(data["result"], list):
            raw_listings = data["result"]
            
        parsed_listings =[]
        
        for item in raw_listings:
            try:
                # 1. BULLETPROOF PROPERTY TYPE
                item_prop_type = str(item.get("propertyType") or "Unknown")
                if prop_type_filter != "All":
                    if prop_type_filter.lower() not in item_prop_type.lower():
                        continue
                
                # 2. BULLETPROOF AGENT NAME
                agent_info = item.get("listAgent") or {}
                agent_full_name = str(agent_info.get("fullName") or agent_info.get("name") or item.get("agentName") or "Unknown Agent")
                if agent_filter:
                    if agent_filter.lower() not in agent_full_name.lower():
                        continue 

                # 3. BULLETPROOF DATE FILTERING
                list_date_str = str(item.get("listDate") or item.get("listingDate") or "")
                close_date_str = str(item.get("closeDate") or item.get("closedDate") or "")
                
                if apply_date:
                    target_date_str = close_date_str if status == "Closed" else list_date_str
                    if target_date_str and len(target_date_str) >= 10:
                        try:
                            item_date = datetime.strptime(target_date_str[:10], "%Y-%m-%d").date()
                            if item_date < since_date:
                                continue 
                        except Exception:
                            pass 
                
                # 4. BULLETPROOF ADDRESS
                addr_info = item.get("address") or {}
                if isinstance(addr_info, dict):
                    if addr_info.get("withheld", False) or "deliveryLine" not in addr_info:
                        city = addr_info.get("city", "Unknown City")
                        zip_code = addr_info.get("zip", "")
                        address = f"Address Withheld ({city} {zip_code})".strip()
                    else:
                        address = addr_info.get("deliveryLine", "Unknown Address")
                else:
                    address = str(addr_info)

                # 5. BULLETPROOF PRICING
                raw_price = item.get("listPrice")
                if raw_price is None:
                    raw_price = item.get("price", 0)
                try:
                    price = float(raw_price) if raw_price else 0.0
                except (ValueError, TypeError):
                    price = 0.0

                beds = item.get("beds", item.get("bedrooms", 0))
                baths = item.get("baths", item.get("bathrooms", 0))
                
                # 6. BULLETPROOF COORDINATES
                coords = item.get("coordinates") or {}
                item_lat = coords.get("latitude", coords.get("lat", item.get("lat")))
                item_lng = coords.get("longitude", coords.get("lon", item.get("lon", item.get("lng"))))
                
                if item_lat and item_lng:
                    parsed_listings.append({
                        "address": address,
                        "price": price,
                        "beds": beds,
                        "baths": baths,
                        "property_type": item_prop_type,
                        "agent": agent_full_name,
                        "lat": float(item_lat),
                        "lng": float(item_lng),
                        "status": str(item.get("status", status)),
                        "list_date": list_date_str[:10] if list_date_str else "N/A",
                        "close_date": close_date_str[:10] if close_date_str else "N/A"
                    })
            except Exception as loop_error:
                print(f"Skipped a row due to parsing error: {loop_error}")
                continue
                
        return parsed_listings

    except Exception as e:
        st.error(f"Error fetching data from API: {e}")
        return[]

# --- MAP RENDERING ---
m = folium.Map(location=[st.session_state.clicked_lat, st.session_state.clicked_lng], zoom_start=15)

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
    popup_text = f"<b>{listing['address']}</b><br/>${listing['price']:,.0f}<br/>{listing['beds']}B / {listing['baths']}b<br/><i>{listing['property_type']}</i>"
    
    if listing['status'] == "Closed" and listing['close_date'] != "N/A":
        popup_text += f"<br/>Closed: {listing['close_date']}"
    elif listing['list_date'] != "N/A":
        popup_text += f"<br/>Listed: {listing['list_date']}"
        
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
        with st.spinner(f"Fetching {listing_status} listings from {market_id.upper()} (Max {max_results})..."):
            st.session_state.listings = fetch_slipstream_listings(
                st.session_state.clicked_lat,
                st.session_state.clicked_lng,
                radius_miles,
                api_key,
                market_id,
                listing_status,
                apply_date_filter,
                filter_date,
                property_type,      
                agent_name_filter,
                max_results         
            )
            
        if st.session_state.listings:
            st.success(f"Successfully mapped {len(st.session_state.listings)} properties matching your filters!")
            st.rerun() 
        else:
            st.warning("No listings found matching your exact filters. Check the Debug Expander below.")

# --- RESULTS DATAFRAME ---
if st.session_state.listings:
    st.write("### Listing Details (Click column headers to sort)")
    df = pd.DataFrame(st.session_state.listings)
    
    # Force columns to numeric safely so the frontend React table doesn't crash on mixed types
    df["price"] = pd.to_numeric(df["price"], errors="coerce").fillna(0)
    df["beds"] = pd.to_numeric(df["beds"], errors="coerce").fillna(0)
    df["baths"] = pd.to_numeric(df["baths"], errors="coerce").fillna(0)
    
    df = df[["address", "price", "status", "property_type", "beds", "baths", "agent", "list_date", "close_date"]]
    
    st.dataframe(
        df, 
        use_container_width=True, 
        hide_index=True,
        column_config={
            "address": "Address",
            "price": st.column_config.NumberColumn("Price", format="$%.0f"), # FIX: Changed to %.0f
            "status": "Status",
            "property_type": "Type",
            "beds": st.column_config.NumberColumn("Beds"),
            "baths": st.column_config.NumberColumn("Baths"),
            "agent": "Agent Name",
            "list_date": "List Date",
            "close_date": "Close Date"
        }
    )

with st.expander("🛠️ View Raw API Response (Debug)"):
    if st.session_state.raw_api_response:
        st.json(st.session_state.raw_api_response)
    else:
        st.write("No API calls made yet.")
