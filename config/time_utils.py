# HELPER HH:MM <-> min
# config/time_utils.py
"""
Time utilities for Turin Airport simulation
Handles time conversions, calculations, and scheduling
"""

from datetime import datetime, time, timedelta
import numpy as np
from .parameters import *


class TimeUtils:
    """
    Utility class for time-related operations in the simulation
    """
    
    @staticmethod
    def time_to_minutes(t):
        """Convert datetime.time or datetime.datetime to minutes since midnight"""
        if isinstance(t, time):
            return t.hour * 60 + t.minute
        elif isinstance(t, datetime):
            return t.hour * 60 + t.minute
        else:
            raise ValueError(f"Unsupported type: {type(t)}")
    
    @staticmethod
    def minutes_to_time(minutes):
        """Convert minutes since midnight to datetime.time object"""
        # Handle negative minutes (shouldn't happen in our simulation)
        total = int(round(minutes))
        total %= (24 * 60)
        hours = total // 60
        mins = total % 60
        return time(hour=hours, minute=mins)
    
    @staticmethod
    def time_difference(start_time, end_time):
        """Calculate difference in minutes between two time objects"""
        start_minutes = TimeUtils.time_to_minutes(start_time)
        end_minutes = TimeUtils.time_to_minutes(end_time)
        return end_minutes - start_minutes
    
    @staticmethod
    def add_minutes_to_time(t, minutes):
        """Add minutes to a time object and return a new time object"""
        if isinstance(t, time):
            total_minutes = TimeUtils.time_to_minutes(t) + minutes
            return TimeUtils.minutes_to_time(total_minutes)
        elif isinstance(t, datetime):
            return t + timedelta(minutes=minutes)
        else:
            raise ValueError(f"Unsupported type: {type(t)}")
    
    @staticmethod
    def is_time_between(check_time, start_time, end_time):
        """Check if a time is between two other times (inclusive)"""
        check_min = TimeUtils.time_to_minutes(check_time)
        start_min = TimeUtils.time_to_minutes(start_time)
        end_min = TimeUtils.time_to_minutes(end_time)
        
        if start_min <= end_min:
            # Normal case: times are on the same day
            return start_min <= check_min <= end_min
        else:
            # Overnight case (not needed for our simulation)
            return check_min >= start_min or check_min <= end_min
    
    @staticmethod
    def datetime_from_date_and_time(date_obj, time_obj):
        """Create a datetime object from date and time objects"""
        return datetime.combine(date_obj, time_obj)
    
    @staticmethod
    def format_time_duration(minutes):
        """Format a duration in minutes to a readable string"""
        if minutes < 60:
            return f"{minutes:.1f} min"
        else:
            hours = minutes // 60
            mins = minutes % 60
            return f"{hours:.0f}h {mins:.0f}min"
    
    @staticmethod
    def get_current_simulation_time(start_datetime, elapsed_minutes):
        """Get current simulation datetime based on start and elapsed minutes"""
        return start_datetime + timedelta(minutes=elapsed_minutes)
    
    @staticmethod
    def calculate_passenger_arrival_time(flight_departure_time, arrival_offset_minutes, rng=None):
        """
        Calculate when a passenger arrives at the airport based on flight time and offset
        Returns a time object
        """
        # Convert flight departure time to minutes since midnight
        flight_minutes = TimeUtils.time_to_minutes(flight_departure_time)
        
        # Calculate arrival time (subtract offset)
        arrival_minutes = flight_minutes - arrival_offset_minutes
        
        if ARRIVAL_TIME_JITTER and ARRIVAL_TIME_JITTER > 0:
            if rng is None:
                # Fallback: usa numpy random (meno ideale)
                jitter = np.random.randint(-ARRIVAL_TIME_JITTER, ARRIVAL_TIME_JITTER + 1)
            else:
                # Usa il generatore RNG per riproducibilità
                jitter = rng.random_int(-ARRIVAL_TIME_JITTER, ARRIVAL_TIME_JITTER)
            arrival_minutes += jitter

        # Ensure arrival is not before 4:00 AM (simulation start)
        arrival_minutes = max(4 * 60, arrival_minutes)
        
        return TimeUtils.minutes_to_time(arrival_minutes)
    
    @staticmethod
    def generate_passenger_arrival_schedule(flight_schedule, rng):
        """
        Generate arrival times for all passengers based on flight schedule
        Returns a list of (passenger_id, arrival_time, flight) tuples
        """
        arrivals = []
        passenger_id = 0
        
        for flight in flight_schedule:
            for i in range(flight.num_passengers):
                # Determine arrival type and offset
                arrival_type = rng.passenger_arrival_type()
                arrival_offset = rng.passenger_arrival_offset(arrival_type)
                
                # Calculate arrival time - MODIFICA: passa rng
                arrival_time = TimeUtils.calculate_passenger_arrival_time(
                    flight.departure_time, arrival_offset, rng
                )
                
                # Create passenger ID
                passenger_id += 1
                passenger_data = {
                    'passenger_id': f"P{passenger_id:06d}",
                    'arrival_time': arrival_time,
                    'flight': flight,
                    'arrival_type': arrival_type,
                    'arrival_offset': arrival_offset
                }
                
                arrivals.append(passenger_data)
        
        # Sort arrivals by time
        arrivals.sort(key=lambda x: x['arrival_time'])
        
        return arrivals
    
    @staticmethod
    def calculate_boarding_start_end(flight):
        """Calculate boarding start and end times for a flight"""
        departure_dt = TimeUtils.datetime_from_date_and_time(flight.date, flight.departure_time)
        
        boarding_start = departure_dt - timedelta(minutes=BOARDING_OPEN_MIN)
        boarding_end = departure_dt - timedelta(minutes=BOARDING_CLOSE_MIN)
        
        return boarding_start.time(), boarding_end.time()
    
    @staticmethod
    def is_flight_departing_soon(flight, current_time, threshold_minutes=30):
        """Check if a flight is departing within the threshold minutes"""
        flight_minutes = TimeUtils.time_to_minutes(flight.departure_time)
        current_minutes = TimeUtils.time_to_minutes(current_time)
        return (flight_minutes - current_minutes) <= threshold_minutes

# Alternative: function-based approach for simpler usage
def time_to_minutes(t):
    """Convert time to minutes since midnight"""
    return TimeUtils.time_to_minutes(t)

def minutes_to_time(minutes):
    """Convert minutes to time object"""
    return TimeUtils.minutes_to_time(minutes)

def add_minutes(t, minutes):
    """Add minutes to time"""
    return TimeUtils.add_minutes_to_time(t, minutes)