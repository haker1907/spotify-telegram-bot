// Music Downloader - Spotify Style Web App

let currentTrack = null;
let searchTimeout = null;
let searchController = null;
let lastSearchQuery = '';
let resultsData = [];
let libraryData = [];
let historyData = [];
let userData = null;
const audioPlayer = document.getElementById('audioPlayer');
const searchCache = new Map(); // query -> {ts, tracks}
const LIBRARY_PAGE_SIZE = 24;
const HISTORY_PAGE_SIZE = 20;
let libraryRendered = 0;
let historyRendered = 0;
let historyItemsRaw = [];
let isHistoryChunkLoading = false;
let isLibraryChunkLoading = false;

// Player state variables
let isRepeatEnabled = false;
let isShuffleEnabled = false;
let currentPlaylist = [];
let currentTrackIndex = -1;
let currentCardPlayBtn = null;
let pendingSeekSeconds = null;

const PLAYBACK_STORAGE_KEY = 'playbackStateV1';
const LAST_TRACK_STORAGE_KEY = 'lastPlayedTrackV1';
let lastPlaybackSaveAt = 0;

function updateQueueStatus() {
    const el = document.getElementById('queueStatus');
    if (!el) return;
    if (!currentPlaylist || currentPlaylist.length === 0 || currentTrackIndex < 0) {
        el.textContent = 'Queue: empty';
        return;
    }
    const current = currentPlaylist[currentTrackIndex];
    const nextIndex = isShuffleEnabled
        ? Math.floor(Math.random() * currentPlaylist.length)
        : (currentTrackIndex + 1) % currentPlaylist.length;
    const prevIndex = (currentTrackIndex - 1 + currentPlaylist.length) % currentPlaylist.length;
    const prev = currentPlaylist[prevIndex];
    const next = currentPlaylist[nextIndex];
    const mode = `${isShuffleEnabled ? 'Shuffle:on' : 'Shuffle:off'} | ${isRepeatEnabled ? 'Repeat:on' : 'Repeat:off'}`;
    el.textContent = `${mode} | Prev: ${prev?.name || '-'} | Now: ${current?.name || '-'} | Next: ${next?.name || '-'}`;
}

// Initialize app
document.addEventListener('DOMContentLoaded', () => {
    checkAuthToken();
    updateUserUI();
    initializeNavigation();
    initializeHeaderNav();
    initializeSearch();
    initializePlayer();
    initializeNowPlayingPanel();
    initializePlaylists();
    initializeUploadTrack();
    initializeViewToggle();
    loadLibrary();
    restoreLastPlayedTrackUI();

    if (userData) {
        loadPlaylists();
    }

    // Backup БД при закрытии/обновлении страницы
    // endpoint теперь требует авторизацию, поэтому используем fetch с keepalive.
    window.addEventListener('beforeunload', function () {
        if (!userData) return;

        const backupUrl = '/api/backup-db';
        fetch(backupUrl, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({}),
            credentials: 'same-origin',
            keepalive: true
        }).catch(err => console.log('Backup request failed:', err));
    });
});

function restoreLastPlayedTrackUI() {
    // Восстанавливаем только UI (без автоплея), чтобы после refresh был виден последний трек
    try {
        const raw = localStorage.getItem(LAST_TRACK_STORAGE_KEY);
        if (!raw) return;
        const track = JSON.parse(raw);
        if (!track || (!track.name && !track.artist)) return;

        currentTrack = track;
        updatePlayerUI(track);

        // Восстанавливаем сохранённую позицию (только UI), даже если duration пока неизвестна
        try {
            const pRaw = localStorage.getItem(PLAYBACK_STORAGE_KEY);
            const state = pRaw ? JSON.parse(pRaw) : null;
            if (state && state.trackId && state.trackId === track.id && typeof state.position === 'number' && state.position > 0) {
                const currentTimeEl = document.getElementById('currentTime');
                if (currentTimeEl) currentTimeEl.textContent = formatTime(state.position);

                // Если есть сохранённая длительность — выставим totalTime и положение ползунка корректно
                const totalTimeEl = document.getElementById('totalTime');
                const progressSlider = document.getElementById('progressSlider');
                if (typeof state.duration === 'number' && state.duration > 0) {
                    if (totalTimeEl) totalTimeEl.textContent = formatTime(state.duration);
                    if (progressSlider) {
                        const pct = Math.min(100, Math.max(0, (state.position / state.duration) * 100));
                        progressSlider.value = pct;
                    }
                }
            }
        } catch (_) { }

        // Подсветим правильную иконку на правой панели/плеере
        setNowPlayingPlayButtonState(!audioPlayer.paused);
        updatePlayButton(!audioPlayer.paused);
    } catch (_) {
        // ignore
    }
}

function persistLastPlayedTrack(track) {
    try {
        if (!track) return;
        // сохраняем только нужные поля, чтобы не раздувать storage
        const minimal = {
            id: track.id || '',
            name: track.name || '',
            artist: track.artist || '',
            album: track.album || '',
            image: track.image || '',
            preview_url: track.preview_url || null,
            from_discover: !!track.from_discover
        };
        localStorage.setItem(LAST_TRACK_STORAGE_KEY, JSON.stringify(minimal));
    } catch (_) {
        // ignore
    }
}

function initializeHeaderNav() {
    const backBtn = document.getElementById('navBackBtn');
    const fwdBtn = document.getElementById('navForwardBtn');
    const homeBtn = document.getElementById('navHomeBtn');

    backBtn?.addEventListener('click', () => window.history.back());
    fwdBtn?.addEventListener('click', () => window.history.forward());
    homeBtn?.addEventListener('click', () => {
        // Переключаемся на Search
        document.querySelectorAll('.content-section').forEach(s => s.classList.remove('active'));
        document.getElementById('searchResults')?.classList.add('active');
        document.querySelectorAll('.nav-item').forEach(nav => nav.classList.remove('active'));
        document.querySelector('[data-page="search"]')?.classList.add('active');
        // Сброс поля поиска (не трогаем Discover)
        const searchInput = document.getElementById('searchInput');
        if (searchInput) searchInput.value = '';
        const resultsGrid = document.getElementById('resultsGrid');
        if (resultsGrid) resultsGrid.innerHTML = '';
        lastSearchQuery = '';
    });
}

