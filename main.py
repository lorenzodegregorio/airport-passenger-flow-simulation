"""
Simulatore Aeroporto di Torino — versione a tempo continuo (event-based).

- Security lanes dinamiche (SecurityCheckpoint + SecurityProcess)
- Imbarco parallelo su più corsie per gate (BoardingProcess)
- Event scheduler (SimulationEngine) con FES
- Metriche + OutputAnalysis + Visualization
"""

import os
import sys
from datetime import datetime

# Esecuzione diretta dal repo
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
GENERATE_PLOTS = True  # set to False if you don't want PNGs


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
# Metrics logger for SimulationEngine
# ------------------------------------------------------
def make_metrics_logger(metrics, env, stats, landside_passengers, airside_passengers):
    """
    Called by the engine every full minute.
    Converts minutes (float) to datetime.time and forwards to metrics.log_time_step.
    """
    def logger(engine: SimulationEngine, log_time_min: float):
        current_time = TimeUtils.minutes_to_time(int(log_time_min))
        metrics.log_time_step(current_time, env, stats, landside_passengers, airside_passengers)
    return logger


#def estimate_security_wait_minutes(env, now_min: float) -> float:
#    """
#    Rough ETA of the security queue at *current* time.
#    Uses only current facility state and mean service time.
#    """
#    chk = env['security_checkpoint']
#    lanes = getattr(chk, 'active_lanes', chk.num_lanes)
#
#    if lanes <= 0:
#        return 9999.0  # security closed
#
#    q = len(chk.queue)
#    busy = len(chk.in_service)
#    free_now = max(0, lanes - busy)
#    effective_queue = max(0, q - free_now)
#
#    mean_service = SECURITY_MEAN_SERVICE_MIN
#    return (effective_queue / lanes) * mean_service


