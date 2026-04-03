// Infinite scroll helper module
(function () {
    const observers = new Map(); // key -> {observer, sentinel}

    function detach(key) {
        const entry = observers.get(key);
        if (!entry) return;
        try {
            entry.observer.disconnect();
        } catch (_) { }
        try {
            entry.sentinel.remove();
        } catch (_) { }
        observers.delete(key);
    }

    function attach(key, container, onReachEnd) {
        if (!container || typeof onReachEnd !== 'function') return;
        detach(key);

        const sentinel = document.createElement('div');
        sentinel.className = 'infinite-sentinel';
        container.appendChild(sentinel);

        const observer = new IntersectionObserver((entries) => {
            const visible = entries.some((e) => e.isIntersecting);
            if (visible) onReachEnd();
        }, {
            root: document.querySelector('.main-content'),
            rootMargin: '0px 0px 240px 0px',
            threshold: 0
        });

        observer.observe(sentinel);
        observers.set(key, { observer, sentinel });
    }

    window.InfiniteScroll = {
        attach,
        detach
    };
})();