function initializeNowPlayingPanel() {
    const npPlayBtn = document.getElementById('npPlayBtn');
    const npDownloadBtn = document.getElementById('npDownloadBtn');

    npPlayBtn?.addEventListener('click', () => {
        if (!currentTrack) {
            showNotification('Сначала выберите трек', 'info');
            return;
        }
        // Если после refresh src пустой — нужно заново подготовить стрим (URL из Telegram может истечь).
        const hasSrc = !!(audioPlayer.src && audioPlayer.src !== window.location.href);
        if (audioPlayer.paused) {
            if (!hasSrc) {
                playTrack(null, currentTrack);
                return;
            }
            audioPlayer.play().catch(() => showNotification('Не удалось воспроизвести', 'error'));
        } else {
            audioPlayer.pause();
        }
    });

    npDownloadBtn?.addEventListener('click', () => {
        if (!currentTrack) {
            showNotification('Сначала выберите трек', 'info');
            return;
        }
        document.getElementById('downloadModal')?.classList.add('active');
    });

    // синхронизируем иконку Play/Pause с реальным плеером
    audioPlayer.addEventListener('play', () => setNowPlayingPlayButtonState(true));
    audioPlayer.addEventListener('pause', () => setNowPlayingPlayButtonState(false));
}

function setNowPlayingPlayButtonState(isPlaying) {
    const btn = document.getElementById('npPlayBtn');
    if (!btn) return;
    btn.innerHTML = isPlaying
        ? `<svg viewBox="0 0 24 24" fill="currentColor"><path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z" /></svg>`
        : `<svg viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z" /></svg>`;
}

function updateNowPlayingPanel(track) {
    const cover = document.getElementById('npCover');
    const name = document.getElementById('npName');
    const artist = document.getElementById('npArtist');
    const about = document.getElementById('npAbout');

    if (!cover || !name || !artist || !about) return;
    if (!track) return;

    cover.innerHTML = track.image
        ? `<img src="${track.image}" alt="" loading="lazy" decoding="async" />`
        : `<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M12 3v10.55c-.59-.34-1.27-.55-2-.55-2.21 0-4 1.79-4 4s1.79 4 4 4 4-1.79 4-4V7h4V3h-6z" /></svg>`;

    name.textContent = track.name || 'Трек';
    artist.textContent = track.artist || '—';

    const source = track.from_discover ? 'Discover' : 'Spotify/поиск';
    about.innerHTML = `
        <div style="display:grid; gap:6px;">
            <div><span style="opacity:.75;">Источник:</span> <span style="font-weight:800;">${source}</span></div>
            ${track.album ? `<div><span style="opacity:.75;">Альбом:</span> <span style="font-weight:800;">${track.album}</span></div>` : ''}
        </div>
    `;
}

function renderTrackSkeletons(count = 8) {
    const items = [];
    for (let i = 0; i < count; i++) {
        items.push(`
            <div class="track-card skeleton-card">
                <div class="track-image">
                    <div class="skeleton-img" style="width:100%;height:100%;margin-bottom:0;"></div>
                </div>
                <div class="track-info">
                    <div class="skeleton-row" style="width: 80%;"></div>
                    <div class="skeleton-row" style="width: 55%;"></div>
                </div>
                <div class="track-actions">
                    <div class="skeleton-row" style="width: 36px; height: 36px; border-radius: 6px; margin: 0;"></div>
                    <div class="skeleton-row" style="width: 36px; height: 36px; border-radius: 6px; margin: 0; background: rgba(255,255,255,0.08);"></div>
                </div>
            </div>
        `);
    }
    return items.join('');
}

function renderPlaylistsSkeletons(count = 6) {
    const items = [];
    for (let i = 0; i < count; i++) {
        items.push(`
            <div class="skeleton-card">
                <div class="skeleton-img"></div>
                <div class="skeleton-row" style="width: 85%;"></div>
                <div class="skeleton-row" style="width: 55%;"></div>
            </div>
        `);
    }
    return items.join('');
}

function renderHistorySkeletons(count = 8) {
    const items = [];
    for (let i = 0; i < count; i++) {
        items.push(`
            <div class="history-item history-item-skeleton">
                <div class="skeleton-img history-thumb-skeleton"></div>
                <div class="history-main-col">
                    <div class="skeleton-row history-line-primary"></div>
                    <div class="skeleton-row history-line-secondary"></div>
                </div>
                <div class="skeleton-row history-line-meta"></div>
            </div>
        `);
    }
    return items.join('');
}

function renderHistoryItem(item, index) {
    const downloadedAt = item.downloaded_at ? new Date(item.downloaded_at) : null;
    const downloadedAtText = downloadedAt && !isNaN(downloadedAt.getTime())
        ? downloadedAt.toLocaleString()
        : '';

    const track = item.track || {};
    const name = track.name || 'Track';
    const artist = track.artist || '';
    const quality = item.quality || '';

    return `
        <div class="history-item" role="button" tabindex="0" onclick="openHistoryDetails(${index})">
            <div class="track-image history-thumb">
                <svg viewBox="0 0 24 24" fill="currentColor" class="history-thumb-icon">
                    <path d="M12 3v10.55c-.59-.34-1.27-.55-2-.55-2.21 0-4 1.79-4 4s1.79 4 4 4 4-1.79 4-4V7h4V3h-6z"/>
                </svg>
            </div>
            <div class="history-main-col">
                <div class="track-name history-track-name">${name}</div>
                <div class="track-artist history-track-artist">${artist}</div>
            </div>
            <div class="history-meta-col">
                <div class="history-quality">${quality}</div>
                <div class="history-date">${downloadedAtText}</div>
            </div>
        </div>
    `;
}

