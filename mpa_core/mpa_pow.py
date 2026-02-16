import hashlib
from typing import Tuple

# MPAALG: memory-hard PoW inspired by RandomX ideas (scratchpad + data-dependent rounds).
ALGORITHM_NAME = "MPAALG"
SCRATCHPAD_KB = 64
SCRATCHPAD_SIZE = SCRATCHPAD_KB * 1024
ROUNDS = 24


def _seed_bytes(header_hash: str, nonce: int) -> bytes:
    base = f"{ALGORITHM_NAME}|{header_hash}|{nonce}".encode()
    return hashlib.blake2b(base, digest_size=32).digest()


def _build_scratchpad(seed: bytes) -> bytearray:
    scratch = bytearray(SCRATCHPAD_SIZE)
    block = seed
    cursor = 0
    while cursor < SCRATCHPAD_SIZE:
        block = hashlib.blake2b(block + cursor.to_bytes(4, "little"), digest_size=64).digest()
        end = min(cursor + 64, SCRATCHPAD_SIZE)
        scratch[cursor:end] = block[: end - cursor]
        cursor = end
    return scratch


def mpaalg_hash(header_hash: str, nonce: int) -> str:
    """Compute MPAALG digest for (header_hash, nonce)."""
    seed = _seed_bytes(header_hash, int(nonce))
    scratch = _build_scratchpad(seed)
    acc = int.from_bytes(seed[:8], "little") ^ int.from_bytes(seed[8:16], "little")

    for r in range(ROUNDS):
        idx = (acc ^ (r * 0x9E3779B185EBCA87)) % (SCRATCHPAD_SIZE - 32)
        lane = bytes(scratch[idx : idx + 32])
        lane_int = int.from_bytes(lane[:8], "little")

        mixed = hashlib.sha3_256(
            lane
            + acc.to_bytes(8, "little", signed=False)
            + r.to_bytes(4, "little")
            + seed
        ).digest()
        m0 = int.from_bytes(mixed[:8], "little")
        m1 = int.from_bytes(mixed[8:16], "little")

        acc = ((acc + m0) ^ ((lane_int << 1) | (lane_int >> 63))) & 0xFFFFFFFFFFFFFFFF
        acc = (acc * (m1 | 1)) & 0xFFFFFFFFFFFFFFFF

        write_at = (idx + ((m0 ^ m1) & 0x3FF)) % (SCRATCHPAD_SIZE - 16)
        scratch[write_at : write_at + 16] = hashlib.blake2s(mixed + lane, digest_size=16).digest()

    final = hashlib.blake2b(seed + acc.to_bytes(8, "little") + bytes(scratch[:64]), digest_size=32).hexdigest()
    return final


def hash_meets_difficulty(pow_hash: str, difficulty: int) -> bool:
    return pow_hash.startswith("0" * int(max(1, round(difficulty))))


def mine_nonce(header_hash: str, difficulty: int, start_nonce: int = 0) -> Tuple[int, str]:
    nonce = int(start_nonce)
    while True:
        h = mpaalg_hash(header_hash, nonce)
        if hash_meets_difficulty(h, difficulty):
            return nonce, h
        nonce += 1
