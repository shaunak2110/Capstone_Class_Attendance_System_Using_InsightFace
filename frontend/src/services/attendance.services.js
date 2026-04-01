import api from './api';
import { teamMembers, lectureInfo } from '@/data/mockstudents';

const USE_MOCK = import.meta.env.VITE_USE_MOCK_DATA === 'true';

export const attendanceService = {
    uploadAttendance: async (formData) => {
        if (USE_MOCK) {
        // --- MOCK MODE (For Demo) ---
        return new Promise((resolve) => {
            setTimeout(() => {
            resolve({
                success: true,
                data: {
                lecture_info: lectureInfo,
                attendance: teamMembers,
                processed_image_url: null 
                }
            });
            }, 1500);
        });
        } else {
        // --- REAL API MODE (For Deployment) ---
        const response = await api.post('/api/upload-lecture', formData, {
            headers: { 'Content-Type': 'multipart/form-data' },
        });
        return response.data;
        }
    },

    updateStatus: async (prn, newStatus) => {
        if (USE_MOCK) {
        return new Promise((resolve) => setTimeout(() => resolve({ success: true }), 500));
        } else {
        const response = await api.post('/api/correct-attendance', { prn, status: newStatus });
        return response.data;
        }
    },
};