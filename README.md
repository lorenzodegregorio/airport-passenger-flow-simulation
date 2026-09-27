# Airport Passenger Flow Simulation

This repository presents a cleaned portfolio version of a discrete-event simulation project focused on airport passenger flows.

The project models the departure process of a medium-sized airport, using Torino Airport as a reference scenario. The simulation follows passengers from terminal arrival to security screening, airside activities and final boarding, while also accounting for companions, retail facilities and time-dependent airport operations.

The goal is to evaluate how passenger behaviour, flight schedules, security capacity and retail activity interact over time, and how these dynamics affect operational KPIs such as queue length, waiting time, missed-flight rate and terminal occupancy.

---

## Project overview

Airport terminals are complex systems where passenger flows, infrastructure capacity and time-dependent demand interact continuously.

This simulation focuses on the departure area and includes:

- passenger arrivals before departure;
- companions staying in the landside area;
- landside shops, bars and restaurants;
- security screening with time-varying active lanes;
- airside retail activity;
- gate boarding with capacity and closing-time constraints;
- missed-flight tracking;
- one-day and seven-day simulation scenarios.

The model is implemented in Python using a custom event-based simulation engine.

---

## Simulation logic

The system is divided into three main areas.

### 1. Landside area

Passengers arrive at the terminal before their flight. Some passengers are accompanied by friends or relatives.

In this area, passengers and companions may visit retail facilities such as shops, bars and restaurants. Companions remain landside and do not pass through security.

### 2. Security checkpoint

Passengers leave the landside area and join a single security queue.

Security is modelled as a resource with multiple lanes. The number of active lanes can vary over time to reflect different demand levels during the day.

### 3. Airside area and gates

After security, passengers enter the airside departure lounge. If they have enough time before departure, they may visit airside retail facilities.

Eventually, passengers move to their assigned gate and join the boarding queue. Gates open and close according to predefined timing rules, and boarding is constrained by flight capacity.

---

## Key performance indicators

The simulation tracks several operational metrics:

- number of passengers arrived;
- number of passengers boarded;
- number of missed flights;
- missed-flight rate;
- security queue length over time;
- security waiting time;
- total time spent in the system;
- landside and airside population over time;
- landside and airside retail activity;
- boarding performance by flight.

---

## Visual overview

### Flight schedule distribution

![Flight schedule distribution](figures/flight_schedule_distribution.png)

### Security queue over one day

![Security queue one day](figures/security_queue_one_day.png)

### Airport population over one day

![Airport population one day](figures/airport_population_one_day.png)

### Security queue over seven days

![Security queue seven days](figures/security_queue_seven_days.png)

### Passenger time distributions

![Passenger time CDFs](figures/passenger_time_cdfs.png)

---

## Repository structure

```text
airport-passenger-flow-simulation/
├── airport_simulation/
│   ├── analysis/
│   │   ├── metrics.py
│   │   ├── output_analysis.py
│   │   └── visualization.py
│   ├── config/
│   │   ├── flight_schedule.py
│   │   ├── parameters.py
│   │   ├── rng.py
│   │   └── time_utils.py
│   ├── entities/
│   │   ├── facility.py
│   │   ├── flight.py
│   │   └── passenger.py
│   ├── processes/
│   │   ├── arrival_process.py
│   │   ├── boarding_process.py
│   │   └── security_process.py
│   ├── resources/
│   │   ├── gates.py
│   │   ├── security.py
│   │   └── shops.py
│   ├── __init__.py
│   ├── main.py
│   ├── simulation_engine.py
│   └── simulation_more_days.py
├── figures/
│   ├── airport_population_one_day.png
│   ├── airport_population_seven_days.png
│   ├── boarding_by_flights.png
│   ├── flight_schedule_distribution.png
│   ├── passenger_time_cdfs.png
│   ├── retail_activity_one_day.png
│   ├── retail_activity_seven_days.png
│   ├── security_queue_one_day.png
│   ├── security_queue_seven_days.png
│   └── time_in_system_histogram.png
├── reports/
│   └── project_summary.md
├── scripts/
│   ├── run_one_day_simulation.py
│   └── run_seven_day_simulation.py
├── README.md
├── requirements.txt
└── .gitignore
```

---

## Code structure

The project is organized as a small Python package.

### `airport_simulation/entities/`

Contains the main simulation entities:

- `Passenger`
- `Flight`
- `Facility`

These classes store the state and attributes of the main objects moving through the system.

### `airport_simulation/resources/`

Contains airport resources:

- security checkpoint;
- gates;
- shops and retail facilities.

These resources manage queues, service processes and capacity constraints.

### `airport_simulation/processes/`

Contains the main event processes:

- passenger arrivals;
- security screening;
- boarding.

These modules define how events are handled during the simulation.

### `airport_simulation/config/`

Contains configuration files for:

- simulation parameters;
- flight schedule;
- random number generation;
- time utilities.

### `airport_simulation/analysis/`

Contains utilities for:

- metric computation;
- output analysis;
- visualization.

---

## Running the project

Clone the repository:

```bash
git clone https://github.com/lorenzodegregorio/airport-passenger-flow-simulation.git
cd airport-passenger-flow-simulation
```

Create and activate a virtual environment:

```bash
python -m venv .venv
```

On Windows:

```bash
.venv\Scripts\activate
```

On macOS/Linux:

```bash
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Run the one-day simulation:

```bash
python scripts/run_one_day_simulation.py
```

Run the seven-day simulation:

```bash
python scripts/run_seven_day_simulation.py
```

The scripts generate local output files and plots inside an `analysis_results/` folder.

This folder is intentionally excluded from the repository through `.gitignore`.

---

## Dependencies

The project uses a lightweight Python stack:

- `numpy`
- `matplotlib`

Dependencies can be installed with:

```bash
pip install -r requirements.txt
```

---

## Notes on generated outputs

The repository includes selected figures in the `figures/` folder for portfolio presentation purposes.

Generated outputs such as:

- `analysis_results/`
- logs;
- cache folders;
- local simulation outputs;
- Python bytecode files;

are intentionally excluded from version control.

This keeps the repository lightweight and focused on the cleaned public version of the project.

---

## Technical keywords

`Python` · `Discrete-event simulation` · `Queueing systems` · `Airport operations` · `Passenger flow simulation` · `Security queue` · `Boarding process` · `Operational KPIs` · `Complex systems` · `Simulation modelling`

---

## Project status

This repository is a cleaned and public-facing portfolio version of a university simulation project.

It is intended to demonstrate the ability to design, implement and analyse a realistic event-based simulation system, with clear entities, resources, processes, performance metrics and visual outputs.
