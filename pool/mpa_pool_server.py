import socket,json,threading
from core.mpa_blockchain import Blockchain

HOST="0.0.0.0";PORT=3333
bc=Blockchain();miners={};shares={};share_window=[];balances={}

def record_share(miner): share_window.append(miner);balances.setdefault(miner,0);
def distribute_pplns(block_reward):
    counts={};[counts.update({m:counts.get(m,0)+1}) for m in share_window[-10000:]]
    total=sum(counts.values())
    for miner,c in counts.items(): balances[miner]+=block_reward*(c/total)

def handle_miner(conn,addr):
    miner_id=None; buffer=b""
    while True:
        data=conn.recv(4096)
        if not data: break
        buffer+=data
        try: msg=json.loads(buffer.decode()); buffer=b""
        except: continue
        if msg["method"]=="mining.subscribe": conn.send(json.dumps({"result":True}).encode())
        elif msg["method"]=="mining.authorize": miner_id=msg["params"][0]; miners[miner_id]=addr; shares[miner_id]=0; conn.send(json.dumps({"result":True}).encode())
        elif msg["method"]=="mining.submit": miner=msg["params"][0]; record_share(miner); conn.send(json.dumps({"result":True}).encode())

s=socket.socket();s.bind((HOST,PORT));s.listen()
while True: conn,addr=s.accept();threading.Thread(target=handle_miner,args=(conn,addr),daemon=True).start()
