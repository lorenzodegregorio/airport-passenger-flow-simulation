# processes/boarding_process.py
"""
Boarding process (continuous-time version).

Gestisce:
- arrivo passeggeri al gate
- inizio servizi di boarding (più corsie per gate)
- completamento servizi (eventi BOARDING_COMPLETE)
- apertura gate (GATE_OPEN)
- partenza volo (FLIGHT_DEPARTURE)

Non c'è più un loop per-minuto: tutto avviene tramite eventi schedulati
nel SimulationEngine.
"""

import sys
import os
from datetime import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from config.time_utils import TimeUtils
from entities.passenger import Passenger
from entities.flight import Flight
from resources.gates import Gate


class BoardingProcess:
    def __init__(self, environment, rng):
        """
        environment: dict con almeno 'gates'
        rng: oggetto RNG con metodo boarding_time()
        """
        self.env = environment
        self.rng = rng
        self.gates: dict[str, Gate] = self.env['gates']
        self._missed_buffer = 0  # contatore interno per debug/metriche opzionali

    # ------------------------------------------------------------------
    # 1) Arrivo passeggero al gate (chiamato da handler/evento esterno)
    # ------------------------------------------------------------------
    def passenger_arrives_at_gate(self, engine, passenger: Passenger) -> bool:
        """
        Chiamato quando un passeggero decide di andare al gate.
        Usa l'orologio del motore (engine.time) come current_time.

        - Se arriva dopo la chiusura del gate -> missed.
        - Se il volo è già partito -> missed.
        - Altrimenti entra in coda e, se possibile, inizia subito un servizio
          (schedulando BOARDING_COMPLETE).
        """
        now_min = engine.time
        current_time = TimeUtils.minutes_to_time(int(now_min))
        #check: se passeggero imbarcato o ha perso volo, non fare nulla
        if passenger.state in ('boraded', 'missed_flight'):
            return False
        flight: Flight = passenger.flight
        gate: Gate = self.gates.get(flight.gate_id)

        if gate is None:
            passenger.miss_flight(current_time, reason="no_gate_assigned")
            self._missed_buffer += 1
            return False

        passenger.time_arrived_at_gate = current_time

        cur_min = now_min
        open_min = TimeUtils.time_to_minutes(flight.boarding_open)
        close_min = TimeUtils.time_to_minutes(flight.boarding_close)
         # volo già partito / chiuso
        if flight.state in ('departed',):
            passenger.miss_flight(current_time, reason='arrived_after_departure')
            self._missed_buffer += 1
            return False

        if cur_min > close_min:
            passenger.miss_flight(current_time, reason='arrived_after_gate_closure')
            self._missed_buffer += 1
            return False
        #se il volo non può più accettare passeggeri (posti esauritI)
        if not flight.can_accept_passenger():
            passenger.miss_flight(current_time, reason='flight_already_full')
            return False
        #check: se il passeggero è gia in coda o inservisio, non aggiungerlo di nuovo
        is_in_queue=any(p is passenger for p in gate.queue)
        is_in_service=any(p[0] is passenger for p in gate.in_service)
        if is_in_queue or is_in_service:
            return False
        # Accettiamo in coda anche se il gate non è ancora in "boarding":
        # il servizio partirà quando si aprirà il gate.
        passenger.state = 'at_gate_queue'
        passenger.current_location = 'airside'
        #check: se il volo è pieno, non entrare in coda
        if not flight.can_board():
            passenger.miss_flight(current_time, reason='flight_already_full_on_arrival')
            self._missed_buffer+=1
            return False
        gate.enqueue(passenger)

        # Se il gate è già in boarding, prova a far partire subito il servizio
        if gate.assigned_flight is flight and gate.active_lanes > 0:
            self._try_start_boarding(engine, gate, flight, now_min)

        return True

    # ------------------------------------------------------------------
    # 2) Apertura gate (evento GATE_OPEN)
    # ------------------------------------------------------------------
    def handle_gate_open(self, engine, flight: Flight):
        """
        Event handler per GATE_OPEN.
        - Assegna il volo al gate (se non già assegnato)
        - Imposta lo stato di boarding
        - Avvia subito il boarding per i passeggeri eventualmente già in coda
        """
        now_min = engine.time
        current_time = TimeUtils.minutes_to_time(int(now_min))

        gate: Gate = self.gates.get(flight.gate_id)
        if gate is None:
            return

        if gate.assigned_flight is None:
            gate.assign_flight(flight, current_time)

        # Attiva le corsie e cambia lo stato del volo
        gate.start_boarding(current_time)  # questo di solito setta active_lanes = num_lanes
        flight.start_boarding(current_time)

        # Se ci sono già persone in coda, comincia subito
        self._try_start_boarding(engine, gate, flight, now_min)

    # ------------------------------------------------------------------
    # 3) Completamento di un servizio di boarding (evento BOARDING_COMPLETE)
    # ------------------------------------------------------------------
    def handle_boarding_complete(self, engine, passenger: Passenger):
        """
        Event handler per BOARDING_COMPLETE.

        - Libera la corsia al gate
        - Se c'è posto sul volo -> passenger.boarded, flight.add_boarded_passenger()
        - Se non c'è posto -> passenger missed (over_capacity_at_departure)
        - Tenta di far partire un nuovo servizio dalla coda
        """
        now_min = engine.time
        current_time = TimeUtils.minutes_to_time(int(now_min))
        #check: se passeggero già imbarcato o ha perso volo, non fare nulla
        if passenger.state in ('boarded', 'missed_flight'):
            return

        flight: Flight = passenger.flight
        gate: Gate = self.gates.get(flight.gate_id)
        if gate is None:
            # Gate non più esistente / sgomberato: consideriamo perso
            passenger.miss_flight(current_time, reason="gate_not_found_on_completion")
            self._missed_buffer += 1
            return

        if gate.assigned_flight is not flight:
            # Il gate è stato riassegnato o il volo è già finito: consideriamo perso
            passenger.miss_flight(current_time, reason="flight_not_assigned_on_completion")
            self._missed_buffer += 1
            return

        # Finisci il servizio su questo passeggero
        gate.finish_service(passenger)

        if flight.can_accept_passenger():
            passenger.complete_boarding(current_time)
            flight.add_boarded_passenger()
        else:
            passenger.miss_flight(current_time, reason="over_capacity_at_departure")
            self._missed_buffer += 1

        # Prova a far partire un nuovo servizio
        self._try_start_boarding(engine, gate, flight, now_min)

    # ------------------------------------------------------------------
    # 4) Partenza del volo (evento FLIGHT_DEPARTURE)
    # ------------------------------------------------------------------
    def handle_flight_departure(self, engine, flight: Flight):
        """
        Event handler per FLIGHT_DEPARTURE.

        - Forza lo smaltimento di tutti i passeggeri:
          * chi è in servizio viene completato istantaneamente
          * chi è in coda viene imbarcato fino a saturazione, gli altri sono missed
        - Chiude il gate e aggiorna lo stato del volo.
        """
        now_min = engine.time
        current_time = TimeUtils.minutes_to_time(int(now_min))

        gate: Gate = self.gates.get(flight.gate_id)
        if gate is None:
            # Se per qualche motivo il gate non c'è più, consideriamo già partito.
            flight.depart(current_time)
            return [], []

        boarded, missed = self._force_finish_boarding_for_flight(gate, flight, current_time)
        self._missed_buffer += len(missed)

        # Chiudi boarding e libera gate
        gate.end_boarding(current_time)
        gate.clear_gate(current_time)  # questo di solito chiama flight.depart(current_time)

        return boarded, missed

    # ------------------------------------------------------------------
    # 5) Logica interna: avvio servizi
    # ------------------------------------------------------------------
    def _try_start_boarding(self, engine, gate: Gate, flight: Flight, now_min: float):
        """
        Finché ci sono corsie libere, persone in coda e posti sul volo,
        preleva passeggeri dalla coda, li mette in servizio e schedula
        gli eventi BOARDING_COMPLETE.
        """
        current_time = TimeUtils.minutes_to_time(int(now_min))
        available_seats=flight.seats-flight.passengers_boarded
        remainig_passengers=flight.num_passengers-flight.passengers_boarded
        can_board=min(available_seats, remainig_passengers)

        while (gate.get_available_lanes() > 0 and len(gate.queue) > 0 and can_board>0) :
            p = gate.dequeue()
            if not p:
                continue
            if p.state in ('boarded', 'missed_flight'):
                continue
            if p.flight.flight_id != flight.flight_id:
                p.miss_flight(current_time, reason='wrond_flight_gate')
                continue

            service_time = self.rng.boarding_time()  # in minuti
            p.start_boarding(current_time)
            # Il gate memorizza internamente end_time come time; noi usiamo anche minuti
            gate.start_service(p, current_time, service_time=service_time)

            end_min = now_min + service_time
            # schedula l'evento di completamento
            engine.schedule(end_min, "BOARDING_COMPLETE", p)
            can_board-=1

    # ------------------------------------------------------------------
    # 6) Logica interna: smaltimento forzato a partenza volo
    # ------------------------------------------------------------------
    def _force_finish_boarding_for_flight(self, gate: Gate, flight: Flight, current_time: time):
        """
        Forza lo smaltimento completo della coda e dei servizi in corso al gate.
        Usa la capacità residua del volo:
        - chi è in servizio viene completato (boarded se c'è posto, altrimenti missed)
        - chi è in coda idem
        """
        boarded = []
        missed = []

        # 1) Chi è già in servizio viene completato istantaneamente
        #    gate.in_service è tipicamente una lista di (Passenger, end_time)
        for (p, end_time) in list(gate.in_service):
            gate.finish_service(p)
            #chek: se il passeggero è già stato imbarcato o ha perso il volo, salta
            if p.state in ('boraded', 'missed_flight'):
                continue
            if flight.can_accept_passenger():
                p.complete_boarding(current_time)
                flight.add_boarded_passenger()
                boarded.append(p)
            else:
                p.miss_flight(current_time, reason="over_capacity_at_departure")
                missed.append(p)

        gate.in_service.clear()

        # 2) Tutta la coda residua viene smaltita istantaneamente
        while len(gate.queue) > 0:
            p = gate.dequeue()
            #chek: se il passeggero è già stato imbarcato o ha perso il volo salta
            if p.state in ('boraded', 'missed_flight'):
                continue
            if flight.can_accept_passenger():
                p.start_boarding(current_time)
                p.complete_boarding(current_time)
                flight.add_boarded_passenger()
                boarded.append(p)
            else:
                p.miss_flight(current_time, reason="over_capacity_at_departure")
                missed.append(p)

        return boarded, missed

    # ------------------------------------------------------------------
    # 7) Utilità
    # ------------------------------------------------------------------
    def pop_missed_count(self):
        n = self._missed_buffer
        self._missed_buffer = 0
        return n
