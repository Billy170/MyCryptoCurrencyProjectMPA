import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from flask import Flask, render_template_string
from pool.mpa_pool_server import miners, balances

app = Flask(__name__)

tpl = """
<h2>MPA Pool Dashboard</h2>
<h3>Miners</h3>
<ul>{% for m,v in miners.items() %}<li>{{m}} shares={{v['shares']}}</li>{% endfor %}</ul>
<h3>Balances</h3>
<ul>{% for m,b in balances.items() %}<li>{{m}} => {{b}} MPA</li>{% endfor %}</ul>
"""

@app.route("/")
def home():
    return render_template_string(tpl, miners=miners, balances=balances)

if __name__ == "__main__":
    app.run(port=8080)