function openHistoryDetails(index) {
    const idx = Number(index);
    if (!Number.isFinite(idx)) return;
    const item = historyItemsRaw?.[idx];
    const track = item?.track;
    if (!track) return;

    const modal = document.getElementById('historyDetailsModal');
    const body = document.getElementById('historyDetailsBody');
    if (!modal || !body) return;

    const downloadedAt = item.downloaded_at ? new Date(item.downloaded_at) : null;
    const downloadedAtText = downloadedAt && !isNaN(downloadedAt.getTime()) ? downloadedAt.toLocaleString() : '';
    const quality = item.quality || '';

    body.innerHTML = `
        <div style="display:flex; gap:12px; align-items:center;">
            <div style="width:56px; height:56px; border-radius:8px; overflow:hidden; background: rgba(0,0,0,0.25); display:flex; align-items:center; justify-content:center;">
                ${track.image ? `<img src="${track.image}" alt="" style="width:100%;height:100%;object-fit:cover;display:block;" />`
            : `<svg viewBox="0 0 24 24" fill="currentColor" style="width:26px;height:26px;opacity:.85;"><path d="M12 3v10.55c-.59-.34-1.27-.55-2-.55-2.21 0-4 1.79-4 4s1.79 4 4 4 4-1.79 4-4V7h4V3h-6z"/></svg>`}
            </div>
            <div style="min-width:0;">
                <div style="font-weight:800; font-size:16px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;" title="${track.name || ''}">${track.name || ''}</div>
                <div style="opacity:.8; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;" title="${track.artist || ''}">${track.artist || ''}</div>
            </div>
        </div>
        <div style="margin-top:14px; display:grid; gap:8px;">
            <div><span style="opacity:.7;">Качество:</span> <span style="font-weight:700;">${quality || '-'}</span></div>
            <div><span style="opacity:.7;">Скачано:</span> <span style="font-weight:700;">${downloadedAtText || '-'}</span></div>
        </div>
        <div style="margin-top:16px; display:flex; gap:10px; flex-wrap:wrap;">
            <button class="admin-btn" style="padding:10px 12px;" onclick="closeHistoryDetailsModal(); playHistoryFromModal(${idx});">Play</button>
            <button class="admin-btn" style="padding:10px 12px; background: transparent; border:1px solid rgba(255,255,255,0.18);" onclick="closeHistoryDetailsModal(); downloadHistoryFromModal(${idx});">Download</button>
        </div>
    `;

    modal.classList.add('active');
}

function closeHistoryDetailsModal() {
    document.getElementById('historyDetailsModal')?.classList.remove('active');
}

function playHistoryFromModal(index) {
    const idx = Number(index);
    if (!Number.isFinite(idx)) return;
    const track = historyItemsRaw?.[idx]?.track;
    if (!track) return;
    // Очередь = история, чтобы next/prev работали после явного Play
    currentPlaylist = historyData.filter(Boolean);
    const actualIndex = currentPlaylist.findIndex(t => t && t.id === track.id);
    currentTrackIndex = actualIndex >= 0 ? actualIndex : 0;
    playTrack(null, track);
}

function downloadHistoryFromModal(index) {
    const idx = Number(index);
    if (!Number.isFinite(idx)) return;
    const track = historyItemsRaw?.[idx]?.track;
    if (!track) return;

    // Открываем download modal через временную "карточку"
    // (используем существующую логику startDownload())
    currentTrack = track;
    document.getElementById('downloadModal')?.classList.add('active');
}

async function loadHistory(limit = 10) {
    if (!userData) return;
    try {
        const historyList = document.getElementById('historyList');
        if (historyList) historyList.innerHTML = renderHistorySkeletons(8);

        const response = await fetch(`/api/history?limit=${limit}`, {
            credentials: 'same-origin'
        });
        const data = await response.json();

        historyItemsRaw = data.history || [];
        // Важно: НЕ фильтруем null, иначе индексы historyData и historyItemsRaw разъедутся,
        // и клик по элементу истории будет передавать неправильный трек.
        historyData = historyItemsRaw.map(x => x.track);
        historyRendered = 0;

        if (!historyList) return;
        if (!data.history || data.history.length === 0) {
            historyList.innerHTML = window.AppUI.emptyState('No history yet');
            return;
        }

        renderHistoryChunk(true);
    } catch (error) {
        console.error('Load history error:', error);
        showNotification('Failed to load history', 'error');
    }
}

function renderHistoryChunk(reset = false) {
    const historyList = document.getElementById('historyList');
    if (!historyList) return;
    if (isHistoryChunkLoading) return;
    isHistoryChunkLoading = true;

    if (reset) {
        historyList.innerHTML = '';
        if (window.InfiniteScroll) window.InfiniteScroll.detach('history');
    }
    const start = historyRendered;
    const end = Math.min(historyRendered + HISTORY_PAGE_SIZE, historyItemsRaw.length);
    if (start >= end) {
        isHistoryChunkLoading = false;
        if (window.InfiniteScroll) window.InfiniteScroll.detach('history');
        return;
    }

    const html = historyItemsRaw
        .slice(start, end)
        .map((item, idx) => renderHistoryItem(item, start + idx))
        .join('');

    historyList.insertAdjacentHTML('beforeend', html);
    historyRendered = end;
    isHistoryChunkLoading = false;

    if (historyRendered < historyItemsRaw.length && window.InfiniteScroll) {
        window.InfiniteScroll.attach('history', historyList, () => renderHistoryChunk(false));
    } else if (window.InfiniteScroll) {
        window.InfiniteScroll.detach('history');
    }
}

// View Toggle for Discover Section
function initializeViewToggle() {
    const viewToggle = document.getElementById('viewToggle');
    const libraryGrid = document.getElementById('libraryGrid');
    const savedView = localStorage.getItem('discoverView') || 'grid';

    // Apply saved view
    if (savedView === 'list') {
        libraryGrid.classList.add('list-view');
        document.querySelector('.view-btn[data-view="list"]').classList.add('active');
        document.querySelector('.view-btn[data-view="grid"]').classList.remove('active');
    }

    // Toggle view on button click
    viewToggle.addEventListener('click', (e) => {
        const btn = e.target.closest('.view-btn');
        if (!btn) return;

        const view = btn.dataset.view;

        // Update active state
        viewToggle.querySelectorAll('.view-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');

        // Toggle list view class
        if (view === 'list') {
            libraryGrid.classList.add('list-view');
        } else {
            libraryGrid.classList.remove('list-view');
        }

        // Save preference
        localStorage.setItem('discoverView', view);
    });
}

// Auth Logic
async function checkAuthToken() {
    const urlParams = new URLSearchParams(window.location.search);
    const tokenFromUrl = urlParams.get('auth');
    const hostToken = tokenFromUrl;

    if (hostToken) {
        try {
            showNotification('Authenticating...', 'info');
            const response = await fetch('/api/auth', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ token: hostToken }),
                credentials: 'same-origin'
            });

            const data = await response.json();
            if (data.success) {
                userData = data.user;
                showNotification(`Welcome back, ${userData.first_name || userData.username}!`, 'success');
                // Clear URL param
                window.history.replaceState({}, document.title, window.location.pathname);
                updateUserUI();
                loadPlaylists();
            } else {
                showNotification('Invalid or expired token', 'error');
            }
        } catch (error) {
            console.error('Auth error:', error);
            showNotification('Authentication failed', 'error');
        }
    } else {
        // Нет токена в URL: пробуем восстановить user по HttpOnly cookie-сессии
        try {
            const response = await fetch('/api/me', { credentials: 'same-origin' });
            if (response.ok) {
                const data = await response.json();
                if (data?.success && data?.user) {
                    userData = data.user;
                    updateUserUI();
                    loadPlaylists();
                }
            }
        } catch (_) {
            // Ignore silently for anonymous users
        }
    }
}

