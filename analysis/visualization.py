import os
import sys
import numpy as np
import matplotlib.pyplot as plt
from collections import defaultdict
from matplotlib.ticker import MultipleLocator, FuncFormatter
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from analysis.metrics import Metrics
from config.time_utils import TimeUtils
from datetime import datetime
from config.parameters import NUM_FLIGHTS_PER_DAY, FLIGHT_SCHEDULE_DISTRIBUTION


def _minutes_formatter():
    """Formatter HH:MM per asse X espresso in minuti da mezzanotte (wrappato 24h)."""
    return FuncFormatter(lambda m, _: TimeUtils.minutes_to_time(int(round(m))).strftime("%H:%M"))

def _daily_average_time_series(log):
    """
    Prende una serie [(time, value), ...] anche su più giorni
    e restituisce due liste (minutes_of_day, avg_value) con la
    media per ogni minuto del giorno.
    """
    if not log:
        return [], []

    buckets = defaultdict(list)
    for t, v in log:
        m = TimeUtils.time_to_minutes(t)  # 0..1439
        buckets[m].append(v)

    minutes = sorted(buckets.keys())
    avg_values = [sum(vals) / len(vals) for vals in (buckets[m] for m in minutes)]
    return minutes, avg_values

class Visualization:
    def __init__(self, metrics: Metrics, output_dir="analysis_results"):
        self.metrics = metrics
        self.output_dir = output_dir
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    # -------------------- PLOT: coda sicurezza --------------------
    def plot_security_queue_over_time(self, filename="security_queue_over_time.png"):
        if not self.metrics.security_queue_log:
            print("No data on security queue to plot.")
            return

        x_time = [TimeUtils.time_to_minutes(t) for t, _ in self.metrics.security_queue_log]
        y_queue = [v for _, v in self.metrics.security_queue_log]

        fig, ax = plt.subplots(figsize=(12, 6))
        ax.plot(x_time, y_queue, label="Lenght Security Queue")

        ax.set_title("Lenght Security Queue Over Time")
        ax.set_xlabel("Hour")
        ax.set_ylabel("People on Queue")
        ax.grid(True, which="both", linestyle="--", alpha=0.4)
        ax.legend()

        # Limiti e tick asse X: evita valori fuori [min,max] che causano label strane
        xmin, xmax = min(x_time), max(x_time)
        ax.set_xlim(xmin, xmax)
        ax.xaxis.set_major_locator(MultipleLocator(60))   # ogni ora
        ax.xaxis.set_minor_locator(MultipleLocator(30))   # ogni 30'
        ax.xaxis.set_major_formatter(_minutes_formatter())

        # Asse Y non negativo
        ax.set_ylim(bottom=0)

        fig.tight_layout()
        outpath = os.path.join(self.output_dir, filename)
        fig.savefig(outpath, bbox_inches="tight")
        plt.close(fig)
        print(f"Graph security queue saved in: {outpath}")

    # -------------------- PLOT: popolazione aree --------------------
    def plot_airport_population(self, filename="airport_population_over_time.png"):
        if not self.metrics.landside_pop_log or not self.metrics.airside_pop_log:
            print("No data on population to plot.")
            return

        x_time = [TimeUtils.time_to_minutes(t) for t, _ in self.metrics.landside_pop_log]
        y_landside = [v for _, v in self.metrics.landside_pop_log]
        y_airside  = [v for _, v in self.metrics.airside_pop_log]

        fig, ax = plt.subplots(figsize=(12, 6))
        ax.plot(x_time, y_landside, label="Population Landside (watinig/shops)")
        ax.plot(x_time, y_airside,  label="Populatoin Airside (waiting/shops)")

        ax.set_title("Airport Areas Population over Time")
        ax.set_xlabel("Hours")
        ax.set_ylabel("Number of Passeggers")
        ax.grid(True, which="both", linestyle="--", alpha=0.4)
        ax.legend()

        xmin, xmax = min(x_time), max(x_time)
        ax.set_xlim(xmin, xmax)
        ax.xaxis.set_major_locator(MultipleLocator(60))
        ax.xaxis.set_minor_locator(MultipleLocator(30))
        ax.xaxis.set_major_formatter(_minutes_formatter())
        ax.set_ylim(bottom=0)

        fig.tight_layout()
        outpath = os.path.join(self.output_dir, filename)
        fig.savefig(outpath, bbox_inches="tight")
        plt.close(fig)
        print(f"Graph population saved in: {outpath}")

    # -------------------- PLOT: attività retail (shop/bar) --------------------
    def plot_retail_activity_over_time(self, filename="retail_activity_over_time.png"):
        """
        Mostra quanti passeggeri stanno svolgendo un'attività retail
        (negozi/bar/ristoranti) in landside e in airside nel tempo.
        """
        if not self.metrics.landside_activity_log or not self.metrics.airside_activity_log:
            print("No data on retail activity to plot.")
            return

        x_time = [TimeUtils.time_to_minutes(t) for t, _ in self.metrics.landside_activity_log]
        y_land = [v for _, v in self.metrics.landside_activity_log]
        y_air  = [v for _, v in self.metrics.airside_activity_log]

        fig, ax = plt.subplots(figsize=(12, 6))
        ax.plot(x_time, y_land, label="N° Active Retail Landside")
        ax.plot(x_time, y_air,  label="N° Active Retail Airside")

        ax.set_title("Attivities Retail over Time")
        ax.set_xlabel("Hours")
        ax.set_ylabel("Passengers in activity (shop/bar)")
        ax.grid(True, which="both", linestyle="--", alpha=0.4)
        ax.legend()

        xmin, xmax = min(x_time), max(x_time)
        ax.set_xlim(xmin, xmax)
        ax.xaxis.set_major_locator(MultipleLocator(60))   # ogni ora
        ax.xaxis.set_minor_locator(MultipleLocator(30))   # ogni 30'
        ax.xaxis.set_major_formatter(_minutes_formatter())
        ax.set_ylim(bottom=0)

        fig.tight_layout()
        outpath = os.path.join(self.output_dir, filename)
        fig.savefig(outpath, bbox_inches="tight")
        plt.close(fig)
        print(f"Graph retail activity saved in: {outpath}")

    # -------------------- PLOT: istogramma tempi nel sistema --------------------
    def plot_time_in_system_histogram(self, filename="time_in_system_hist.png"):
        """
        Istogramma del tempo totale passato nel sistema dai passeggeri,
        separando imbarcati e persi.
        """
        completed = getattr(self.metrics, "completed_passengers", None)
        if not completed:
            print("No passenger data completed for histogram.")
            return

        boarded_times = []
        missed_times = []

        for p in completed:
            state = p.get('state')
            t_tot = p.get('total_time')
            if t_tot is None or t_tot < 0:
                continue
            if state == 'boarded':
                boarded_times.append(t_tot)
            elif state == 'missed_flight':
                missed_times.append(t_tot)

        if not boarded_times and not missed_times:
            print("No valid gtime for time histogram.")
            return

        # Bins comuni per confrontare le distribuzioni
        all_times = boarded_times + missed_times
        bins = min(20, max(5, int(np.sqrt(len(all_times)))))  # regola empirica

        fig, ax = plt.subplots(figsize=(12, 6))

        if boarded_times:
            ax.hist(boarded_times, bins=bins, alpha=0.6, label="Boarded")
        if missed_times:
            ax.hist(missed_times, bins=bins, alpha=0.6, label="Lost")

        ax.set_title("Total Time Distribution of the System")
        ax.set_xlabel("Time in the system (minutes)")
        ax.set_ylabel("Number of passengers")
        ax.grid(True, which="both", linestyle="--", alpha=0.4)
        ax.legend()

        fig.tight_layout()
        outpath = os.path.join(self.output_dir, filename)
        fig.savefig(outpath, bbox_inches="tight")
        plt.close(fig)
        print(f"Histogram times in the sysyem saved in: {outpath}")


    #grafici per media + giorni
    def plot_security_queue_more_days(self, filename="security_queue_more_days.png"):
        if not self.metrics.security_queue_log:
            print("No data on security queue to plot.")
            return

        x_time, y_queue = _daily_average_time_series(self.metrics.security_queue_log)
        if not x_time:
            print("No available data to daily mean security queue.")
            return

        fig, ax = plt.subplots(figsize=(12, 6))
        ax.plot(x_time, y_queue, label="Lenght Security Queue (daily mean)")

        ax.set_title("Lenght Security Queue over Time (daily mean)")
        ax.set_xlabel("Hours")
        ax.set_ylabel("People in Queue")
        ax.grid(True, which="both", linestyle="--", alpha=0.4)
        ax.legend()

        xmin, xmax = min(x_time), max(x_time)
        ax.set_xlim(xmin, xmax)
        ax.xaxis.set_major_locator(MultipleLocator(60))   # ogni ora
        ax.xaxis.set_minor_locator(MultipleLocator(30))   # ogni 30'
        ax.xaxis.set_major_formatter(_minutes_formatter())
        ax.set_ylim(bottom=0)

        fig.tight_layout()
        outpath = os.path.join(self.output_dir, filename)
        fig.savefig(outpath, bbox_inches="tight")
        plt.close(fig)
        print(f"Graph security queue (daily mean) saved in: {outpath}")

    def plot_airport_population_more_days(self, filename="airport_population_more_days.png"):
        if not self.metrics.landside_pop_log or not self.metrics.airside_pop_log:
            print("No data on population to plot.")
            return

        x_time, y_landside = _daily_average_time_series(self.metrics.landside_pop_log)
        _,      y_airside  = _daily_average_time_series(self.metrics.airside_pop_log)

        if not x_time:
            print("No available data to population daily mean.")
            return

        fig, ax = plt.subplots(figsize=(12, 6))
        ax.plot(x_time, y_landside, label="Landside Poputaion (daily mean)")
        ax.plot(x_time, y_airside,  label="Airdside Poputaion (daily mean)")

        ax.set_title("Population in Airport Areas (daily mean)")
        ax.set_xlabel("Hours")
        ax.set_ylabel("Number of Passengers")
        ax.grid(True, which="both", linestyle="--", alpha=0.4)
        ax.legend()

        xmin, xmax = min(x_time), max(x_time)
        ax.set_xlim(xmin, xmax)
        ax.xaxis.set_major_locator(MultipleLocator(60))
        ax.xaxis.set_minor_locator(MultipleLocator(30))
        ax.xaxis.set_major_formatter(_minutes_formatter())
        ax.set_ylim(bottom=0)

        fig.tight_layout()
        outpath = os.path.join(self.output_dir, filename)
        fig.savefig(outpath, bbox_inches="tight")
        plt.close(fig)
        print(f"Graph population (daily average) saved in: {outpath}")
    
    def plot_retail_activity_more_days(self, filename="retail_activity_more_days.png"):
        """
        Mostra quanti passeggeri stanno svolgendo un'attività retail
        (negozi/bar/ristoranti) in landside e airside nel tempo,
        come profilo medio giornaliero.
        """
        if not self.metrics.landside_activity_log or not self.metrics.airside_activity_log:
            print("No data to plot.")
            return

        x_time, y_land = _daily_average_time_series(self.metrics.landside_activity_log)
        _,      y_air  = _daily_average_time_series(self.metrics.airside_activity_log)

        if not x_time:
            print("No available data.")
            return

        fig, ax = plt.subplots(figsize=(12, 6))
        ax.plot(x_time, y_land, label="Retail Landside Active (daily mean)")
        ax.plot(x_time, y_air,  label="Attivi Retail Active (daily mean)")

        ax.set_title("Attivities Retail over Time (daily mean)")
        ax.set_xlabel("Hours")
        ax.set_ylabel("Passengers in activity (shop/bar)")
        ax.grid(True, which="both", linestyle="--", alpha=0.4)
        ax.legend()

        xmin, xmax = min(x_time), max(x_time)
        ax.set_xlim(xmin, xmax)
        ax.xaxis.set_major_locator(MultipleLocator(60))   # ogni ora
        ax.xaxis.set_minor_locator(MultipleLocator(30))   # ogni 30'
        ax.xaxis.set_major_formatter(_minutes_formatter())
        ax.set_ylim(bottom=0)

        fig.tight_layout()
        outpath = os.path.join(self.output_dir, filename)
        fig.savefig(outpath, bbox_inches="tight")
        plt.close(fig)
        print(f"Graph retail activities (daily mean) saved in: {outpath}")

    def plot_flight_schedule_distribution(self, filename="flight_schedule_distribution.png"):
        hours = sorted(FLIGHT_SCHEDULE_DISTRIBUTION.keys())
        probs = [FLIGHT_SCHEDULE_DISTRIBUTION[h] for h in hours]

        # expected flights per hour (can be non-integer)
        expected_flights = [p * NUM_FLIGHTS_PER_DAY for p in probs]

        fig, ax = plt.subplots(figsize=(10, 5))
        ax.bar(hours, expected_flights, width=0.8)

        ax.set_title("Daily Flight Schedule Distribution")
        ax.set_xlabel("Hour of day")
        ax.set_ylabel("Expected number of flights")

        ax.set_xticks(hours)
        ax.grid(True, axis="y", linestyle="--", alpha=0.4)

        fig.tight_layout()

        # make sure directory exists
        os.makedirs(self.output_dir, exist_ok=True)

        outpath = os.path.join(self.output_dir, filename)

        try:
            fig.savefig(outpath, bbox_inches="tight")
            print(f"Grafico distribuzione voli salvato in: {outpath}")
        except PermissionError:
            # file probabilmente aperto da un viewer: salva con nome alternativo
            base, ext = os.path.splitext(filename)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            alt_filename = f"{base}_{ts}{ext}"
            alt_path = os.path.join(self.output_dir, alt_filename)
            fig.savefig(alt_path, bbox_inches="tight")
            print(f"ATTENZIONE: impossibile sovrascrivere {outpath} (file aperto o protetto?).")
            print(f"Grafico distribuzione voli salvato come: {alt_path}")
        finally:
            plt.close(fig)


    def plot_boarding_by_flight(self, filename="boarding_by_flight.png"):
        """
        Average boarded vs missed per flight, aggregated by departure hour
        (useful when simulating multiple days).
        """
        departed = getattr(self.metrics, "departed_flights", None)
        if not departed:
            print("Nessun volo partito registrato per grafico boarding.")
            return

        # Aggrega per ora di partenza
        hour_stats = {}  # hour -> {'boarded_sum':..., 'missed_sum':..., 'count':...}

        for f in departed:
            dep_time = f.get("departure_time")
            if dep_time is None:
                continue
            hour = dep_time.hour

            boarded = f.get("passengers_boarded", 0)
            demand = f.get("num_passengers", 0)
            missed = max(0, demand - boarded)

            if hour not in hour_stats:
                hour_stats[hour] = {"boarded_sum": 0, "missed_sum": 0, "count": 0}
            hour_stats[hour]["boarded_sum"] += boarded
            hour_stats[hour]["missed_sum"] += missed
            hour_stats[hour]["count"] += 1

        # Tieni solo le ore che hanno almeno un volo
        hours = sorted(h for h, s in hour_stats.items() if s["count"] > 0)
        if not hours:
            print("Nessun dato valido per grafico boarding per ora.")
            return

        avg_boarded = [
            hour_stats[h]["boarded_sum"] / hour_stats[h]["count"] for h in hours
        ]
        avg_missed = [
            hour_stats[h]["missed_sum"] / hour_stats[h]["count"] for h in hours
        ]

        import numpy as np
        x = np.arange(len(hours))
        width = 0.4

        fig, ax = plt.subplots(figsize=(10, 5))
        ax.bar(x - width/2, avg_boarded, width, label="Boarded (avg per flight)")
        ax.bar(x + width/2, avg_missed,  width, label="Missed (avg per flight)")

        ax.set_title("Average Boarded vs Missed per Flight by Departure Hour")
        ax.set_xlabel("Departure hour")
        ax.set_ylabel("Passengers per flight (average)")

        ax.set_xticks(x)
        ax.set_xticklabels([f"{h:02d}:00" for h in hours])

        ax.grid(True, axis="y", linestyle="--", alpha=0.4)
        ax.legend()

        fig.tight_layout()
        outpath = os.path.join(self.output_dir, filename)
        fig.savefig(outpath, bbox_inches="tight")
        plt.close(fig)
        print(f"Grafico boarding per ora salvato in: {outpath}")


    def plot_time_cdf(self, filename="time_cdf.png"):
        completed = getattr(self.metrics, "completed_passengers", None)
        if not completed:
            print("Nessun dato passeggeri per CDF.")
            return

        import numpy as np

        boarded_times = [p["total_time"] for p in completed
                         if p.get("state") == "boarded" and p.get("total_time") is not None]
        missed_times = [p["total_time"] for p in completed
                        if p.get("state") == "missed_flight" and p.get("total_time") is not None]

        if not boarded_times and not missed_times:
            print("Tempi non disponibili per CDF.")
            return

        def ecdf(data):
            data = np.sort(np.array(data))
            y = np.arange(1, len(data)+1) / len(data)
            return data, y

        fig, ax = plt.subplots(figsize=(10, 5))

        if boarded_times:
            x_b, y_b = ecdf(boarded_times)
            ax.step(x_b, y_b, where="post", label="Boarded")

        if missed_times:
            x_m, y_m = ecdf(missed_times)
            ax.step(x_m, y_m, where="post", label="Missed")

        ax.set_title("CDF of Total Time in System")
        ax.set_xlabel("Time in system (minutes)")
        ax.set_ylabel("Cumulative probability")
        ax.grid(True, which="both", linestyle="--", alpha=0.4)
        ax.legend()

        fig.tight_layout()
        outpath = os.path.join(self.output_dir, filename)
        fig.savefig(outpath, bbox_inches="tight")
        plt.close(fig)
        print(f"CDF tempi salvata in: {outpath}")

    