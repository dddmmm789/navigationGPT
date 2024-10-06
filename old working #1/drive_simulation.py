import googlemaps
import time
from datetime import datetime, timedelta
import openai
import logging
import re

# Ensure your OpenAI API key is set
openai.api_key = "xxx"  # Replace with your actual OpenAI API key

# Initialize logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Function to log simulation updates
def log_simulation_update(update_message):
    logging.info(update_message)

# Function to get updated route with real-time traffic data
def get_updated_route(gmaps, origin_coords, destination_coords):
    try:
        directions_result = gmaps.directions(
            origin_coords,
            destination_coords,
            mode="driving",
            departure_time="now"  # Get real-time traffic data
        )
        return directions_result
    except Exception as e:
        log_simulation_update(f"Error fetching updated route: {e}")
        return None

# Function to simulate the drive with faster time and periodic updates
def simulate_drive_with_updates(gmaps, origin, destination, desired_arrival_time, interval=3):
    """
    Simulates a drive where every 3 seconds equals 5 minutes of real-time driving.
    """
    try:
        origin_geocode = gmaps.geocode(origin)
        destination_geocode = gmaps.geocode(destination)

        if not origin_geocode or not destination_geocode:
            log_simulation_update("Error: Could not find origin or destination.")
            return

        origin_coords = origin_geocode[0]['geometry']['location']
        destination_coords = destination_geocode[0]['geometry']['location']

    except Exception as e:
        log_simulation_update(f"Error fetching geocode data: {e}")
        return

    # Get initial driving route
    route = get_updated_route(gmaps, origin_coords, destination_coords)
    leg = route[0]['legs'][0]
    steps = leg['steps']  # Get step-by-step breakdown of the route
    total_distance = leg['distance']['value']  # Total distance in meters
    original_eta = leg['duration']['value'] / 60  # Convert to minutes
    remaining_distance = total_distance
    leg_duration = leg['duration']['value']  # total trip time in seconds

    log_simulation_update(f"Simulation started from {leg['start_address']} to {leg['end_address']}")
    log_simulation_update(f"Initial ETA: {original_eta:.2f} minutes")

    elapsed_simulation_time = 0
    current_step_index = 0  # Start at the first step

    while remaining_distance > 0:
        time.sleep(interval)  # Every 3 seconds equals 5 minutes of real driving
        elapsed_simulation_time += 300  # Add 5 minutes (in seconds) to simulated time

        # Simulate that the car has moved based on elapsed simulation time
        fraction_of_trip_completed = elapsed_simulation_time / leg_duration
        distance_covered = fraction_of_trip_completed * total_distance
        remaining_distance = total_distance - distance_covered

        if remaining_distance <= 0:
            remaining_distance = 0

        # Update the current step if we have completed the current step's distance
        while current_step_index < len(steps) and remaining_distance < total_distance - steps[current_step_index]['distance']['value']:
            total_distance -= steps[current_step_index]['distance']['value']
            current_step_index += 1

        # Update the car's location to the new step
        if current_step_index < len(steps):
            current_step = steps[current_step_index]
            current_location = current_step['start_location']

            log_simulation_update(f"[Update] Location: {clean_html(current_step['html_instructions'])}, Remaining Distance: {remaining_distance / 1000:.2f} km")
        else:
            current_location = leg['end_location']
            log_simulation_update(f"[Update] Location: {leg['end_address']}, Remaining Distance: {remaining_distance / 1000:.2f} km")

        # Recalculate ETA based on remaining distance
        new_eta = (remaining_distance / total_distance) * original_eta
        log_simulation_update(f"Updated ETA: {new_eta:.2f} minutes")

        # Check if significant changes have occurred and notify via GPT if necessary
        eta_difference = abs(new_eta - original_eta)
        if eta_difference > 5:
            suggestion = gpt_suggestion(destination, eta_difference, new_eta, current_location)
            log_simulation_update(f"GPT Suggestion: {suggestion}")
        
        original_eta = new_eta

        # Break if close to destination
        if remaining_distance <= 100:  # Close enough to be considered arrived
            log_simulation_update("Arrived at your destination!")
            break

# GPT suggestion function
def gpt_suggestion(destination, eta_change, new_eta, current_location):
    prompt = f"You are driving to {destination}. The ETA has changed by {eta_change:.2f} minutes, and your new ETA is {new_eta:.2f} minutes. You are currently at {current_location}. What would you suggest to help the driver?"

    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are an assistant that helps with driving suggestions."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=100
        )
        suggestion = response['choices'][0]['message']['content']
        return suggestion
    except Exception as e:
        log_simulation_update(f"Error retrieving GPT suggestion: {e}")
        return "No suggestion available at the moment."

# Function to clean HTML from instructions
def clean_html(raw_html):
    cleanr = re.compile('<.*?>')
    cleantext = re.sub(cleanr, '', raw_html)
    return cleantext
