import os
import requests
import json
import googlemaps

def get_directions(origin_lat, origin_lng, dest_lat, dest_lng, api_key):
    """Fetches driving directions from Google Maps API using latitude & longitude."""
    
    # Format coordinates as "lat,lng"
    origin = f"{origin_lat},{origin_lng}"
    destination = f"{dest_lat},{dest_lng}"

    url = "https://maps.googleapis.com/maps/api/directions/json"
    params = {
        "origin": origin,
        "destination": destination,
        "mode": "driving",
        "key": api_key
    }

    response = requests.get(url, params=params)
    
    if response.status_code != 200:
        raise Exception(f"Google Maps API request failed: {response.status_code}\n{response.text}")

    data = response.json()

    if data['status'] != 'OK':
        raise Exception(f"Google Maps API error: {data['status']}")

    if not data.get('routes'):
        raise Exception("No routes found.")

    leg = data['routes'][0]['legs'][0]

    return {
        "distance": leg['distance']['text'],
        "duration": leg['duration']['text'],
        "start_location": f"{leg['start_location']['lat']}, {leg['start_location']['lng']}",
        "end_location": f"{leg['end_location']['lat']}, {leg['end_location']['lng']}",
        "steps": [step['html_instructions'] for step in leg['steps']]
    }

def get_waypoints(api_key, origin, destination, leg_index=0):
    """Fetches traffic details for a specific leg of the route."""
    
    gmaps = googlemaps.Client(key=api_key)

    try:
        result = gmaps.directions(origin, destination, mode="driving", traffic_model="best_guess", departure_time="now")

        if result and len(result) > 0 and len(result[0]['legs']) > leg_index:
            leg = result[0]['legs'][leg_index]
            
        
        waypoints = {}

        for step in leg['steps']:
            start_location = f"{step['start_location']['lat']},{step['start_location']['lng']}"
            waypoints[start_location] = step["html_instructions"]

        return waypoints

        return "No route found or leg index out of range."

    except googlemaps.exceptions.ApiError as e:
        return f"Google Maps API error: {e}"
    except Exception as e:
        return f"An error occurred: {e}"

if __name__ == "__main__":
    # Example coordinates: Chicago, IL → New York, NY
    origin_lat, origin_lng = 18.517500125498525, 73.87937093008591  # Chicago, IL
    dest_lat, dest_lng = 18.607221238680346, 73.87507577543245  # New York, NY

    api_key = "AIzaSyBJPodhXJS9puryhC-trj7sRGeyX77a0M0"  # Fetch API key from environment

    if not api_key:
        raise Exception("API key is missing. Set 'GOOGLE_MAPS_API_KEY' in your environment.")

    try:
        details = get_directions(origin_lat, origin_lng, dest_lat, dest_lng, api_key)
        waypoints = get_waypoints(api_key, f"{origin_lat},{origin_lng}", f"{dest_lat},{dest_lng}")



        route_deets = {
            "pickup_point": "George Restaurant",
            "pickup_coordinates": {"lat": origin_lat, "lng": origin_lng},
            "delivery_point": "Army Institute of Technology",
            "delivery_coordinates": {"lat": dest_lat, "lng": dest_lng},
            "estimated_distance": details['distance'],
            "estimated_time": details['duration'],
            "waypoints": waypoints

        }

        print(route_deets)


    except Exception as e:
        print(f"An error occurred: {e}")
