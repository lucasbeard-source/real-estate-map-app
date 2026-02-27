import streamlit as st
import folium
from streamlit_folium import st_folium
import requests
import pandas as pd
from datetime import datetime

# --- INITIALIZE SESSION STATE ---
if "listings" not in st.session_state:
    st.session_state.listings =[]
if "raw_api_response" not in st.session_state:
    st.session_state.raw_api_response = {}

st.set_page_config(page_title="MLS Market Dashboard", layout="wide")

st.title("🏡 MLS Market Dashboard")
st.markdown("Search an entire MLS database for active, coming soon, or closed inventory with advanced filters.")

# --- FETCH API KEY FROM SECRETS ---
if "SLIPSTREAM_API_KEY" in st.secrets:
    api_key = st.secrets["SLIPSTREAM_API_KEY"]
else:
    api_key = None
    st.error("🚨 API Key not found! Please add 'SLIPSTREAM_API_KEY' to your Streamlit Cloud Secrets.")

# --- SIDEBAR: SEARCH SETTINGS ---
st.sidebar.header("1. Market Setup")
market_id = st.sidebar.text_input("Market ID", value="sfar", help="Your MLS Market ID (e.g., 'sfar')")

listing_status = st.sidebar.selectbox(
    "Listing Status",["Coming Soon", "Active", "Active Under Contract", "Pending", "Closed", "Canceled", "Expired", "Hold", "Withdrawn"],
    index=0 # Defaults to Coming Soon!
)

listing_type_filter = st.sidebar.selectbox(
    "Listing Type",["Residential", "Commercial", "Farm", "Land", "Multifamily", "Rental", "All"],
    index=0
)

# --- SIDEBAR: PROPERTY FILTERS ---
st.sidebar.header("2. Property Filters")

col1, col2 = st.sidebar.columns(2)
with col1:
    min_price = st.number_input("Min Price", min_value=0, value=0, step=50000)
with col2:
    max_price = st.number_input("Max Price", min_value=0, value=10000000, step=50000, help="Set to 0 for no maximum.")

col3, col4 = st.sidebar.columns(2)
with col3:
    min_beds = st.number_input("Min Beds", min_value=0.0, value=0.0, step=1.0)
with col4:
    min_baths = st.number_input("Min Baths", min_value=0.0, value=0.0, step=0.5)

# --- SIDEBAR: API LIMITS ---
st.sidebar.header("3. API Limits")
max_results = st.sidebar.number_input(
    "Max Results per Request",
    min_value=1,
    max_value=1000,
    value=250,
    step=50,
    help="Safeguard your API quota."
)

# --- HELPER FUNCTIONS ---
def extract_nested_value(item, possible_keys):
    """Aggressively hunts for a specific key (like listDate or daysOnMarket) inside a deeply nested JSON payload."""
    for key in possible_keys:
        if item.get(key) is not None: return item.get(key)
    for nested in["dates", "timestamps", "system", "details", "extended"]:
        if isinstance(item.get(nested), dict):
            for key in possible_keys:
                if item[nested].get(key) is not None: return item[nested].get(key)
    return None

def fetch_mls_listings(key, market, status, limit_size, list_type, min_p, max_p, min_bd, min_ba):
    url = "https://slipstream.homejunction.com/ws/listings/search"
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {key}",
        "HJI-API-Key": key 
    }
    
    # We pass the market, status, and limit to the API. 
    # (We will filter beds/baths/price in Python to ensure 100% stability against 400 Bad Request errors)
    params = {
        "market": market,
        "status": status,
        "limit": limit_size,
        "pageSize": limit_size,
        "details": "true",
        "extended": "true" 
    }
    
    if list_type != "All":
        params["listingType"] = list_type
    
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
                # 1. PRICING & PROPERTY SIZING (For our Python Filters)
                raw_price = item.get("listPrice") if item.get("listPrice") is not None else item.get("price", 0)
                try: price = float(raw_price) if raw_price else 0.0
                except (ValueError, TypeError): price = 0.0

                beds = float(item.get("beds", item.get("bedrooms", 0)))
                baths = float(item.get("baths", item.get("bathrooms", 0)))

                # --- APPLY PYTHON FILTERS ---
                if price < min_p: continue
                if max_p > 0 and price > max_p: continue
                if beds < min_bd: continue
                if baths < min_ba: continue
                
                # 2. LISTING & PROPERTY TYPES
                item_listing_type = str(item.get("listingType") or "Unknown")
                item_prop_type = str(item.get("propertyType") or "Unknown")
                
                # 3. DATE & DOM FILTERING
                list_date_str = str(extract_nested_value(item,["listDate", "listingDate", "onMarketDate", "entryDate"]) or "")
                close_date_str = str(extract_nested_value(item, ["closeDate", "closedDate", "soldDate"]) or "")
                
                # Hunt for Days On Market
                dom = extract_nested_value(item,["daysOnMarket", "dom", "cdom"])
                try: dom = int(dom) if dom is not None else 0
                except (ValueError, TypeError): dom = 0
                
                # 4. ADDRESS
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

                # 5. COORDINATES
                coords = item.get("coordinates") or {}
                item_lat = coords.get("latitude", coords.get("lat", item.get("lat")))
                item_lng = coords.get("longitude", coords.get("lon", item.get("lon", item.get("lng"))))
                
                if item_lat and item_lng:
                    parsed_listings.append({
                        "address": address,
                        "price": price,
                        "beds": beds,
                        "baths": baths,
                        "dom": dom,
                        "listing_type": item_listing_type,
                        "property_type": item_prop_type,
                        "lat": float(item_lat),
                        "lng": float(item_lng),
                        "status": str(item.get("status", status)),
                        "list_date": list_date_str[:10] if list_date_str else "N/A",
                        "close_date": close_date_str[:10] if close_date_str else "N/A"
                    })
            except Exception as loop_error:
                continue
                
        return parsed_listings, len(raw_listings)

    except Exception as e:
        st.error(f"Error fetching data from API: {e}")
        return[], 0

