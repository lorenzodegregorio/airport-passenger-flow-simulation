"""
Calcola le statistiche di output aggregate (KPI)
basandosi sui dati grezzi raccolti dalla classe Metrics.
"""

import sys
import os
import numpy as np
from datetime import time
from typing import Dict, List, Any, Optional

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from analysis.metrics import Metrics
from config.time_utils import TimeUtils

class OutputAnalysis:
    """ Esegue calcoli statistici sui dati grezzi di un oggetto Metrics."""
    
    def __init__(self, metrics: Metrics):
        if not isinstance(metrics, Metrics):
            raise TypeError("Input deve essere un oggetto di tipo Metrics")
            
        self.metrics = metrics
        self.results: Dict[str, Any] = {} # Dizionario per contenere i risultati finali

    def run_analysis(self) -> Optional[Dict[str, Any]]:
        """Esegue tutte le analisi e popola self.results"""
        # CORREZIONE: Verifica più robusta della presenza di dati
        has_passenger_data = (self.metrics.completed_passengers and 
                             len(self.metrics.completed_passengers) > 0)
        has_queue_data = (self.metrics.security_queue_log and 
                         len(self.metrics.security_queue_log) > 0)
        
        if not has_passenger_data and not has_queue_data:
            print("Warning:  Metrics empty. ")
            return None
            
        self.calculate_passenger_stats()
        self.calculate_queue_stats()
        self.calculate_global_counts()
        self.calculate_missed_reasons()
        self.calculate_retail_stats()
        self.calculate_system_throughput()
        
        return self.results

    def calculate_passenger_stats(self):
        """Calcola le statistiche basate sui singoli passeggeri (solo imbarcati)."""
        # CORREZIONE: Filtra SOLO i passeggeri che hanno completato il processo
        completed_passengers = [p for p in self.metrics.completed_passengers 
                              if p.get('state') in ['boarded', 'missed_flight']]
        
        boarded_passengers = [p for p in completed_passengers 
                            if p.get('state') == 'boarded']
        missed_passengers = [p for p in completed_passengers 
                           if p.get('state') == 'missed_flight']

        # CORREZIONE: Calcola statistiche per TUTTI i passeggeri completati
        self._calculate_time_stats(completed_passengers, 'all_completed')
        self._calculate_time_stats(boarded_passengers, 'boarded')
        self._calculate_time_stats(missed_passengers, 'missed')

    def _calculate_time_stats(self, passengers: List[Dict], prefix: str):
        """Helper per calcolare statistiche temporali per un gruppo di passeggeri"""
        security_times = []
        total_times = []
        
        for p in passengers:
            # CORREZIONE: Gestione più robusta dei valori mancanti
            sec_time = p.get('security_time')
            if sec_time is not None and sec_time >= 0:  # >=0 per includere 0
                security_times.append(sec_time)
            
            total_time = p.get('total_time')
            if total_time is not None and total_time >= 0:
                total_times.append(total_time)

        # Statistiche sicurezza
        if security_times:
            self.results[f'{prefix}_avg_security_time'] = float(np.mean(security_times))
            self.results[f'{prefix}_p95_security_time'] = float(np.percentile(security_times, 95))
            self.results[f'{prefix}_max_security_time'] = float(np.max(security_times))
            self.results[f'{prefix}_min_security_time'] = float(np.min(security_times))
        else:
            self.results[f'{prefix}_avg_security_time'] = 0.0
            self.results[f'{prefix}_p95_security_time'] = 0.0
            self.results[f'{prefix}_max_security_time'] = 0.0
            self.results[f'{prefix}_min_security_time'] = 0.0

        # Statistiche tempo totale
        if total_times:
            self.results[f'{prefix}_avg_total_time'] = float(np.mean(total_times))
            self.results[f'{prefix}_p95_total_time'] = float(np.percentile(total_times, 95))
            self.results[f'{prefix}_max_total_time'] = float(np.max(total_times))
            self.results[f'{prefix}_min_total_time'] = float(np.min(total_times))
        else:
            self.results[f'{prefix}_avg_total_time'] = 0.0
            self.results[f'{prefix}_p95_total_time'] = 0.0
            self.results[f'{prefix}_max_total_time'] = 0.0
            self.results[f'{prefix}_min_total_time'] = 0.0

    def calculate_queue_stats(self):
        """Calcola le statistiche sulle code (basate sul tempo)."""
        
        # CORREZIONE: Gestione array vuoti
        if not self.metrics.security_queue_log:
            self.results['avg_security_queue'] = 0.0
            self.results['max_security_queue'] = 0
            self.results['p95_security_queue'] = 0.0
            self.results['queue_utilization_ratio'] = 0.0
            return

        queue_lengths = [val for _, val in self.metrics.security_queue_log]
        
        self.results['avg_security_queue'] = float(np.mean(queue_lengths))
        self.results['max_security_queue'] = int(np.max(queue_lengths))
        self.results['p95_security_queue'] = float(np.percentile(queue_lengths, 95))
        
        # NUOVO: Calcola utilizzo delle corsie sicurezza
        if self.metrics.security_utilization_log:
            util_values = [val for _, val in self.metrics.security_utilization_log]
            # CORREZIONE: Assumi che ci sia almeno una corsia attiva, altrimenti usa 1
            max_lanes = max(util_values) if util_values else 1
            self.results['security_utilization_rate'] = (np.mean(util_values) / max_lanes * 100) if max_lanes > 0 else 0.0
        else:
            self.results['security_utilization_rate'] = 0.0

    def calculate_global_counts(self):
        """Salva i contatori globali."""
        # CORREZIONE: Allineamento con la nuova struttura di Metrics
        self.results['total_passengers_arrived'] = (self.metrics.total_boarded + self.metrics.total_missed_flights)
        self.results['total_companions_arrived'] = self.metrics.total_companions_arrived
        self.results['total_people_arrived'] = (self.metrics.total_companions_arrived+self.metrics.total_boarded + self.metrics.total_missed_flights)  # Usa il valore già calcolato
        
        self.results['total_boarded'] = self.metrics.total_boarded
        self.results['total_missed_flights'] = self.metrics.total_missed_flights
        self.results['total_security_cleared'] = (self.metrics.total_boarded + self.metrics.total_missed_flights)
        # CORREZIONE: Usa attributi nuovi se disponibili
        if hasattr(self.metrics, 'total_entered_security_queue'):
            self.results['total_entered_security_queue'] = self.metrics.total_entered_security_queue
        else:
            self.results['total_entered_security_queue'] = self.metrics.total_security_cleared  # Stima

        # Calcola il tasso di passeggeri persi (SOLO PASSEGGERI)
        total_passengers = self.results['total_passengers_arrived']
        if total_passengers > 0:
            self.results['missed_flight_rate'] = (self.metrics.total_missed_flights / total_passengers) * 100
        else:
            self.results['missed_flight_rate'] = 0.0

        # NUOVO: Calcola tasso di successo sicurezza
        if self.results['total_entered_security_queue'] > 0:
            self.results['security_success_rate'] = (self.metrics.total_security_cleared / self.results['total_entered_security_queue']) * 100
        else:
            self.results['security_success_rate'] = 0.0

    def calculate_missed_reasons(self):
        """Conteggia i motivi di perdita del volo basandosi su completed_passengers."""
        reason_counts = {}
        for p in self.metrics.completed_passengers:
            if p.get('state') == 'missed_flight':
                r = p.get('miss_reason', 'unknown')
                reason_counts[r] = reason_counts.get(r, 0) + 1
        self.results['missed_flight_reasons'] = reason_counts


    def calculate_retail_stats(self):
        """Stima uso retail da log per-minuto (quanti in attività land/air)."""
        # CORREZIONE: Gestione array vuoti
        land_act = [val for _, val in self.metrics.landside_activity_log] if self.metrics.landside_activity_log else []
        air_act = [val for _, val in self.metrics.airside_activity_log] if self.metrics.airside_activity_log else []

        def _stats(arr: List[float]) -> Dict[str, float]:
            if not arr:
                return {'avg': 0.0, 'max': 0, 'p95': 0.0, 'total_activity_minutes': 0}
            return {
                'avg': float(np.mean(arr)),
                'max': int(np.max(arr)),
                'p95': float(np.percentile(arr, 95)),
                'total_activity_minutes': float(np.sum(arr))  # Minuti-persona totali di attività
            }

        land_stats = _stats(land_act)
        air_stats = _stats(air_act)

        self.results['retail_landside_avg_active'] = land_stats['avg']
        self.results['retail_landside_max_active'] = land_stats['max']
        self.results['retail_landside_p95_active'] = land_stats['p95']
        self.results['retail_landside_total_activity_minutes'] = land_stats['total_activity_minutes']

        self.results['retail_airside_avg_active'] = air_stats['avg']
        self.results['retail_airside_max_active'] = air_stats['max']
        self.results['retail_airside_p95_active'] = air_stats['p95']
        self.results['retail_airside_total_activity_minutes'] = air_stats['total_activity_minutes']

    def calculate_system_throughput(self):
        """NUOVO: Calcola metriche di throughput del sistema"""
        # Throughput sicurezza (passeggeri/ora)
        total_simulation_minutes = len(self.metrics.security_queue_log)  # Assumi 1 minuto per log entry
        if total_simulation_minutes > 0:
            security_throughput_per_hour = (self.metrics.total_security_cleared / total_simulation_minutes) * 60
            self.results['security_throughput_per_hour'] = security_throughput_per_hour
        else:
            self.results['security_throughput_per_hour'] = 0.0

        # Throughput imbarco
        if total_simulation_minutes > 0:
            boarding_throughput_per_hour = (self.metrics.total_boarded / total_simulation_minutes) * 60
            self.results['boarding_throughput_per_hour'] = boarding_throughput_per_hour
        else:
            self.results['boarding_throughput_per_hour'] = 0.0

    def print_summary(self):
        """Stampa un riepilogo leggibile dei risultati."""
        if not self.results:
            print("No resuts. Run before run_analysis().")
            return
            
        print("="*50)
        print("SUMMARY STATISTICS SIMULATION")
        print("="*50)
        
        print("\n[GLOBAL FLOWS]")
        print(f"  Tot People arrived: {self.results.get('total_people_arrived', 0):,}")
        print(f"    - Passengers: {self.results.get('total_passengers_arrived', 0):,}")
        print(f"    - Companions: {self.results.get('total_companions_arrived', 0):,}")
        print(f"  Boarded Passengers: {self.results.get('total_boarded', 0):,}")
        print(f"  Lost Passengers: {self.results.get('total_missed_flights', 0):,}")
        print(f"  Missed Flight Rate: {self.results.get('missed_flight_rate', 0):.2f}%")
        print(f"  Security Cleared: {self.results.get('total_security_cleared', 0):,}")
        
        print("\n[PERFORMANCE SECURITY]")
        print(f"  Max Queue: {self.results.get('max_security_queue', 0):.0f} persone")
        print(f"  Mean Queue: {self.results.get('avg_security_queue', 0):.1f} persone")
        print(f"  P95 Queue: {self.results.get('p95_security_queue', 0):.0f} persone")
        print(f"  Throughput Sicurity: {self.results.get('security_throughput_per_hour', 0):.1f} pax/ora")
        
        print("\n[TIMES BOARDED PASSENGERS]")
        print(f"  Sicurity - Mean: {self.results.get('boarded_avg_security_time', 0):.1f} min")
        print(f"  Sicurity - P95: {self.results.get('boarded_p95_security_time', 0):.1f} min")
        print(f"  Sicurity - Max: {self.results.get('boarded_max_security_time', 0):.1f} min")
        print(f"  Total - Mean: {self.results.get('boarded_avg_total_time', 0):.1f} min")
        print(f"  Total - P95: {self.results.get('boarded_p95_total_time', 0):.1f} min")
        
        print("\n[TIMES PASSEGNGERS LOST]")
        print(f"  Sicurity - Mean: {self.results.get('missed_avg_security_time', 0):.1f} min")
        print(f"  Total - Mean: {self.results.get('missed_avg_total_time', 0):.1f} min")
        
        reasons = self.results.get('missed_flight_reasons', {})
        if reasons:
            print("\n[REASON MISSED FLIGHT]")
            total_missed = max(self.results.get('total_missed_flights', 0), 1)
            # opzionale: ordina per frequenza decrescente
            for reason, count in sorted(reasons.items(), key=lambda kv: kv[1], reverse=True):
                perc = 100.0 * count / total_missed
                print(f"  {reason}: {count} ({perc:.1f}% out of missed passengers)")

        print("\n[RETAIL ACTIVITY]")
        print(f"  Landside - Activity mean: {self.results.get('retail_landside_avg_active', 0):.1f} pax")
        print(f"  Landside - Max: {self.results.get('retail_landside_max_active', 0)} pax")
        print(f"  Airside - Activity mean: {self.results.get('retail_airside_avg_active', 0):.1f} pax")
        print(f"  Airside - Max: {self.results.get('retail_airside_max_active', 0)} pax")
        
        print("\n[THROUGHPUT SYSTEM]")
        print(f"  Boarding: {self.results.get('boarding_throughput_per_hour', 0):.1f} pax/hour")
        
        print("="*50)

    def get_key_metrics(self) -> Dict[str, float]:
        """NUOVO: Restituisce le metriche chiave per reporting"""
        key_metrics = {
            'missed_flight_rate': self.results.get('missed_flight_rate', 0),
            'avg_security_time_boarded': self.results.get('boarded_avg_security_time', 0),
            'max_security_queue': self.results.get('max_security_queue', 0),
            'security_throughput_per_hour': self.results.get('security_throughput_per_hour', 0),
            'retail_utilization_landside': self.results.get('retail_landside_avg_active', 0),
            'retail_utilization_airside': self.results.get('retail_airside_avg_active', 0)
        }
        return key_metrics