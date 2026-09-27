# entities/facility.py
"""
Entità Facility (pulita) per la simulazione.
Gestisce code e risorse multi-corsia basandosi su orari di fine evento.
"""

import sys
import os
from datetime import time, timedelta
from collections import deque

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from config.parameters import FACILITY_CAPACITIES
from config.time_utils import TimeUtils

class Facility:
    """
    Rappresenta una risorsa multi-corsia (es. Sicurezza, Gate)
    che gestisce una coda e processi con una durata.
    """
    
    def __init__(self, facility_id, facility_type, area, num_lanes=1, capacity=None):
        self.facility_id = facility_id
        self.facility_type = facility_type
        self.area = area
        self.num_lanes = num_lanes  # Numero MASSIMO di corsie/slot
        self.active_lanes = num_lanes # Numero di corsie/slot attualmente aperti
        
        if capacity is None:
            capacity_key = f"{area}_side_{facility_type}"
            self.capacity = FACILITY_CAPACITIES.get(capacity_key, float('inf'))
        else:
            self.capacity = capacity
            
        self.queue = deque()
        # self.in_service memorizza (entità, orario_di_fine)
        self.in_service = []
        self.is_gate = (facility_type == 'gate')
        
        # Statistiche
        self.utilization_time = 0.0
        self.max_queue_length = 0
    
    def __repr__(self):
        return (f"Facility({self.facility_id}, Type: {self.facility_type}, "
                f"Lanes: {len(self.in_service)}/{self.active_lanes}, Queue: {len(self.queue)})")

    def enqueue(self, entity):
        """Aggiunge un'entità in coda; ritorna False se la capacità totale è piena."""
        # Controllo sulla capacità totale (per negozi, non per code di sicurezza)
        if (len(self.queue) + len(self.in_service)) >= self.capacity:
             return False
        
        self.queue.append(entity)
        self.max_queue_length = max(self.max_queue_length, len(self.queue))
        return True

    def dequeue(self):
        """Estrae dalla coda."""
        if len(self.queue) > 0:
            return self.queue.popleft()
        return None

    def start_service(self, entity, start_time, service_time):
        """Avvia un servizio e registra l’istante di fine."""
        if self.get_available_lanes() <= 0:
             return False 
            
        end_time = TimeUtils.add_minutes_to_time(start_time, service_time)
        self.in_service.append((entity, end_time))
        # Log utilizzo (opzionale ma utile)
        self.utilization_time += service_time
        return end_time

    def finish_service(self, entity):
        """Rimuove l’entità dalla lista dei servizi in corso."""
        found = False
        for item in self.in_service:
            if item[0] is entity:
                self.in_service.remove(item)
                found = True
                break
        return found
        
    def get_available_lanes(self):
        """Restituisce il numero di corsie o risorse libere."""
        # Usa active_lanes (corsie/slot attivi)
        return max(0, self.active_lanes - len(self.in_service))
    
    def _time_reached(self, end_time, current_time):
        """True se l'istante corrente ha superato/uguale a end_time."""
        return TimeUtils.time_to_minutes(current_time) >= TimeUtils.time_to_minutes(end_time)

    def get_utilization_rate(self):
        """Calcola la percentuale di utilizzo delle corsie attive"""
        if self.active_lanes == 0:
            return 0.0
        return (len(self.in_service) / self.active_lanes) * 100.0

    def get_queue_wait_estimate(self, current_time, service_time_estimate):
        """Stima il tempo di attesa in coda in minuti"""
        if self.get_available_lanes() > 0:
            return 0  # Nessuna attesa se ci sono corsie libere
        
        people_ahead = len(self.queue)
        estimated_wait = (people_ahead / self.active_lanes) * service_time_estimate
        return estimated_wait
    