# --- MAIN DASHBOARD AREA ---
if st.sidebar.button("Search MLS", type="primary", use_container_width=True):
    if not api_key:
        st.error("Cannot search. The API Key is missing from Streamlit Secrets.")
    else:
        with st.spinner(f"Querying {market_id.upper()} for {listing_status} properties..."):
            st.session_state.listings, raw_count = fetch_mls_listings(
                api_key,
                market_id,
                listing_status,
                max_results,
                listing_type_filter,
                min_price,
                max_price,
                min_beds,
                min_baths
            )
            
        if st.session_state.listings:
            st.success(f"Successfully processed {len(st.session_state.listings)} properties matching your criteria!")
        else:
            if raw_count > 0:
                st.warning(f"The API returned {raw_count} properties, but NONE matched your Price, Beds, or Baths filters.")
            else:
                st.warning("The API returned 0 results. Check the Debug Expander below.")

# If we have listings, render the Map and Table views
if st.session_state.listings:
    
    # --- 1. METRICS ROW ---
    st.markdown("---")
    avg_price = sum(item["price"] for item in st.session_state.listings) / len(st.session_state.listings)
    avg_dom = sum(item["dom"] for item in st.session_state.listings) / len(st.session_state.listings)
    
    m_col1, m_col2, m_col3 = st.columns(3)
    m_col1.metric("Total Properties Found", f"{len(st.session_state.listings)}")
    m_col2.metric("Average List Price", f"${avg_price:,.0f}")
    m_col3.metric("Average Days on Market", f"{avg_dom:.0f} Days")
    
    st.markdown("---")

    # --- 2. MAP VIEW ---
    st.write("### Geographic Distribution")
    
    # Calculate map center dynamically based on the returned properties
    avg_lat = sum([L["lat"] for L in st.session_state.listings]) / len(st.session_state.listings)
    avg_lng = sum([L["lng"] for L in st.session_state.listings]) / len(st.session_state.listings)
    
    m = folium.Map(location=[avg_lat, avg_lng], zoom_start=11)
    
    # Fit the map bounds to perfectly frame all properties
    sw = [min([L["lat"] for L in st.session_state.listings]), min([L["lng"] for L in st.session_state.listings])]
    ne = [max([L["lat"] for L in st.session_state.listings]), max([L["lng"] for L in st.session_state.listings])]
    m.fit_bounds([sw, ne])

    for listing in st.session_state.listings:
        popup_text = f"""
        <b>{listing['address']}</b><br/>
        ${listing['price']:,.0f}<br/>
        {listing['beds']}B / {listing['baths']}b<br/>
        <b>DOM:</b> {listing['dom']}<br/>
        <i>{listing['property_type']}</i>
        """
        
        folium.Marker(
            [listing["lat"], listing["lng"]],
            icon=folium.Icon(color="green" if listing_status == "Active" else "blue", icon="home"),
            tooltip=listing["status"],
            popup=folium.Popup(popup_text, max_width=250)
        ).add_to(m)

    st_folium(m, width=1200, height=500, returned_objects=[])

    # --- 3. TABLE VIEW ---
    st.write("### Detailed Property Data")
    df = pd.DataFrame(st.session_state.listings)
    
    # Force column types to prevent React UI crashes
    df["price"] = pd.to_numeric(df["price"], errors="coerce").fillna(0).astype(int)
    df["beds"] = pd.to_numeric(df["beds"], errors="coerce").fillna(0).astype(float)
    df["baths"] = pd.to_numeric(df["baths"], errors="coerce").fillna(0).astype(float)
    df["dom"] = pd.to_numeric(df["dom"], errors="coerce").fillna(0).astype(int)
    
    # Arrange columns beautifully
    df = df[["address", "price", "dom", "status", "listing_type", "property_type", "beds", "baths", "list_date", "close_date"]]
    
    st.dataframe(
        df, 
        use_container_width=True, 
        hide_index=True,
        column_config={
            "address": "Address",
            "price": st.column_config.NumberColumn("Price", format="$%d"),
            "dom": st.column_config.NumberColumn("DOM"),
            "status": "Status",
            "listing_type": "Listing Type",
            "property_type": "Property Sub-Type",
            "beds": st.column_config.NumberColumn("Beds"),
            "baths": st.column_config.NumberColumn("Baths"),
            "list_date": "List Date",
            "close_date": "Close Date"
        }
    )

with st.expander("🛠️ View Raw API Response (Debug)"):
    if st.session_state.raw_api_response:
        st.json(st.session_state.raw_api_response)
    else:
        st.write("No API calls made yet.")