# ------------------------------------------------------
# Single-day simulation (continuous-time)
# ------------------------------------------------------
def run_simulation_test():
    # --- Setup RNG/Environment/Metrics ---
    rng = RNG(seed=42)
    env = create_simulation_environment()
    metrics = Metrics()

    # --- Flights & passenger schedule ---
    daily_flights = generate_daily_flight_schedule(TEST_DATE, rng)
    arrival_schedule = TimeUtils.generate_passenger_arrival_schedule(daily_flights, rng)

    # Processes
    arrival_proc = PassengerArrivalProcess(arrival_schedule, rng, env)
    security_proc = SecurityProcess(env, rng)
    boarding_proc = BoardingProcess(env, rng)

    # Runtime populations
    landside_passengers = []
    airside_passengers = []

    # Live counters
    stats = {
        'arrived': 0,
        'security_cleared': 0,
        'boarded': 0,
        'missed_flight': 0,
        'flights_departed': 0,
        'companions_departed': 0,
    }

    # --- Event-driven engine ---
    logger = make_metrics_logger(metrics, env, stats, landside_passengers, airside_passengers)
    engine = SimulationEngine(
        start_time=SIMULATION_START_TIME,
        end_time=SIMULATION_END_TIME,
        metrics_logger=logger
    )

    # --------------------------------------------------
    # EVENT HANDLERS
    # --------------------------------------------------

    # ARRIVAL - VERSIONE CORRETTA
    def handle_arrival(engine: SimulationEngine, event):
        passenger_data = event.payload
        p = arrival_proc.handle_arrival_event(engine, passenger_data, landside_passengers)
        stats['arrived'] += 1
        metrics.log_arrival(p)

        now_min = engine.time
        t_dep = TimeUtils.time_to_minutes(p.flight.departure_time)

        # Target personale (70 minuti o attributo del passeggero)
        target = getattr(p, "security_target_min", 70.0)
        target_deadline = t_dep - target
        hard_deadline = t_dep - LANDSIDE_FORCE_SECURITY_MIN

        # Schedula SOFT_GO_SECURITY (target personale)
        if target_deadline > now_min:
            engine.schedule(target_deadline, "SOFT_GO_SECURITY", p)

        # Schedula FORCE_GO_SECURITY (deadline rigida) - QUI ERA L'ERRORE
        if hard_deadline > now_min:
            # C'È ANCORA TEMPO: schedula l'evento futuro
            engine.schedule(hard_deadline, "FORCE_GO_SECURITY", p)
        else:
            # LA DEADLINE È GIA' PASSATA: manda SUBITO alla sicurezza
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

    # AGGIUNGI DOPO handle_arrival in main.py
    def handle_soft_go_security(engine: SimulationEngine, event):
        p = event.payload
        
        # Se non è più in landside, ignora
        if p.state not in ('landside', 'in_landside_activity'):
            return

        now_min = engine.time
        current_time = TimeUtils.minutes_to_time(int(now_min))
        t_dep = TimeUtils.time_to_minutes(p.flight.departure_time)
        time_to_dep = t_dep - now_min

        # Se siamo già vicini alla hard deadline, non fare nulla
        if time_to_dep <= LANDSIDE_FORCE_SECURITY_MIN:
            return

        # Se non sta facendo attività → manda in coda sicurezza
        if not p.current_activity:
            if p in landside_passengers:
                landside_passengers.remove(p)
                if p.has_companions and p.num_companions > 0:
                    stats['companions_departed'] += p.num_companions
                    metrics.log_companions_departed(p.num_companions)
                security_proc.add_to_queue(engine, p)
            return

        # Se sta facendo un'attività, lascia finire solo se manca poco
        act_end = TimeUtils.time_to_minutes(
            TimeUtils.add_minutes_to_time(p.activity_start_time, p.current_activity['duration'])
        )
        remaining = act_end - now_min

        if remaining <= 5:
            # Lascia finire (sarà gestito da END_LANDSIDE_ACTIVITY)
            return
        else:
            # Interrompi e manda in sicurezza
            p.complete_activity(current_time)
            if p in landside_passengers:
                landside_passengers.remove(p)
                if p.has_companions and p.num_companions > 0:
                    stats['companions_departed'] += p.num_companions
                    metrics.log_companions_departed(p.num_companions)
                security_proc.add_to_queue(engine, p)

    # REGISTRA l'handler (dopo engine.register_handler("ARRIVAL", handle_arrival))
    engine.register_handler("SOFT_GO_SECURITY", handle_soft_go_security)

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

        # decide whether to go to security now
        if (p.landside_visits_completed >= p.landside_visits_planned or 
            time_to_dep<=LANDSIDE_FORCE_SECURITY_MIN):
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
                # no more landside activities -> go to security anyway
                landside_passengers.remove(p)
                if p.has_companions and p.num_companions > 0:
                    stats['companions_departed'] += p.num_companions
                    metrics.log_companions_departed(p.num_companions)
                security_proc.add_to_queue(engine, p)

    engine.register_handler("END_LANDSIDE_ACTIVITY", handle_end_landside_activity)

    # FORCE_GO_SECURITY
    def handle_force_go_security(engine: SimulationEngine, event):
        p = event.payload

        if p.state in ('boarded', 'missed_flight', 'at_gate_queue', 'boarding'):
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

    # SECURITY_COMPLETE
    def handle_security_complete(engine: SimulationEngine, event):
        p = event.payload
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
            # already past the gate deadline -> go immediately to gate
            if p in airside_passengers:
                airside_passengers.remove(p)
            success = boarding_proc.passenger_arrives_at_gate(engine, p)
            if not success:
                miss_time = TimeUtils.minutes_to_time(int(engine.time))
                p.miss_flight(miss_time, reason="cannot_join_gate_queue_or_closed")
                stats['missed_flight'] += 1
                metrics.log_passenger_completion(p)
            return

        # If enough time, allow airside activities
        if time_to_dep > BOARDING_OPEN_MIN:
            act = p.get_next_airside_activity()
            if act:
                p.start_activity(act, f"air_{act}", current_time)
                dur = p.current_activity['duration']
                end_min = now_min + dur
                engine.schedule(end_min, "END_AIRSIDE_ACTIVITY", p)
        else:
            # too late: straight to gate
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

        # more than 40' left -> can start another airside activity
        if time_to_dep > BOARDING_OPEN_MIN:
            act = p.get_next_airside_activity()
            if act:
                p.start_activity(act, f"air_{act}", current_time)
                dur = p.current_activity['duration']
                end_min = now_min + dur
                engine.schedule(end_min, "END_AIRSIDE_ACTIVITY", p)
                return

        # otherwise must be at the gate
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

        # any passenger of this flight still in airport at departure -> lost
        dep_time = flight.departure_time
        for container in (landside_passengers, airside_passengers):
            for p in list(container):
                if (p.flight is flight and p.state not in ('boarded', 'missed_flight') and p.passenger_id not in {passenger.passenger_id for passenger in boarded + missed}):
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
    # Initial event scheduling
    # --------------------------------------------------

    # 1) All passenger arrivals
    arrival_proc.schedule_all_arrivals(engine)

    # 2) For each flight: gate open + departure
    for f in daily_flights:
        open_min = TimeUtils.time_to_minutes(f.boarding_open)
        dep_min = TimeUtils.time_to_minutes(f.departure_time)

        engine.schedule(open_min, "GATE_OPEN", f)
        engine.schedule(dep_min, "FLIGHT_DEPARTURE", f)

    # --------------------------------------------------
    # Run simulation
    # --------------------------------------------------
    engine.run()
    
    # ----------------- SUMMARY -----------------
    oa = OutputAnalysis(metrics)
    oa.run_analysis()
    oa.print_summary()

    if GENERATE_PLOTS:
        viz = Visualization(metrics, output_dir="analysis_results")
        viz.plot_security_queue_over_time("security_queue_over_time.png")
        viz.plot_airport_population("airport_population_over_time.png")
        viz.plot_retail_activity_over_time("retail_activity_over_time.png")
        #viz.plot_time_in_system_histogram("time_in_system_hist.png")


if __name__ == "__main__":
    run_simulation_test()
