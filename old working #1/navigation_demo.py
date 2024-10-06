import googlemaps
from datetime import timedelta, datetime
import time 
from drive_simulation import simulate_drive_with_updates
import re

# Initialize Google Maps client with API key
gmaps = googlemaps.Client(key="xxx")  # Replace with your actual Google Maps API key

# Function to get route with geocoding for origin and destination
def get_route(gmaps, origin, destination, arrival_time=None):
    # Use geocoding to get precise lat/lng for origin and destination
    origin_geocode = gmaps.geocode(origin)
    destination_geocode = gmaps.geocode(destination)
    
    if not origin_geocode:
        print(f"Error: The origin '{origin}' could not be found. Using default: 367 Addison Avenue, Palo Alto, CA")
        origin = "367 Addison Avenue, Palo Alto, CA"
        origin_geocode = gmaps.geocode(origin)
    
    if not destination_geocode:
        print(f"Error: The destination '{destination}' could not be found. Using default: Golden Gate Bridge, San Francisco, CA")
        destination = "Golden Gate Bridge, San Francisco, CA"
        destination_geocode = gmaps.geocode(destination)
    
    origin_coords = origin_geocode[0]['geometry']['location']
    destination_coords = destination_geocode[0]['geometry']['location']
    
    # Request directions using lat/lng coordinates
    directions_result = gmaps.directions(
        origin_coords, 
        destination_coords, 
        mode="driving", 
        arrival_time=arrival_time
    )
    
    return directions_result, origin, destination

# Function to clean HTML tags from a string
def clean_html(raw_html):
    clean_text = re.sub(r'<.*?>', '', raw_html)
    return clean_text

# Updated function to print route information
def print_route_info(route, final_origin, final_destination):
    first_route = route[0]
    leg = first_route['legs'][0]

    print(f"\nStarting at: {leg['start_address']} (Resolved: {final_origin})")
    print(f"Ending at: {leg['end_address']} (Resolved: {final_destination})")
    print(f"Total Distance: {leg['distance']['text']}")
    print(f"Estimated Time: {leg['duration']['text']}")
    print(f"Travel time considering traffic: {leg.get('duration_in_traffic', {}).get('text', 'N/A')}")

    print("\nStep-by-step directions:")
    for step in leg['steps']:
        instruction = step['html_instructions']
        clean_instruction = clean_html(instruction)  # Clean the HTML tags
        distance = step['distance']['text']
        print(f"- {clean_instruction} for {distance}")

# Main function with user input and default addresses
def main():
    # Default addresses
    default_origin = "367 Addison Avenue, Palo Alto, CA"
    default_destination = "Golden Gate Bridge, San Francisco, CA"
    
    # Prompt user for origin and destination
    origin = input(f"Where are you? (default: {default_origin}) ").strip() or default_origin
    destination = input(f"Where do you want to go? (default: {default_destination}) ").strip() or default_destination

    # Get the current time
    current_time = datetime.now()
    current_time_str = current_time.strftime("%H:%M")
    
    # Calculate the default arrival time, which is 1 hour ahead of the current time
    default_arrival_time = (current_time + timedelta(hours=1)).strftime("%H:%M")
    
    print(f"\nThe current time is: {current_time_str}")
    
    # Prompt the user for arrival time with a default that is 1 hour ahead
    arrival_time_str = input(f"What time do you need to be there? (default: {default_arrival_time}) (HH:MM in 24-hour format) ").strip() or default_arrival_time
    desired_arrival_time = datetime.strptime(arrival_time_str, "%H:%M")

    # Get initial route
    route, final_origin, final_destination = get_route(gmaps, origin, destination)
    
    # Print the route directions
    print_route_info(route, final_origin, final_destination)
    
    # Start the simulation
    simulate_drive_with_updates(gmaps, origin, destination, desired_arrival_time)

if __name__ == "__main__":
    main()
