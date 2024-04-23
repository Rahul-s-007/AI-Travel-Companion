import streamlit as st
from streamlit_folium import st_folium
from streamlit_extras.stateful_button import button

import folium
from folium import plugins
from geopy.geocoders import Nominatim
from geopy.distance import geodesic

import json
import requests
from urllib.parse import quote

import os
from dotenv import load_dotenv
load_dotenv()

# Set up the OpenAI API key
from openai import OpenAI
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Set up the Google Maps API key
google_maps_api_key = os.getenv("GOOGLE_MAPS_API_KEY")

#------------------------------------------------------------------------------------------------------
# Function to get coordinates from address
def get_coordinates(address, api_key = google_maps_api_key):
    geolocator = Nominatim(user_agent="my_app")
    location = geolocator.geocode(address)
    if location is not None:
        return location.latitude, location.longitude

    else:
        url = f"https://maps.googleapis.com/maps/api/place/findplacefromtext/json?input={address}&inputtype=textquery&fields=geometry,name&key={api_key}"
        response = requests.get(url)
        data = response.json()
        if 'candidates' in data:
            if data['candidates']:
                place = data['candidates'][0]
                return place['geometry']['location']['lat'], place['geometry']['location']['lng']

# Function to calculate the shortest path
def calculate_shortest_path(start_coords, destinations):
    path = [start_coords]
    unvisited = destinations.copy()
    
    while unvisited:
        nearest_dest = min(unvisited, key=lambda x: geodesic(path[-1], x).km)
        path.append(nearest_dest)
        unvisited.remove(nearest_dest)
    
    path.append(start_coords)  # Return to the starting point
    return path

def get_place_info(api_key, place_name):
    url = f"https://maps.googleapis.com/maps/api/place/findplacefromtext/json?input={place_name}&inputtype=textquery&fields=geometry,name&key={api_key}"
    response = requests.get(url)
    data = response.json()
    if 'candidates' in data:
        if data['candidates']:
            place = data['candidates'][0]
            return {
                'name': place['name'],
                'lat': place['geometry']['location']['lat'],
                'lng': place['geometry']['location']['lng']
            }
    return None

def fetch_place_images(place_name, api_key = google_maps_api_key):
    place_info = get_place_info(api_key, place_name)
    if place_info:
        lat, lng = place_info['lat'], place_info['lng']
        url = f"https://maps.googleapis.com/maps/api/staticmap?center={lat},{lng}&zoom=17&size=400x400&maptype=satellite&key={api_key}"
        return url
    else:
        return None

#------------------------------------------------------------------------------------------------------
# Streamlit app
def app():
    st.title("AI Travel Buddy")
    
    # Get user input
    location = st.text_input("Enter the location (City, State, Country)")
    num_days = st.number_input("Enter the number of days", min_value=1, step=1)
    hotel_address = st.text_input("Enter the hotel address")

    radio = st.radio("Next:", ["Filling Deatils", "Submit"])

    # if button("Generate Travel Plan", key="Generate Travel Plan"): # stateful_button
    if radio == "Submit":
        # Get hotel coordinates
        hotel_coords = get_coordinates(hotel_address)
        if hotel_address is None:
            st.error("Invalid hotel address. Please enter a valid address.")
        
        else:
        # Call OpenAI API to generate "Must-Visit" places
            prompt = """You have to plan a """+str(num_days)+"""-day trip to """+location+""", starting from the hotel at """+hotel_address+""",
    generate a JSON object with 'Must-Visit' places day-wise, with a short description for each. Only give JSON as output. Give 3 places for each day.

    Example output format(JSON):
    {"Day 1": [{"name": "",
        "description": ""},
        {"name": "",
        "description": ""},
        {"name": "",
        "description": ""}], ... 
    }
    """
            messages = [
                {
                    "role": "system",
                    "content": prompt
                }
            ]
            response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages,
            temperature=1,
            max_tokens=1024
            )
            # st.text(response)
            # st.text(response.choices[0].message.content)
            result = response.choices[0].message.content
            result = json.loads(result)
            st.json(result)

            # Get coordinates for all places
            day_places = []
            day_coords = []
            for day, places in result.items():
                places_coords = []
                for place in places:
                    # address = f"{place['name']}, {location}"
                    # address = place['address']
                    coords = get_coordinates(place['name'] + location)
                    if coords is None:
                        st.error(f"Invalid address for {place['name']}. Please enter a valid address.")
                        break
                    place['coords'] = coords
                    place['image_url'] = fetch_place_images(place['name'] + location)
                    # place['image_url'] = fetch_place_images(coords, location)
                    places_coords.append(coords)
                day_places.append(places)
                day_coords.append(places_coords)
            
            print(place)
            # Display the itinerary with images
            st.subheader("Itinerary")
            day_count = 1
            for places, coords in zip(day_places, day_coords):
                with st.expander(f"Day {day_count}"):
                    cols = st.columns(len(places))
                    for i, place in enumerate(places):
                        with cols[i]:
                            if place['image_url']:
                                st.image(place['image_url'], width=200, caption=place['name'])
                            else:
                                st.write(f"No image available for {place['name']}")
                            st.write(place['description'])
                    
                    # Add a button to generate and display the map
                    radio_map = st.radio("Next:", ["Hide Map", "Show Map"], key=f"Show Map for Day {day_count}")
                    # if button(f"Show Map for Day {day_count}", key=f"Show Map for Day {day_count}"):
                    if radio_map == "Show Map":
                        # Calculate the shortest path for the day
                        path = calculate_shortest_path(hotel_coords, coords)
                        
                        m = folium.Map(location=hotel_coords, zoom_start=12)

                        for i, coords in enumerate(path, start=0):
                            if i == 0:
                                folium.Marker(coords, tooltip="Hotel").add_to(m)
                            elif i < len(path) - 1:
                                folium.Marker(coords, tooltip=f"Place {i}").add_to(m)
                            folium.PolyLine([path[i-1], coords], color="blue", weight=2.5, opacity=1).add_to(m)

                        st_data = st_folium(m, width=725, key=f"map-{day_count}")
                day_count += 1

            # Display the Google Maps link for each day
            st.subheader("Google Maps Links")
            for day, places in result.items():
                st.write(f"Day {day}:")
                url = f"https://www.google.com/maps/dir/{quote(hotel_address)}/"
                for place in places:
                    url += f"{quote(place['name'])},{quote(location)}/"
                url += f"{quote(hotel_address)}"
                
                st.markdown(f"[{day} Google Maps Navigation Link]({url})")
                # st.write(url)

# Run the Streamlit app
if __name__ == "__main__":
    st.sidebar.title("ExploreEase")
    # use local image as logo
    st.sidebar.image("AI Travel Buddy.png", width=200)
    
    page_selection = st.sidebar.radio("Go to", ["Home", "Plan a Trip"])
    if page_selection == "Home":
        st.title("ExploreEase AI Travel Buddy")
        st.write("Welcome to AI Travel Buddy! Plan your trips with ease using AI.")
        st.write("Select 'Plan a Trip' to start planning your trip.")
        st.write("You can enter the location, number of days, and hotel address to generate a travel plan.")
        st.write("The AI will suggest the 'Must-Visit' places day-wise with a short description for each.")
        st.write("You can also view the itinerary with images and Google Maps links for each day.")

    elif page_selection == "Plan a Trip":
        app()



# Test:
# location = "New York City, New York, USA"
# num_days = 2
# hotel_address = "350 W 39th St, New York, NY 10018"