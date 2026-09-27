# entities/passenger.py  # ✅ CORREGGI IL NOME SE NECESSARIO
"""
Passenger entity for Turin Airport simulation
Represents individual passengers and their behavior
"""

import sys
import os
from datetime import datetime, time
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config.parameters import *
from config.rng import *
from config.time_utils import TimeUtils

class Passenger:
    """
    Represents a passenger in the airport simulation
    """
    
    _id_counter = 1  # Class variable for generating unique IDs
    
    def __init__(self, passenger_id, flight, arrival_time, rng=None):
        self.passenger_id = passenger_id
        self.flight = flight
        self.arrival_time = arrival_time
        self.rng = rng if rng else RNG()
        
        # Passenger state
        self.current_location = "entrance"
        self.state = "arrived"
        self.miss_reason=None
        
        # Companions
        self.num_companions = self.rng.num_companions() 
        self.has_companions = (self.num_companions > 0)
        self.companions_with_passenger = self.has_companions
        
        # Activity tracking - MODIFICA: Aggiungi flag per attività in corso
        self.landside_visits_planned = self.rng.num_facility_visits(MAX_LAND_SIDE_VISITS)
        self.airside_visits_planned = self.rng.num_facility_visits(MAX_AIR_SIDE_VISITS)
        self.landside_visits_completed = 0
        self.airside_visits_completed = 0
        self.current_activity = None
        self.activity_start_time = None
        self.activities_log = []
        
        # Timing information
        self.security_processing_time = None
        self.boarding_time = None
        self.actual_boarding_time = None
        self.buffer_before_boarding = self.rng.buffer_time_before_boarding()
        
        # Performance metrics
        self.time_entered_security_queue = None
        self.time_exited_security = None
        self.time_arrived_at_gate = None
        
    def __repr__(self):
        return f"Passenger({self.passenger_id}, Flight: {self.flight.flight_id}, State: {self.state})"
    
    def to_dict(self):
        """Convert passenger to dictionary for data collection"""
        sec_time = self.get_time_in_security()
        total_time = self.get_total_time_in_system(current_time=time(23,0))
        return {
            'passenger_id': self.passenger_id,
            'flight_id': self.flight.flight_id,
            'arrival_time': self.arrival_time,
            'has_companions': self.has_companions,
            'num_companions': self.num_companions,
            'landside_visits_planned': self.landside_visits_planned,
            'airside_visits_planned': self.airside_visits_planned,
            'landside_visits_completed': self.landside_visits_completed,
            'airside_visits_completed': self.airside_visits_completed,
            'state': self.state,
            'buffer_before_boarding': self.buffer_before_boarding,
            'security_time': sec_time,
            'total_time': total_time, 
            'miss_reason':self.miss_reason,
        }
    
    def get_next_landside_activity(self):
        """Determine next landside activity type"""
        if self.landside_visits_completed >= self.landside_visits_planned:
            return None
        
        activity_type = self.rng.visit_land_side_facility()
        # MODIFICA: NON incrementare subito, solo quando l'attività inizia
        return activity_type
    
    def get_next_airside_activity(self):
        """Determine next airside activity type"""
        if self.airside_visits_completed >= self.airside_visits_planned:
            return None
        
        activity_type = self.rng.visit_air_side_facility()
        # MODIFICA: NON incrementare subito, solo quando l'attività inizia
        return activity_type
    
    def get_activity_duration(self, activity_type):
        """Get duration for a specific activity type"""
        if activity_type == 'shop':
            return self.rng.shop_visit_time()
        elif activity_type == 'bar':
            return self.rng.bar_visit_time()
        elif activity_type == 'restaurant':
            return self.rng.restaurant_visit_time()
        else:
            return 0
    
    def select_facility(self, activity_type, area):
        """Select a specific facility for an activity"""
        if area == 'land':
            if activity_type == 'shop':
                count = LAND_SIDE_SHOPS
            else:  # bar or restaurant
                count = LAND_SIDE_RESTAURANTS
        else:  # air
            if activity_type == 'shop':
                count = AIR_SIDE_SHOPS
            else:  # bar or restaurant
                count = AIR_SIDE_RESTAURANTS
        
        return self.rng.select_facility(activity_type, area, count)
    
    def start_activity(self, activity_type, facility_id, start_time):
        """Start a new activity"""
        # MODIFICA: Incrementa i contatori solo quando l'attività inizia
        if self.current_location == 'landside':
            self.landside_visits_completed += 1
        else:  # airside
            self.airside_visits_completed += 1
            
        self.current_activity = {
            'type': activity_type,
            'facility_id': facility_id,
            'start_time': start_time,
            'duration': self.get_activity_duration(activity_type),
            'area': 'land' if self.current_location in ['landside'] else 'air'
        }
        self.activity_start_time = start_time
        self.state = f"{self.current_location}_activity"
        
        # Log the activity start
        self.activities_log.append({
            'activity': 'start',
            'type': activity_type,
            'facility_id': facility_id,
            'time': start_time,
            'area': self.current_location
        })
    
    def complete_activity(self, end_time):
        """Complete the current activity"""
        if self.current_activity:
            self.current_activity['end_time'] = end_time
            self.activities_log.append({
                'activity': 'end',
                'type': self.current_activity['type'],
                'facility_id': self.current_activity['facility_id'],
                'time': end_time,
                'area': self.current_location
            })
            
            self.current_activity = None
            self.activity_start_time = None
            self.state = self.current_location
    
    def enter_security_queue(self, queue_time):
        """Enter security queue"""
        self.time_entered_security_queue = queue_time
        self.state = "security_queue"
        self.current_location = "security_queue"
        
        # Companions leave at security
        self.companions_with_passenger = False
        
        self.activities_log.append({
            'activity': 'security_queue_enter',
            'time': queue_time
        })
    
    def start_security_processing(self, start_time):
        """Start security processing"""
        self.security_processing_time = self.rng.security_processing_time()
        self.state = "security_processing"
        self.current_location = "security_checkpoint"
        
        self.activities_log.append({
            'activity': 'security_processing_start',
            'time': start_time
        })
    
    def complete_security_processing(self, end_time):
        """Complete security processing and enter airside"""
        self.time_exited_security = end_time
        self.state = "airside_activities"
        self.current_location = "airside"
        
        self.activities_log.append({
            'activity': 'security_processing_end',
            'time': end_time
        })
        self.activities_log.append({
            'activity': 'enter_airside',
            'time': end_time
        })
    
    def should_go_to_gate(self, current_time):
        """Determine if passenger should head to gate based on flight time and buffer"""
        flight_departure_minutes = TimeUtils.time_to_minutes(self.flight.departure_time)
        current_minutes = TimeUtils.time_to_minutes(current_time)
        time_to_departure = flight_departure_minutes - current_minutes
        
        return time_to_departure <= self.buffer_before_boarding
    
    
    def start_boarding(self, boarding_time):
        """Start boarding process"""
        self.actual_boarding_time = boarding_time
        self.state = "boarding"
        self.current_location = "gate"
        
        self.activities_log.append({
            'activity': 'boarding_start',
            'time': boarding_time
        })
    
    def complete_boarding(self, boarding_time):
        """Complete boarding"""
        self.state = "boarded"
        
        self.activities_log.append({
            'activity': 'boarding_complete',
            'time': boarding_time
        })
    
    def miss_flight(self, current_time, reason='unknown'):
        """Mark passenger as missed flight"""
        self.state = "missed_flight"
        self.miss_reason=reason
        
        self.activities_log.append({
            'activity': 'missed_flight',
            'time': current_time, 
            'reason':reason
        })
    
    def get_total_time_in_system(self, current_time=None):
        """Calculate total time spent in airport system"""
        if not self.activities_log:
            return 0
        
        arrival_time = self.activities_log[0]['time']
        if self.state in ['boarded', 'missed_flight']:
            end_time = self.activities_log[-1]['time']
        else:
            end_time = current_time if current_time else self.activities_log[-1]['time']
        
        return TimeUtils.time_difference(arrival_time, end_time)
    
    def get_time_in_security(self):
        """Calculate time spent in security (queue + processing)"""
        if not self.time_entered_security_queue or not self.time_exited_security:
            return 0
        
        return TimeUtils.time_difference(self.time_entered_security_queue, self.time_exited_security)
    
    def get_activities_summary(self):
        """Get summary of all activities"""
        return {
            'passenger_id': self.passenger_id,
            'total_landside_visits': self.landside_visits_completed,
            'total_airside_visits': self.airside_visits_completed,
            'total_activities': len([a for a in self.activities_log if a['activity'] in ['start', 'end']]),
            'security_time': self.get_time_in_security(),
            'total_time': self.get_total_time_in_system()
        }
    
    def should_go_to_security(self, current_time):
        """
        Determina se il passeggero (che è in landside) deve andare alla sicurezza.
        """
        # Usa il parametro globale MIN_TIME_BEFORE_FLIGHT_TO_SECURITY
        flight_departure_minutes = TimeUtils.time_to_minutes(self.flight.departure_time)
        current_minutes = TimeUtils.time_to_minutes(current_time)
        time_to_departure = flight_departure_minutes - current_minutes
        
        # Se il tempo al volo è minore o uguale al buffer, vai alla sicurezza
        return time_to_departure <= MIN_TIME_BEFORE_FLIGHT_TO_SECURITY

