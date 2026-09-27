# processes/security_process.py
"""
Security Process for Turin Airport simulation (continuous-time version).

Gestisce:
- ingresso in coda al checkpoint
- avvio dei servizi sulle corsie disponibili
- completamento dei servizi (evento SECURITY_COMPLETE)

Tutte le decisioni avvengono in corrispondenza di eventi:
- quando qualcuno entra in coda
- quando un servizio si completa
"""

import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from config.time_utils import TimeUtils


class SecurityProcess:
    def __init__(self, environment, rng):
        """
        environment: dict che contiene 'security_checkpoint'
        rng: oggetto RNG con metodo security_processing_time()
        """
        self.env = environment
        self.rng = rng
        # SecurityCheckpoint (estende Facility)
        self.checkpoint = self.env['security_checkpoint']

    # ------------------------------------------------------------------
    # 1) Ingresso in coda (evento generato da logica landside/airside)
    # ------------------------------------------------------------------
    def add_to_queue(self, engine, passenger):
        """
        Chiamato quando un passeggero decide di andare alla sicurezza.
        Usa l'orologio del motore (engine.time) come current_time.

        - Logga ingresso in coda
        - Aggiorna il numero di corsie attive in base all'orario
        - Mette il passeggero in coda
        - Prova ad avviare immediatamente i servizi se ci sono corsie libere
        """
        now_min = engine.time
        current_time = TimeUtils.minutes_to_time(int(now_min))

        #check 1: se passeggero già passato la sicurezza non fare nulla
        if passenger.time_exited_security is not None:
            return
        #check 2: se passeggero è già in coda o in servizio non fare nulla
        ckeckpoint=self.checkpoint
        is_in_queue=any(p is passenger for p in ckeckpoint.queue)
        is_in_service= any(p[0] is passenger for p in ckeckpoint.in_service)

        if is_in_queue or is_in_service:
            return
        # Aggiorna corsie attive (in base a SECURITY_LANE_SCHEDULE)
        if hasattr(self.checkpoint, "update_active_lanes"):
            self.checkpoint.update_active_lanes(current_time)

        # Log ingresso in coda
        passenger.enter_security_queue(current_time)
        self.checkpoint.enqueue(passenger)

        # Prova a far partire i servizi
        self._try_start_services(engine, now_min)

    # ------------------------------------------------------------------
    # 2) Completamento servizio (evento SECURITY_COMPLETE)
    # ------------------------------------------------------------------
    def handle_security_complete(self, engine, passenger):
        """
        Event handler per SECURITY_COMPLETE.

        - Completa il servizio per il passeggero
        - Aggiorna lo stato del passeggero (ha passato la sicurezza)
        - Aggiorna eventualmente le corsie attive
        - Prova a far partire un nuovo servizio dalla coda

        Restituisce il passeggero (così il main/handler può spostarlo in airside
        e aggiornare le metriche).
        """
        now_min = engine.time
        current_time = TimeUtils.minutes_to_time(int(now_min))

        # Aggiorna corsie attive all'istante corrente
        if hasattr(self.checkpoint, "update_active_lanes"):
            self.checkpoint.update_active_lanes(current_time)

        # Termina il servizio in corso su questo passeggero
        # (finish_service rimuove il pax da in_service e libera la corsia)
        self.checkpoint.finish_service(passenger)
        passenger.complete_security_processing(current_time)

        # Prova a far partire un nuovo servizio per qualcuno in coda
        self._try_start_services(engine, now_min)

        return passenger

    # ------------------------------------------------------------------
    # 3) Logica interna: avvio servizi in parallelo
    # ------------------------------------------------------------------
    def _try_start_services(self, engine, now_min: float):
        """
        Finché ci sono corsie libere e passeggeri in coda, avvia nuovi servizi.

        Per ogni passeggero estratto dalla coda:
        - imposta lo stato di "in processing" alla sicurezza
        - campiona la durata del servizio
        - chiama checkpoint.start_service(...: registra (p, end_time))
        - schedula un evento SECURITY_COMPLETE al tempo di fine servizio
        """
        current_time = TimeUtils.minutes_to_time(int(now_min))

        # Aggiorna corsie attive all'inizio (in base all'orario corrente)
        if hasattr(self.checkpoint, "update_active_lanes"):
            self.checkpoint.update_active_lanes(current_time)

        while True:
            avail = self.checkpoint.get_available_lanes()
            if avail <= 0 or not self.checkpoint.queue:
                break

            # Estrai prossimo passeggero in coda
            p = self.checkpoint.dequeue()
            if not p:
                break

            # Timestamp inizio servizio lato passeggero
            p.start_security_processing(current_time)

            # Durata servizio in minuti (float)
            service_time = self.rng.security_processing_time()
            if service_time <= 0:
                # per sicurezza, non permettere durate nulle/negative
                service_time = 0.01

            # Facility memorizza il servizio (p, end_time)
            self.checkpoint.start_service(p, current_time, service_time=service_time)

            # Schedula evento SECURITY_COMPLETE esattamente a fine servizio
            end_min = now_min + service_time
            engine.schedule(end_min, "SECURITY_COMPLETE", p)
