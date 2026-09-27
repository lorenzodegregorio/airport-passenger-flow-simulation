# analysis/metrics.py
"""
Classe Metrics per la raccolta dati della simulazione.
Questa classe agisce come un contenitore centrale per tutti i log e i dati raccolti durante un'esecuzione della simulazione.
"""

import sys
import os
from datetime import time
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from entities.passenger import Passenger
from entities.flight import Flight

class Metrics:
    """Un contenitore per raccogliere le statistiche della simulazione."""
    
    def __init__(self):
        # 1. Log basati sul tempo (catturati ad ogni minuto)
        # Formato: (timestamp, valore)
        self.security_queue_log = []      # (time, lunghezza_coda)
        self.security_utilization_log = []  # (time, corsie_occupate)
        self.landside_pop_log = []        # (time, num_passeggeri_landside)
        self.landside_activity_log = []   # (time, num_passeggeri_in_attivita_landside)
        self.airside_pop_log = []         # (time, num_passeggeri_airside)
        self.airside_activity_log = []    # (time, num_passeggeri_in_attivita_airside)

        # 2. Log basati su eventi (catturati quando un'entità finisce)
        self.completed_passengers = []  # Lista di oggetti Passenger (o loro dict)
        self.departed_flights = []      # Lista di oggetti Flight (o loro dict)
        
        # 3. Contatori globali
        self.total_arrivals = 0
        self.total_passengers_arrived=0
        self.total_companions_arrived=0
        self.total_people_arrived=0
        self.total_companions_departed = 0
        self.total_security_cleared = 0
        self.total_boarded = 0
        self.total_missed_flights = 0

        self.passengers_by_state = {
            'boarded': 0,
            'missed': 0,
            'in_system': 0
        }

    def log_time_step(self, current_time: time, environment: dict, stats: dict, 
                      landside_passengers: list, airside_passengers: list):
        """Registra lo stato del sistema a un preciso istante (chiamato ogni minuto)."""
        sec_checkpoint = environment['security_checkpoint']
        
        # Log delle code e utilizzo
        self.security_queue_log.append((current_time, len(sec_checkpoint.queue)))
        self.security_utilization_log.append((current_time, len(sec_checkpoint.in_service)))
        
        # Log delle popolazioni
        self.landside_pop_log.append((current_time, len(landside_passengers)))
        self.airside_pop_log.append((current_time, len(airside_passengers)))
        
        # Log delle attività (quanti sono attivamente in un negozio/bar)
        land_activity = sum(1 for p in landside_passengers if p.current_activity)
        air_activity = sum(1 for p in airside_passengers if p.current_activity)
        self.landside_activity_log.append((current_time, land_activity))
        self.airside_activity_log.append((current_time, air_activity))

    def log_passenger_completion(self, passenger: Passenger):
        """Registra un passeggero che ha completato il suo percorso (imbarcato O ha perso il volo)."""
        if passenger.state == 'boarded':
            self.total_boarded += 1
        elif passenger.state == 'missed_flight':
            self.total_missed_flights += 1
            
        # Salviamo un riepilogo dei dati del passeggero per l'analisi post-simulazione
        self.completed_passengers.append(passenger.to_dict())

    def log_flight_departure(self, flight: Flight):
        """Registra un volo partito."""
        self.departed_flights.append(flight.to_dict())

    def log_arrival(self, passenger=None):
        if passenger:
            self.total_passengers_arrived += 1
            if passenger.has_companions and passenger.num_companions > 0:
                self.total_companions_arrived += passenger.num_companions
                self.total_people_arrived += 1 + passenger.num_companions
            else:
                self.total_people_arrived += 1
        else:
            self.total_passengers_arrived += 1
            self.total_people_arrived += 1
    def log_security_cleared(self):
        self.total_security_cleared += 1

    def log_companions_departed(self, count: int):
        self.total_companions_departed += count

    def check_consistency(self):
        """Verifica che i conteggi siano consistenti"""
        total_expected = self.total_passengers_arrived + self.total_companions_arrived
        if total_expected != self.total_people_arrived:
            print(f"WARNING: Inconsistenza nei conteggi: Passeggeri={self.total_passengers_arrived}, Accomp={self.total_companions_arrived}, Totale={self.total_people_arrived}")
    