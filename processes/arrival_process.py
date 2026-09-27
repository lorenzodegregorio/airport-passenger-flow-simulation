# processes/arrival_process.py
"""
Arrival Process for Turin Airport simulation (continuous-time version).
- Schedula gli eventi di ARRIVAL nella FES
- Crea l'oggetto Passenger quando scatta un ARRIVAL
- Assegna la prima attività (landsid o security) e, se serve,
  schedula la fine della prima attività.
"""

import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from config.time_utils import TimeUtils
from entities.passenger import create_passenger_from_schedule

class PassengerArrivalProcess:
    def __init__(self, arrival_schedule, rng, environment):
        """
        arrival_schedule: lista di dict con almeno 'arrival_time' e info volo
        rng: generatore random
        environment: dizionario env (security, gates, ecc.) – per ora non usato qui
        """
        self.arrival_schedule = arrival_schedule
        self.rng = rng
        self.environment = environment
        self.total_passengers_arrived = 0

    # ------------------------------------------------------------------
    # 1) SCHEDULAZIONE DEGLI ARRIVI NELLA FES
    # ------------------------------------------------------------------
    def schedule_all_arrivals(self, engine):
        """
        Inserisce nella Future Event Set tutti gli eventi di ARRIVAL
        relativi alla arrival_schedule.
        """
        for entry in self.arrival_schedule:
            arr_time = entry['arrival_time']
            t_min = TimeUtils.time_to_minutes(arr_time)
            # payload = entry (i dati grezzi che serviranno per creare il Passenger)
            engine.schedule(t_min, "ARRIVAL", entry)
    # ------------------------------------------------------------------
    # 2) HANDLER DELL’EVENTO ARRIVAL
    # ------------------------------------------------------------------
    def handle_arrival_event(self, engine, passenger_data, landside_passengers):
        """
        Chiamato dal handler globale quando scatta un evento ARRIVAL.
        - Crea il Passenger
        - Assegna lo stato iniziale (landsid o heading_to_security)
        - Se parte subito un’attività landside, schedula anche l’evento END_LANDSIDE_ACTIVITY.
        - Inserisce il passeggero nella lista landside_passengers.
        Restituisce il Passenger creato.
        """
        # 3) crea l'oggetto Passenger
        passenger = create_passenger_from_schedule(passenger_data, self.rng)
        self.total_passengers_arrived += 1

        # 4) routing iniziale: landside vs direttamente sicurezza
        self._assign_initial_activity(passenger)

        # lo mettiamo in landside (di default nasce lì)
        landside_passengers.append(passenger)

        # se ha iniziato subito un'attività landside, schedula la fine attività
        if passenger.current_activity and passenger.current_location == "landside":
            start_t = passenger.current_activity['start_time']   # datetime.time
            dur = passenger.current_activity['duration']         # minuti
            start_min = TimeUtils.time_to_minutes(start_t)
            end_min = start_min + dur

            # evento che dirà "questa attività landside è finita"
            engine.schedule(end_min, "END_LANDSIDE_ACTIVITY", passenger)

        return passenger

    # ------------------------------------------------------------------
    # 3) Routing iniziale (come prima, ma pensato per CT)
    # ------------------------------------------------------------------
    def _assign_initial_activity(self, passenger):
        """
        Decide se il passeggero, al momento dell'arrivo, inizia un’attività landside
        o va direttamente verso la sicurezza.
        """
        # Usa la stessa logica che avevi prima: guarda quanto manca al volo
        must_go_security = passenger.should_go_to_security(passenger.arrival_time)

        if passenger.landside_visits_planned > 0 and not must_go_security:
            # farà almeno un'attività landside
            passenger.state = 'landside'
            passenger.current_location = 'landside'

            activity = passenger.get_next_landside_activity()
            if activity:
                # Come nel tuo codice precedente: facility_id "finto" per ora
                facility_id = f"land_{activity}"
                passenger.start_activity(activity, facility_id, passenger.arrival_time)
        else:
            # nessuna visita landside: si dirige verso la sicurezza
            passenger.state = 'heading_to_security'
            passenger.current_location = 'landside'   # fisicamente è ancora in landside
            # non lo mando ancora in coda qui: decideremo nel resto della logica (security process)
