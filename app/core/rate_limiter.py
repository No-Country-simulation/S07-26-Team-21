import asyncio
from collections import deque
import time


class SlidingWindowRateLimiter:
    """
    Rate limiter asíncrono basado en ventana deslizante (Sliding Window Log).
    Previene activamente fugas de memoria (Memory Leaks) mediante la limpieza
    continua de marcas de tiempo que quedan fuera de la ventana temporal.
    """

    def __init__(self, max_requests: int = 30, window_seconds: float = 60.0):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._timestamps: deque[float] = deque()
        self._lock = asyncio.Lock()

    def _cleanup_old_timestamps(self, now: float) -> None:
        """
        Elimina en O(1) amortizado todas las marcas de tiempo que superan
        el límite de la ventana temporal.
        """
        cutoff = now - self.window_seconds
        while self._timestamps and self._timestamps[0] <= cutoff:
            self._timestamps.popleft()

    async def acquire(self) -> bool:
        """
        Intenta consumir un cupo de request dentro de la ventana deslizante.
        Retorna True si el request es permitido, o False si superó la cuota.
        """
        async with self._lock:
            now = time.monotonic()
            self._cleanup_old_timestamps(now)

            if len(self._timestamps) < self.max_requests:
                self._timestamps.append(now)
                return True
            return False

    async def reset(self) -> None:
        """
        Limpia todos los registros del rate limiter (útil para tests).
        """
        async with self._lock:
            self._timestamps.clear()

    @property
    def current_count(self) -> int:
        """
        Retorna la cantidad actual de requests activos en la ventana (tras limpieza).
        """
        now = time.monotonic()
        self._cleanup_old_timestamps(now)
        return len(self._timestamps)
