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

# Store user answers
user_intent_memory = {
    "is_late": None,
    "switch_transport": None
}

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

        # Check if significant changes have occurred and engage user in conversation
        eta_difference = abs(new_eta - original_eta)
        if eta_difference > 5:
            gpt_suggestion_dynamic(destination, eta_difference, remaining_distance, new_eta, current_location, gmaps)

        original_eta = new_eta

        # Break if close to destination
        if remaining_distance <= 100:  # Close enough to be considered arrived
            log_simulation_update("Arrived at your destination!")
            break

# Function for conversational GPT suggestions with dynamic prompts
def gpt_suggestion_dynamic(destination, eta_difference, remaining_distance, new_eta, current_location, gmaps):
    if user_intent_memory["is_late"] is None:
        gpt_prompt = f"You're running late. How important is it for you to arrive on time?"
        user_input = wait_for_user_input(f"GPT: {gpt_prompt}\nYour response: ")
        user_intent_memory["is_late"] = user_input.lower()

    if "yes" in user_intent_memory["is_late"] or "very" in user_intent_memory["is_late"]:
        if user_intent_memory["switch_transport"] is None:
            gpt_prompt = "Would you like to switch to a faster mode of transport like a scooter or public transport?"
            user_input = wait_for_user_input(f"GPT: {gpt_prompt}\nYour response: ")
            user_intent_memory["switch_transport"] = user_input.lower()

        if "yes" in user_intent_memory["switch_transport"]:
            gpt_response = gpt_get_actionable_suggestions(destination, eta_difference, remaining_distance, gmaps)
            log_simulation_update(f"GPT Response: {gpt_response}")
        else:
            log_simulation_update("You chose to stay on your current route. Let's keep going!")
    else:
        relaxed_prompt = "No worries! Let's take it easy and enjoy the drive. Would you like me to help find some parking along the way?"
        user_input = wait_for_user_input(f"GPT: {relaxed_prompt}\nYour response: ")
        log_simulation_update(f"GPT Response: {relaxed_prompt}")

# GPT gets dynamic actionable suggestions
def gpt_get_actionable_suggestions(destination, eta_difference, remaining_distance, gmaps):
    public_transport_directions, scooter_directions = get_alternative_routes(gmaps, destination)

    if public_transport_directions:
        public_transport_eta = public_transport_directions[0]['legs'][0]['duration']['value'] / 60
        if public_transport_eta < remaining_distance:
            return f"There's public transport nearby that will help you save time. Switch now to reach your destination faster."

    if scooter_directions:
        scooter_eta = scooter_directions[0]['legs'][0]['duration']['value'] / 60
        if scooter_eta < remaining_distance:
            return f"There's a scooter nearby that can speed up your trip. Head to {scooter_directions[0]['legs'][0]['start_address']}."

    return "Unfortunately, no faster alternatives are available. Let me know if you'd like to contact someone about the delay."

# Function to wait for user input in the simulation
def wait_for_user_input(prompt):
    user_input = input(prompt)
    return user_input

# Function to clean HTML from instructions
def clean_html(raw_html):
    cleanr = re.compile('<.*?>')
    cleantext = re.sub(cleanr, '', raw_html)
    return cleantext

# Function to get alternative routes for public transport or scooters
def get_alternative_routes(gmaps, destination):
    public_transport_directions = gmaps.directions(
        destination, destination, mode="transit", departure_time="now"
    )
    scooter_directions = gmaps.directions(
        destination, destination, mode="bicycling", departure_time="now"
    )

    return public_transport_directions, scooter_directions
