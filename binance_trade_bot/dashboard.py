from flask import Flask, render_template_string, jsonify
import threading
import os
from datetime import datetime

app = Flask(__name__)

# Shared state to be updated by the bot
bot_status = {
    "current_coin": "Pending...",
    "bridge": "USDT",
    "balance": 0.0,
    "last_update": "Never",
    "trades": [],
    "is_active": False
}

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Binance Trade Bot | Dashboard</title>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600&display=swap" rel="stylesheet">
    <style>
        :root {
            --primary: #f3ba2f;
            --bg: #0b0e11;
            --card-bg: rgba(30, 35, 41, 0.7);
            --text: #eaecef;
            --text-dim: #848e9c;
            --success: #0ecb81;
            --danger: #f6465d;
        }

        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            font-family: 'Outfit', sans-serif;
        }

        body {
            background-color: var(--bg);
            background-image: radial-gradient(circle at 10% 20%, rgba(243, 186, 47, 0.05) 0%, transparent 40%),
                              radial-gradient(circle at 90% 80%, rgba(14, 203, 129, 0.05) 0%, transparent 40%);
            color: var(--text);
            min-height: 100vh;
            padding: 2rem;
        }

        .container {
            max-width: 1000px;
            margin: 0 auto;
        }

        header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 3rem;
            animation: fadeInDown 0.8s ease-out;
        }

        .logo {
            display: flex;
            align-items: center;
            gap: 12px;
        }

        .logo-icon {
            width: 40px;
            height: 40px;
            background: var(--primary);
            border-radius: 10px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 700;
            color: var(--bg);
            box-shadow: 0 0 20px rgba(243, 186, 47, 0.3);
        }

        .status-badge {
            padding: 6px 16px;
            border-radius: 20px;
            font-size: 0.85rem;
            font-weight: 600;
            display: flex;
            align-items: center;
            gap: 8px;
            background: rgba(14, 203, 129, 0.15);
            color: var(--success);
            border: 1px solid rgba(14, 203, 129, 0.3);
        }

        .status-dot {
            width: 8px;
            height: 8px;
            background: var(--success);
            border-radius: 50%;
            box-shadow: 0 0 10px var(--success);
            animation: pulse 2s infinite;
        }

        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 1.5rem;
            margin-bottom: 2rem;
        }

        .card {
            background: var(--card-bg);
            backdrop-filter: blur(12px);
            border: 1px solid rgba(255, 255, 255, 0.05);
            border-radius: 24px;
            padding: 2rem;
            transition: transform 0.3s ease, border-color 0.3s ease;
        }

        .card:hover {
            transform: translateY(-5px);
            border-color: rgba(243, 186, 47, 0.2);
        }

        .card-label {
            font-size: 0.9rem;
            color: var(--text-dim);
            margin-bottom: 8px;
            text-transform: uppercase;
            letter-spacing: 1px;
        }

        .card-value {
            font-size: 2.5rem;
            font-weight: 600;
            color: var(--text);
        }

        .card-value span {
            font-size: 1.2rem;
            color: var(--primary);
            margin-left: 8px;
        }

        .table-card {
            grid-column: 1 / -1;
        }

        table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 1rem;
        }

        th {
            text-align: left;
            color: var(--text-dim);
            font-weight: 400;
            padding: 12px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.05);
        }

        td {
            padding: 16px 12px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.03);
        }

        .type-buy { color: var(--success); }
        .type-sell { color: var(--danger); }

        @keyframes pulse {
            0% { opacity: 1; }
            50% { opacity: 0.4; }
            100% { opacity: 1; }
        }

        @keyframes fadeInDown {
            from { opacity: 0; transform: translateY(-20px); }
            to { opacity: 1; transform: translateY(0); }
        }

        @media (max-width: 600px) {
            body { padding: 1rem; }
            .card-value { font-size: 2rem; }
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div class="logo">
                <div class="logo-icon">B</div>
                <h1>Trade Bot</h1>
            </div>
            <div class="status-badge" id="bot-status">
                <div class="status-dot"></div>
                Live Analysis
            </div>
        </header>

        <div class="grid">
            <div class="card">
                <p class="card-label">Current Asset</p>
                <p class="card-value" id="current-coin">---</p>
            </div>
            <div class="card">
                <p class="card-label">Estimated Value</p>
                <p class="card-value" id="total-balance">0.00 <span>USDT</span></p>
            </div>
        </div>

        <div class="card table-card">
            <p class="card-label">Recent Activity</p>
            <table>
                <thead>
                    <tr>
                        <th>Time</th>
                        <th>Trade</th>
                        <th>Price</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody id="trade-list">
                    <tr><td colspan="4" style="text-align:center; color:var(--text-dim)">Scanning markets...</td></tr>
                </tbody>
            </table>
        </div>
    </div>

    <script>
        async function updateDashboard() {
            try {
                const response = await fetch('/api/status');
                const data = await response.json();
                
                document.getElementById('current-coin').innerText = data.current_coin;
                document.getElementById('total-balance').innerHTML = `${data.balance.toFixed(2)} <span>${data.bridge}</span>`;
                
                const tradeList = document.getElementById('trade-list');
                if (data.trades && data.trades.length > 0) {
                    tradeList.innerHTML = data.trades.map(t => `
                        <tr>
                            <td>${t.time}</td>
                            <td class="type-${t.type.toLowerCase()}">${t.pair} (${t.type})</td>
                            <td>${t.price}</td>
                            <td>Complete</td>
                        </tr>
                    `).join('');
                }
            } catch (error) {
                console.error('Failed to fetch status:', error);
            }
        }

        setInterval(updateDashboard, 5000);
        updateDashboard();
    </script>
</body>
</html>
"""

@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route("/api/status")
def status():
    return jsonify(bot_status)

@app.route("/api/ping")
def ping():
    return jsonify({"status": "ok", "timestamp": datetime.now().isoformat()})

def run_dashboard():
    port = int(os.environ.get("PORT", 5000))
    # Use threaded=True to ensure it doesn't block the bot's updates
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

def start_dashboard():
    thread = threading.Thread(target=run_dashboard, daemon=True)
    thread.start()
    return thread
