# File: airport_simulation/simulation_engine.py

import heapq
from dataclasses import dataclass, field
from typing import Any, List, Callable, Dict, Optional

from config.time_utils import TimeUtils


@dataclass(order=True)
class Event:
    """
    Basic event for continuous-time DES.
    time: absolute simulation time in minutes (float)
    etype: event type string (e.g. "ARRIVAL", "END_ACTIVITY", ...)
    payload: arbitrary data (Passenger, Flight, etc.)
    """
    time: float
    counter: int = field(compare=False)
    etype: str = field(compare=False)
    payload: Any = field(compare=False)


class SimulationEngine:
    """
    Continuous-time event-based engine with a Future Event Set (FES).

    - time: current simulation time in minutes (float, from 0 = start of day)
    - events: min-heap of Event
    - handlers: dict etype -> function(engine, event)
    - metrics_logger: optional function called to log per-minute snapshots
    """

    def __init__(
        self,
        start_time,
        end_time,
        metrics_logger: Optional[Callable[[Any, float], None]] = None
    ):
        # convert datetime.time to minutes from midnight
        self.start_minutes = TimeUtils.time_to_minutes(start_time)
        self.end_minutes = TimeUtils.time_to_minutes(end_time)

        self.time: float = self.start_minutes
        self._counter: int = 0
        self._fes: List[Event] = []

        self.handlers: Dict[str, Callable[[Any, Event], None]] = {}
        self.metrics_logger = metrics_logger

        # per-minute logging support
        self._next_log_time: float = self.start_minutes

    # --------- core API ---------

    def register_handler(self, etype: str, handler: Callable[[Any, Event], None]):
        """
        Register a callback for event type etype.
        handler signature: handler(engine, event)
        """
        self.handlers[etype] = handler

    def schedule(self, time_min: float, etype: str, payload: Any):
        """
        Schedule a new event at absolute time (minutes from midnight).
        """
        if time_min > self.end_minutes:
            # outside horizon, ignore
            return
        ev = Event(time_min, self._counter, etype, payload)
        self._counter += 1
        heapq.heappush(self._fes, ev)

    def run(self):
        """
        Main simulation loop: processes events in time order.
        """
        while self._fes and self.time <= self.end_minutes:
            ev = heapq.heappop(self._fes)

            # advance time
            if ev.time > self.end_minutes:
                break
            self._advance_time(ev.time)

            # dispatch
            handler = self.handlers.get(ev.etype, None)
            if handler is None:
                # no handler -> ignore silently (or raise if prefer)
                continue
            handler(self, ev)

        # ensure we log until end_time if necessary
        if self.metrics_logger is not None:
            self._advance_time(self.end_minutes)

    # --------- internal helpers ---------

    def _advance_time(self, new_time: float):
        """
        Advance engine time to new_time (>= current), and perform periodic logging
        at integer minutes while moving forward.
        """
        if new_time < self.time:
            raise ValueError("New time cannot be smaller than current time")

        if self.metrics_logger is not None:
            # log at each full minute crossed
            while self._next_log_time <= new_time and self._next_log_time <= self.end_minutes:
                self.metrics_logger(self, self._next_log_time)
                self._next_log_time += 1.0

        self.time = new_time

    # convenience: convert internal minutes to datetime.time for metrics if needed
    def current_datetime_time(self):
        return TimeUtils.minutes_to_time(int(self.time))
