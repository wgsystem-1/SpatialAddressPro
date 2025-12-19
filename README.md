# SpatialAddressPro

This project is a Korean Address Normalization Solution (한국 주소 정제 솔루션).

## Project Structure

- `backend/`: Python FastAPI application.
    - `app/api/endpoints/`: API Logic (API 로직).
    - `app/core/`: Configuration (설정).
    - `app/models/`: Database Models (DB 모델).
- `frontend/`: React + TypeScript (Vite) Web Application.
- `database/`: Database scripts (Not used in local SQLite mode).

## Getting Started (Local Development)

Since Docker is currently unavailable, we use **SQLite** for local development.

### 1. Backend Setup
```bash
cd backend
# Create Virtual Env (Optional but recommended)
# pip install -r requirements.txt
uvicorn main:app --reload
```
- Server: http://127.0.0.1:8000
- Docs: http://127.0.0.1:8000/docs

### 2. Frontend Setup
```bash
cd frontend
# npm install (Already done)
npm run dev
```
- Web UI: http://localhost:5173

## Configuration

To switch to **PostGIS (PostgreSQL)** later:
1. Update `backend/app/core/config.py`: Set `DATABASE_URL` to postgres.
2. Run `docker compose up -d`.
