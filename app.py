import os
import csv
import io
import time
import requests
import firebase_admin
from firebase_admin import credentials, db
from flask import Flask, render_template_string, request, redirect, url_for, Response

app = Flask(__name__)

# Firebase Initialization
FIREBASE_URL = os.getenv("FIREBASE_URL", "https://YOUR-FIREBASE-URL.firebaseio.com/")
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")

if not firebase_admin._apps:
    cred_path = "secret_key.json"
    if os.path.exists(cred_path):
        cred = credentials.Certificate(cred_path)
        firebase_admin.initialize_app(cred, {'databaseURL': FIREBASE_URL})
    else:
        print("⚠️ secret_key.json not found! Please check secrets.")

def get_settings():
    settings = db.reference('settings').get() or {}
    return {
        'task_reward': float(settings.get('task_reward', 20.0)),
        'referral_reward': float(settings.get('referral_reward', 5.0)),
        'min_withdraw': float(settings.get('min_withdraw', 50.0)),
        'channel_link': settings.get('channel_link', 'https://t.me/telegram')
    }

def send_telegram_msg(chat_id, text):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        data = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
        requests.post(url, data=data, timeout=5)
    except Exception as e:
        print("Telegram Send Error:", e)

def broadcast_to_all(text):
    try:
        users_ref = db.reference('users').get() or {}
        for u_id in users_ref.keys():
            send_telegram_msg(u_id, text)
    except Exception as e:
        print("Broadcast Error:", e)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en" data-bs-theme="dark">