function updateUserUI() {
    const userInfo = document.getElementById('userInfo');
    const loginBtn = document.getElementById('loginBtn');
    const displayUsername = document.getElementById('displayUsername');
    const userAvatar = document.getElementById('userAvatar');

    if (userData) {
        userInfo.style.display = 'flex';
        loginBtn.style.display = 'none';
        displayUsername.textContent = userData.first_name || userData.username;

        if (userAvatar) {
            const avatarUrl = userData.avatar_url;
            if (avatarUrl) {
                userAvatar.innerHTML = `<img src="${avatarUrl}" alt="Avatar" referrerpolicy="no-referrer" />`;
            } else {
                // Fallback: встроенная иконка из шаблона
                if (!userAvatar.querySelector('svg')) {
                    userAvatar.innerHTML = `
                        <svg viewBox="0 0 24 24" fill="currentColor">
                            <path d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z" />
                        </svg>
                    `;
                }
            }
        }
    } else {
        userInfo.style.display = 'none';
        loginBtn.style.display = 'block';
        if (userAvatar) {
            // Оставляем дефолтную иконку (она уже в HTML)
        }
    }
}

document.getElementById('loginBtn').addEventListener('click', () => {
    showNotification('Please use /login command in the Telegram bot', 'info');
});

// Logout
document.addEventListener('click', async (e) => {
    const btn = e.target.closest('#logoutBtn');
    if (!btn) return;
    try {
        const res = await fetch('/api/logout', {
            method: 'POST',
            credentials: 'same-origin'
        });
        // даже если сессии нет — просто сбрасываем UI
        if (!res.ok) {
            // ignore
        }
    } catch (_) {
        // ignore
    } finally {
        userData = null;
        updateUserUI();
        showNotification('Logged out', 'info');
    }
});

// Navigation
function initializeNavigation() {
    const navItems = document.querySelectorAll('.nav-item');
    const sections = document.querySelectorAll('.content-section');

    navItems.forEach(item => {
        item.addEventListener('click', (e) => {
            e.preventDefault();
            const page = item.dataset.page;

            navItems.forEach(nav => nav.classList.remove('active'));
            item.classList.add('active');

            sections.forEach(section => section.classList.remove('active'));
            document.getElementById(page === 'search' ? 'searchResults' : page).classList.add('active');

            if (page === 'playlists' && userData) {
                loadPlaylists();
            }

            if (page === 'history' && userData) {
                loadHistory();
            }
        });
    });
}

// Search functionality
function initializeSearch() {
    const searchInput = document.getElementById('searchInput');

    searchInput.addEventListener('input', (e) => {
        clearTimeout(searchTimeout);
        const query = e.target.value.trim();

        if (query.length < 2) {
            document.getElementById('resultsGrid').innerHTML = '';
            lastSearchQuery = '';
            return;
        }

        searchTimeout = setTimeout(() => {
            searchTracks(query);
        }, 280);
    });

    searchInput.addEventListener('keydown', (e) => {
        if (e.key !== 'Enter') return;
        clearTimeout(searchTimeout);
        const query = e.target.value.trim();
        if (query.length >= 2) {
            searchTracks(query);
        }
    });
}

async function searchTracks(query) {
    try {
        const normalizedQuery = (query || '').trim();
        if (!normalizedQuery || normalizedQuery === lastSearchQuery) return;
        lastSearchQuery = normalizedQuery;

        // Serve fresh cached results immediately
        const cached = searchCache.get(normalizedQuery);
        if (cached && (Date.now() - cached.ts) < 30000) {
            displayResults(cached.tracks || []);
            return;
        }

        // Cancel previous in-flight search request
        if (searchController) searchController.abort();
        searchController = new AbortController();

        // Skeleton вместо пустого состояния пока идет запрос
        const resultsGrid = document.getElementById('resultsGrid');
        if (resultsGrid) resultsGrid.innerHTML = renderTrackSkeletons(6);

        const response = await fetch('/api/search', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query: normalizedQuery }),
            signal: searchController.signal
        });

        const data = await response.json();
        const tracks = data.tracks || [];
        searchCache.set(normalizedQuery, { ts: Date.now(), tracks });
        displayResults(tracks);
    } catch (error) {
        if (error?.name === 'AbortError') return;
        console.error('Search error:', error);
        showNotification('Search failed. Please try again.', 'error');
    } finally {
        searchController = null;
    }
}

async function syncLibrary() {
    const btn = document.getElementById('syncLibraryBtn');
    if (!btn) return;
    try {
        btn.classList.add('spinning');
        btn.disabled = true;
        showNotification('Syncing discovery library...', 'info');

        const response = await fetch('/api/sync-library', {
            method: 'POST',
            credentials: 'same-origin'
        });

        const data = await response.json();
        if (data.success) {
            showNotification(`Sync complete! Added ${data.added_count} tracks.`, 'success');
            loadLibrary(); // Reload the library to show new tracks
        } else {
            showNotification(data.error || 'Sync failed', 'error');
        }
    } catch (error) {
        console.error('Sync error:', error);
        showNotification('Failed to connect to sync service', 'error');
    } finally {
        btn.classList.remove('spinning');
        btn.disabled = false;
    }
}

async function loadLibrary() {
    try {
        const libraryGrid = document.getElementById('libraryGrid');
        const librarySection = document.getElementById('librarySection');
        if (librarySection) librarySection.style.display = 'block';
        if (libraryGrid) libraryGrid.innerHTML = renderTrackSkeletons(12);

        const response = await fetch('/api/library');
        const data = await response.json();
        const libraryGridAfter = document.getElementById('libraryGrid');

        if (!data.tracks || data.tracks.length === 0) {
            document.getElementById('librarySection').style.display = 'none';
            return;
        }

        document.getElementById('librarySection').style.display = 'block';
        libraryData = data.tracks;
        libraryRendered = 0;
        renderLibraryChunk(true);
    } catch (error) {
        console.error('Load library error:', error);
    }
}

