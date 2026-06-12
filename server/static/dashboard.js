const PLACEMENTS = [
    { id: 'H', title: 'Hand-held', subtitle: 'Natural arm swing', icon: 'fa-solid fa-hand', color: 'var(--color-hand)' },
    { id: 'BP', title: 'Back Pocket', subtitle: 'Trousers rear pocket', icon: 'fa-solid fa-mobile-screen-button', color: 'var(--color-bp)' },
    { id: 'FP', title: 'Front Pocket', subtitle: 'Trousers front pocket', icon: 'fa-solid fa-mobile-screen', color: 'var(--color-fp)' },
    { id: 'SB', title: 'Shoulder Bag', subtitle: 'Carried in bag', icon: 'fa-solid fa-suitcase', color: 'var(--color-sb)' }
];

let ws;
let isConnected = false;

// DOM Elements
const grid = document.querySelector('.placements-grid');
const terminalOutput = document.getElementById('terminal-output');
const serverAddress = document.getElementById('server-address');
const statusDot = document.getElementById('status-dot');
const statusText = document.getElementById('status-text');
const heroTitle = document.getElementById('hero-title');
const heroSubtitle = document.getElementById('hero-subtitle');
const heroIcon = document.getElementById('hero-icon');
const bufferRing = document.getElementById('buffer-ring');
const bufferProgress = document.getElementById('buffer-progress');
const confidenceContainer = document.getElementById('confidence-container');
const confidenceValue = document.getElementById('confidence-value');
const confidenceFill = document.getElementById('confidence-fill');
const bgGradientTop = document.getElementById('bg-gradient-top');
const controlStatus = document.getElementById('control-status');
const statusBadge = document.getElementById('status-badge');

// Initialize Grid
function initGrid() {
    grid.innerHTML = '';
    PLACEMENTS.forEach(p => {
        const chip = document.createElement('div');
        chip.className = 'placement-chip';
        chip.id = `chip-${p.id}`;
        chip.innerHTML = `
            <div class="chip-header">
                <i class="${p.icon}" style="color: ${p.color}"></i>
                <span>${p.id}</span>
                <i class="fa-solid fa-crown crown-icon"></i>
            </div>
            <div class="chip-probability" id="prob-${p.id}">0.0%</div>
            <div class="chip-bar-track">
                <div class="chip-bar-fill" id="bar-${p.id}" style="background-color: ${p.color}; width: 0%"></div>
            </div>
        `;
        grid.appendChild(chip);
    });
}

function updateHeroState(state, data = null) {
    heroIcon.classList.remove('fa-wave-square', 'fa-spinner', 'fa-satellite-dish');
    bufferRing.style.display = 'none';
    confidenceContainer.style.display = 'none';
    heroIcon.classList.remove('pulse');

    if (state === 'disconnected') {
        statusDot.style.backgroundColor = 'var(--color-disconnected)';
        statusText.innerText = 'OFFLINE';
        heroTitle.innerText = "Where's My Phone?";
        heroSubtitle.innerText = "Waiting for connection...";
        heroIcon.className = "fa-solid fa-satellite-dish hero-icon pulse";
        controlStatus.innerText = "Ready";
        statusBadge.innerHTML = `<i class="fa-solid fa-plug"></i><span>Offline</span>`;
        statusBadge.style.background = 'linear-gradient(135deg, #8e8e93, #636366)';
    } else if (state === 'connecting') {
        statusDot.style.backgroundColor = 'var(--color-connecting)';
        statusText.innerText = 'CONNECTING';
        heroTitle.innerText = "Connecting...";
        heroSubtitle.innerText = `ws://${window.location.host}/ws/dashboard`;
        heroIcon.className = "fa-solid fa-spinner hero-icon pulse";
    } else if (state === 'buffering') {
        statusDot.style.backgroundColor = 'var(--color-connected)';
        statusText.innerText = 'BUFFERING';
        heroTitle.innerText = "Calibrating Motion";
        heroSubtitle.innerText = `Collecting ${data.buffered_seconds}/10 seconds of gait data`;
        heroIcon.className = "fa-solid fa-wave-square hero-icon";
        bufferRing.style.display = 'block';
        
        // Update circle progress
        const circumference = 402;
        const offset = circumference - (data.buffered_seconds / 10) * circumference;
        bufferProgress.style.strokeDashoffset = offset;
        
        controlStatus.innerText = "Receiving Data";
        statusBadge.innerHTML = `<i class="fa-solid fa-bolt"></i><span>Buffering</span>`;
        statusBadge.style.background = 'linear-gradient(135deg, var(--color-connected), var(--color-bp))';
    } else if (state === 'predicting') {
        statusDot.style.backgroundColor = 'var(--color-live)';
        statusText.innerText = 'LIVE';
        
        // Find top prediction
        let topId = null;
        let topProb = -1;
        for (const [id, prob] of Object.entries(data)) {
            if (prob > topProb) {
                topProb = prob;
                topId = id;
            }
        }
        
        const placement = PLACEMENTS.find(p => p.id === topId);
        if (placement) {
            heroTitle.innerText = placement.title;
            heroSubtitle.innerText = placement.subtitle;
            heroIcon.className = `${placement.icon} hero-icon pulse`;
            
            // Confidence Bar
            confidenceContainer.style.display = 'flex';
            confidenceValue.innerText = `${(topProb * 100).toFixed(1)}%`;
            confidenceFill.style.width = `${topProb * 100}%`;
            confidenceFill.style.backgroundColor = placement.color;
            
            // Update Background Gradient Color
            bgGradientTop.style.background = `radial-gradient(circle, ${placement.color} 0%, transparent 60%)`;
        }
        
        controlStatus.innerText = "Streaming Inference";
        statusBadge.innerHTML = `<i class="fa-solid fa-wave-square"></i><span>Live</span>`;
        statusBadge.style.background = 'linear-gradient(135deg, var(--color-live), var(--color-cp))';
        
        updateGrid(data, topId);
    }
}

function updateGrid(predictions, topId) {
    PLACEMENTS.forEach(p => {
        const prob = predictions[p.id] || 0;
        const isTop = (p.id === topId);
        
        const chip = document.getElementById(`chip-${p.id}`);
        const probText = document.getElementById(`prob-${p.id}`);
        const barFill = document.getElementById(`bar-${p.id}`);
        
        probText.innerText = `${(prob * 100).toFixed(1)}%`;
        barFill.style.width = `${prob * 100}%`;
        
        if (isTop) {
            chip.classList.add('active');
            barFill.style.opacity = '1';
        } else {
            chip.classList.remove('active');
            barFill.style.opacity = '0.65';
        }
    });
}

function connect() {
    updateHeroState('connecting');
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/dashboard`;
    serverAddress.innerText = window.location.host;
    
    ws = new WebSocket(wsUrl);
    
    ws.onopen = () => {
        isConnected = true;
        updateHeroState('disconnected'); // Waiting for data
    };
    
    ws.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            
            // Update terminal
            terminalOutput.innerText = JSON.stringify(data, null, 2);
            
            if (data.status === 'loading') {
                updateHeroState('buffering', data);
            } else if (data.error) {
                console.error(data.error);
            } else {
                // It's a prediction
                updateHeroState('predicting', data);
            }
        } catch (e) {
            console.error("Failed to parse message", e);
        }
    };
    
    ws.onclose = () => {
        isConnected = false;
        updateHeroState('disconnected');
        setTimeout(connect, 3000); // Auto-reconnect
    };
    
    ws.onerror = (err) => {
        console.error("WebSocket error", err);
        ws.close();
    };
}

// Initialize
initGrid();
connect();
