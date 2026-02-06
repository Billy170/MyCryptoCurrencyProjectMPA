from ecdsa import SigningKey, SECP256k1, VerifyingKey

def create_wallet():
    sk = SigningKey.generate(curve=SECP256k1)
    vk = sk.get_verifying_key()
    return sk, vk

def sign_transaction(sk, tx):
    return sk.sign(str(tx).encode())

def verify_transaction(vk, tx, signature):
    try:
        return vk.verify(signature, str(tx).encode())
    except:
        return False
