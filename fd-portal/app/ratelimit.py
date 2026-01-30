import time
from dataclasses import dataclass
from collections import defaultdict, deque

@dataclass(frozen=True)
class DefenseState:
    failures: int
    captcha_required: bool
    locked_out: bool
    lockout_seconds_left: int

class LoginDefense:
    """
    In-memory (per pod) defense state machine keyed by a stable client key.
    Uses LoginPolicy as the single source of truth for thresholds.
    """

    def __init__(self, policy, window_sec: int = 900, soft_lockout_sec: int = 300):
        self.policy = policy
        self.window_sec = window_sec
        self.soft_lockout_sec = soft_lockout_sec

        self._hits = defaultdict(lambda: deque())  # key -> deque[timestamps]
        self._lockout_until = {}                   # key -> unix ts

    def _prune(self, key: str) -> None:
        now = time.time()
        q = self._hits[key]
        while q and (now - q[0]) > self.window_sec:
            q.popleft()

    def state(self, key: str) -> DefenseState:
        now = time.time()
        self._prune(key)

        failures = len(self._hits[key])

        until = self._lockout_until.get(key, 0)
        locked = now < until
        left = int(until - now) if locked else 0

        # Captcha starts at (policy.captcha_start_failure), e.g. 5th failure
        captcha_required = failures >= self.policy.captcha_start_failure

        # Simulate block/lockout at policy.block_after_failure, e.g. 7th failure
        if failures >= self.policy.block_after_failure and not locked:
            self._lockout_until[key] = now + self.soft_lockout_sec
            locked = True
            left = int(self.soft_lockout_sec)

        return DefenseState(
            failures=failures,
            captcha_required=captcha_required,
            locked_out=locked,
            lockout_seconds_left=left,
        )

    def record_failure(self, key: str) -> DefenseState:
        self._prune(key)
        self._hits[key].append(time.time())
        return self.state(key)

    def reset(self, key: str) -> None:
        self._hits.pop(key, None)
        self._lockout_until.pop(key, None)

