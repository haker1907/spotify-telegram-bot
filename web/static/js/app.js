// Music Downloader - Spotify Style Web App

let currentTrack = null;
let searchTimeout = null;
let resultsData = [];
let libraryData = [];
let userData = JSON.parse(localStorage.getItem('userData') || 'null');
const audioPlayer = document.getElementById('audioPlayer');

// Player state variables
let isRepeatEnabled = false;
let isShuffleEnabled = false;
let currentPlaylist = [];
let currentTrackIndex = -1;

// Initialize app
document.addEventListener('DOMContentLoaded', () => {
    checkAuthToken();
    updateUserUI();
    initializeNavigation();
    initializeSearch();
    initializePlayer();
    initializePlaylists();
    initializeViewToggle();
    loadLibrary();

    if (userData) {
        loadPlaylists();
    }

    // Backup БД при закрытии/обновлении страницы
    window.addEventListener('beforeunload', function (e) {
        // Отправляем запрос на backup (используем sendBeacon для надежности)
        const backupUrl = '/api/backup-db';

        // sendBeacon гарантирует отправку даже при закрытии страницы
        if (navigator.sendBeacon) {
            navigator.sendBeacon(backupUrl, new Blob([JSON.stringify({})], { type: 'application/json' }));
        } else {
            // Fallback для старых браузеров
            fetch(backupUrl, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({}),
                keepalive: true  // Важно для отправки при закрытии
            }).catch(err => console.log('Backup request failed:', err));
        }
    });
});

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
    const hostToken = urlParams.get('auth');

    if (hostToken) {
        try {
            showNotification('Authenticating...', 'info');
            const response = await fetch('/api/auth', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ token: hostToken })
            });

            const data = await response.json();
            if (data.success) {
                userData = data.user;
                localStorage.setItem('userData', JSON.stringify(userData));
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
    }
}

function updateUserUI() {
    const userInfo = document.getElementById('userInfo');
    const loginBtn = document.getElementById('loginBtn');
    const displayUsername = document.getElementById('displayUsername');

    if (userData) {
        userInfo.style.display = 'flex';
        loginBtn.style.display = 'none';
        displayUsername.textContent = userData.first_name || userData.username;
    } else {
        userInfo.style.display = 'none';
        loginBtn.style.display = 'block';
    }
}

document.getElementById('loginBtn').addEventListener('click', () => {
    showNotification('Please use /login command in the Telegram bot', 'info');
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
            return;
        }

        searchTimeout = setTimeout(() => {
            if (query.includes('spotify.com') || query.includes('open.spotify')) {
                searchTracks(query);
            } else {
                searchTracks(query);
            }
        }, 500);
    });
}

async function searchTracks(query) {
    try {
        const response = await fetch('/api/search', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query })
        });

        const data = await response.json();
        displayResults(data.tracks || []);
    } catch (error) {
        console.error('Search error:', error);
        showNotification('Search failed. Please try again.', 'error');
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
            method: 'POST'
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
        const response = await fetch('/api/library');
        const data = await response.json();
        const libraryGrid = document.getElementById('libraryGrid');

        if (!data.tracks || data.tracks.length === 0) {
            document.getElementById('librarySection').style.display = 'none';
            return;
        }

        document.getElementById('librarySection').style.display = 'block';
        libraryGrid.innerHTML = '';
        libraryData = data.tracks;

        data.tracks.forEach((track, index) => {
            const card = renderTrackCard(track, index, 'library');
            libraryGrid.innerHTML += card;
        });
    } catch (error) {
        console.error('Load library error:', error);
    }
}

function displayResults(tracks) {
    const resultsGrid = document.getElementById('resultsGrid');
    resultsData = tracks;

    if (tracks.length === 0) {
        resultsGrid.innerHTML = '<p style="grid-column: 1/-1; text-align: center; color: var(--spotify-light-gray); padding: 48px;">No results found</p>';
        return;
    }

    resultsGrid.innerHTML = tracks.map((track, index) => renderTrackCard(track, index, 'search')).join('');
}

