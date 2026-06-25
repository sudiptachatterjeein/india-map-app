import os
import json
import pandas as pd
from datetime import datetime
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_bcrypt import Bcrypt
from werkzeug.utils import secure_filename
from functools import wraps

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'india-map-secret-2024')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///india_map.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# ─── Models ───────────────────────────────────────────────────────────────────

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), default='user')  # 'admin' or 'user'
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    # Restrictions (comma-separated state codes)
    allowed_states = db.Column(db.Text, default='')  # empty = all states allowed

class DataUpload(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(200))
    original_name = db.Column(db.String(200))
    uploaded_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    record_count = db.Column(db.Integer, default=0)
    status = db.Column(db.String(20), default='processing')

class UserActivity(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    action = db.Column(db.String(200))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            return jsonify({'error': 'Admin access required'}), 403
        return f(*args, **kwargs)
    return decorated

# ─── Data Loading ─────────────────────────────────────────────────────────────

_df_cache = None

def get_data():
    global _df_cache
    if _df_cache is None:
        csv_path = os.path.join('data', 'india_data.csv')
        if os.path.exists(csv_path):
            _df_cache = pd.read_csv(csv_path, dtype=str)
            _df_cache.columns = [c.strip().replace('-', '_') for c in _df_cache.columns]
    return _df_cache

# ─── Auth Routes ──────────────────────────────────────────────────────────────

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        data = request.get_json() if request.is_json else request.form
        user = User.query.filter_by(username=data.get('username')).first()
        if user and bcrypt.check_password_hash(user.password, data.get('password')):
            if not user.is_active:
                return jsonify({'error': 'Account disabled'}), 403
            login_user(user)
            db.session.add(UserActivity(user_id=user.id, action='Logged in'))
            db.session.commit()
            if request.is_json:
                return jsonify({'success': True, 'role': user.role})
            return redirect(url_for('admin_panel') if user.role == 'admin' else url_for('user_panel'))
        if request.is_json:
            return jsonify({'error': 'Invalid credentials'}), 401
        flash('Invalid credentials', 'error')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    db.session.add(UserActivity(user_id=current_user.id, action='Logged out'))
    db.session.commit()
    logout_user()
    return redirect(url_for('login'))
@app.route('/health')
def health():
    return 'OK', 200


@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('admin_panel') if current_user.role == 'admin' else url_for('user_panel'))
    return redirect(url_for('login'))

# ─── Admin Panel ──────────────────────────────────────────────────────────────

@app.route('/admin')
@login_required
def admin_panel():
    if current_user.role != 'admin':
        return redirect(url_for('user_panel'))
    return render_template('admin.html', user=current_user)

@app.route('/user')
@login_required
def user_panel():
    return render_template('user.html', user=current_user)

@app.route('/dashboard')
@login_required
def dashboard():
    if current_user.role == 'admin':
        return redirect(url_for('admin_panel'))
    return redirect(url_for('user_panel'))

# ─── Admin API: User Management ───────────────────────────────────────────────

@app.route('/api/admin/users', methods=['GET'])
@login_required
@admin_required
def get_users():
    users = User.query.all()
    return jsonify([{
        'id': u.id,
        'username': u.username,
        'email': u.email,
        'role': u.role,
        'is_active': u.is_active,
        'allowed_states': u.allowed_states,
        'created_at': u.created_at.isoformat()
    } for u in users])

@app.route('/api/admin/users', methods=['POST'])
@login_required
@admin_required
def create_user():
    data = request.get_json()
    if User.query.filter_by(username=data['username']).first():
        return jsonify({'error': 'Username already exists'}), 400
    hashed = bcrypt.generate_password_hash(data['password']).decode('utf-8')
    user = User(
        username=data['username'],
        email=data.get('email', ''),
        password=hashed,
        role=data.get('role', 'user'),
        allowed_states=data.get('allowed_states', '')
    )
    db.session.add(user)
    db.session.add(UserActivity(user_id=current_user.id, action=f"Created user: {data['username']}"))
    db.session.commit()
    return jsonify({'success': True, 'id': user.id})

@app.route('/api/admin/users/<int:uid>', methods=['PUT'])
@login_required
@admin_required
def update_user(uid):
    user = User.query.get_or_404(uid)
    data = request.get_json()
    if 'is_active' in data:
        user.is_active = data['is_active']
    if 'allowed_states' in data:
        user.allowed_states = data['allowed_states']
    if 'role' in data:
        user.role = data['role']
    if 'password' in data and data['password']:
        user.password = bcrypt.generate_password_hash(data['password']).decode('utf-8')
    db.session.add(UserActivity(user_id=current_user.id, action=f"Updated user: {user.username}"))
    db.session.commit()
    return jsonify({'success': True})

@app.route('/api/admin/users/<int:uid>', methods=['DELETE'])
@login_required
@admin_required
def delete_user(uid):
    user = User.query.get_or_404(uid)
    uname = user.username
    db.session.delete(user)
    db.session.add(UserActivity(user_id=current_user.id, action=f"Deleted user: {uname}"))
    db.session.commit()
    return jsonify({'success': True})

# ─── Admin API: Data Upload ────────────────────────────────────────────────────