function renderLibraryChunk(reset = false) {
    const libraryGrid = document.getElementById('libraryGrid');
    if (!libraryGrid) return;
    if (isLibraryChunkLoading) return;
    isLibraryChunkLoading = true;
    if (reset) {
        libraryGrid.innerHTML = '';
        if (window.InfiniteScroll) window.InfiniteScroll.detach('library');
    }

    const start = libraryRendered;
    const end = Math.min(libraryRendered + LIBRARY_PAGE_SIZE, libraryData.length);
    if (start >= end) {
        isLibraryChunkLoading = false;
        if (window.InfiniteScroll) window.InfiniteScroll.detach('library');
        return;
    }

    const html = libraryData
        .slice(start, end)
        .map((track, idx) => renderTrackCard(track, start + idx, 'library'))
        .join('');
    libraryGrid.insertAdjacentHTML('beforeend', html);
    libraryRendered = end;
    isLibraryChunkLoading = false;

    if (libraryRendered < libraryData.length && window.InfiniteScroll) {
        window.InfiniteScroll.attach('library', libraryGrid, () => renderLibraryChunk(false));
    } else if (window.InfiniteScroll) {
        window.InfiniteScroll.detach('library');
    }
}

function displayResults(tracks) {
    const resultsGrid = document.getElementById('resultsGrid');
    resultsData = tracks;

    if (tracks.length === 0) {
        resultsGrid.innerHTML = window.AppUI.emptyState('No results found');
        return;
    }

    resultsGrid.innerHTML = tracks.map((track, index) => renderTrackCard(track, index, 'search')).join('');
}

function renderTrackCard(track, index, type = 'search') {
    return `
        <div class="track-card" data-index="${index}" data-type="${type}">
            <div class="track-image">
                ${track.image ? `<img loading="lazy" decoding="async" src="${track.image}" alt="${track.name}" />` :
            `<svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 3v10.55c-.59-.34-1.27-.55-2-.55-2.21 0-4 1.79-4 4s1.79 4 4 4 4-1.79 4-4V7h4V3h-6z"/></svg>`}
            </div>
            <div class="track-info">
                <div class="track-name" title="${track.name}">${track.name}</div>
                <div class="track-artist" title="${track.artist}">${track.artist}</div>
            </div>
            <div class="track-actions">
                <button class="action-btn play-track-btn" onclick="playTrack(this)">
                    <svg viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>
                </button>
                <button class="action-btn secondary" onclick="openDownloadModal(this)">
                    <svg viewBox="0 0 24 24" fill="currentColor"><path d="M19 12v7H5v-7H3v7c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2v-7h-2zm-6 .67l2.59-2.58L17 11.5l-5 5-5-5 1.41-1.41L11 12.67V3h2z"/></svg>
                </button>
                ${userData ? `<button class="action-btn secondary" onclick="openAddToPlaylistModal(${index}, '${type}')">
                    <svg viewBox="0 0 24 24" fill="currentColor"><path d="M19 13h-6v6h-2v-6H5v-2h6V5h2v6h6v2z"/></svg>
                </button>` : ''}
            </div>
        </div>
    `;
}

// Playback Logic
async function playTrack(button, trackData = null) {
    let track, index, type;

    if (trackData) {
        // Called from playNext/playPrevious
        track = trackData;
    } else {
        // Toggle pause/resume for the same card button
        if (button && currentCardPlayBtn === button && !audioPlayer.paused) {
            audioPlayer.pause();
            return;
        }

        // Called from UI button click
        const card = button.closest('.track-card');
        index = parseInt(card.dataset.index);
        type = card.dataset.type;
        track = type === 'library' ? libraryData[index] : resultsData[index];

        // Set current playlist and index
        currentPlaylist = type === 'library' ? libraryData : resultsData;
        currentTrackIndex = index;
        updateQueueStatus();
    }

    if (!track) return;

    // Обновляем правую панель сразу при выборе трека
    updateNowPlayingPanel(track);
    persistLastPlayedTrack(track);

    if (button && currentCardPlayBtn && currentCardPlayBtn !== button) {
        setCardPlayButtonState(currentCardPlayBtn, false);
    }
    if (button) {
        currentCardPlayBtn = button;
    }

    // Сначала пробуем Spotify preview (30 секунд)
    if (track.preview_url) {
        currentTrack = track;
        persistLastPlayedTrack(track);
        audioPlayer.src = track.preview_url;
        audioPlayer.play().catch(err => {
            console.error('Preview play error:', err);
            // Если preview не сработал, пробуем YouTube
            playFromYouTube(track);
        });
        updatePlayerUI(track);
        updatePlayButton(true);
    } else {
        // Нет preview - сразу используем YouTube
        playFromYouTube(track);
    }
}

async function playFromYouTube(track) {
    try {
        if (!userData) {
            showNotification('Please login first', 'info');
            return;
        }

        showNotification('Preparing track...', 'info');

        // Автоподхват сохранённой позиции для этого трека (если есть)
        pendingSeekSeconds = null;
        try {
            const raw = localStorage.getItem(PLAYBACK_STORAGE_KEY);
            const state = raw ? JSON.parse(raw) : null;
            if (state && state.trackId && state.trackId === track.id && typeof state.position === 'number' && state.position > 2) {
                pendingSeekSeconds = state.position;
            }
        } catch (_) {}

        const response = await fetch('/api/prepare-stream', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            credentials: 'same-origin',
            body: JSON.stringify({
                id: track.id,
                artist: track.artist,
                name: track.name,
                image: track.image
            })
        });

        const data = await response.json();

        if (response.ok && data.stream_url) {
            currentTrack = track;
            persistLastPlayedTrack(track);
            // Используем прямую ссылку из Telegram
            audioPlayer.src = data.stream_url;
            audioPlayer.play().catch(err => {
                console.error('Play error:', err);
                showNotification('Could not play track', 'error');
            });
            if (pendingSeekSeconds != null) {
                const seekTo = pendingSeekSeconds;
                const onMeta = () => {
                    try {
                        // не прыгаем почти в конец
                        if (audioPlayer.duration && seekTo < (audioPlayer.duration - 2)) {
                            audioPlayer.currentTime = seekTo;
                        }
                    } finally {
                        audioPlayer.removeEventListener('loadedmetadata', onMeta);
                        pendingSeekSeconds = null;
                    }
                };
                audioPlayer.addEventListener('loadedmetadata', onMeta);
            }
            updatePlayerUI(track);
            updatePlayButton(true);

            // Показываем статус кеширования
            if (data.cached) {
                showNotification('Playing from cache!', 'success');
            } else {
                showNotification('Now playing!', 'success');
            }
        } else {
            showNotification(data.error || 'Could not load track', 'error');
        }
    } catch (error) {
        console.error('Stream error:', error);
        showNotification('Failed to load track for streaming', 'error');
    }
}

function updatePlayerUI(track) {
    const playerTrackInfo = document.querySelector('.player-track-info');
    playerTrackInfo.querySelector('.track-image').innerHTML = track.image ?
        `<img class="player-track-cover" src="${track.image}" alt="${track.name}" />` :
        `<svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 3v10.55c-.59-.34-1.27-.55-2-.55-2.21 0-4 1.79-4 4s1.79 4 4 4 4-1.79 4-4V7h4V3h-6z" /></svg>`;
    playerTrackInfo.querySelector('.track-name').textContent = track.name;
    playerTrackInfo.querySelector('.track-artist').textContent = track.artist;

    updateNowPlayingPanel(track);
}

