from flask import Flask, render_template_string
from pool.mpa_pool_server import miners,balances

app=Flask(__name__)
HTML="""
<h2>MPA Pool</h2>
<p>Miners: {{ miners }}</p>
<table border=1>
<tr><th>Miner</th><th>Balance</th></tr>
{% for m,b in balances.items() %}<tr><td>{{m}}</td><td>{{b:.4f}}</td></tr>{% endfor %}
</table>
"""

@app.route("/")
def index(): return render_template_string(HTML, miners=len(miners), balances=balances)
app.run(port=8080)