@app.route('/api/admin/upload', methods=['POST'])
@login_required
@admin_required
def upload_data():
    global _df_cache
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    file = request.files['file']
    if not file.filename.endswith(('.xlsx', '.csv')):
        return jsonify({'error': 'Only .xlsx or .csv files allowed'}), 400
    fname = secure_filename(file.filename)
    fpath = os.path.join(app.config['UPLOAD_FOLDER'], fname)
    file.save(fpath)
    try:
        if fname.endswith('.xlsx'):
            df = pd.read_excel(fpath, dtype=str)
        else:
            df = pd.read_csv(fpath, dtype=str)
        df.columns = [c.strip().replace('-', '_') for c in df.columns]
        csv_path = os.path.join('data', 'india_data.csv')
        df.to_csv(csv_path, index=False)
        _df_cache = None  # Clear cache
        record = DataUpload(filename=fname, original_name=file.filename,
                            uploaded_by=current_user.id, record_count=len(df), status='success')
        db.session.add(record)
        db.session.add(UserActivity(user_id=current_user.id, action=f"Uploaded data: {file.filename} ({len(df)} records)"))
        db.session.commit()
        return jsonify({'success': True, 'records': len(df)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/uploads', methods=['GET'])
@login_required
@admin_required
def get_uploads():
    uploads = DataUpload.query.order_by(DataUpload.uploaded_at.desc()).limit(20).all()
    users = {u.id: u.username for u in User.query.all()}
    return jsonify([{
        'id': u.id,
        'original_name': u.original_name,
        'uploaded_by': users.get(u.uploaded_by, 'unknown'),
        'uploaded_at': u.uploaded_at.isoformat(),
        'record_count': u.record_count,
        'status': u.status
    } for u in uploads])

@app.route('/api/admin/activity', methods=['GET'])
@login_required
@admin_required
def get_activity():
    logs = UserActivity.query.order_by(UserActivity.timestamp.desc()).limit(50).all()
    users = {u.id: u.username for u in User.query.all()}
    return jsonify([{
        'user': users.get(l.user_id, 'unknown'),
        'action': l.action,
        'timestamp': l.timestamp.isoformat()
    } for l in logs])

@app.route('/api/admin/stats', methods=['GET'])
@login_required
@admin_required
def get_stats():
    df = get_data()
    return jsonify({
        'total_users': User.query.count(),
        'active_users': User.query.filter_by(is_active=True).count(),
        'total_states': int(df['state_name'].nunique()) if df is not None else 0,
        'total_districts': int(df['district_name'].nunique()) if df is not None else 0,
        'total_villages': int(df['village_name'].nunique()) if df is not None else 0,
        'total_records': len(df) if df is not None else 0,
    })

# ─── Data API (with access control) ──────────────────────────────────────────

def get_allowed_states():
    """Return set of allowed state codes for current user (empty = all)"""
    if current_user.role == 'admin':
        return set()
    s = current_user.allowed_states or ''
    return set(s.split(',')) if s.strip() else set()

@app.route('/api/states')
@login_required
def api_states():
    df = get_data()
    if df is None:
        return jsonify([])
    states = df[['state_code', 'state_name']].drop_duplicates().sort_values('state_name')
    allowed = get_allowed_states()
    if allowed:
        states = states[states['state_code'].isin(allowed)]
    return jsonify(states.to_dict('records'))

@app.route('/api/districts')
@login_required
def api_districts():
    state_code = request.args.get('state_code')
    df = get_data()
    if df is None:
        return jsonify([])
    allowed = get_allowed_states()
    if allowed and state_code not in allowed:
        return jsonify({'error': 'Access denied'}), 403
    filtered = df[df['state_code'] == state_code] if state_code else df
    districts = filtered[['district_code', 'district_name']].drop_duplicates().sort_values('district_name')
    return jsonify(districts.to_dict('records'))

@app.route('/api/subdistricts')
@login_required
def api_subdistricts():
    district_code = request.args.get('district_code')
    state_code = request.args.get('state_code')
    df = get_data()
    if df is None:
        return jsonify([])
    allowed = get_allowed_states()
    if allowed and state_code and state_code not in allowed:
        return jsonify({'error': 'Access denied'}), 403
    filtered = df[df['district_code'] == district_code] if district_code else df
    subs = filtered[['sub_district_code', 'sub_district_name']].drop_duplicates().sort_values('sub_district_name')
    return jsonify(subs.to_dict('records'))

@app.route('/api/villages')
@login_required
def api_villages():
    subdistrict_code = request.args.get('subdistrict_code')
    state_code = request.args.get('state_code')
    df = get_data()
    if df is None:
        return jsonify([])
    allowed = get_allowed_states()
    if allowed and state_code and state_code not in allowed:
        return jsonify({'error': 'Access denied'}), 403
    filtered = df[df['sub_district_code'] == subdistrict_code] if subdistrict_code else df
    villages = filtered[['village_code', 'village_name']].drop_duplicates().sort_values('village_name')
    return jsonify(villages.to_dict('records'))

@app.route('/api/search')
@login_required
def api_search():
    q = request.args.get('q', '').strip()
    if len(q) < 2:
        return jsonify([])
    df = get_data()
    if df is None:
        return jsonify([])
    allowed = get_allowed_states()
    if allowed:
        df = df[df['state_code'].isin(allowed)]
    mask = (
        df['state_name'].str.contains(q, case=False, na=False) |
        df['district_name'].str.contains(q, case=False, na=False) |
        df['sub_district_name'].str.contains(q, case=False, na=False) |
        df['village_name'].str.contains(q, case=False, na=False)
    )
    results = df[mask].head(20)
    return jsonify(results.to_dict('records'))

# ─── Init DB ──────────────────────────────────────────────────────────────────

def init_db():
    with app.app_context():
        db.create_all()
        if not User.query.filter_by(username='admin').first():
            hashed = bcrypt.generate_password_hash('admin123').decode('utf-8')
            admin = User(username='admin', email='admin@indiamap.com', password=hashed, role='admin')
            db.session.add(admin)
            db.session.commit()
            print("✅ Default admin created: admin / admin123")

if __name__ == '__main__':
    init_db()
    app.run(debug=False, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