function initializePlayer() {
    const playBtn = document.getElementById('playBtn');
    const volumeSlider = document.querySelector('.volume-slider');
    const progressSlider = document.getElementById('progressSlider');
    const currentTimeEl = document.getElementById('currentTime');
    const totalTimeEl = document.getElementById('totalTime');

    playBtn.addEventListener('click', () => {
        if (audioPlayer.paused) {
            // Если src пустой (после refresh), стартуем текущий трек через prepare-stream
            const hasSrc = !!(audioPlayer.src && audioPlayer.src !== window.location.href);
            if (!hasSrc && currentTrack) {
                playTrack(null, currentTrack);
                return;
            }
            audioPlayer.play().catch(() => showNotification('Не удалось воспроизвести', 'error'));
            updatePlayButton(true);
        } else {
            audioPlayer.pause();
            updatePlayButton(false);
        }
    });

    volumeSlider.addEventListener('input', (e) => audioPlayer.volume = e.target.value / 100);

    // Обновление прогресса
    audioPlayer.addEventListener('timeupdate', () => {
        if (!audioPlayer.duration) return;
        const progress = (audioPlayer.currentTime / audioPlayer.duration) * 100;
        progressSlider.value = progress;
        currentTimeEl.textContent = formatTime(audioPlayer.currentTime);

        // Сохраняем позицию (throttle ~1.5s)
        const now = Date.now();
        if (currentTrack?.id && (now - lastPlaybackSaveAt) > 1500) {
            lastPlaybackSaveAt = now;
            try {
                localStorage.setItem(PLAYBACK_STORAGE_KEY, JSON.stringify({
                    trackId: currentTrack.id,
                    position: audioPlayer.currentTime,
                    duration: audioPlayer.duration,
                    updatedAt: now
                }));
            } catch (_) {}
        }
    });

    // Установка общей длительности + восстановление UI прогресса
    audioPlayer.addEventListener('loadedmetadata', () => {
        totalTimeEl.textContent = formatTime(audioPlayer.duration);
        try {
            const raw = localStorage.getItem(PLAYBACK_STORAGE_KEY);
            const state = raw ? JSON.parse(raw) : null;
            if (state && state.trackId && currentTrack?.id && state.trackId === currentTrack.id && typeof state.position === 'number') {
                currentTimeEl.textContent = formatTime(state.position);
                if (audioPlayer.duration && audioPlayer.duration > 0) {
                    const progress = Math.min(100, Math.max(0, (state.position / audioPlayer.duration) * 100));
                    progressSlider.value = progress;
                }
            }
        } catch (_) { }
    });

    // Синхронизация иконок плеера/карточки с реальным состоянием аудио
    audioPlayer.addEventListener('play', () => {
        updatePlayButton(true);
        if (currentCardPlayBtn) setCardPlayButtonState(currentCardPlayBtn, true);
    });
    audioPlayer.addEventListener('pause', () => {
        updatePlayButton(false);
        if (currentCardPlayBtn) setCardPlayButtonState(currentCardPlayBtn, false);

        // Надёжно сохраняем позицию при паузе (на случай, если timeupdate не успел)
        try {
            const now = Date.now();
            if (currentTrack?.id && Number.isFinite(audioPlayer.currentTime)) {
                localStorage.setItem(PLAYBACK_STORAGE_KEY, JSON.stringify({
                    trackId: currentTrack.id,
                    position: audioPlayer.currentTime,
                    duration: Number.isFinite(audioPlayer.duration) ? audioPlayer.duration : 0,
                    updatedAt: now
                }));
                lastPlaybackSaveAt = now;
            }
        } catch (_) { }
    });

    // Перемотка
    progressSlider.addEventListener('input', (e) => {
        const time = (e.target.value / 100) * audioPlayer.duration;
        audioPlayer.currentTime = time;
    });

    // После перемотки тоже фиксируем позицию
    audioPlayer.addEventListener('seeked', () => {
        try {
            const now = Date.now();
            if (currentTrack?.id && Number.isFinite(audioPlayer.currentTime)) {
                localStorage.setItem(PLAYBACK_STORAGE_KEY, JSON.stringify({
                    trackId: currentTrack.id,
                    position: audioPlayer.currentTime,
                    updatedAt: now
                }));
                lastPlaybackSaveAt = now;
            }
        } catch (_) { }
    });

    audioPlayer.addEventListener('ended', () => {
        // Сброс сохранённой позиции, чтобы при следующем старте не начинать "с конца"
        if (currentTrack?.id) {
            try {
                const raw = localStorage.getItem(PLAYBACK_STORAGE_KEY);
                const state = raw ? JSON.parse(raw) : null;
                if (state && state.trackId === currentTrack.id) {
                    state.position = 0;
                    state.updatedAt = Date.now();
                    localStorage.setItem(PLAYBACK_STORAGE_KEY, JSON.stringify(state));
                }
            } catch (_) {}
        }
        if (isRepeatEnabled) {
            // Repeat current track
            audioPlayer.currentTime = 0;
            audioPlayer.play();
        } else {
            // Play next track
            playNext();
        }
    });

    // Add event listeners for new controls
    document.getElementById('shuffleBtn').addEventListener('click', toggleShuffle);
    document.getElementById('repeatBtn').addEventListener('click', toggleRepeat);
    document.getElementById('prevBtn').addEventListener('click', playPrevious);
    document.getElementById('nextBtn').addEventListener('click', playNext);
}

