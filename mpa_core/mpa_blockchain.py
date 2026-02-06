import hashlib
import json
import time

try:
    from .mpa_crypto import verify_transaction
except ImportError:
    # Allow running this module directly from within the `mpa_core` directory.
    from mpa_crypto import verify_transaction


class Blockchain:
    """Lightweight Bitcoin-style chain (PoW + prev-hash linking + merkle root)."""

    def __init__(self):
        self.chain = []
        self.pending_transactions = []
        self.difficulty = 3
        self.used_nonces = set()
        self._create_genesis_block()

    @staticmethod
    def _sha256(data: str) -> str:
        return hashlib.sha256(data.encode()).hexdigest()

    def _tx_hash(self, tx: dict) -> str:
        return self._sha256(json.dumps(tx, sort_keys=True))

    def _merkle_root(self, txs: list) -> str:
        if not txs:
            return self._sha256("EMPTY")
        layer = [self._tx_hash(tx) for tx in txs]
        while len(layer) > 1:
            if len(layer) % 2 == 1:
                layer.append(layer[-1])
            layer = [self._sha256(layer[i] + layer[i + 1]) for i in range(0, len(layer), 2)]
        return layer[0]

    def _block_header_hash(self, block: dict) -> str:
        header = {
            "index": block["index"],
            "timestamp": block["timestamp"],
            "prev_hash": block["prev_hash"],
            "merkle_root": block["merkle_root"],
            "nonce": block["nonce"],
            "miner": block.get("miner", ""),
            "difficulty": block["difficulty"],
        }
        return self._sha256(json.dumps(header, sort_keys=True))

    def _create_genesis_block(self):
        genesis = {
            "index": 0,
            "timestamp": time.time(),
            "prev_hash": "0" * 64,
            "transactions": [],
            "merkle_root": self._sha256("GENESIS"),
            "nonce": 0,
            "difficulty": self.difficulty,
            "miner": "GENESIS",
        }
        genesis["hash"] = self._block_header_hash(genesis)
        self.chain.append(genesis)

    def add_signed_transaction(self, sender, receiver, amount, nonce, public_key, signature):
        tx = {"sender": sender, "receiver": receiver, "amount": amount, "nonce": nonce, "coin": "MPA"}
        tx_id = f"{sender}:{nonce}"
        if tx_id in self.used_nonces:
            return False
        if verify_transaction(public_key, tx, signature):
            self.pending_transactions.append(tx)
            self.used_nonces.add(tx_id)
            return True
        return False

    def mine(self, miner):
        txs = list(self.pending_transactions)
        prev_hash = self.chain[-1]["hash"]
        block = {
            "index": len(self.chain),
            "timestamp": time.time(),
            "prev_hash": prev_hash,
            "transactions": txs,
            "merkle_root": self._merkle_root(txs),
            "nonce": 0,
            "difficulty": self.difficulty,
            "miner": miner,
        }
        target_prefix = "0" * self.difficulty
        while True:
            block_hash = self._block_header_hash(block)
            if block_hash.startswith(target_prefix):
                block["hash"] = block_hash
                break
            block["nonce"] += 1

        self.chain.append(block)
        self.pending_transactions = []
        return block

    def current_reward(self):
        return 50
