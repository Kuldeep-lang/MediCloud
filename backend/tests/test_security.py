"""Password-hashing safeguards."""

import threading
import time
from concurrent.futures import ThreadPoolExecutor

from app.core import security


class SlowTrackingHasher:
    """Stands in for Argon2: records how many hashes run at the same time."""

    def __init__(self) -> None:
        self.active = 0
        self.peak = 0
        self.lock = threading.Lock()

    def verify(self, password: str, hashed: str) -> bool:
        with self.lock:
            self.active += 1
            self.peak = max(self.peak, self.active)
        time.sleep(0.05)
        with self.lock:
            self.active -= 1
        return password == hashed


def test_concurrent_password_hashing_is_capped(monkeypatch):
    """A login flood must not run unbounded memory-hard hashes in parallel (OOM risk)."""
    fake = SlowTrackingHasher()
    monkeypatch.setattr(security, "password_hash", fake)
    with ThreadPoolExecutor(max_workers=20) as pool:
        results = list(pool.map(lambda i: security.verify_password("pw", "pw"), range(20)))
    assert all(results)
    assert fake.peak == security.MAX_CONCURRENT_HASHES
