import time
from collections import defaultdict, deque

class RateLimiter:
    """
    Simple in-memory rate limiter (per pod). Good enough for stage-1.
    For multi-replica strictness, move state to Redis later.
    """
    def __init__(self, window_sec: int, max_attempts: int):
        self.window_sec = window_sec
        self.max_attempts = max_attempts
        self._hits = defaultdict(lambda: deque())

    def limited(self, key: str) -> bool:
        now = time.time()
        q = self._hits[key]
        while q and (now - q[0]) > self.window_sec:
            q.popleft()
        return len(q) >= self.max_attempts

    def note(self, key: str) -> None:
        self._hits[key].append(time.time())
