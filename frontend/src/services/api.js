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

export async function getUserProfile() {
  // GET /user/profile — expects X-User-Id header (injected automatically)
  // Backend returns: { user_id, username, name, email_id, school, department, privilege_level }
  const response = await api.get('/user/profile');
  return response.data;
}

export async function enrollStudent(prn, name, year, course, specialisation, rollno, panel, images) {
  const response = await api.post('/admin/enroll-student', { prn, name, year, course, specialisation, rollno, panel, images });
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

export async function getAllLectures() {
  try {
    const response = await api.get('/admin/lectures');
    return response.data;
  } catch (err) {
    if (err?.response?.status === 404) return [];
    throw err;
  }
}

export async function getAttendanceAnalytics(filters) {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(filters)) {
    if (value) params.append(key, value);
  }
  const response = await api.get(`/admin/attendance-analytics?${params.toString()}`);
  return response.data;
}

export async function getUsers() {
  const response = await api.get('/superadmin/users');
  return response.data;
}

export async function createAdmin(data) {
  const response = await api.post('/superadmin/create-admin', data);
  return response.data;
}

export async function markAttendance(lecId, images, lectureDatetime = null) {
  const payload = { lec_id: lecId, images };
  if (lectureDatetime) payload.lecture_datetime = lectureDatetime;
  const response = await api.post('/user/mark-attendance', payload);
  return response.data;
}

export async function finalizeAttendance(lecId, identifiedPrns = []) {
  const response = await api.post('/user/finalize-attendance', { lec_id: lecId, identified_prns: identifiedPrns });
  return response.data;
}

export async function createTeacher(data) {
  const response = await api.post('/admin/create-teacher', data);
  return response.data;
}

export async function scheduleLecture(data) {
  const response = await api.post('/admin/schedule-lecture', data);
  return response.data;
}

export async function getPrivilegeRequests() {
  const response = await api.get('/superadmin/requests');
  return response.data;
}

export async function approvePrivilegeRequest(requestId, targetUserId) {
  const response = await api.post('/superadmin/approve-request', {
    request_id: requestId,
    user_id: targetUserId
  });
  return response.data;
}

export async function requestPrivilege() {
  const response = await api.post('/user/request-privilege');
  return response.data;
}

export async function downloadCsv(lecId) {
  // Uses blob response type to handle file download properly
  const response = await api.get(`/user/download-csv/${lecId}`, { responseType: 'blob' });
  return response.data;
}

export async function getEnrolledStudents(lecId) {
  const response = await api.get(`/user/enrolled-students/${lecId}`);
  return response.data;
}

export async function resolveFaces(lecId, resolutions) {
  const response = await api.post('/user/resolve-faces', {
    lec_id: lecId,
    resolutions: resolutions
  });
  return response.data;
}

export async function getAttendanceRecords(lecId, dateFrom = null, dateTo = null) {
  const params = new URLSearchParams();
  if (dateFrom) params.append('date_from', dateFrom);
  if (dateTo) params.append('date_to', dateTo);
  const query = params.toString() ? `?${params.toString()}` : '';
  const response = await api.get(`/user/attendance-records/${lecId}${query}`);
  return response.data;
}

export default api;
