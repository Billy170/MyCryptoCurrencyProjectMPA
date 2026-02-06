import time

try:
    from .mpa_crypto import verify_transaction
except ImportError:
    # Allow running this module directly from within the `core` directory.
    from mpa_crypto import verify_transaction

class Blockchain:
    def __init__(self):
        self.chain = []
        self.pending_transactions = []
        self.difficulty = 2
        self.used_nonces = set()

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
        block = {"index": len(self.chain)+1, "timestamp": time.time(), "transactions": self.pending_transactions, "miner": miner}
        self.chain.append(block)
        self.pending_transactions = []

    def current_reward(self):
        return 50
