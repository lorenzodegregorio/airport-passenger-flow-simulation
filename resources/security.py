# resources/security.py
"""
Risorsa Security Checkpoint.
Eredita da Facility e gestisce corsie attive dinamiche tramite schedule.
"""

import sys
import os
from datetime import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from entities.facility import Facility
from config.parameters import *
from config.time_utils import TimeUtils

class SecurityCheckpoint(Facility):
    def __init__(self, facility_id="SECURITY_MAIN"):
        super().__init__(
            facility_id=facility_id,
            facility_type='security',
            area='land',
            num_lanes=SECURITY_LANES,       # massimo fisico
            capacity=SECURITY_QUEUE_CAPACITY
        )
        # parti con 0 corsie (verranno attivate dallo schedule)
        # PRIMA: self.set_active_lanes = 0  (sbagliato: attributo mai usato)
        # ORA: usiamo l'attributo vero usato da Facility
        self.active_lanes = 0

    def update_active_lanes(self, current_time):
        """
        Imposta le corsie attive in base allo schedule (ordinato per orario).
        Se il tuo SECURITY_LANE_SCHEDULE è un dict, ordiniamo per sicurezza.
        """
        cur_min = TimeUtils.time_to_minutes(current_time)
        active_count = 0
        for sched_time, count in sorted(
            SECURITY_LANE_SCHEDULE.items(),
            key=lambda kv: TimeUtils.time_to_minutes(kv[0])
        ):
            if TimeUtils.time_to_minutes(sched_time) <= cur_min:
                active_count = count
            else:
                break

        # PRIMA: self.set_active_lanes = active_count  (sbagliato)
        # ORA: settiamo l'attributo effettivamente usato dalle code/servizi,
        # clampato al massimo fisico num_lanes per sicurezza.
        self.active_lanes = min(active_count, self.num_lanes)

    def __repr__(self):
        return (
            f"SecurityCheckpoint({self.facility_id}, "
            f"Corsie Attive: {self.active_lanes}/{self.num_lanes}, "
            f"In Servizio: {len(self.in_service)}, In Coda: {len(self.queue)})"
        )