function renderTrackCard(track, index, type = 'search') {
    return `
        <div class="track-card" data-index="${index}" data-type="${type}">
            <div class="track-image">
                ${track.image ? `<img src="${track.image}" alt="${track.name}" />` :
            `<svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 3v10.55c-.59-.34-1.27-.55-2-.55-2.21 0-4 1.79-4 4s1.79 4 4 4 4-1.79 4-4V7h4V3h-6z"/></svg>`}
            </div>
            <div class="track-info">
                <div class="track-name" title="${track.name}">${track.name}</div>
                <div class="track-artist" title="${track.artist}">${track.artist}</div>
            </div>
            <div class="track-actions">
                <button class="action-btn" onclick="playTrack(this)">
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
        // Called from UI button click
        const card = button.closest('.track-card');
        index = parseInt(card.dataset.index);
        type = card.dataset.type;
        track = type === 'library' ? libraryData[index] : resultsData[index];

        // Set current playlist and index
        currentPlaylist = type === 'library' ? libraryData : resultsData;
        currentTrackIndex = index;
    }

    if (!track) return;

    // Сначала пробуем Spotify preview (30 секунд)
    if (track.preview_url) {
        currentTrack = track;
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
        showNotification('Preparing track...', 'info');

        const response = await fetch('/api/prepare-stream', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
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
            // Используем прямую ссылку из Telegram
            audioPlayer.src = data.stream_url;
            audioPlayer.play().catch(err => {
                console.error('Play error:', err);
                showNotification('Could not play track', 'error');
            });
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
        `<img src="${track.image}" style="width: 100%; height: 100%; object-fit: cover; border-radius: 4px;" />` :
        `<svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 3v10.55c-.59-.34-1.27-.55-2-.55-2.21 0-4 1.79-4 4s1.79 4 4 4 4-1.79 4-4V7h4V3h-6z" /></svg>`;
    playerTrackInfo.querySelector('.track-name').textContent = track.name;
    playerTrackInfo.querySelector('.track-artist').textContent = track.artist;
}

function initializePlayer() {
    const playBtn = document.getElementById('playBtn');
    const volumeSlider = document.querySelector('.volume-slider');
    const progressSlider = document.getElementById('progressSlider');
    const currentTimeEl = document.getElementById('currentTime');
    const totalTimeEl = document.getElementById('totalTime');

    playBtn.addEventListener('click', () => {
        if (audioPlayer.paused) {
            audioPlayer.play();
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
    });

    // Установка общей длительности
    audioPlayer.addEventListener('loadedmetadata', () => {
        totalTimeEl.textContent = formatTime(audioPlayer.duration);
    });

    // Перемотка
    progressSlider.addEventListener('input', (e) => {
        const time = (e.target.value / 100) * audioPlayer.duration;
        audioPlayer.currentTime = time;
    });

    audioPlayer.addEventListener('ended', () => {
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

async function loadPlaylists() {
    if (!userData) return;
    try {
        const response = await fetch('/api/playlists', {
            headers: { 'X-User-ID': userData.id.toString() }
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
            headers: { 'X-User-ID': userData.id.toString() }
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
                'Content-Type': 'application/json',
                'X-User-ID': userData.id.toString()
            },
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
            headers: { 'X-User-ID': userData.id.toString() }
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
                'Content-Type': 'application/json',
                'X-User-ID': userData.id.toString()
            },
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
            headers: { 'Content-Type': 'application/json' },
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
    const notification = document.createElement('div');
    notification.style.cssText = `
        position: fixed; top: 24px; right: 24px;
        background: ${type === 'error' ? '#e22134' : type === 'success' ? '#1db954' : '#2a2a2a'};
        color: white; padding: 16px 24px; border-radius: 8px;
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.3); z-index: 10000;
        animation: slideIn 0.3s ease; font-size: 14px; font-weight: 600;
    `;
    notification.textContent = message;
    document.body.appendChild(notification);
    setTimeout(() => {
        notification.style.animation = 'slideOut 0.3s ease';
        setTimeout(() => notification.remove(), 300);
    }, 3000);
}

document.getElementById('downloadModal').addEventListener('click', (e) => {
    if (e.target.id === 'downloadModal') closeDownloadModal();
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
