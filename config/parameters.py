"""
Simulation parameters for Turin Airport departure lounge model
All times are in minutes unless specified otherwise
"""

import numpy as np
from datetime import time

# SIMULATION CONTROL PARAMETERS
SIMULATION_START_TIME = time(4, 0)  # 4:00 AM
SIMULATION_END_TIME = time(23, 0)   # 11:00 PM
SIMULATION_DAYS = 7                # Number of replications
WARM_UP_PERIOD = time(8, 0)         # Warm-up until 8:00 AM

# AIRPORT CAPACITY AND LAYOUT

NUM_GATES = 22
NUM_FLIGHTS_PER_DAY = 51
DAILY_PASSENGERS = 12000
FLIGHT_CAPACITY=200
FLIGHT_LOAD_FACTOR=0.90

# Facility counts
LAND_SIDE_SHOPS = 6
LAND_SIDE_RESTAURANTS = 4  # Includes bars and restaurants
AIR_SIDE_SHOPS = 17
AIR_SIDE_RESTAURANTS = 8   # Includes bars and restaurants

# Security checkpoints
SECURITY_LANES=25 #SAREBBERO 5 CORSIE * 5 SLOT OGNI CORSIA
SECURITY_QUEUE_CAPACITY = np.inf  # I begin with infinite cose and then I measure the length and limits
SECURITY_MEAN_SERVICE_MIN=1.5
SECURITY_LANE_SCHEDULE = {
    time(4, 0): 25,   
    time(6, 0): 20, 
    time(11, 0): 25,
    time(15, 0): 20, 
    time(21, 0): 25
}
# Security processing time
SECURITY_PROCESSING_TIME = {
    'distribution': 'gamma',
    'mean': 1.5,
    'shape': 3.0 
}
# PASSENGER ARRIVAL PARAMETERS
# Arrival time before flight (in minutes)
ARRIVAL_MIX = {
  'early':   {'w':0.30, 'dist':'lognorm', 'mean':120, 'sd':25},
  'regular': {'w':0.50, 'dist':'lognorm', 'mean':90, 'sd':20},
  'late':    {'w':0.20, 'dist':'lognorm', 'mean': 60, 'sd':12},
}
SECURITY_TARGET_BY_PROFILE = {
    'early':   100,   # chi arriva molto presto vuole togliersi il pensiero prima
    'regular': 80,
    'late':    60,
}

# Hard safety cutoff: dopo questo limite, chiunque è forzato verso la sicurezza
GLOBAL_HARD_SECURITY_CUTOFF = 40.0

BOARDING_OPEN_MIN = 40
BOARDING_CLOSE_MIN = 7
FORCE_GATE_MIN=25
MIN_TIME_BEFORE_FLIGHT_TO_SECURITY=90
BOARDING_LANES_PER_GATE=2
BOARDING_PER_PAX_TIME={
    'distribution': 'gamma',
    'mean':0.30,
    'shape':5.0
}
# Boarding process
BOARDING_TIME = {
    'distribution': 'lognorm',
    'mean':0.12,
    'std':0.05  # min, max boarding time per flight
}

# Companion statistics
COMPANION_PROBABILITY = 0.30  # Probability passenger has companions
COMPANIONS_MEAN = 0.8        # Average number of companions (geometric distribution)
COMPANIONS_MAX = 3           # Maximum number of companions

# TIME DISTRIBUTIONS (in minutes)
# Land-side activities
SHOP_VISIT_TIME = {
    'distribution': 'triangular',
    'params': (5, 10, 20)  # min, mode, max
}

BAR_VISIT_TIME = {
    'distribution': 'triangular', 
    'params': (5, 15, 25)
}

RESTAURANT_VISIT_TIME = {
    'distribution': 'triangular',
    'params': (20, 30, 60)
}

# Transition times between areas
TRANSITION_TIMES = {
    'entrance_to_landside_facilities': 2,
    'landside_to_security': 3,
    'security_to_airside_facilities': 2,
    'airside_to_gates': 5
}

# Probability of visiting facilities
PROB_VISIT_LAND_SIDE_SHOP = 0.3
PROB_VISIT_LAND_SIDE_BAR = 0.3
PROB_VISIT_LAND_SIDE_RESTAURANT = 0.2

PROB_VISIT_AIR_SIDE_SHOP = 0.4
PROB_VISIT_AIR_SIDE_BAR = 0.4  
PROB_VISIT_AIR_SIDE_RESTAURANT = 0.3

# Maximum number of facility visits
MAX_LAND_SIDE_VISITS = 2
MAX_AIR_SIDE_VISITS = 2


# FACILITY CAPACITIES
FACILITY_CAPACITIES = {
    'land_side_shop': 25,
    'land_side_bar': 35, 
    'land_side_restaurant': 50,
    'air_side_shop': 30,
    'air_side_bar': 40,
    'air_side_restaurant': 60
}

# Relative frequency of flights per hour (6:00-22:30)
FLIGHT_SCHEDULE_DISTRIBUTION = {
    6: 0.12,   # 6:00-6:59
    7: 0.02,   # 7:00-7:59  
    8: 0.05,   # 8:00-8:59
    9: 0.04,   # 9:00-9:59
    10: 0.08,  # 10:00-10:59
    11: 0.08,  # 11:00-11:59
    12: 0.10,  # 12:00-12:59
    13: 0.02,  # 13:00-13:59
    14: 0.08,  # 14:00-14:59
    15: 0.05,  # 15:00-15:59
    16: 0.04,  # 16:00-16:59
    17: 0.02,  # 17:00-17:59
    18: 0.05,  # 18:00-18:59
    19: 0.05,  # 19:00-19:59
    20: 0.02,  # 20:00-20:59
    21: 0.09,  # 21:00-21:59
    22: 0.09   # 22:00-22:30
}

# Time buffer before flight departure
DEPARTURE_MINUTE_JITTER=20
ARRIVAL_TIME_JITTER=12
MIN_BUFFER_BEFORE_BOARDING = 20  # Minimum time before flight to head to gate
MAX_BUFFER_BEFORE_BOARDING = 25  # Maximum time before flight to head to gate
LANDSIDE_FORCE_SECURITY_MIN = 50   #se mancano 50min al volo e sei ancora in ladside vai alla sicurezza


# Group behavior
GROUP_STAY_TOGETHER_PROB = 0.8  # Probability group visits facilities together

# Expected utilizations for model validation
EXPECTED_UTILIZATIONS = {
    'security_checkpoints': (0.65, 0.85),  # min, max expected
    'land_side_shops': (0.4, 0.6),
    'air_side_shops': (0.3, 0.7),
    'gates': (0.7, 0.9)
}
