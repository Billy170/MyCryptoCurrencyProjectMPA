PAYOUT_THRESHOLD=5.0
def auto_payout(blockchain,balances):
    for miner,amount in list(balances.items()):
        if amount>=PAYOUT_THRESHOLD:
            blockchain.add_signed_transaction("SYSTEM",miner,amount,0,None,None)
            balances[miner]=0.0
