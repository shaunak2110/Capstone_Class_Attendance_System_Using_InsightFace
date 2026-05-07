# Classroom Attendance Frontend

React 18 + Vite SPA for the [class attendance system](https://github.com/shaunak2110/Capstone_Class_Attendance_System_Using_InsightFace). Backed by a FastAPI service on Hugging Face Spaces.

| Layer | Stack |
|---|---|
| Framework | React 18 |
| Build | Vite |
| Routing | React Router |
| HTTP | Axios |
| Styling | Tailwind CSS + Radix UI primitives |
| Production host | **Vercel** — https://capstone-class-attendance-system-us.vercel.app |

---

## Quick start (local)

```bash
npm install --legacy-peer-deps
npm run dev
```

App: **http://localhost:5173**

The Vite dev proxy forwards `/auth`, `/admin`, `/user`, `/superadmin`, `/health` to `http://127.0.0.1:8000` — leave `VITE_API_URL` empty in local `.env`.

Default login: `superadmin@mitwpu.edu.in` / `Super@admin` (see `CREDENTIALS.md` at the repo root).

---

## Production build

```bash
npm run build
```

Outputs to `dist/`. `vercel.json` rewrites all non-asset paths back to `index.html` for SPA client-side routing.

---

## Environment variables

| Variable | Local | Production (Vercel) | Notes |
|---|---|---|---|
| `VITE_API_URL` | Leave empty | `https://Shaunak2110-attendance-backend.hf.space` | Vite bakes this into the bundle at build time. Changing it requires a redeploy on Vercel. |

Set production `VITE_API_URL` in **Vercel → Project Settings → Environment Variables**, then **Deployments → ⋯ → Redeploy** the latest production deployment.

---

## Project structure

```
src/
  main.jsx                 React entry point + Router
  App.jsx                  Route definitions
  pages/                   Route components
    Login.jsx
    Dashboard.jsx          Mark attendance (Today/Past tabs), archive logs
    Results.jsx            Attendance results, face resolution dialog
    AdminDashboard.jsx     Create teacher, schedule timetable
    AdminStudents.jsx      Enroll / unenroll students
    AdminRecords.jsx       Lectures, analytics, timetable
    SuperadminDashboard.jsx  User roster, revoke, create admin/teacher
    Profile.jsx
  services/
    api.js                 27 API functions, axios instance with auth header interceptor
  components/
    Layout.jsx             Navbar + theme toggle + auth state
    ProtectedRoute.jsx     Privilege-based route guard
    ui/                    Radix UI primitives (Dialog, Select, etc.)
public/
  ...                      Static assets
vercel.json                SPA rewrites (catch-all → index.html)
vite.config.js             Dev proxy + build config + path aliases
```

---

## Auth flow

1. User submits credentials to `POST /auth/login`
2. Response stored in `localStorage`: `user_id`, `username`, `privilege_level`, `role`
3. Axios interceptor in `services/api.js` attaches `X-User-Id` and `X-Privilege-Level` headers to every subsequent request
4. `ProtectedRoute` checks privilege level for guarded routes

| Privilege | Routes accessible |
|---|---|
| `1` (Superadmin) | All |
| `2` (Admin) | All except `/superadmin` |
| `3` (Teacher) | `/dashboard`, `/results`, `/profile` |

---

## API client

All API calls go through `src/services/api.js`. Base URL is `import.meta.env.VITE_API_URL || ''` — empty string means relative paths, which the Vite dev proxy handles in development.

The interceptor automatically attaches auth headers. To add a new endpoint:

```javascript
// services/api.js
export async function myNewEndpoint(payload) {
  const response = await api.post('/admin/my-new-endpoint', payload);
  return response.data;
}
```

Then import and call from any page component.

---

## Common tasks

### If `npm install` fails

```bash
npm install --legacy-peer-deps
```

Some Radix UI peer-dep ranges conflict with newer React minor versions; the `--legacy-peer-deps` flag ignores those warnings.

### Hard-refresh after backend changes

The browser caches the Vite-built JS aggressively. After deploying a new build:
- Production: hard refresh (Ctrl+Shift+R) or clear site data
- Dev: Vite HMR usually handles it; restart `npm run dev` if it doesn't

### Adding a new protected route

1. Create the page component in `src/pages/`
2. Add a route in `App.jsx` wrapped in `<ProtectedRoute requiredLevel={2}>`
3. Add a navigation link in `Layout.jsx`

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| Login works but other pages 401 | Check axios interceptor is attaching headers — `console.log(localStorage)` should show `user_id` and `privilege_level` |
| Network tab shows requests to localhost in production | `VITE_API_URL` not set in Vercel, or Vercel deployed before the env var was added — redeploy |
| CORS error in console | Backend `ALLOWED_ORIGINS` doesn't match exactly — check trailing slash, http/https, subdomain |
| 413 on student enrollment | Image batch too large for HF edge — upload in batches of ~10 images per click |
| Logged in but redirected to /login | localStorage cleared or `privilege_level` missing — re-login |

---

## Related docs

- Full project README: `../README.md`
- Backend setup: `../backend/README.md`
- Cloud deployment guide: `../deployment.md`
- Account credentials + fresh-start: `../CREDENTIALS.md`
