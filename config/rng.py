# STREAM RNG SEPARATI

# config/rng.py
"""
Random Number Generation for Turin Airport simulation
Centralized RNG with multiple streams for different processes
"""

import numpy as np
from .parameters import *

class RNG:
    """
    Random Number Generator with multiple streams for different processes
    """
    
    def __init__(self, seed=None):
        """
        Initialize RNG with optional seed
        Different streams for different processes to avoid correlation
        """
        self.seed = seed
        if seed is not None:
            np.random.seed(seed)
        
        # Create separate generators for different processes
        self.arrival_rng = np.random.default_rng(seed)
        self.facility_rng = np.random.default_rng(seed + 1 if seed else None)
        self.security_rng = np.random.default_rng(seed + 2 if seed else None)
        self.boarding_rng = np.random.default_rng(seed + 3 if seed else None)
        self.behavior_rng = np.random.default_rng(seed + 4 if seed else None)
    
    # =========================================================================
    # PASSENGER ARRIVAL AND BEHAVIOR
    # =========================================================================
    
    def passenger_arrival_type(self):
        """Determine if passenger is early, regular, or late"""
        types = list(ARRIVAL_MIX.keys())
        weights = [ARRIVAL_MIX[t]['w'] for t in types]
        return self.arrival_rng.choice(types, p=weights)
    
    def passenger_arrival_offset(self, arrival_type):
        """Generate arrival time offset before flight (in minutes)"""
        params = ARRIVAL_MIX[arrival_type]
        if params['dist'] == 'lognorm':
            # Convert mean and sd to parameters for lognormal
            mu = np.log(params['mean'] ** 2 / np.sqrt(params['sd'] ** 2 + params['mean'] ** 2))
            sigma = np.sqrt(np.log(1 + (params['sd'] ** 2 / params['mean'] ** 2)))
            return max(10, self.arrival_rng.lognormal(mu, sigma))
        else:
            raise ValueError(f"Unsupported distribution: {params['dist']}")
    
    def has_companions(self):
        """Determine if passenger has companions"""
        return self.behavior_rng.random() < COMPANION_PROBABILITY
    
    def num_companions(self):
        """Generate number of companions"""
        # Geometric distribution with mean COMPANIONS_MEAN
        # p = 1/(mean + 1) for support starting at 0
        if self.behavior_rng.random() < COMPANION_PROBABILITY:
            p = COMPANION_PROBABILITY / COMPANIONS_MEAN 
            return min(COMPANIONS_MAX, self.behavior_rng.geometric(p) )
        else:
            return 0
    
    # =========================================================================
    # FACILITY VISITS AND TIMINGS
    # =========================================================================
    
    def visit_land_side_facility(self):
        """Determine which land side facility to visit (if any)"""
        r = self.behavior_rng.random()
        cumulative = 0.0
        
        cumulative += PROB_VISIT_LAND_SIDE_SHOP
        if r < cumulative:
            return 'shop'
        
        cumulative += PROB_VISIT_LAND_SIDE_BAR
        if r < cumulative:
            return 'bar'
        
        cumulative += PROB_VISIT_LAND_SIDE_RESTAURANT
        if r < cumulative:
            return 'restaurant'
        
        return None  # No visit
    
    def visit_air_side_facility(self):
        """Determine which air side facility to visit (if any)"""
        r = self.behavior_rng.random()
        cumulative = 0.0
        
        cumulative += PROB_VISIT_AIR_SIDE_SHOP
        if r < cumulative:
            return 'shop'
        
        cumulative += PROB_VISIT_AIR_SIDE_BAR
        if r < cumulative:
            return 'bar'
        
        cumulative += PROB_VISIT_AIR_SIDE_RESTAURANT
        if r < cumulative:
            return 'restaurant'
        
        return None  # No visit
    
    def num_facility_visits(self, max_visits):
        """Generate number of facility visits (land side or air side)"""
        return self.behavior_rng.integers(0, max_visits + 1)
    
    def shop_visit_time(self):
        """Generate shop visit time in minutes"""
        params = SHOP_VISIT_TIME['params']
        if SHOP_VISIT_TIME['distribution'] == 'triangular':
            return self.facility_rng.triangular(params[0], params[1], params[2])
        else:
            raise ValueError(f"Unsupported distribution: {SHOP_VISIT_TIME['distribution']}")
    
    def bar_visit_time(self):
        """Generate bar visit time in minutes"""
        params = BAR_VISIT_TIME['params']
        if BAR_VISIT_TIME['distribution'] == 'triangular':
            return self.facility_rng.triangular(params[0], params[1], params[2])
        else:
            raise ValueError(f"Unsupported distribution: {BAR_VISIT_TIME['distribution']}")
    
    def restaurant_visit_time(self):
        """Generate restaurant visit time in minutes"""
        params = RESTAURANT_VISIT_TIME['params']
        if RESTAURANT_VISIT_TIME['distribution'] == 'triangular':
            return self.facility_rng.triangular(params[0], params[1], params[2])
        else:
            raise ValueError(f"Unsupported distribution: {RESTAURANT_VISIT_TIME['distribution']}")
    
    # =========================================================================
    # SECURITY AND BOARDING
    # =========================================================================
    
    def security_processing_time(self):
        """Tempo di servizio sicurezza (minuti) per pax"""
        cfg = SECURITY_PROCESSING_TIME
        dist = cfg.get('distribution', 'gamma').lower()

        if dist == 'exponential':
            (m,) = cfg['params']
            return self.security_rng.exponential(m)

        elif dist == 'gamma':
            # CORREZIONE: usa i parametri aggiornati da parameters.py
            mean = cfg.get('mean', 2.0)  # MODIFICATO: 1.2 → 2.0
            k = cfg.get('shape', 3.0)
            theta = mean / k  # scale
            return self.security_rng.gamma(shape=k, scale=theta)

        elif dist == 'triangular':
            a, c, b = cfg['params']
            return self.security_rng.triangular(a, c, b)

        else:
            # fallback: usa media di default
            return SECURITY_MEAN_SERVICE_MIN

    
    def boarding_time(self):
        """Generate boarding time per passenger (in minutes)."""
        cfg = BOARDING_TIME
        dist = cfg.get('distribution', 'uniform').lower()

        # helper: lognormal da mean/std oppure da mu/sigma
        def _lognorm_minutes(cfg):
            if 'mu' in cfg and 'sigma' in cfg:
                mu = float(cfg['mu'])
                sigma = float(cfg['sigma'])
            else:
                mean = float(cfg.get('mean', 0.12))
                std  = float(cfg.get('std',  0.04))
                mu = np.log(mean**2 / np.sqrt(std**2 + mean**2))
                sigma = np.sqrt(np.log(1.0 + (std**2 / mean**2)))
            return self.boarding_rng.lognormal(mu, sigma)

        if dist == 'uniform':
            if 'params' not in cfg:
                raise KeyError("BOARDING_TIME['params'] mancante per distribuzione 'uniform'.")
            lo, hi = cfg['params']
            return self.boarding_rng.uniform(lo, hi)

        elif dist == 'triangular':
            if 'params' not in cfg:
                raise KeyError("BOARDING_TIME['params'] mancante per distribuzione 'triangular'.")
            a, c, b = cfg['params']
            return self.boarding_rng.triangular(a, c, b)

        elif dist == 'exponential':
            if 'params' not in cfg:
                raise KeyError("BOARDING_TIME['params'] mancante per distribuzione 'exponential'.")
            (lam,) = cfg['params']
            return self.boarding_rng.exponential(lam)

        elif dist == 'lognorm':
            return _lognorm_minutes(cfg)

        else:
            raise ValueError(f"Unsupported BOARDING_TIME distribution: {dist}")

    def buffer_time_before_boarding(self):
        """Generate buffer time before flight to head to gate"""
        return self.behavior_rng.uniform(MIN_BUFFER_BEFORE_BOARDING, MAX_BUFFER_BEFORE_BOARDING)
    
    # =========================================================================
    # GROUP BEHAVIOR AND TRANSITIONS
    # =========================================================================
    
    def group_stay_together(self):
        """Determine if group stays together during facility visits"""
        return self.behavior_rng.random() < GROUP_STAY_TOGETHER_PROB
    
    def transition_time(self, transition_type):
        """Get transition time between areas"""
        return TRANSITION_TIMES.get(transition_type, 0)
    
    # =========================================================================
    # FACILITY SELECTION
    # =========================================================================
    
    def select_facility(self, facility_type, area, count):
        """Randomly select a specific facility ID"""
        if count == 0:
            return None
        facility_id = self.behavior_rng.integers(1, count + 1)
        return f"{area}_{facility_type}_{facility_id:02d}"
    
    # =========================================================================
    # UTILITY METHODS
    # =========================================================================
    
    def random_choice(self, items, weights=None):
        """Random choice from a list with optional weights"""
        return self.behavior_rng.choice(items, p=weights)
    
    def random_uniform(self, low=0.0, high=1.0):
        """Generate uniform random number between low and high"""
        return self.behavior_rng.uniform(low, high)
    
    def random_int(self, low, high):
        """Generate random integer between low and high (inclusive)"""
        return self.behavior_rng.integers(low, high + 1)

    def random_poisson(self, lam):
        """Generate Poisson distributed random number"""
        return self.arrival_rng.poisson(lam)
    
default_rng = RNG()


