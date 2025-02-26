import json
import time
import pygame
from datetime import datetime
from plyer import notification

# Path to JSON file containing medicine schedule
JSON_FILE = "medicine_schedule.json"
ALARM_SOUND = "little_do_you_know.mp3"  # Replace with your MP3 file

# Initialize pygame mixer for alarm sound
pygame.mixer.init()

def load_medicine_schedule():
    """Loads medicine schedule from JSON file."""
    try:
        with open(JSON_FILE, "r") as file:
            return json.load(file)
    except Exception as e:
        print(f"Error reading JSON file: {e}")
        return {}

def play_alarm():
    """Plays the alarm sound when it's time to take medicine."""
    try:
        pygame.mixer.music.load(ALARM_SOUND)
        pygame.mixer.music.play()
        print("\n⏰ ALARM RINGING! Time to take your medicine! ⏰")

        # Keep alarm playing for 10 seconds
        time.sleep(10)
        pygame.mixer.music.stop()
    
    except Exception as e:
        print(f"Error playing alarm: {e}")

def check_medicine_reminders():
    """Continuously checks if it's time to take medicine."""
    medicine_schedule = load_medicine_schedule()
    
    while True:
        current_time = datetime.now().strftime("%H:%M")  # Get current time (HH:MM format)

        for medicine, details in medicine_schedule.items():
            if current_time in details["timings"]:  # Check if it's medicine time
                message = f"Time to take {medicine}"
                if "dosage" in details:
                    message += f" - {details['dosage']}"
                
                # Show notification
                notification.notify(
                    title="Medicine Reminder",
                    message=message,
                    timeout=10
                )

                # Print to console
                print(f"\n🔔 Reminder: {message} 🔔")

                # Play alarm sound
                play_alarm()

                time.sleep(60)  # Prevent multiple triggers within the same minute

        time.sleep(30)  # Check every 30 seconds

# Run the reminder system
check_medicine_reminders()