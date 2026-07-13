"""Simple in-memory rate limiter. No external dependencies."""
import time
from collections import defaultdict
from typing import Dict, Tuple


class RateLimiter:
    """Track request counts per key within a time window."""

    def __init__(self, max_requests: int = 5, window_seconds: int = 60, block_seconds: int = 900):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.block_seconds = block_seconds
        self._attempts: Dict[str, list] = defaultdict(list)
        self._blocked: Dict[str, float] = {}

    def _cleanup(self):
        """Periodically remove expired entries to prevent memory leak."""
        now = time.time()
        self._attempts = {k: [t for t in v if now - t < self.window_seconds]
                          for k, v in self._attempts.items() if v}
        self._blocked = {k: until for k, until in self._blocked.items() if until > now}

    def is_blocked(self, key: str) -> Tuple[bool, int]:
        """Returns (is_blocked, seconds_remaining)."""
        now = time.time()
        if key in self._blocked:
            remaining = int(self._blocked[key] - now)
            if remaining > 0:
                return True, remaining
            del self._blocked[key]
        return False, 0

    def record_attempt(self, key: str) -> Tuple[bool, int]:
        """Record a failed attempt. Returns (is_now_blocked, seconds_remaining)."""
        now = time.time()
        self._attempts[key].append(now)
        # Keep only recent attempts
        cutoff = now - self.window_seconds
        self._attempts[key] = [t for t in self._attempts[key] if t > cutoff]

        if len(self._attempts[key]) >= self.max_requests:
            self._blocked[key] = now + self.block_seconds
            return True, self.block_seconds

        # Periodic cleanup every ~1000 calls
        if sum(len(v) for v in self._attempts.values()) % 1000 < 1:
            self._cleanup()

        return False, 0

    def reset(self, key: str):
        """Reset rate limit for a key (e.g., after successful login)."""
        self._attempts.pop(key, None)
        self._blocked.pop(key, None)


# Global instance for login endpoints
login_limiter = RateLimiter(max_requests=5, window_seconds=60, block_seconds=900)
