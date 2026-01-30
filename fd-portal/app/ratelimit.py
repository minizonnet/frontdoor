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
    In-memory (per pod) login defense state machine keyed by client IP.

    Policy:
      - failures 1..3: no captcha; show remaining tries (2,1,0)
      - failure 4: no captcha; warn "captcha on next attempt"
      - failures 5..6: captcha required; warn "2 more incorrect and your IP will be blocked" then "1 more..."
      - failures >=7: treat as locked out (simulate block for now)
    """

    def __init__(
        self,
        window_sec: int = 900,                # reset counters after inactivity window
        soft_lockout_sec: int = 300,          # when failures>=7, simulate a lockout
        captcha_after_failures: int = 4,      # captcha starts on attempt #5 (after 4 failures)
        max_failures_before_block: int = 7,   # would block on 7th failure
    ):
        self.window_sec = window_sec
        self.soft_lockout_sec = soft_lockout_sec
        self.captcha_after_failures = captcha_after_failures
        self.max_failures_before_block = max_failures_before_block

        self._hits = defaultdict(lambda: deque())     # ip -> deque[timestamps]
        self._lockout_until = {}                      # ip -> unix ts

    def _prune(self, key: str) -> None:
        now = time.time()
        q = self._hits[key]
        while q and (now - q[0]) > self.window_sec:
            q.popleft()

    def state(self, key: str) -> DefenseState:
        now = time.time()
        self._prune(key)

        until = self._lockout_until.get(key, 0)
        locked = now < until
        left = int(until - now) if locked else 0

        failures = len(self._hits[key])
        captcha_required = failures >= (self.captcha_after_failures + 1)  # captcha from 5th attempt
        # If we have reached or exceeded the block threshold, consider locked (even if lockout timer not set yet)
        if failures >= self.max_failures_before_block and not locked:
            # start a soft lockout to simulate future IP blocking behavior
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

