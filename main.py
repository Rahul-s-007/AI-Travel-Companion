import streamlit as st
import requests
import json
import folium
from folium import plugins
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
import openai
from streamlit_folium import st_folium
from streamlit_extras.stateful_button import button
from urllib.parse import quote

import os
from dotenv import load_dotenv
load_dotenv()

# Set up the OpenAI API key
openai.api_key = os.getenv("YOUR_OPENAI_API_KEY")

# Set up the Google Maps API key
google_maps_api_key = os.getenv("GOOGLE_MAPS_API_KEY")

# Function to get coordinates from address
def get_coordinates(address):
    geolocator = Nominatim(user_agent="my_app")
    location = geolocator.geocode(address)
    return location.latitude, location.longitude

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

# Streamlit app
def app():
    st.title("AI Travel Buddy")
    
    # Get user input
    location = st.text_input("Enter the location (Country, State, City)")
    num_days = st.number_input("Enter the number of days", min_value=1, step=1)
    hotel_address = st.text_input("Enter the hotel address")
    
    radio = st.radio("Next:", ["Filling Deatils", "Submit"])

    # if button("Generate Travel Plan", key="Generate Travel Plan"): # stateful_button
    if radio == "Submit":
        # Get hotel coordinates
        hotel_coords = get_coordinates(hotel_address)

        # Call OpenAI API to generate "Must-Visit" places
        # prompt = f"For a {num_days}-day trip to {location}, starting from the hotel at {hotel_address}, generate a JSON object with 'Must-Visit' places day-wise, with a short description for each."
        # response = openai.Completion.create(
        #     engine="text-davinci-003",
        #     prompt=prompt,
        #     max_tokens=2048,
        #     n=1,
        #     stop=None,
        #     temperature=0.7,
        # )
        
        # result = json.loads(response.choices[0].text)
        
        result = {"Day 1": [
                    {
                    "name": "Central Park",
                    "description": "A famous urban park in Manhattan with beautiful landscapes, lakes, and attractions like the Central Park Zoo and the Metropolitan Museum of Art."
                    },
                    {
                    "name": "Empire State Building",
                    "description": "An iconic 102-story skyscraper and one of the most famous buildings in the world, offering stunning views of New York City from its observation decks."
                    },
                    {
                    "name": "Times Square",
                    "description": "The bright and lively intersection of Broadway and 7th Avenue, known for its massive electronic billboards, entertainment venues, and bustling atmosphere."
                    }],
                "Day 2": [
                    {
                    "name": "Statue of Liberty",
                    "description": "A colossal neoclassical sculpture on Liberty Island, a famous landmark and symbol of freedom and democracy."
                    },
                    {
                    "name": "9/11 Memorial & Museum",
                    "description": "A memorial and museum honoring the victims of the September 11, 2001 terrorist attacks and exploring the history of the events."
                    },
                    {
                    "name": "High Line",
                    "description": "An elevated park built on a former railroad line, offering unique views of the city and featuring art installations, gardens, and food vendors."
                    }]
                }
        
        # Get coordinates for all places
        day_places = []
        day_coords = []
        for day, places in result.items():
            places_coords = []
            for place in places:
                address = f"{place['name']}, {location}"
                coords = get_coordinates(address)
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
            st.write(url)

# Run the Streamlit app
if __name__ == "__main__":
    app()


# Test:
# location = "New York City, New York, USA"
# num_days = 2
# hotel_address = "350 W 39th St, New York, NY 10018"
