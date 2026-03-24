// API wrapper for timetable system
const API = {
    async get(url) {
        const response = await fetch(url);
        if (!response.ok) throw new Error(`API error: ${response.status}`);
        return response.json();
    },

    async post(url, data) {
        const response = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data),
        });
        if (!response.ok) throw new Error(`API error: ${response.status}`);
        return response.json();
    },

    async put(url, data) {
        const response = await fetch(url, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data),
        });
        if (!response.ok) throw new Error(`API error: ${response.status}`);
        return response.json();
    },

    async delete(url) {
        const response = await fetch(url, { method: 'DELETE' });
        if (!response.ok) throw new Error(`API error: ${response.status}`);
        return response.json();
    },

    // Convenience methods
    getAcademicYears: () => API.get('/api/academic-years'),
    getLecturers: () => API.get('/api/lecturers'),
    getCourses: () => API.get('/api/courses'),
    getClassrooms: () => API.get('/api/classrooms'),
    getCourseRuns: (yearId) => API.get(`/api/course-runs?year_id=${yearId || ''}`),
    getScheduleGantt: (params) => API.get(`/api/schedule/gantt?${new URLSearchParams(params)}`),
    getScheduleLoading: (yearId) => API.get(`/api/schedule/loading?year_id=${yearId || ''}`),
    getResits: (params) => API.get(`/api/resits?${new URLSearchParams(params || {})}`),
    getRules: () => API.get('/api/rules'),
    updateRule: (id, data) => API.put(`/api/rules/${id}`, data),
    runSolver: (data) => API.post('/api/solver/run', data),
    getSolverStatus: (jobId) => API.get(`/api/solver/status/${jobId}`),
    confirmProposals: (yearId) => API.post('/api/schedule/confirm', { year_id: yearId }),
};
