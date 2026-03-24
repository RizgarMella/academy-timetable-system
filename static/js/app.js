// Shared utilities for timetable system
const App = {
    // Generate consistent color for a course ID
    courseColor(courseId, lightness = 65) {
        const hue = (courseId * 47) % 360;
        return `hsl(${hue}, 70%, ${lightness}%)`;
    },

    // Format date for display
    formatDate(dateStr) {
        if (!dateStr) return '';
        const d = new Date(dateStr + 'T00:00:00');
        return d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
    },

    // Format snake_case to Title Case
    formatKey(key) {
        return key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
    },

    // Status badge HTML
    statusBadge(status) {
        return `<span class="badge badge-${status}">${status.replace('_', ' ')}</span>`;
    },

    // Show toast notification
    showToast(message, type = 'info') {
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        toast.textContent = message;
        document.body.appendChild(toast);
        setTimeout(() => toast.classList.add('show'), 10);
        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    },

    // Week number from date
    getWeekNumber(dateStr) {
        const d = new Date(dateStr + 'T00:00:00');
        const start = new Date(d.getFullYear(), 0, 1);
        const diff = d - start;
        return Math.ceil((diff / 86400000 + start.getDay() + 1) / 7);
    },

    // Days between two dates
    daysBetween(start, end) {
        const s = new Date(start + 'T00:00:00');
        const e = new Date(end + 'T00:00:00');
        return Math.ceil((e - s) / 86400000);
    },
};
