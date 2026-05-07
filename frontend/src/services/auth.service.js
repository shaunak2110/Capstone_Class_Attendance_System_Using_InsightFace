import { loginUser } from './api';

// Thin wrapper kept for backward compatibility.
// All real auth goes through api.js → loginUser().
export const authService = {
  login: async (username, password) => {
    return loginUser(username, password);
  },

  logout: () => {
    localStorage.removeItem('user_id');
    localStorage.removeItem('username');
    localStorage.removeItem('privilege_level');
    localStorage.removeItem('role');
    localStorage.removeItem('name');
    localStorage.removeItem('token');
  },
};
