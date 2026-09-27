"""
Flight schedule generation for Turin Airport simulation
"""

import numpy as np
from datetime import datetime, time, timedelta

from entities.flight import Flight
from .parameters import *
from .rng import RNG

def generate_daily_flight_schedule(date, rng=None):
    """
    Generate flight schedule for a given day
    Returns list of Flight objects
    """
    flights = []
    if rng is None:
        rng = RNG()
    
    # Genera i voli per ogni ora in base alla distribuzione esatta
    flight_hours = []
    for hour, probability in FLIGHT_SCHEDULE_DISTRIBUTION.items():
        expected_flights = probability * NUM_FLIGHTS_PER_DAY
        num_flights_this_hour = int(round(expected_flights))
        flight_hours.extend([hour] * num_flights_this_hour) 

    # Aggiusta per avere esattamente NUM_FLIGHTS_PER_DAY voli
    while len(flight_hours) > NUM_FLIGHTS_PER_DAY:
        max_prob_hour = max(set(flight_hours), key=lambda h: FLIGHT_SCHEDULE_DISTRIBUTION[h])
        flight_hours.remove(max_prob_hour)
    
    while len(flight_hours) < NUM_FLIGHTS_PER_DAY:
        min_prob_hour = min(FLIGHT_SCHEDULE_DISTRIBUTION.keys(), 
                           key=lambda h: FLIGHT_SCHEDULE_DISTRIBUTION[h])
        if min_prob_hour in flight_hours:
            flight_hours.append(min_prob_hour)
    
    rng.arrival_rng.shuffle(flight_hours)
    
    # Create gate assignments in advance
    gate_assignments = _create_gate_schedule(date, flight_hours, rng)
    
    # PRIMO: Crea tutti i voli con capacità massima (200 posti)
    for i, (hour, gate_id) in enumerate(zip(flight_hours, gate_assignments)):
        minute = rng.arrival_rng.integers(0, 60)
        jitter = rng.arrival_rng.integers(-DEPARTURE_MINUTE_JITTER, DEPARTURE_MINUTE_JITTER + 1)
        minute = max(0, min(59, minute + jitter))
        departure_time = time(hour, minute)
        
        flight = Flight(
            flight_id=f"FL{date.strftime('%Y%m%d')}{i:03d}",
            departure_time=departure_time,
            gate_id=gate_id,
            date=date,
            seats=FLIGHT_CAPACITY,  # 200 posti fisici
            num_passengers=0  # Sarà assegnato dopo
        )
        
        dep_dt = datetime.combine(date, departure_time)
        open_dt = dep_dt - timedelta(minutes=BOARDING_OPEN_MIN)
        close_dt = dep_dt - timedelta(minutes=BOARDING_CLOSE_MIN)
        flight.boarding_open = open_dt.time()
        flight.boarding_close = close_dt.time()
        
        flights.append(flight)
    
    flights.sort(key=lambda x: x.departure_time)
    
    # SECONDO: Assegna un numero casuale di passeggeri (biglietti venduti) per ogni volo
    # Calcola il numero effettivo di passeggeri da generare
    num_flights = len(flights)
    max_capacity = FLIGHT_CAPACITY * num_flights  # Massimo teorico
    
    # Il numero effettivo è il minimo tra DAILY_PASSENGERS e la capacità massima
    target_passengers = min(DAILY_PASSENGERS, max_capacity)
    
    # Distribuisci i passeggeri in modo casuale tra i voli
    pax_counts = [0] * num_flights
    total_assigned = 0
    
    # Se effective_passengers è maggiore di 0, distribuiscili
    # Se target_passengers è maggiore di 0, distribuiscili
    if target_passengers > 0:
        # Prima assegna almeno 1 passeggero a ogni volo (per evitare voli vuoti)
        passengers_to_distribute = target_passengers
        for i in range(num_flights):
            if passengers_to_distribute > 0:
                pax_counts[i] += 1
                total_assigned += 1
                passengers_to_distribute -= 1
        
        # Ora distribuisci i restanti in modo casuale
        while passengers_to_distribute > 0:
            # Trova voli che non hanno raggiunto la capacità
            available_indices = [i for i in range(num_flights) if pax_counts[i] < FLIGHT_CAPACITY]
            
            if not available_indices:
                # Se tutti i voli sono pieni, assegna a un volo casuale (anche se supera la capacità)
                chosen_idx = rng.arrival_rng.integers(0, num_flights)
            else:
                # Scegli un volo casuale tra quelli disponibili
                chosen_idx = rng.arrival_rng.choice(available_indices)
            
            pax_counts[chosen_idx] += 1
            total_assigned += 1
            passengers_to_distribute -= 1
    
    # Assegna i passeggeri ai voli
    for i, (flight, n_pax) in enumerate(zip(flights, pax_counts)):
        flight.num_passengers = n_pax      
    # Verifica che il totale assegnato corrisponda a effective_passengers
    if total_assigned != target_passengers:
        print(f"\nATTENZIONE: Totale assegnato ({total_assigned}) non corrisponde a effective_passengers ({target_passengers})")
        # Correzione: aggiusta l'ultimo volo
        diff = target_passengers - total_assigned
        if diff>0:
            available_flights=[i for i, count in enumerate(pax_counts) if count<FLIGHT_CAPACITY]
            if not available_flights:
                avg_additional=diff//num_flights
                remainder=diff%num_flights
                
                for i in range (num_flights):
                    pax_counts[i]+=avg_additional
                    if i < remainder:
                        pax_counts[i]+=1
            else:
                avg_additional=diff//len(available_flights)
                remainder=diff%len(available_flights)
                for idx in available_flights:
                    pax_counts[idx]+=avg_additional
                for i in range(remainder):
                    if i<len(available_flights):
                        pax_counts[available_flights[i]]+=1
        for i,(flight, n_pax) in enumerate (zip(flights, pax_counts)):
            flights.num_passengers = n_pax
        total_assigned = sum(pax_counts)
        print(f"  Corretto: nuovo totale {total_assigned}")
    
    return flights

