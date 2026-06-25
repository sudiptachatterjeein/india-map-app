#!/usr/bin/env python3
"""Run this once to initialize the database before starting the app."""
import sys
sys.path.insert(0, '.')
from app import app, init_db

if __name__ == '__main__':
    init_db()
    print("Database initialized successfully!")
