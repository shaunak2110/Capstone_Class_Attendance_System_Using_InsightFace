---
title: Attendance Backend
emoji: 🎓
colorFrom: blue
colorTo: green
sdk: docker
app_port: 7860
pinned: false
---

# Class Attendance Backend (FastAPI + InsightFace)

FastAPI service backing the class attendance frontend on Vercel. Handles auth,
enrollment, and face-based attendance marking via InsightFace.

## Required secrets (set in Space → Settings → Variables and secrets)

- `DB_CONNECTION_STRING` — Azure SQL connection string
- `ALLOWED_ORIGINS` — comma-separated list of frontend origins (e.g. `https://your-app.vercel.app`)
