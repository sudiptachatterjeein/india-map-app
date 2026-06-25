# 🇮🇳 India Map Portal

A full-stack web application for browsing India's administrative hierarchy (State → District → Sub-District → Village) with an interactive map, admin controls, and user access management.

## Features

### Admin Panel (`/admin`)
- **Dashboard** — Stats: total users, states, districts, villages, records
- **User Management** — Create/edit/disable users, set roles (admin/user)
- **State Restrictions** — Restrict each user to specific states only
- **Data Upload** — Upload new `.xlsx` or `.csv` data files to replace the dataset
- **Activity Log** — Full audit trail of all user actions

### User Panel (`/user`)
- **Interactive Map** — OpenStreetMap, Satellite, and Terrain layers
- **Cascading Filters** — State → District → Sub-District → Village dropdowns
- **Live Search** — Search across all geographic levels
- **Breadcrumb Navigation** — Visual location trail
- **State Access Control** — Sees only states admin has permitted

## Default Login

| Username | Password | Role  |
|----------|----------|-------|
| admin    | admin123 | Admin |

**⚠️ Change the admin password after first login!**

## Data Format

The uploaded file must have these columns (in any order):
```
state_code, state_name, district_code, district_name,
sub-district_code, sub-district_name, village_code, village_name
```

## Deploy to Railway

### 1. Push to GitHub
```bash
cd india-map-app
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/YOUR_USERNAME/india-map-app.git
git push -u origin main
```

### 2. Deploy on Railway
1. Go to [railway.app](https://railway.app)
2. Click **New Project** → **Deploy from GitHub repo**
3. Select your repository
4. Set environment variables:
   - `SECRET_KEY` = any random string (e.g. `openssl rand -hex 32`)
   - `DATABASE_URL` = (leave blank for SQLite, or add PostgreSQL from Railway)
5. Railway auto-detects and deploys!

### 3. Add PostgreSQL (Recommended for Production)
In Railway dashboard:
- Click **+ New** → **Database** → **PostgreSQL**
- Railway auto-injects `DATABASE_URL` into your app

## Environment Variables

| Variable     | Description                    | Default              |
|-------------|--------------------------------|----------------------|
| `SECRET_KEY` | Flask session secret           | `india-map-secret-2024` |
| `DATABASE_URL` | Database connection string  | `sqlite:///india_map.db` |
| `PORT`       | Server port                    | `5000`               |

## Local Development

```bash
pip install -r requirements.txt
python init_db.py
python app.py
```

Open http://localhost:5000

## Tech Stack
- **Backend**: Python Flask + SQLAlchemy + Flask-Login
- **Frontend**: Vanilla JS + Leaflet.js (OpenStreetMap)
- **Database**: SQLite (local) / PostgreSQL (production)
- **Data**: 676,667 records — 35 states, 778 districts, 6,764 sub-districts, 472,840 villages
