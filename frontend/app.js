document.addEventListener('DOMContentLoaded', () => {
    if (window.lucide) {
        lucide.createIcons();
    }

    const extractForm = document.getElementById('extractForm');
    const youtubeUrlInput = document.getElementById('youtubeUrl');
    const pasteBtn = document.getElementById('pasteBtn');
    const submitBtn = document.getElementById('submitBtn');
    const ffmpegAlert = document.getElementById('ffmpegAlert');
    const copyCmdBtn = document.getElementById('copyCmdBtn');
    
    const progressSection = document.getElementById('progressSection');
    const statusMessage = document.getElementById('statusMessage');
    const progressBar = document.getElementById('progressBar');
    const progressPercent = document.getElementById('progressPercent');
    const speedMetric = document.getElementById('speedMetric');
    const etaMetric = document.getElementById('etaMetric');
    
    const resultCard = document.getElementById('resultCard');
    const videoThumbnail = document.getElementById('videoThumbnail');
    const videoTitle = document.getElementById('videoTitle');
    const videoChannel = document.getElementById('videoChannel');
    const videoDuration = document.getElementById('videoDuration');
    const outputSpec = document.getElementById('outputSpec');
    const sourceSpec = document.getElementById('sourceSpec');
    const audioPreview = document.getElementById('audioPreview');
    const downloadBtn = document.getElementById('downloadBtn');
    const resetBtn = document.getElementById('resetBtn');

    const playlistCard = document.getElementById('playlistCard');
    const playlistTitle = document.getElementById('playlistTitle');
    const playlistCount = document.getElementById('playlistCount');
    const playlistDownloadBtn = document.getElementById('playlistDownloadBtn');
    const playlistResetBtn = document.getElementById('playlistResetBtn');

    const errorCard = document.getElementById('errorCard');
    const errorMessage = document.getElementById('errorMessage');
    const errorRetryBtn = document.getElementById('errorRetryBtn');

    let pollInterval = null;

    fetchSystemStatus();

    async function fetchSystemStatus() {
        try {
            const res = await fetch('/api/system-status');
            if (res.ok) {
                const data = await res.json();
                if (!data.ffmpeg_installed) {
                    ffmpegAlert.classList.remove('hidden');
                }
            }
        } catch (e) {
            console.log('System check:', e);
        }
    }

    pasteBtn.addEventListener('click', async () => {
        try {
            const text = await navigator.clipboard.readText();
            if (text) {
                youtubeUrlInput.value = text.trim();
                youtubeUrlInput.focus();
            }
        } catch (err) {
            console.warn('Clipboard read failed:', err);
        }
    });

    copyCmdBtn.addEventListener('click', () => {
        navigator.clipboard.writeText('winget install ffmpeg');
        copyCmdBtn.innerHTML = '<i data-lucide="check"></i>';
        if (window.lucide) lucide.createIcons();
        setTimeout(() => {
            copyCmdBtn.innerHTML = '<i data-lucide="copy"></i>';
            if (window.lucide) lucide.createIcons();
        }, 2000);
    });

    const qualityOptions = document.querySelectorAll('.quality-option');
    qualityOptions.forEach(option => {
        option.addEventListener('click', () => {
            qualityOptions.forEach(o => o.classList.remove('active'));
            option.classList.add('active');
            const radio = option.querySelector('input[type="radio"]');
            if (radio) radio.checked = true;
        });
    });

    extractForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const url = youtubeUrlInput.value.trim();
        const selectedQuality = document.querySelector('input[name="quality"]:checked')?.value || "192";

        if (!url) return;

        resetUIState();
        showProgressSection();
        submitBtn.disabled = true;

        try {
            const res = await fetch('/extract', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url: url, quality: selectedQuality })
            });

            const data = await res.json();

            if (!res.ok) {
                throw new Error(data.detail || 'Failed to start extraction.');
            }

            const jobId = data.job_id;
            pollJobStatus(jobId);

        } catch (err) {
            showErrorState(err.message);
            submitBtn.disabled = false;
        }
    });

    function showProgressSection() {
        progressSection.classList.remove('hidden');
    }

    function pollJobStatus(jobId) {
        if (pollInterval) clearInterval(pollInterval);

        pollInterval = setInterval(async () => {
            try {
                const res = await fetch(`/status/${jobId}`);
                if (!res.ok) {
                    throw new Error('Failed to fetch job status.');
                }

                const job = await res.json();
                updateProgressUI(job);

                if (job.status === 'completed') {
                    clearInterval(pollInterval);
                    pollInterval = null;
                    setTimeout(() => renderCompletedResult(job), 400);
                } else if (job.status === 'error') {
                    clearInterval(pollInterval);
                    pollInterval = null;
                    showErrorState(job.error || 'Audio extraction failed.');
                }
            } catch (err) {
                clearInterval(pollInterval);
                pollInterval = null;
                showErrorState(err.message);
            }
        }, 1000);
    }

    function updateProgressUI(job) {
        const percent = Math.min(100, Math.max(0, job.progress || 0));
        progressBar.style.width = `${percent}%`;
        progressPercent.textContent = `${Math.round(percent)}%`;
        statusMessage.textContent = job.message || 'Processing stream...';

        speedMetric.innerHTML = `<i data-lucide="download-cloud"></i> ${job.speed || '-- KB/s'}`;
        etaMetric.innerHTML = `<i data-lucide="clock"></i> ETA: ${job.eta || '--'}`;
        if (window.lucide) lucide.createIcons();
    }

    function renderCompletedResult(job) {
        progressSection.classList.add('hidden');
        submitBtn.disabled = false;

        if (job.is_playlist) {
            playlistTitle.textContent = job.title;
            playlistCount.textContent = `${job.total_items || 0} tracks converted to MP3`;
            playlistDownloadBtn.href = job.download_url;
            playlistCard.classList.remove('hidden');
        } else {
            videoThumbnail.src = job.thumbnail || 'https://via.placeholder.com/140x80?text=Audio';
            videoTitle.textContent = job.title || 'YouTube Audio Track';
            videoChannel.textContent = job.channel || 'YouTube';
            videoDuration.textContent = formatDuration(job.duration || 0);

            outputSpec.textContent = job.bitrate || '192kbps MP3';
            sourceSpec.textContent = job.source_info ? `Source: ${job.source_info}` : 'Converted Stream';

            downloadBtn.href = job.download_url;
            downloadBtn.download = job.filename || 'audio.mp3';

            audioPreview.src = job.download_url;

            resultCard.classList.remove('hidden');
        }
    }

    function showErrorState(message) {
        progressSection.classList.add('hidden');
        submitBtn.disabled = false;
        errorMessage.textContent = message;
        errorCard.classList.remove('hidden');
    }

    function resetUIState() {
        if (pollInterval) {
            clearInterval(pollInterval);
            pollInterval = null;
        }
        progressSection.classList.add('hidden');
        resultCard.classList.add('hidden');
        playlistCard.classList.add('hidden');
        errorCard.classList.add('hidden');
        progressBar.style.width = '0%';
        progressPercent.textContent = '0%';
        audioPreview.pause();
        audioPreview.src = '';
    }

    function formatDuration(seconds) {
        if (!seconds) return '00:00';
        const mins = Math.floor(seconds / 60);
        const secs = Math.floor(seconds % 60);
        return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
    }

    resetBtn.addEventListener('click', () => {
        resetUIState();
        youtubeUrlInput.value = '';
        youtubeUrlInput.focus();
    });

    playlistResetBtn.addEventListener('click', () => {
        resetUIState();
        youtubeUrlInput.value = '';
        youtubeUrlInput.focus();
    });

    errorRetryBtn.addEventListener('click', () => {
        resetUIState();
        extractForm.requestSubmit();
    });
});
