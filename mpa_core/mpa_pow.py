import hashlib

DAG_MB = 512

def build_dag(seed):
    words = (DAG_MB * 1024 * 1024) // 4
    import numpy as np
    rng = np.random.RandomState(seed)
    return rng.randint(0, 2**32, size=words, dtype='uint32')

def ethash(header_hash, nonce, dag):
    idx = int(hashlib.sha256(f"{header_hash}{nonce}".encode()).hexdigest(), 16)
    mix = dag[idx % dag.size]
    for i in range(64):
        mix ^= dag[(idx + mix + i) % dag.size]
    return hashlib.sha256(str(int(mix)).encode()).hexdigest()
