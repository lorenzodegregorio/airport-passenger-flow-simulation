# resources/gates.py
"""
Gate Resource for Turin Airport simulation.
Extends the general Facility to handle specific gate assignment and boarding logic.
"""

import sys
import os
from datetime import time, timedelta
from collections import deque

# HACK: Permette l'esecuzione diretta del file 
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from entities.facility import Facility 
from entities.flight import Flight 
from config.time_utils import TimeUtils 

class Gate(Facility):
    def __init__(self, gate_id):
        super().__init__(
            facility_id=gate_id, 
            facility_type='gate', 
            area='air', 
            num_lanes=4, # <--- 4 corsie per l'imbarco
            capacity=float('inf')
        )
        self.active_lanes = 0 # <--- L'imbarco non è attivo all'inizio
        self.assigned_flight = None
        self.boarding_start_time = None
        self.boarding_end_time = None
        
    def __repr__(self):
        flight_info = self.assigned_flight.flight_id if self.assigned_flight else "Nessuno"
        return f"Gate({self.facility_id}, Volo: {flight_info}, Attivo: {self.active_lanes > 0}, Corsie: {len(self.in_service)}/{self.active_lanes}, Coda: {len(self.queue)})"
    
    def assign_flight(self, flight: Flight, current_time: time):
        if self.assigned_flight is not None:
            raise ValueError(f"Gate {self.facility_id} già assegnato a {self.assigned_flight.flight_id}")
        self.assigned_flight = flight

    def start_boarding(self, current_time: time):
        if not self.assigned_flight: return False
        self.active_lanes = self.num_lanes # Attiva tutte e 4 le corsie
        self.boarding_start_time = current_time
        self.assigned_flight.start_boarding(current_time)
        return True

    def end_boarding(self, current_time: time):
        if self.active_lanes == 0: return False
        self.active_lanes = 0 # Chiudi le corsie
        self.boarding_end_time = current_time
        self.assigned_flight.complete_boarding(current_time)
        return True

    def clear_gate(self, current_time: time):
        if self.assigned_flight:
            self.assigned_flight.depart(current_time)
        self.assigned_flight = None
        self.boarding_start_time = None
        self.boarding_end_time = None
        return True