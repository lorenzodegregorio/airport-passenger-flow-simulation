# resources/shops.py
"""
Shop Resource for Turin Airport simulation.
Extends Facility to represent commercial areas (shops, bars, restaurants).
"""

import sys
import os
from datetime import time
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from entities.facility import Facility
from config.parameters import FACILITY_CAPACITIES 

class Shop(Facility):
    """
    Rappresenta un'area commerciale (Shop, Bar, o Ristorante).
    È una Facility con una capacità definita in parameters.py e una singola corsia/cassa (num_lanes=1).
    """
    
    def __init__(self, facility_id, facility_type, area):
        # facility_type può essere 'shop', 'bar', 'restaurant'
        # area può essere 'land' o 'air'
        
        super().__init__(
            facility_id=facility_id, 
            facility_type=facility_type, 
            area=area, 
            num_lanes=1 # Assumiamo 1 "servizio" (cassa/entrata) per 1 coda
        )
        
    def __repr__(self):
        return (f"Shop({self.facility_id}, Tipo: {self.facility_type}, Area: {self.area}, "
                f"Capacità: {self.capacity}, In Servizio: {len(self.in_service)}, Coda: {len(self.queue)})")

