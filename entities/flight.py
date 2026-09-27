"""
Flight entity for Turin Airport simulation
Represents a flight with its schedule and passenger information
"""

import sys
import os
from datetime import datetime, timedelta
import numpy as np

# Aggiungi la cartella root al path di Python per risolvere gli import
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from config.parameters import (
    DAILY_PASSENGERS, FLIGHT_CAPACITY, FLIGHT_LOAD_FACTOR, NUM_FLIGHTS_PER_DAY, BOARDING_OPEN_MIN, BOARDING_CLOSE_MIN
)
from config.time_utils import TimeUtils
from config.rng import RNG

class Flight:
    """
    Represents a flight in the airport simulation.
    - num_passengers = domanda attesa per quel volo (usata anche come seats di default)
    - passengers_boarded = quanti pax sono saliti
    - boarding_open / boarding_close = finestre di boarding (time)
    - state: scheduled -> boarding -> boarded -> departed
    """

    def __init__(self, flight_id, departure_time, gate_id, date, seats=None, num_passengers=None, rng=None):
        self.flight_id = flight_id
        self.departure_time = departure_time
        self.gate_id = gate_id
        self.date = date
        self.rng = rng if rng else RNG()
        self.seats = int(seats) if seats is not None else FLIGHT_CAPACITY

        if num_passengers is not None and num_passengers>self.seats:
            self.seats=num_passengers
        # Domanda attesa sul volo
        self.num_passengers = (
            int(num_passengers) if num_passengers is not None
            else 0
        )


        # Boarding window
        self.boarding_open = self._calculate_boarding_open()
        self.boarding_close = self._calculate_boarding_close()

        # Stato e tracciamenti
        self.state = "scheduled"          # scheduled, boarding, boarded, departed
        self.passengers_boarded = 0
        self.passengers_checked_in = 0
        self.boarding_start_time = None
        self.boarding_end_time = None
        self.actual_departure_time = None
        self.on_time_performance = True
        

        # Flag per conteggio partenza nel main (evita doppi conteggi)
        self._counted_departure = False

    # ---------------------------
    # Generazione e tempi boarding
    # ---------------------------

    def _generate_actual_passenger_demand(self, rng=None):
        """genera un numero di passeggeri attorno al carico target (80% di 200=160)"""
        if rng is None:
            rng=np.random
        mean_pax=self.seats*FLIGHT_LOAD_FACTOR
        pax_count=int (np.random.normal(mean_pax, 10))
        return max(30, min(pax_count, self.seats))
    
    def _calculate_boarding_open(self):
        departure_dt = datetime.combine(self.date, self.departure_time)
        return (departure_dt - timedelta(minutes=BOARDING_OPEN_MIN)).time()

    def _calculate_boarding_close(self):
        departure_dt = datetime.combine(self.date, self.departure_time)
        return (departure_dt - timedelta(minutes=BOARDING_CLOSE_MIN)).time()

    # ---------------------------
    # Utility per il boarding
    # ---------------------------
    def seats_left(self):
        return max(0, self.seats - self.passengers_boarded)

    def can_board(self):
        return self.passengers_boarded < self.seats
    def can_accept_passenger(self):
        return self.passengers_boarded<self.seats
    def start_boarding(self, current_time):
        if self.state == "scheduled":
            self.state = "boarding"
            self.boarding_start_time = current_time

    def add_boarded_passenger(self):
        """Incrementa i pax a bordo rispettando la capacità."""
        if self.state!='boarding':
            return False
        if not self.can_accept_passenger():
            return False
        self.passengers_boarded += 1
        return True

    def complete_boarding(self, current_time):
        """Completa la fase di boarding (opzionale: può rimanere 'boarding' fino a partenza)."""
        # Manteniamo 'boarding' finché non parte, ma salviamo il timestamp se serve.
        self.state='boarded'
        self.boarding_end_time = current_time

    def depart(self, current_time):
        """Marca il volo come partito e calcola OTP."""
        if self.state != "departed":
            self.state = "departed"
            self.actual_departure_time = current_time

            scheduled_minutes = TimeUtils.time_to_minutes(self.departure_time)
            actual_minutes = TimeUtils.time_to_minutes(current_time)
            delay = actual_minutes - scheduled_minutes
            self.on_time_performance = delay <= 15  # on-time se <= 15'

    # ---------------------------
    # Metriche e serializzazione
    # ---------------------------
    def get_boarding_progress(self):
        # Progress rispetto ai posti (capacità)
        if self.seats <= 0:
            return 0.0
        return (self.passengers_boarded / self.seats) * 100.0

    def is_boarding_complete(self):
        return self.passengers_boarded >= self.seats

    def get_boarding_duration(self):
        if not self.boarding_start_time or not self.boarding_end_time:
            return None
        return TimeUtils.time_difference(self.boarding_start_time, self.boarding_end_time)

    def to_dict(self):
        return {
            'flight_id': self.flight_id,
            'departure_time': self.departure_time,
            'gate_id': self.gate_id,
            'num_passengers': self.num_passengers,
            'seats': self.seats,
            'passengers_boarded': self.passengers_boarded,
            'boarding_open': self.boarding_open,
            'boarding_close': self.boarding_close,
            'state': self.state,
            'on_time_performance': self.on_time_performance
        }

    def __repr__(self):
        return (f"Flight({self.flight_id}, {self.departure_time}, "
                f"Gate:{self.gate_id}, Demand:{self.num_passengers}, Seats:{self.seats}, "
                f"Boarded:{self.passengers_boarded}, State:{self.state})")
