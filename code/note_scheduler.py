# Copyright (C) 2025 VanilleIce
# This program is licensed under the GNU AGPLv3. See LICENSE for details.

import logging, heapq, time
from threading import Thread, Event, Lock
from typing import Callable, Any

logger = logging.getLogger("ProjectLyrica.NoteScheduler")

class NoteScheduler:
    def __init__(self, release_callback: Callable[[Any], None]):
        """Initialize the note scheduler with a release callback function."""
        self.queue = []
        self.callback = release_callback
        self.lock = Lock()
        self.stop_event = Event()
        self.thread = Thread(target=self._run, daemon=True, name="NoteSchedulerThread")
        self.active = False
        self._start_time = 0.0
        
        logger.debug("Initializing NoteScheduler")
        self.thread.start()
        self.active = True
        self._start_time = time.time()

    def add(self, key: Any, delay: float):
        """Add a key to be released after specified delay."""
        with self.lock:
            release_time = time.time() + delay
            heapq.heappush(self.queue, (release_time, key))
            logger.debug(f"Added key {key} to be released at {release_time:.3f}s")

    def reset(self):
        """Clear all pending key releases."""
        with self.lock:
            self.queue = []

    def stop(self):
        """Stop the scheduler thread gracefully."""
        if self.active:
            logger.debug("Stopping NoteScheduler thread")
            self.stop_event.set()
            self.thread.join(timeout=0.1)
            
            if self.thread.is_alive():
                logger.warning("NoteScheduler thread did not terminate gracefully")
            else:
                logger.debug("NoteScheduler thread stopped successfully")
                
            self.active = False

    def restart(self):
        """Restart the scheduler if it was stopped."""
        if not self.active:
            logger.debug("Restarting NoteScheduler")
            self.stop_event.clear()
            self.thread = Thread(target=self._run, daemon=True, name="NoteSchedulerThread")
            self.thread.start()
            self.active = True
            self._start_time = time.time()

    def _run(self):
        """Main scheduler loop that processes the release queue."""
        logger.debug("NoteScheduler thread started")
        
        while not self.stop_event.is_set():
            now = time.time()
            keys_to_process = []
            
            with self.lock:
                while self.queue and self.queue[0][0] <= now:
                    _, key = heapq.heappop(self.queue)
                    keys_to_process.append(key)
            
            for key in keys_to_process:
                try:
                    self.callback(key)
                    logger.debug(f"Released key: {key}")
                except Exception as e:
                    logger.error(f"Error releasing key {key}: {e}")
            
            with self.lock:
                sleep_time = 0.1
                if self.queue:
                    next_time = self.queue[0][0]
                    sleep_time = max(0.01, min(0.1, next_time - now))
            
            time.sleep(sleep_time)
                
        logger.debug("NoteScheduler thread exiting")
        self.active = False