<head>
    <meta charset="UTF-8">
    <title>SaaS Pro Task Admin Dashboard</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.5/font/bootstrap-icons.css">
    <style>
        body { background-color: #0f172a; color: #f8fafc; font-family: 'Inter', system-ui, sans-serif; }
        .card-stat { background: #1e293b; border: 1px solid #334155; border-radius: 12px; }
        .user-group-card { background: #1e293b; border: 1px solid #334155; border-radius: 14px; padding: 20px; margin-bottom: 25px; }
        .badge-pending { background: #78350f; color: #fef3c7; }
        .badge-approved { background: #064e3b; color: #a7f3d0; }
        .badge-rejected { background: #7f1d1d; color: #fecaca; }
        .action-btn { font-size: 0.82rem; border-radius: 6px; font-weight: 500; }
        .nav-tabs .nav-link.active { background-color: #3b82f6; color: white; border: none; }
        .nav-tabs .nav-link { color: #94a3b8; border: none; }
    </style>
</head>
<body class="p-3 p-md-4">
    <div class="container-fluid max-width-1400">
        <!-- HEADER -->
        <div class="d-flex flex-wrap justify-content-between align-items-center mb-4 pb-3 border-bottom border-secondary gap-2">
            <div>
                <h2 class="fw-bold text-white mb-0"><i class="bi bi-cpu text-primary me-2"></i>SaaS Pro Task Control Center</h2>
                <small class="text-secondary">Firebase Cloud Powered Realtime Platform</small>
            </div>
            <div class="d-flex gap-2 align-items-center">
                <input type="text" id="searchInput" onkeyup="filterTables()" class="form-control form-control-sm bg-dark text-white border-secondary" style="width: 240px;" placeholder="🔍 Search User ID, Name...">
                <a href="/download-csv" class="btn btn-sm btn-outline-light"><i class="bi bi-download me-1"></i>CSV Export</a>
            </div>
        </div>

        <!-- CONFIGURATION & SETTINGS MODAL CARD -->
        <div class="card card-stat p-3 mb-4">
            <h5 class="fw-bold text-primary mb-3"><i class="bi bi-sliders me-2"></i>Live Dynamic Settings</h5>
            <form action="/update-settings" method="POST" class="row g-3 align-items-center">
                <div class="col-6 col-md-3">
                    <label class="form-label small text-secondary">Task Reward (₹)</label>
                    <input type="number" step="0.5" name="task_reward" value="{{ settings['task_reward'] }}" class="form-control form-control-sm bg-dark text-white border-secondary" required>
                </div>
                <div class="col-6 col-md-3">
                    <label class="form-label small text-secondary">Referral Reward (₹)</label>
                    <input type="number" step="0.5" name="referral_reward" value="{{ settings['referral_reward'] }}" class="form-control form-control-sm bg-dark text-white border-secondary" required>
                </div>
                <div class="col-6 col-md-3">
                    <label class="form-label small text-secondary">Min Withdrawal (₹)</label>
                    <input type="number" step="1" name="min_withdraw" value="{{ settings['min_withdraw'] }}" class="form-control form-control-sm bg-dark text-white border-secondary" required>
                </div>
                <div class="col-6 col-md-3">
                    <label class="form-label small text-secondary">&nbsp;</label>
                    <button type="submit" class="btn btn-primary btn-sm w-100 fw-bold">Save Settings</button>
                </div>
            </form>
        </div>

        <!-- STATS CARDS -->
        <div class="row g-3 mb-4">
            <div class="col-6 col-lg-3">
                <div class="card card-stat p-3 border-start border-4 border-primary">
                    <div class="text-secondary small fw-bold">TOTAL USERS</div>
                    <div class="fs-2 fw-bold text-white mt-1">{{ total_users }}</div>
                </div>
            </div>
            <div class="col-6 col-lg-3">
                <div class="card card-stat p-3 border-start border-4 border-success">
                    <div class="text-secondary small fw-bold">TOTAL SUBMISSIONS</div>
                    <div class="fs-2 fw-bold text-success mt-1">{{ total_submissions }}</div>
                </div>
            </div>
            <div class="col-6 col-lg-3">
                <div class="card card-stat p-3 border-start border-4 border-warning">
                    <div class="text-secondary small fw-bold">PENDING APPROVALS</div>
                    <div class="fs-2 fw-bold text-warning mt-1">{{ pending_count }}</div>
                </div>
            </div>
            <div class="col-6 col-lg-3">
                <div class="card card-stat p-3 border-start border-4 border-info">
                    <div class="text-secondary small fw-bold">PENDING PAYOUTS</div>
                    <div class="fs-2 fw-bold text-info mt-1">{{ pending_withdraws }}</div>
                </div>
            </div>
        </div>

        <!-- BROADCAST SECTION -->
        <div class="card card-stat p-3 mb-4">
            <h5 class="fw-bold text-info mb-2"><i class="bi bi-megaphone me-2"></i>Broadcast Announcement</h5>
            <form action="/broadcast" method="POST" class="d-flex gap-2">
                <input type="text" name="message" class="form-control form-control-sm bg-dark text-white border-secondary" placeholder="Enter message to broadcast to ALL users..." required>
                <button type="submit" class="btn btn-info btn-sm fw-bold px-4">Send Broadcast</button>
            </form>
        </div>

        <!-- SUBMISSIONS LIST -->
        <h4 class="fw-bold mb-3"><i class="bi bi-people-fill text-primary me-2"></i>User Submissions</h4>
        
        {% for u_id, u_data in grouped_users.items() %}
        <div class="user-group-card searchable-user-card">
            <div class="d-flex flex-wrap justify-content-between align-items-center border-bottom border-secondary pb-2 mb-3">
                <div>
                    <h5 class="fw-bold text-white mb-0">{{ u_data['info'].get('first_name') or 'User' }} 
                        <span class="text-primary fs-6">(@{{ u_data['info'].get('username') if u_data['info'].get('username') else 'no_username' }})</span>
                        {% if u_data['info'].get('banned') %}
                            <span class="badge bg-danger ms-2">BANNED</span>
                        {% endif %}
                    </h5>
                    <small class="text-secondary">User ID: <code>{{ u_id }}</code> | UPI: <b class="text-light">{{ u_data['info'].get('upi_id') or 'Not Added' }}</b> | Referred By: <code>{{ u_data['info'].get('referred_by') or 'None' }}</code></small>
                </div>
                <div class="d-flex gap-2 align-items-center mt-2 mt-md-0">
                    <span class="badge bg-success fs-6">Balance: ₹{{ u_data['info'].get('balance', 0) }}</span>
                    <a href="/toggle-ban/{{ u_id }}" class="btn btn-sm {{ 'btn-outline-warning' if u_data['info'].get('banned') else 'btn-outline-danger' }} action-btn">
                        {{ 'Unban User' if u_data['info'].get('banned') else 'Ban User' }}
                    </a>
                </div>
            </div>

            <div class="table-responsive">
                <table class="table table-dark table-hover align-middle mb-0">
                    <thead>
                        <tr>
                            <th>Task ID</th>
                            <th>Email Submitted</th>
                            <th>Proof Screenshot</th>
                            <th>Status</th>
                            <th>Submitted At</th>
                            <th>Action</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for task in u_data['tasks'] %}
                        <tr>
                            <td><b>#{{ task['id'] }}</b></td>
                            <td><code>{{ task['assigned_email'] }}</code></td>
                            <td>
                                {% if task.get('screenshot_id') %}
                                <button class="btn btn-sm btn-outline-info action-btn" onclick="openPhotoModal('{{ task['screenshot_id'] }}')">
                                    <i class="bi bi-image me-1"></i>View Proof
                                </button>
                                {% else %}
                                <span class="text-secondary small">No Proof</span>
                                {% endif %}
                            </td>
                            <td>
                                {% if task['status'] == 'Approved' %}
                                    <span class="badge badge-approved px-2 py-1 rounded">Approved</span>
                                {% elif task['status'] == 'Rejected' %}
                                    <span class="badge badge-rejected px-2 py-1 rounded">Rejected</span>
                                {% else %}
                                    <span class="badge badge-pending px-2 py-1 rounded">Pending</span>
                                {% endif %}
                            </td>
                            <td><small class="text-secondary">{{ task.get('submission_time') or 'Just now' }}</small></td>
                            <td>
                                {% if task['status'] == 'Pending' %}
                                <a href="/task-action/approve/{{ task['id'] }}/{{ u_id }}" class="btn btn-success action-btn"><i class="bi bi-check-lg"></i> Approve (+₹{{ settings['task_reward'] }})</a>
                                <a href="/task-action/reject/{{ task['id'] }}/{{ u_id }}" class="btn btn-danger action-btn"><i class="bi bi-x-lg"></i> Reject</a>
                                {% else %}
                                <span class="text-secondary small">Completed</span>
                                {% endif %}
                            </td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
        {% else %}
        <div class="alert alert-secondary bg-dark text-white border-secondary">No task submissions yet.</div>
        {% endfor %}

        <!-- WITHDRAWAL REQUESTS SECTION -->
        <div class="card card-stat p-4 mb-4">
            <h5 class="fw-bold mb-3 text-white"><i class="bi bi-wallet2 text-success me-2"></i>Withdrawal Requests</h5>
            <div class="table-responsive">
                <table class="table table-dark table-hover align-middle mb-0">
                    <thead>
                        <tr>
                            <th>Req ID</th>
                            <th>User ID</th>
                            <th>UPI Address</th>
                            <th>Amount</th>
                            <th>Status</th>
                            <th>Action</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for w in withdrawals %}
                        <tr>
                            <td>#{{ w['id'] }}</td>
                            <td><code>{{ w['user_id'] }}</code></td>
                            <td><b class="text-info">{{ w['upi_id'] }}</b></td>
                            <td><span class="fw-bold text-success">₹{{ w['amount'] }}</span></td>
                            <td>
                                <span class="badge {{ 'badge-approved' if w['status'] == 'Paid' else 'badge-pending' }} px-2 py-1 rounded">{{ w['status'] }}</span>
                            </td>
                            <td>
                                {% if w['status'] == 'Pending' %}
                                <a href="/payout/pay/{{ w['id'] }}/{{ w['user_id'] }}/{{ w['amount'] }}" class="btn btn-primary action-btn"><i class="bi bi-send me-1"></i>Mark Paid & Broadcast</a>
                                {% else %}
                                <span class="text-secondary small">Paid</span>
                                {% endif %}
                            </td>
                        </tr>
                        {% else %}
                        <tr><td colspan="6" class="text-center text-secondary">No payout requests right now.</td></tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
    </div>

    <!-- SCREENSHOT MODAL -->
    <div class="modal fade" id="photoModal" tabindex="-1" aria-hidden="true">
        <div class="modal-dialog modal-dialog-centered">
            <div class="modal-content bg-dark text-white border-secondary">
                <div class="modal-header border-secondary">
                    <h5 class="modal-title fw-bold">Proof Screenshot</h5>
                    <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
                </div>
                <div class="modal-body text-center p-3">
                    <img id="modalImage" src="" class="img-fluid rounded border border-secondary shadow-sm" style="max-height: 480px;">
                </div>
            </div>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        function openPhotoModal(fileId) {
            var modalImage = document.getElementById('modalImage');
            modalImage.src = "/get-telegram-photo/" + fileId;
            var myModal = new bootstrap.Modal(document.getElementById('photoModal'));
            myModal.show();
        }

        function filterTables() {
            var input = document.getElementById("searchInput");
            var filter = input.value.toLowerCase();
            var cards = document.getElementsByClassName("searchable-user-card");

            for (var i = 0; i < cards.length; i++) {
                var text = cards[i].textContent || cards[i].innerText;
                if (text.toLowerCase().indexOf(filter) > -1) {
                    cards[i].style.display = "";
                } else {
                    cards[i].style.display = "none";
                }
            }
        }
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    settings = get_settings()
    users_data = db.reference('users').get() or {}
    tasks_data = db.reference('tasks').get() or {}
    withdrawals_data = db.reference('withdrawals').get() or {}

    tasks_list = [t for t in tasks_data.values() if t and t.get('screenshot_id')]
    tasks_list.sort(key=lambda x: str(x.get('submission_time', '')), reverse=True)

    withdrawals = list(withdrawals_data.values()) if isinstance(withdrawals_data, dict) else []
    withdrawals.sort(key=lambda x: str(x.get('created_at', '')), reverse=True)

    grouped_users = {}
    for uid, uinfo in users_data.items():
        u_tasks = [t for t in tasks_list if str(t.get('user_id')) == str(uid)]
        if u_tasks:
            grouped_users[uid] = {'info': uinfo, 'tasks': u_tasks}

    total_users = len(users_data)
    total_submissions = len(tasks_list)
    pending_count = sum(1 for t in tasks_list if t.get('status') == 'Pending')
    pending_withdraws = sum(1 for w in withdrawals if w.get('status') == 'Pending')

    return render_template_string(HTML_TEMPLATE, grouped_users=grouped_users, withdrawals=withdrawals, 
                                  total_users=total_users, total_submissions=total_submissions,
                                  pending_count=pending_count, pending_withdraws=pending_withdraws, settings=settings)

@app.route('/update-settings', methods=['POST'])
def update_settings():
    db.reference('settings').update({
        'task_reward': float(request.form.get('task_reward', 20.0)),
        'referral_reward': float(request.form.get('referral_reward', 5.0)),
        'min_withdraw': float(request.form.get('min_withdraw', 50.0))
    })
    return redirect(url_for('index'))

@app.route('/broadcast', methods=['POST'])
def handle_broadcast():
    msg = request.form.get('message')
    if msg:
        broadcast_to_all(f"📢 <b>ADMIN ANNOUNCEMENT:</b>\n\n{msg}")
    return redirect(url_for('index'))

@app.route('/toggle-ban/<user_id>')
def toggle_ban(user_id):
    u_ref = db.reference(f"users/{user_id}")
    u_data = u_ref.get() or {}
    is_banned = u_data.get('banned', False)
    u_ref.update({'banned': not is_banned})
    return redirect(url_for('index'))

@app.route('/get-telegram-photo/<file_id>')
def get_telegram_photo(file_id):
    try:
        res = requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getFile?file_id={file_id}").json()
        if res.get("ok"):
            file_path = res["result"]["file_path"]
            img_res = requests.get(f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}")
            return Response(img_res.content, mimetype=img_res.headers.get('content-type', 'image/jpeg'))
    except Exception as e:
        print("Error photo:", e)
    return "Image unavailable", 404

@app.route('/task-action/<type>/<task_id>/<user_id>')
def handle_task_action(type, task_id, user_id):
    settings = get_settings()
    task_reward = settings['task_reward']
    referral_reward = settings['referral_reward']

    if type == 'approve':
        db.reference(f"tasks/{task_id}").update({'status': 'Approved'})
        u_ref = db.reference(f"users/{user_id}")
        u_data = u_ref.get() or {}
        
        new_balance = float(u_data.get('balance', 0)) + task_reward
        new_tasks = int(u_data.get('tasks_done', 0)) + 1
        
        u_ref.update({'balance': new_balance, 'tasks_done': new_tasks})
        send_telegram_msg(user_id, f"🎉 <b>Task Approved!</b>\nYour task was verified. <b>₹{task_reward}</b> added to your wallet!")

        # Process Referral Commission on First Task
        ref_id = u_data.get('referred_by')
        if ref_id and not u_data.get('referral_paid'):
            ref_user_ref = db.reference(f"users/{ref_id}")
            ref_user_data = ref_user_ref.get() or {}
            ref_bal = float(ref_user_data.get('balance', 0)) + referral_reward
            ref_user_ref.update({'balance': ref_bal})
            u_ref.update({'referral_paid': True})
            send_telegram_msg(ref_id, f"🎁 <b>Referral Bonus Received!</b>\nYour invited friend completed their task. You earned <b>₹{referral_reward}</b>!")

    elif type == 'reject':
        db.reference(f"tasks/{task_id}").update({'status': 'Rejected'})
        send_telegram_msg(user_id, "❌ <b>Task Rejected!</b>\nYour submitted proof was invalid.")
        
    return redirect(url_for('index'))

@app.route('/payout/pay/<w_id>/<user_id>/<float:amount>')
def handle_payout(w_id, user_id, amount):
    db.reference(f"withdrawals/{w_id}").update({'status': 'Paid'})
    send_telegram_msg(user_id, f"✅ <b>Withdrawal Successful!</b>\nYour payout of <b>₹{amount}</b> has been processed via UPI.")
    
    masked_user = str(user_id)[:4] + "****"
    public_notice = (
        "🥳 <b>NEW PAYOUT PROOF!</b> 🥳\n\n"
        f"👤 <b>User ID:</b> <code>{masked_user}</code>\n"
        f"💸 <b>Amount Paid:</b> <b>₹{amount}</b>\n"
        "💳 <b>Status:</b> Payment Sent Successfully!\n\n"
        "🚀 <i>Complete tasks and withdraw daily!</i>"
    )
    broadcast_to_all(public_notice)
    return redirect(url_for('index'))

@app.route('/download-csv')
def download_csv():
    tasks_data = db.reference('tasks').get() or {}
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Task ID', 'User ID', 'Email', 'Status', 'Time'])
    
    for tid, t in tasks_data.items():
        if t and t.get('screenshot_id'):
            writer.writerow([t.get('id'), t.get('user_id'), t.get('assigned_email'), t.get('status'), t.get('submission_time')])
        
    output.seek(0)
    return Response(output.getvalue(), mimetype="text/csv", headers={"Content-Disposition": "attachment;filename=tasks_history.csv"})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
