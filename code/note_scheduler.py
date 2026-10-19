# Copyright (C) 2026 VanilleIce
# This program is licensed under the GNU AGPLv3. See LICENSE for details.

import heapq
import logging
import time
from threading import Event, Lock, Thread
from typing import Any, Callable, List, Optional, Tuple

logger = logging.getLogger("ProjectLyrica.NoteScheduler")


class NoteScheduler:
    """Scheduler der Tasten-Releases zu bestimmten Zeitpunkten auslöst.

    Verwendet einen Heap für zeitbasierte Sortierung und einen
    eigenen Thread zur Verarbeitung. Thread-safe.
    """

    # Wie lange soll der Thread maximal auf Stop warten (Sekunden)
    STOP_TIMEOUT = 0.5

    # Minimaler/Maximaler Sleep zwischen Checks (Sekunden)
    MIN_SLEEP = 0.001
    MAX_SLEEP = 0.05
    IDLE_SLEEP = 0.02

    def __init__(self, release_callback: Callable[[Any], None]):
        """
        Args:
            release_callback: Wird aufgerufen wenn ein Key released werden soll.
        """
        self._queue: List[Tuple[float, int, Any]] = []
        self._callback = release_callback
        self._lock = Lock()
        self._stop_event = Event()
        self._thread: Optional[Thread] = None
        self._active = False
        self._counter = 0

        self._start_thread()

    # ==================== Öffentliche API ====================

    @property
    def active(self) -> bool:
        """Ist der Scheduler aktiv?"""
        with self._lock:
            return self._active

    def add(self, key: Any, delay: float):
        """Fügt einen Key hinzu, der nach `delay` Sekunden released wird.

        Args:
            key: Taste die released werden soll.
            delay: Verzögerung in Sekunden (muss > 0 sein).
        """
        if delay < 0:
            delay = 0.0

        with self._lock:
            release_time = time.time() + delay
            # Counter als Tiebreaker damit Keys nicht verglichen werden müssen
            self._counter += 1
            heapq.heappush(self._queue, (release_time, self._counter, key))

    def reset(self):
        """Leert die Queue (noch nicht verarbeitete Keys verwerfen)."""
        with self._lock:
            self._queue.clear()

    def stop(self):
        """Stoppt den Scheduler-Thread sauber."""
        with self._lock:
            if not self._active:
                return
            self._active = False

        logger.debug("Stopping NoteScheduler thread")
        self._stop_event.set()

        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=self.STOP_TIMEOUT)

            if thread.is_alive():
                logger.warning(
                    f"NoteScheduler thread did not terminate within "
                    f"{self.STOP_TIMEOUT}s"
                )
            else:
                logger.debug("NoteScheduler thread stopped successfully")

        self._thread = None

    def restart(self):
        """Startet den Scheduler nach stop() erneut."""
        with self._lock:
            if self._active:
                return  # Läuft schon
        self._start_thread()

    def is_alive(self) -> bool:
        """Prüft ob der Thread noch lebt."""
        thread = self._thread
        return thread is not None and thread.is_alive()

    # ==================== Interne Methoden ====================

    def _start_thread(self):
        """Startet den Scheduler-Thread."""
        with self._lock:
            if self._active:
                return  # Schon aktiv

            self._stop_event.clear()
            self._thread = Thread(
                target=self._run,
                daemon=True,
                name="NoteSchedulerThread",
            )
            self._active = True
            self._thread.start()

        logger.debug("NoteScheduler thread started")

    def _run(self):
        """Haupt-Loop: verarbeitet fällige Keys, schläft zwischen Checks."""
        logger.debug("NoteScheduler loop entered")

        try:
            while not self._stop_event.is_set():
                keys_to_process = self._pop_due_keys()

                # Keys verarbeiten (außerhalb des Locks!)
                for key in keys_to_process:
                    if self._stop_event.is_set():
                        break
                    try:
                        self._callback(key)
                    except Exception as e:
                        logger.error(f"Error releasing key {key!r}: {e}")

                # Sleep bis zum nächsten fälligen Key
                sleep_time = self._calculate_sleep_time()
                if sleep_time > 0:
                    time.sleep(sleep_time)

        except Exception as e:
            logger.critical(f"NoteScheduler crashed: {e}", exc_info=True)

        finally:
            with self._lock:
                self._active = False
            logger.debug("NoteScheduler loop exited")

    def _pop_due_keys(self) -> List[Any]:
        """Holt alle fälligen Keys aus der Queue (thread-safe)."""
        keys: List[Any] = []
        now = time.time()

        with self._lock:
            while self._queue and self._queue[0][0] <= now:
                _, _, key = heapq.heappop(self._queue)
                keys.append(key)

        return keys

    def _calculate_sleep_time(self) -> float:
        """Berechnet die optimale Sleep-Zeit bis zum nächsten Key."""
        with self._lock:
            if not self._queue:
                return self.IDLE_SLEEP

            next_time = self._queue[0][0]
            now = time.time()
            time_until_next = next_time - now

            # Direkt fällig oder minimal warten
            if time_until_next <= 0:
                return self.MIN_SLEEP

            return max(self.MIN_SLEEP, min(self.MAX_SLEEP, time_until_next))