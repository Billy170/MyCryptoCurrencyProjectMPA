from flask import Flask
app = Flask(__name__)

@app.route("/admin")
def admin():
    return {
        "blocks": len(bc.chain),
        "difficulty": bc.difficulty,
        "miners": list(miners),
        "balances": balances,
        "hashrate": total_hashrate(),
        "shares": total_shares()
    }

app.run(port=9000)
