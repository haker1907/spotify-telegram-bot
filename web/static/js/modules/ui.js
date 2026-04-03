// UI module: notifications and small helpers
(function () {
    function showNotification(message, type = 'info') {
        const container = document.getElementById('toastContainer') || document.body;
        const notification = document.createElement('div');
        notification.className = `toast ${type}`;
        notification.textContent = message;
        container.appendChild(notification);

        setTimeout(() => {
            notification.classList.add('leaving');
            setTimeout(() => notification.remove(), 220);
        }, 2500);
    }

    function emptyState(text) {
        return `<p class="empty-state">${text}</p>`;
    }

    window.AppUI = {
        showNotification,
        emptyState
    };
})();
