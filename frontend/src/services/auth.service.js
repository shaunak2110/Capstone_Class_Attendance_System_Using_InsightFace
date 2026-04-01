import api from './api';

const USE_MOCK = import.meta.env.VITE_USE_MOCK_DATA === 'true';

export const authService = {
  login: async (email, password) => {
    if (USE_MOCK) {
      // --- MOCK MODE (For Demo) ---
      return new Promise((resolve, reject) => {
        setTimeout(() => {
          if (email && password) {
            resolve({ 
              token: 'mock-token-123', 
              user: { email, name: 'Faculty', role: 'admin' } 
            });
          } else {
            reject(new Error('Invalid credentials'));
          }
        }, 800);
      });
    } else {
      // --- REAL API MODE (For Deployment) ---
      const response = await api.post('/api/login', { email, password });
      return response.data;
    }
  },

  logout: () => {
    localStorage.removeItem('token');
    localStorage.removeItem('user');
  },
};