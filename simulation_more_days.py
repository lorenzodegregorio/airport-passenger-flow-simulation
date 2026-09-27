"""
Simulatore Aeroporto di Torino — versione a tempo continuo (event-based)
per più giorni consecutivi (es. 7 giorni).

- Security lanes dinamiche (SecurityCheckpoint + SecurityProcess)
- Imbarco parallelo su più corsie per gate (BoardingProcess)
- Event scheduler (SimulationEngine) con FES
- Metriche + OutputAnalysis + Visualization aggregate su più giorni
"""

import os
import sys
from datetime import datetime, timedelta

sys.path.append(os.path.abspath(os.path.dirname(__file__)))

# ----------------- Config & Utils -----------------
from config.parameters import *
from config.rng import RNG
from config.flight_schedule import generate_daily_flight_schedule
from config.time_utils import TimeUtils

# ----------------- Entities & Resources -----------------
from entities.flight import Flight
from resources.gates import Gate
from resources.security import SecurityCheckpoint

# ----------------- Processes -----------------
from processes.arrival_process import PassengerArrivalProcess
from processes.security_process import SecurityProcess
from processes.boarding_process import BoardingProcess

# ----------------- Analysis -----------------
from analysis.metrics import Metrics
from analysis.output_analysis import OutputAnalysis
from analysis.visualization import Visualization

# ----------------- Simulation Engine -----------------
from simulation_engine import SimulationEngine


TEST_DATE = datetime(2024, 1, 1).date()
GENERATE_PLOTS = True


# ------------------------------------------------------
# Environment
# ------------------------------------------------------
def create_simulation_environment():
    env = {
        'security_checkpoint': SecurityCheckpoint(),
        'gates': {},
        'landside_facilities': {},
        'airside_facilities': {},
    }
    for i in range(1, NUM_GATES + 1):
        env['gates'][f"GATE{i:02d}"] = Gate(f"GATE{i:02d}")
    return env


# ------------------------------------------------------
# Metrics logger per SimulationEngine
# ------------------------------------------------------
def make_metrics_logger(metrics, env, stats, landside_passengers, airside_passengers, day_idx):
    """
    Funzione che il motore chiama ad ogni minuto intero.
    Converte i minuti in datetime.time e richiama metrics.log_time_step().

    Aggiunge anche il numero di giorno (day_idx) dentro metrics, se necessario.
    """
    def logger(engine: SimulationEngine, log_time_min: float):
        current_time = TimeUtils.minutes_to_time(int(log_time_min))
        # Puoi estendere metrics.log_time_step per salvare anche day_idx, se vuoi
        metrics.log_time_step(current_time, env, stats, landside_passengers, airside_passengers)
    return logger