function formatTime(seconds) {
    if (isNaN(seconds)) return '0:00';
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}: ${secs < 10 ? '0' : ''}${secs}`;
}

function updatePlayButton(isPlaying) {
    document.getElementById('playBtn').innerHTML = isPlaying ?
        `<svg viewBox="0 0 24 24" fill="currentColor"><path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z" /></svg>` :
        `<svg viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z" /></svg>`;
}

function setCardPlayButtonState(button, isPlaying) {
    if (!button) return;
    button.innerHTML = isPlaying
        ? `<svg viewBox="0 0 24 24" fill="currentColor"><path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z" /></svg>`
        : `<svg viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>`;
}

// Player control functions
function toggleRepeat() {
    isRepeatEnabled = !isRepeatEnabled;
    const repeatBtn = document.getElementById('repeatBtn');
    if (isRepeatEnabled) {
        repeatBtn.classList.remove('inactive');
        showNotification('Repeat enabled', 'success');
    } else {
        repeatBtn.classList.add('inactive');
        showNotification('Repeat disabled', 'info');
    }
    updateQueueStatus();
}

function toggleShuffle() {
    isShuffleEnabled = !isShuffleEnabled;
    const shuffleBtn = document.getElementById('shuffleBtn');
    if (isShuffleEnabled) {
        shuffleBtn.classList.remove('inactive');
        showNotification('Shuffle enabled', 'success');
    } else {
        shuffleBtn.classList.add('inactive');
        showNotification('Shuffle disabled', 'info');
    }
}

function playNext() {
    if (currentPlaylist.length === 0) {
        showNotification('No playlist active', 'info');
        return;
    }

    if (isShuffleEnabled) {
        // Random next track
        const randomIndex = Math.floor(Math.random() * currentPlaylist.length);
        currentTrackIndex = randomIndex;
    } else {
        // Sequential next track
        currentTrackIndex = (currentTrackIndex + 1) % currentPlaylist.length;
    }

    const nextTrack = currentPlaylist[currentTrackIndex];
    updateQueueStatus();
    playTrack(null, nextTrack);
}

function playPrevious() {
    if (currentPlaylist.length === 0) {
        showNotification('No playlist active', 'info');
        return;
    }

    // Always go to previous track sequentially
    currentTrackIndex = (currentTrackIndex - 1 + currentPlaylist.length) % currentPlaylist.length;
    const prevTrack = currentPlaylist[currentTrackIndex];
    updateQueueStatus();
    playTrack(null, prevTrack);
}

// Playlists Logic
function initializePlaylists() {
    // Modal events
    document.getElementById('createPlaylistModal').addEventListener('click', (e) => {
        if (e.target.id === 'createPlaylistModal') closeCreatePlaylistModal();
    });
    document.getElementById('addToPlaylistModal').addEventListener('click', (e) => {
        if (e.target.id === 'addToPlaylistModal') closeAddToPlaylistModal();
    });
}

function initializeUploadTrack() {
    const btn = document.getElementById('uploadMusicBtn');
    btn?.addEventListener('click', () => {
        if (!userData) {
            showNotification('Please login first', 'info');
            return;
        }
        document.getElementById('uploadTrackModal')?.classList.add('active');
    });

    document.getElementById('uploadTrackModal')?.addEventListener('click', (e) => {
        if (e.target.id === 'uploadTrackModal') closeUploadTrackModal();
    });
}

function closeUploadTrackModal() {
    document.getElementById('uploadTrackModal')?.classList.remove('active');
}

async function uploadTrack() {
    if (!userData) {
        showNotification('Please login first', 'info');
        return;
    }
    const fileInput = document.getElementById('uploadTrackFile');
    const nameInput = document.getElementById('uploadTrackName');
    const artistInput = document.getElementById('uploadTrackArtist');
    const coverInput = document.getElementById('uploadTrackCover');
    const file = fileInput?.files?.[0];
    if (!file) {
        showNotification('Choose audio file first', 'error');
        return;
    }

    const formData = new FormData();
    formData.append('file', file);
    formData.append('name', (nameInput?.value || '').trim());
    formData.append('artist', (artistInput?.value || '').trim());
    const coverFile = coverInput?.files?.[0];
    if (coverFile) {
        formData.append('cover', coverFile);
    }

    try {
        showNotification('Uploading track...', 'info');
        const response = await fetch('/api/upload-track', {
            method: 'POST',
            credentials: 'same-origin',
            body: formData
        });
        const data = await response.json();
        if (!response.ok || !data.success) {
            showNotification(data.error || 'Upload failed', 'error');
            return;
        }

        showNotification('Track uploaded to library', 'success');
        closeUploadTrackModal();
        if (fileInput) fileInput.value = '';
        if (nameInput) nameInput.value = '';
        if (artistInput) artistInput.value = '';
        if (coverInput) coverInput.value = '';

        await loadLibrary();
    } catch (error) {
        console.error('Upload track error:', error);
        showNotification('Upload failed', 'error');
    }
}

async function loadPlaylists() {
    if (!userData) return;
    try {
        const grid = document.getElementById('playlistsGrid');
        if (grid) grid.innerHTML = renderPlaylistsSkeletons(6);

        const response = await fetch('/api/playlists', {
            credentials: 'same-origin'
        });
        const data = await response.json();
        displayPlaylists(data.playlists || []);
    } catch (error) {
        console.error('Load playlists error:', error);
    }
}

function displayPlaylists(playlists) {
    const grid = document.getElementById('playlistsGrid');
    if (playlists.length === 0) {
        grid.innerHTML = '<p style="grid-column: 1/-1; text-align: center; color: var(--spotify-light-gray); padding: 48px;">No playlists created yet.</p>';
        return;
    }

    grid.innerHTML = playlists.map(pl => `
        <div class="playlist-card" onclick="viewPlaylist(${pl.id}, '${pl.name.replace(/'/g, "\\'")}')">
            <div class="playlist-icon">
                <svg viewBox="0 0 24 24" fill="currentColor"><path d="M15 6H3v2h12V6zm0 4H3v2h12v-2zM3 16h8v-2H3v2zM17 6v8.18c-.31-.11-.65-.18-1-.18-1.66 0-3 1.34-3 3s1.34 3 3 3 3-1.34 3-3V8h3V6h-5z" /></svg>
            </div>
            <div class="playlist-name">${pl.name}</div>
            <div class="playlist-count">${pl.track_count} tracks</div>
        </div>
    `).join('');
}