def _create_gate_schedule(date, flight_hours, rng):
    """Create a gate schedule that avoids conflicts"""
    # Group flights by hour to balance gate usage
    hourly_flights = {}
    for hour in flight_hours:
        hourly_flights[hour] = hourly_flights.get(hour, 0) + 1
    
    # Assign gates sequentially within each hour
    gate_assignments = []
    gate_counter = 1
    
    # Sort hours to process in chronological order
    sorted_hours = sorted(set(flight_hours))
    
    for hour in sorted_hours:
        num_flights_this_hour = hourly_flights[hour]
        # Assign gates for this hour (can reuse gates from previous hours if no overlap)
        available_gates = list(range(1, NUM_GATES + 1))
        
        # Shuffle to randomize gate assignment
        rng.arrival_rng.shuffle(available_gates)
        
        for _ in range(num_flights_this_hour):
            if available_gates:
                gate_id = available_gates.pop()
                gate_assignments.append(f"GATE{gate_id:02d}")
            else:
                # If no gates available in this hour, use the next sequential gate
                gate_id = gate_counter
                gate_assignments.append(f"GATE{gate_id:02d}")
                gate_counter = (gate_counter % NUM_GATES) + 1
    
    # Shuffle the final assignments to match the original flight order
    rng.arrival_rng.shuffle(gate_assignments)
    return gate_assignments

def get_flight_schedule_for_period(start_date, num_days, rng=None):
    """
    Generate flight schedule for multiple days
    Returns dictionary: {date: [list_of_flights]}
    """
    schedule = {}
    current_date = start_date
    
    # CORREZIONE: Definisci rng se non fornito
    if rng is None:
        rng = RNG()
    
    for day in range(num_days):
        schedule[current_date] = generate_daily_flight_schedule(current_date, rng)
        current_date += timedelta(days=1)
    
    return schedule