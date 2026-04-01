import axios from 'axios';

const api = axios.create({
  baseURL: 'http://127.0.0.1:8000',
  headers: { 'Content-Type': 'application/json' },
});

// Auto-attach user headers from localStorage on every request
api.interceptors.request.use((config) => {
  const userId = localStorage.getItem('user_id');
  const privilegeLevel = localStorage.getItem('privilege_level');
  if (userId) config.headers['X-User-Id'] = userId;
  if (privilegeLevel) config.headers['X-Privilege-Level'] = privilegeLevel;
  return config;
});

export async function loginUser(username, password) {
  const response = await api.post('/auth/login', { username, password });
  const { user_id, username: uname, privilege_level } = response.data;
  localStorage.setItem('user_id', user_id);
  localStorage.setItem('username', uname);
  localStorage.setItem('privilege_level', privilege_level);
  return response.data;
}

export async function enrollStudent(prn, name, panel, images) {
  const response = await api.post('/admin/enroll-student', { prn, name, panel, images });
  return response.data;
}

export async function getLectures() {
  const userId = localStorage.getItem('user_id');
  try {
    const response = await api.get(`/user/lectures/${userId}`);
    return response.data;
  } catch (err) {
    // 404 means no lectures scheduled — return empty array instead of throwing
    if (err?.response?.status === 404) return [];
    throw err;
  }
}

export async function getUsers() {
  const response = await api.get('/superadmin/users');
  return response.data;
}

export async function createAdmin(data) {
  const response = await api.post('/superadmin/create-admin', data);
  return response.data;
}

export async function markAttendance(lecId, images) {
  const response = await api.post('/user/mark-attendance', { lec_id: lecId, images });
  return response.data;
}

export async function finalizeAttendance(lecId, identifiedPrns = []) {
  const response = await api.post('/user/finalize-attendance', { lec_id: lecId, identified_prns: identifiedPrns });
  return response.data;
}

export default api;