# ------------------------------------------------------
# Simulazione multi–day (continuous-time)
# ------------------------------------------------------
def run_simulation_test(num_days: int = 7):
    rng = RNG(seed=42)
    metrics = Metrics()

    # Loop sui giorni
    for day_idx in range(num_days):
        current_date = TEST_DATE + timedelta(days=day_idx)
        print(f"\n=== SIMULATION DAY {day_idx+1} — Date {current_date} ===")

        # --- Environment & processes per quel giorno ---
        env = create_simulation_environment()
        daily_flights = generate_daily_flight_schedule(current_date, rng)
        arrival_schedule = TimeUtils.generate_passenger_arrival_schedule(daily_flights, rng)

        arrival_proc = PassengerArrivalProcess(arrival_schedule, rng, env)
        security_proc = SecurityProcess(env, rng)
        boarding_proc = BoardingProcess(env, rng)

        landside_passengers = []
        airside_passengers = []

        # Contatori live PER GIORNO (si resettano ogni giorno)
        stats = {
            'arrived': 0,
            'security_cleared': 0,
            'boarded': 0,
            'missed_flight': 0,
            'flights_departed': 0,
            'companions_departed': 0,
        }

        # --- Setup motore a eventi per il singolo giorno ---
        logger = make_metrics_logger(
            metrics, env, stats, landside_passengers, airside_passengers, day_idx
        )

        engine = SimulationEngine(
            start_time=SIMULATION_START_TIME,
            end_time=SIMULATION_END_TIME,
            metrics_logger=logger
        )

        # --------------------------------------------------
        # Handler EVENTI (stessa logica di main.py)
        # --------------------------------------------------

        # ARRIVAL
        def handle_arrival(engine: SimulationEngine, event):
            passenger_data = event.payload
            p = arrival_proc.handle_arrival_event(engine, passenger_data, landside_passengers)
            stats['arrived'] += 1
            metrics.log_arrival(p)

            now_min = engine.time
            t_dep = TimeUtils.time_to_minutes(p.flight.departure_time)

            # Target personale di arrivo alla sicurezza (se definito in Passenger)
            # altrimenti fallback ad es. 70'
            target = getattr(p, "security_target_min", 70.0)
            target_deadline = t_dep - target
            hard_deadline = t_dep - LANDSIDE_FORCE_SECURITY_MIN

            # Schedulo l'evento "soft" (target personale), se ha senso
            if target_deadline > now_min:
                engine.schedule(target_deadline, "SOFT_GO_SECURITY", p)

            # Schedulo SEMPRE l'hard deadline, se nel futuro
            if hard_deadline > now_min:
                engine.schedule(hard_deadline, "FORCE_GO_SECURITY", p)
            else:
                # troppo tardi, deve andare SUBITO a sicurezza
                if p in landside_passengers:
                    current_time = TimeUtils.minutes_to_time(int(now_min))
                    if p.current_activity:
                        p.complete_activity(current_time)
                    landside_passengers.remove(p)
                    if p.has_companions and p.num_companions > 0:
                        stats['companions_departed'] += p.num_companions
                        metrics.log_companions_departed(p.num_companions)
                    security_proc.add_to_queue(engine, p)

        engine.register_handler("ARRIVAL", handle_arrival)

        # SOFT_GO_SECURITY (gentle push verso la sicurezza)
        def handle_soft_go_security(engine: SimulationEngine, event):
            p = event.payload
            if p.state not in ('landside', 'in_landside_activity'):
                return

            now_min = engine.time
            current_time = TimeUtils.minutes_to_time(int(now_min))
            t_dep = TimeUtils.time_to_minutes(p.flight.departure_time)
            time_to_dep = t_dep - now_min

            # Se siamo già vicini alla hard deadline, non faccio nulla:
            if time_to_dep <= LANDSIDE_FORCE_SECURITY_MIN:
                return

            # Se non sta facendo nulla → lo mando in coda sicurezza
            if not p.current_activity:
                if p in landside_passengers:
                    landside_passengers.remove(p)
                    if p.has_companions and p.num_companions > 0:
                        stats['companions_departed'] += p.num_companions
                        metrics.log_companions_departed(p.num_companions)
                    security_proc.add_to_queue(engine, p)
                return

            # Se sta facendo un'attività, lascio finire SOLO se manca poco alla fine
            act_end = TimeUtils.time_to_minutes(
                TimeUtils.add_minutes_to_time(p.activity_start_time, p.current_activity['duration'])
            )
            remaining = act_end - now_min

            if remaining <= 5:
                # lo lascio finire, la END_LANDSIDE_ACTIVITY lo gestirà
                return
            else:
                # interrompo e mando in sicurezza
                p.complete_activity(current_time)
                if p in landside_passengers:
                    landside_passengers.remove(p)
                    if p.has_companions and p.num_companions > 0:
                        stats['companions_departed'] += p.num_companions
                        metrics.log_companions_departed(p.num_companions)
                    security_proc.add_to_queue(engine, p)

        engine.register_handler("SOFT_GO_SECURITY", handle_soft_go_security)

        # FORCE_GO_SECURITY (hard deadline)
        def handle_force_go_security(engine: SimulationEngine, event):
            p = event.payload

            # se è già oltre la sicurezza o ha già perso/imbarcato, non faccio nulla
            if p.state in ('boarded', 'missed_flight', 'at_gate_queue', 'boarding', 'airside'):
                return

            if p in landside_passengers:
                current_time = TimeUtils.minutes_to_time(int(engine.time))
                if p.current_activity:
                    p.complete_activity(current_time)
                landside_passengers.remove(p)

                if p.has_companions and p.num_companions > 0:
                    stats['companions_departed'] += p.num_companions
                    metrics.log_companions_departed(p.num_companions)

            security_proc.add_to_queue(engine, p)

        engine.register_handler("FORCE_GO_SECURITY", handle_force_go_security)

        # END_LANDSIDE_ACTIVITY
        def handle_end_landside_activity(engine: SimulationEngine, event):
            p = event.payload
            now_min = engine.time
            current_time = TimeUtils.minutes_to_time(int(now_min))

            if p.current_activity:
                p.complete_activity(current_time)

            if p not in landside_passengers:
                return

            t_dep = TimeUtils.time_to_minutes(p.flight.departure_time)
            time_to_dep = t_dep - now_min

            if (p.landside_visits_completed >= p.landside_visits_planned or
                    time_to_dep <= LANDSIDE_FORCE_SECURITY_MIN):
                landside_passengers.remove(p)
                if p.has_companions and p.num_companions > 0:
                    stats['companions_departed'] += p.num_companions
                    metrics.log_companions_departed(p.num_companions)
                security_proc.add_to_queue(engine, p)
            else:
                act = p.get_next_landside_activity()
                if act:
                    p.start_activity(act, f"land_{act}", current_time)
                    dur = p.current_activity['duration']
                    end_min = now_min + dur
                    engine.schedule(end_min, "END_LANDSIDE_ACTIVITY", p)
                else:
                    landside_passengers.remove(p)
                    if p.has_companions and p.num_companions > 0:
                        stats['companions_departed'] += p.num_companions
                        metrics.log_companions_departed(p.num_companions)
                    security_proc.add_to_queue(engine, p)

        engine.register_handler("END_LANDSIDE_ACTIVITY", handle_end_landside_activity)

        # SECURITY_COMPLETE
        def handle_security_complete(engine: SimulationEngine, event):
            p = event.payload
            if p.time_exited_security is not None:
                return p
            p = security_proc.handle_security_complete(engine, p)

            stats['security_cleared'] += 1
            metrics.log_security_cleared()

            if p in landside_passengers:
                landside_passengers.remove(p)
            if p not in airside_passengers:
                airside_passengers.append(p)

            now_min = engine.time
            current_time = TimeUtils.minutes_to_time(int(now_min))
            t_dep = TimeUtils.time_to_minutes(p.flight.departure_time)
            time_to_dep = t_dep - now_min

            force_gate_time = t_dep - FORCE_GATE_MIN
            if force_gate_time > now_min:
                engine.schedule(force_gate_time, "FORCE_GO_GATE", p)
            else:
                if p in airside_passengers:
                    airside_passengers.remove(p)
                success = boarding_proc.passenger_arrives_at_gate(engine, p)
                if not success:
                    miss_time = TimeUtils.minutes_to_time(int(engine.time))
                    p.miss_flight(miss_time, reason="cannot_join_gate_queue_or_closed")
                    stats['missed_flight'] += 1
                    metrics.log_passenger_completion(p)
                return

            if time_to_dep > BOARDING_OPEN_MIN:
                act = p.get_next_airside_activity()
                if act:
                    p.start_activity(act, f"air_{act}", current_time)
                    dur = p.current_activity['duration']
                    end_min = now_min + dur
                    engine.schedule(end_min, "END_AIRSIDE_ACTIVITY", p)
            else:
                if p in airside_passengers:
                    airside_passengers.remove(p)
                success = boarding_proc.passenger_arrives_at_gate(engine, p)
                if not success:
                    miss_time = TimeUtils.minutes_to_time(int(engine.time))
                    p.miss_flight(miss_time, reason="cannot_join_gate_queue_or_closed")
                    stats['missed_flight'] += 1
                    metrics.log_passenger_completion(p)

        engine.register_handler("SECURITY_COMPLETE", handle_security_complete)

        # END_AIRSIDE_ACTIVITY
        def handle_end_airside_activity(engine: SimulationEngine, event):
            p = event.payload
            now_min = engine.time
            current_time = TimeUtils.minutes_to_time(int(now_min))

            if p.current_activity:
                p.complete_activity(current_time)

            if p not in airside_passengers:
                return

            t_dep = TimeUtils.time_to_minutes(p.flight.departure_time)
            time_to_dep = t_dep - now_min

            if time_to_dep > BOARDING_OPEN_MIN:
                act = p.get_next_airside_activity()
                if act:
                    p.start_activity(act, f"air_{act}", current_time)
                    dur = p.current_activity['duration']
                    end_min = now_min + dur
                    engine.schedule(end_min, "END_AIRSIDE_ACTIVITY", p)
                    return

            if p in airside_passengers:
                airside_passengers.remove(p)

            success = boarding_proc.passenger_arrives_at_gate(engine, p)
            if not success:
                missed_time = TimeUtils.minutes_to_time(int(engine.time))
                p.miss_flight(missed_time, reason="cannot_join_gate_queue_or_closed")
                stats['missed_flight'] += 1
                metrics.log_passenger_completion(p)

        engine.register_handler("END_AIRSIDE_ACTIVITY", handle_end_airside_activity)

        # GATE_OPEN
        def handle_gate_open(engine: SimulationEngine, event):
            flight: Flight = event.payload
            boarding_proc.handle_gate_open(engine, flight)

        engine.register_handler("GATE_OPEN", handle_gate_open)

        # BOARDING_COMPLETE
        def handle_boarding_complete(engine: SimulationEngine, event):
            p = event.payload
            boarding_proc.handle_boarding_complete(engine, p)

            if p.state == 'boarded':
                stats['boarded'] += 1
            elif p.state == 'missed_flight':
                stats['missed_flight'] += 1

            metrics.log_passenger_completion(p)

        engine.register_handler("BOARDING_COMPLETE", handle_boarding_complete)

        # FORCE_GO_GATE
        def handle_force_go_gate(engine: SimulationEngine, event):
            p = event.payload
            if p.state in ('boarded', 'missed_flight'):
                return

            now_time = TimeUtils.minutes_to_time(int(engine.time))
            if p.current_activity:
                p.complete_activity(now_time)

            if p in airside_passengers:
                airside_passengers.remove(p)
                success = boarding_proc.passenger_arrives_at_gate(engine, p)
                if not success:
                    p.miss_flight(now_time, reason="cannot_join_gate_queue_or_closed")
                    stats['missed_flight'] += 1
                    metrics.log_passenger_completion(p)

        engine.register_handler("FORCE_GO_GATE", handle_force_go_gate)

        # FLIGHT_DEPARTURE
        def handle_flight_departure(engine: SimulationEngine, event):
            flight: Flight = event.payload
            boarded, missed = boarding_proc.handle_flight_departure(engine, flight)

            stats['boarded'] += len(boarded)
            stats['missed_flight'] += len(missed)

            for p in boarded + missed:
                metrics.log_passenger_completion(p)

            stats['flights_departed'] += 1
            metrics.log_flight_departure(flight)

            dep_time = flight.departure_time
            for container in (landside_passengers, airside_passengers):
                for p in list(container):
                    if p.flight is flight and p.state not in ('boarded', 'missed_flight'):
                        if p.current_location == 'landside':
                            reason = 'still_in_landside_at_departure'
                        elif p.current_location == 'airside':
                            reason = 'still_in_airside_at_departure'
                        else:
                            reason = 'still_in_airport_at_departure'

                        p.miss_flight(dep_time, reason=reason)
                        container.remove(p)
                        stats['missed_flight'] += 1
                        metrics.log_passenger_completion(p)

        engine.register_handler("FLIGHT_DEPARTURE", handle_flight_departure)

        # --------------------------------------------------
        # Schedulazione eventi iniziali del giorno
        # --------------------------------------------------
        arrival_proc.schedule_all_arrivals(engine)
        for f in daily_flights:
            open_min = TimeUtils.time_to_minutes(f.boarding_open)
            dep_min = TimeUtils.time_to_minutes(f.departure_time)
            engine.schedule(open_min, "GATE_OPEN", f)
            engine.schedule(dep_min, "FLIGHT_DEPARTURE", f)

        # --------------------------------------------------
        # Esecuzione simulazione del giorno
        # --------------------------------------------------
        engine.run()
        
        # Cleanup finale del giorno: chi è ancora in aeroporto perde il volo
        final_time = SIMULATION_END_TIME
        for container in (landside_passengers, airside_passengers):
            for p in list(container):
                if p.state not in ('boarded', 'missed_flight'):
                    p.miss_flight(final_time, reason="still_in_airport_at_end_of_sim")
                    stats['missed_flight'] += 1
                    metrics.log_passenger_completion(p)
                    container.remove(p)

        print(f"Day {day_idx+1} completed: boarded={stats['boarded']}, "
              f"missed={stats['missed_flight']}")
    
    # ----------------- FINE SETTIMANA -----------------
    oa = OutputAnalysis(metrics)
    oa.run_analysis()
    oa.print_summary()

    if GENERATE_PLOTS:
        viz = Visualization(metrics, output_dir="analysis_results")
        viz.plot_security_queue_more_days("security_queue_7_days.png")
        viz.plot_airport_population_more_days("airport_population_7_days.png")
        viz.plot_retail_activity_more_days("retail_activity_7_days.png")
        viz.plot_time_in_system_histogram("time_in_system_hist.png")
        viz.plot_flight_schedule_distribution("flight_schedule_distribution.png")
        viz.plot_boarding_by_flight("boarding_by_flights.png")
        viz.plot_time_cdf("time_cdfs.png")


if __name__ == "__main__":
    run_simulation_test(num_days=7)
