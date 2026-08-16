"""
MARKUS OS CRDT State Store (Port of SUPRIME DistributedStore)
Provides gossip-replicated last-writer-wins key/value storage with
tombstone-safe deletion and WAL hooks for mesh state convergence.

Ported from SUPRIME's suprime/store.py — preserves the exact merge semantics
(commutative, associative, idempotent) for cross-repo compatibility.

Integration point: markus_router.py uses this for shared state sync across
mesh nodes. markus_mesh.py PeerTable.digest() feeds into this store's
apply_digest() for gossip convergence.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple


@dataclass(frozen=True)
class Version:
    """A causality tag for a store entry.

    Ordering is by ts first, then by origin as a deterministic tie-breaker
    so concurrent writes resolve identically on every replica.
    """
    ts: float
    origin: str

    def __gt__(self, other: "Version") -> bool:
        return (self.ts, self.origin) > (other.ts, other.origin)

    def __ge__(self, other: "Version") -> bool:
        return (self.ts, self.origin) >= (other.ts, other.origin)

    def __lt__(self, other: "Version") -> bool:
        return (self.ts, self.origin) < (other.ts, other.origin)

    def __le__(self, other: "Version") -> bool:
        return (self.ts, self.origin) <= (other.ts, other.origin)


@dataclass
class Entry:
    """A versioned key/value entry in the distributed store.

    Tombstones (deleted=True) let deletions propagate through gossip
    like any other write — prevents resurrecting stale keys.
    """
    value: Any
    version: Version
    deleted: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "value": self.value,
            "ts": self.version.ts,
            "origin": self.version.origin,
            "deleted": self.deleted,
        }

    @classmethod
    def from_dict(cls, key_data: Dict[str, Any]) -> "Entry":
        return cls(
            value=key_data.get("value"),
            version=Version(ts=key_data["ts"], origin=str(key_data["origin"])),
            deleted=bool(key_data.get("deleted", False)),
        )


class DistributedStore:
    """A gossip-replicated LWW key/value map.

    Ported from SUPRIME (suprime/store.py) — pure state, no I/O, deterministic.
    All replicas that observe the same set of writes converge to the same
    state regardless of message order or duplication.

    Args:
        node_id: The owning node, used as the origin on local writes.
        clock: Injectable time source for versioning; defaults to time.time.
    """

    def __init__(self, node_id: str, clock: Callable[[], float] = time.time) -> None:
        self._node_id = node_id
        self._clock = clock
        self._data: Dict[str, Entry] = {}
        self._subscribers: List[Callable[[str, Any], None]] = []
        self._commit_subs: List[Callable[[str, Entry], None]] = []
        self._highest_ts: float = 0.0

    def _next_version(self) -> Version:
        """Generate a monotonically increasing version tag."""
        ts = self._clock()
        if ts <= self._highest_ts:
            ts = self._highest_ts + 1e-6
        self._highest_ts = ts
        return Version(ts=ts, origin=self._node_id)

    def set(self, key: str, value: Any) -> Entry:
        """Write value at key with a fresh local version."""
        entry = Entry(value=value, version=self._next_version(), deleted=False)
        self._data[key] = entry
        self._notify(key, value)
        self._emit_commit(key, entry)
        return entry

    def delete(self, key: str) -> Optional[Entry]:
        """Tombstone key so deletion replicates through gossip."""
        if key not in self._data:
            return None
        entry = Entry(value=None, version=self._next_version(), deleted=True)
        self._data[key] = entry
        self._notify(key, None)
        self._emit_commit(key, entry)
        return entry

    def get(self, key: str, default: Any = None) -> Any:
        """Get the value for key, or default if not found/deleted."""
        entry = self._data.get(key)
        if entry is None or entry.deleted:
            return default
        return entry.value

    def entry(self, key: str) -> Optional[Entry]:
        """Return the raw versioned Entry for key (or None)."""
        return self._data.get(key)

    def __contains__(self, key: object) -> bool:
        entry = self._data.get(key)  # type: ignore[arg-type]
        return entry is not None and not entry.deleted

    def items(self) -> List[Tuple[str, Any]]:
        """Return all live (non-deleted) key/value pairs."""
        return [(k, e.value) for k, e in self._data.items() if not e.deleted]

    def keys(self) -> List[str]:
        """Return all live keys."""
        return [k for k, e in self._data.items() if not e.deleted]

    # -- Replication --------------------------------------------------------

    def merge_entry(self, key: str, entry: Entry) -> bool:
        """Merge a single remote entry; returns True if state changed."""
        current = self._data.get(key)
        if current is None or entry.version > current.version:
            self._data[key] = entry
            if entry.version.origin == self._node_id and entry.version.ts > self._highest_ts:
                self._highest_ts = entry.version.ts
            if not entry.deleted:
                self._notify(key, entry.value)
            self._emit_commit(key, entry)
            return True
        return False

    def merge(self, snapshot: Iterable[Tuple[str, Entry]]) -> bool:
        """Merge a batch of (key, entry) pairs from a remote replica."""
        changed = False
        for key, entry in snapshot:
            if self.merge_entry(key, entry):
                changed = True
        return changed

    def digest(self) -> Dict[str, Dict[str, Any]]:
        """A serialisable snapshot of every entry (including tombstones)."""
        return {k: e.to_dict() for k, e in self._data.items()}

    def apply_digest(self, digest: Dict[str, Dict[str, Any]]) -> bool:
        """Merge a digest from a gossip message."""
        return self.merge(
            (key, Entry.from_dict(data)) for key, data in digest.items()
        )

    def tombstones(self) -> int:
        """Count deleted-but-retained entries."""
        return sum(1 for e in self._data.values() if e.deleted)

    def collect_garbage(self, min_age: float) -> int:
        """Purge tombstones older than min_age seconds.

        Deletions must linger as tombstones long enough to propagate.
        min_age should exceed worst-case propagation + node-downtime window.
        """
        now = self._clock()
        stale = [
            k for k, e in self._data.items()
            if e.deleted and (now - e.version.ts) >= min_age
        ]
        for key in stale:
            del self._data[key]
        return len(stale)

    # -- Observation --------------------------------------------------------

    def subscribe(self, callback: Callable[[str, Any], None]) -> None:
        """Register a callback invoked as callback(key, value) on change."""
        self._subscribers.append(callback)

    def _notify(self, key: str, value: Any) -> None:
        for callback in self._subscribers:
            callback(key, value)

    def on_commit(self, callback: Callable[[str, Entry], None]) -> None:
        """Register a callback invoked with (key, entry) on every commit.

        Unlike subscribe(), this passes the full versioned Entry (including
        tombstones), which is what a durable WAL needs.
        """
        self._commit_subs.append(callback)

    def _emit_commit(self, key: str, entry: "Entry") -> None:
        for callback in self._commit_subs:
            callback(key, entry)

    # -- Queries ------------------------------------------------------------

    @property
    def node_id(self) -> str:
        return self._node_id

    def __len__(self) -> int:
        return len([e for e in self._data.values() if not e.deleted])

    def __repr__(self) -> str:
        live = len(self)
        tombs = self.tombstones()
        return f"DistributedStore(node_id={self._node_id!r}, entries={live}, tombstones={tombs})"


if __name__ == "__main__":
    # Self-test
    store_a = DistributedStore(node_id="node-a")
    store_b = DistributedStore(node_id="node-b")

    # Write on A
    store_a.set("greeting", "hello swarm")
    store_a.set("count", 42)

    # Gossip digest from A → B
    digest = store_a.digest()
    store_b.apply_digest(digest)

    # Write on B (concurrent write to same key)
    store_b.set("greeting", "hello from B")

    # Gossip back: B's newer write should win
    store_b_digest = store_b.digest()
    store_a.apply_digest(store_b_digest)

    # Both should converge
    assert store_a.get("greeting") == store_b.get("greeting"), "CRDT convergence failure!"
    print(f"[CRDT] Converged greeting: {store_a.get('greeting')}")
    print(f"[CRDT] Store A: {store_a}")
    print(f"[CRDT] Store B: {store_b}")
    print("[CRDT] Self-test PASSED — convergence verified")