async function viewPlaylist(playlistId, playlistName) {
    if (!userData) return;

    try {
        const response = await fetch(`/api/playlists/${playlistId}/tracks`, {
            credentials: 'same-origin'
        });
        const data = await response.json();

        if (response.ok) {
            // Переключаемся на раздел поиска и показываем треки плейлиста
            document.querySelectorAll('.content-section').forEach(s => s.classList.remove('active'));
            document.getElementById('searchResults').classList.add('active');

            // Обновляем навигацию
            document.querySelectorAll('.nav-item').forEach(nav => nav.classList.remove('active'));
            document.querySelector('[data-page="search"]').classList.add('active');

            // Показываем треки
            displayResults(data.tracks || []);

            // Обновляем заголовок поиска
            const searchInput = document.getElementById('searchInput');
            searchInput.value = `Playlist: ${playlistName}`;

            showNotification(`Showing ${data.tracks.length} tracks from "${playlistName}"`, 'success');
        } else {
            showNotification(data.error || 'Failed to load playlist', 'error');
        }
    } catch (error) {
        console.error('View playlist error:', error);
        showNotification('Failed to load playlist tracks', 'error');
    }
}

function openCreatePlaylistModal() {
    if (!userData) {
        showNotification('Please login first', 'info');
        return;
    }
    document.getElementById('createPlaylistModal').classList.add('active');
}

function closeCreatePlaylistModal() {
    document.getElementById('createPlaylistModal').classList.remove('active');
}

async function createPlaylist() {
    const name = document.getElementById('playlistNameInput').value.trim();
    const description = document.getElementById('playlistDescInput').value.trim();

    if (!name) return;

    try {
        const response = await fetch('/api/playlists', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            credentials: 'same-origin',
            body: JSON.stringify({ name, description })
        });

        if (response.ok) {
            showNotification('Playlist created!', 'success');
            closeCreatePlaylistModal();
            loadPlaylists();
        }
    } catch (error) {
        showNotification('Failed to create playlist', 'error');
    }
}

let trackToPlaylist = null;
function openAddToPlaylistModal(trackIndex, type = 'search') {
    trackToPlaylist = type === 'library' ? libraryData[trackIndex] : resultsData[trackIndex];
    loadPlaylistsForSelection();
    document.getElementById('addToPlaylistModal').classList.add('active');
}

function closeAddToPlaylistModal() {
    document.getElementById('addToPlaylistModal').classList.remove('active');
}

async function loadPlaylistsForSelection() {
    try {
        const response = await fetch('/api/playlists', {
            credentials: 'same-origin'
        });
        const data = await response.json();
        const list = document.getElementById('playlistsSelectionList');

        if (data.playlists.length === 0) {
            list.innerHTML = '<p>No playlists found. Create one first!</p>';
            return;
        }

        list.innerHTML = data.playlists.map(pl => `
            <div class="pl-selection-item" onclick="addTrackToPlaylist(${pl.id})">
                ${pl.name} (${pl.track_count} tracks)
            </div>
        `).join('');
    } catch (error) {
        console.error('Load selection error:', error);
    }
}

async function addTrackToPlaylist(playlistId) {
    if (!trackToPlaylist) return;

    try {
        const response = await fetch('/api/playlists/add_track', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            credentials: 'same-origin',
            body: JSON.stringify({
                playlist_id: playlistId,
                track: trackToPlaylist
            })
        });

        const data = await response.json();
        if (response.ok) {
            showNotification('Added to playlist!', 'success');
            closeAddToPlaylistModal();
            loadPlaylists();
        } else {
            showNotification(data.error || 'Failed to add track', 'error');
        }
    } catch (error) {
        showNotification('Critical error', 'error');
    }
}

// Download & Modal Helpers
function openDownloadModal(button) {
    const card = button.closest('.track-card');
    const index = parseInt(card.dataset.index);
    const type = card.dataset.type;
    currentTrack = type === 'library' ? libraryData[index] : resultsData[index];
    document.getElementById('downloadModal').classList.add('active');
}

function closeDownloadModal() {
    document.getElementById('downloadModal').classList.remove('active');
}

async function startDownload() {
    if (!currentTrack) return;
    const format = document.querySelector('input[name="format"]:checked').value;
    const quality = document.getElementById('qualitySelect').value;

    try {
        showNotification('Starting download...', 'info');
        const response = await fetch('/api/download', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            credentials: 'same-origin',
            body: JSON.stringify({
                track_id: currentTrack.id || '',
                track_name: currentTrack.name,
                track_artist: currentTrack.artist,
                quality: quality,
                format: format
            })
        });

        if (response.ok) {
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `${currentTrack.artist} - ${currentTrack.name}.${format}`;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);
            showNotification('Download completed!', 'success');
            closeDownloadModal();
        } else {
            showNotification('Download failed', 'error');
        }
    } catch (error) {
        showNotification('Download error', 'error');
    }
}

function showNotification(message, type = 'info') {
    if (window.AppUI && typeof window.AppUI.showNotification === 'function') {
        window.AppUI.showNotification(message, type);
        return;
    }
    console.log(`[${type}] ${message}`);
}

document.getElementById('downloadModal').addEventListener('click', (e) => {
    if (e.target.id === 'downloadModal') closeDownloadModal();
});

document.getElementById('historyDetailsModal')?.addEventListener('click', (e) => {
    if (e.target.id === 'historyDetailsModal') closeHistoryDetailsModal();
});

// Format Quality Switcher
document.querySelectorAll('input[name="format"]').forEach(radio => {
    radio.addEventListener('change', (e) => {
        const qualitySelect = document.getElementById('qualitySelect');
        if (e.target.value === 'flac') {
            qualitySelect.innerHTML = `<option value="1411">1411 kbps (CD)</option><option value="2300">2300 kbps (Hi-Res)</option>`;
        } else {
            qualitySelect.innerHTML = `<option value="128">128 kbps</option><option value="192">192 kbps</option><option value="320" selected>320 kbps</option>`;
        }
    });
});