# MODIFICA: Valuta se hai davvero bisogno di PassengerGroup
# Se non la usi nel main loop, puoi rimuoverla per semplificare
class PassengerGroup:
    """
    Represents a group of passengers traveling together
    """
    
    def __init__(self, group_id, passengers, rng=None):
        self.group_id = group_id
        self.passengers = passengers
        self.rng = rng if rng else RNG()
        self.stay_together = self.rng.group_stay_together()
    
    def __repr__(self):
        return f"PassengerGroup({self.group_id}, Size: {len(self.passengers)}, StayTogether: {self.stay_together})"
    
    def split_for_activities(self):
        """Split group for activities if they don't stay together"""
        if self.stay_together:
            return [self.passengers]
        else:
            return [[p] for p in self.passengers]
    
    def all_passengers_ready(self, condition_func):
        """Check if all passengers in group meet a condition"""
        return all(condition_func(p) for p in self.passengers)

def create_passenger_from_schedule(passenger_data, rng=None):
    """Create a Passenger object from schedule data"""
    passenger = Passenger(
        passenger_id=passenger_data['passenger_id'],
        flight=passenger_data['flight'],
        arrival_time=passenger_data['arrival_time'],
        rng=rng
    )
    profile = passenger_data.get("arrival_profile", "regular")  # fallback
    passenger.arrival_profile = profile

    default_target = 70.0
    passenger.security_target_min = SECURITY_TARGET_BY_PROFILE.get(profile, default_target)
    return passenger
