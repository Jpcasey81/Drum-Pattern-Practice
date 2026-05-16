'use strict';

// ─── Constants ────────────────────────────────────────────────────────────────
const NOTE_W     = 44;           // px per 16th note
const MEASURE_W  = NOTE_W * 16;
const PLAYHEAD_X = 230;
const LINE_SP    = 13;           // px between staff lines
const NOTE_R     = 7;            // notehead radius
const STEM_H     = 50;           // stem height above notehead
const BEAM_H     = 5;            // beam rectangle thickness
const BEAM_GAP   = 7;            // gap between primary and secondary beam
const BPM_MIN    = 40;
const BPM_MAX    = 160;
const SUB_LABELS = ['1','e','+','a','2','e','+','a','3','e','+','a','4','e','+','a'];

// ─── State ────────────────────────────────────────────────────────────────────
let canvas, ctx;
let bpm           = 80;
let playing       = false;
let scrollX       = 0;
let lastTick      = -1;
let metroQuarter  = true;
let metro16th     = false;
let accentDensity = 0.5;
let measures      = [];
let lastTs        = null;
let audioCtx      = null;
let elapsedTime   = 0;   // seconds played (accumulates while playing, pauses when stopped)

// ─── Audio ────────────────────────────────────────────────────────────────────
function ensureAudio() {
    if (!audioCtx) {
        audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    }
    if (audioCtx.state === 'suspended') audioCtx.resume();
}

function playClick(freq, vol) {
    if (!audioCtx) return;
    const osc  = audioCtx.createOscillator();
    const gain = audioCtx.createGain();
    osc.connect(gain);
    gain.connect(audioCtx.destination);
    osc.frequency.value = freq;
    const t = audioCtx.currentTime;
    gain.gain.setValueAtTime(vol, t);
    gain.gain.exponentialRampToValueAtTime(0.0001, t + 0.03);
    osc.start(t);
    osc.stop(t + 0.04);
}

// ─── Measure generation ───────────────────────────────────────────────────────
function genMeasure() {
    return Array.from({length: 16}, () => Math.random() < accentDensity);
}

// ─── Update ───────────────────────────────────────────────────────────────────
function scrollSpeed() {
    return NOTE_W * bpm * 4 / 60;   // px per second
}

function metronomeTick(idx) {
    const pos = idx % 16;
    if (pos === 0 && (metroQuarter || metro16th)) {
        playClick(1550, 0.90);
    } else if (pos % 4 === 0 && metroQuarter) {
        playClick(1000, 0.65);
    } else if (metro16th && pos % 4 !== 0) {
        playClick(600, 0.38);
    }
}

function update(dt) {
    if (!playing) return;

    elapsedTime += dt;
    scrollX += scrollSpeed() * dt;

    const cur = Math.floor(scrollX / NOTE_W);
    for (let i = lastTick + 1; i <= cur; i++) metronomeTick(i);
    lastTick = Math.max(lastTick, cur);

    // Extend measure buffer far enough ahead of visible window
    const needed = scrollX + (canvas.width - PLAYHEAD_X) + MEASURE_W * 2;
    while (measures.length * MEASURE_W < needed) measures.push(genMeasure());
}

// ─── Drawing ──────────────────────────────────────────────────────────────────
// Convert absolute staff x-position to canvas screen x
function sx(absX) { return absX - scrollX + PLAYHEAD_X; }

function draw() {
    const W  = canvas.width;
    const H  = canvas.height;
    const cy = Math.round(H / 2) + 15;   // staff centre Y in canvas coords

    ctx.clearRect(0, 0, W, H);

    // ── Five staff lines ──────────────────────────────────────────────────────
    ctx.strokeStyle = '#000';
    ctx.lineWidth   = 1;
    for (let i = -2; i <= 2; i++) {
        const y = cy + i * LINE_SP;
        ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(W, y); ctx.stroke();
    }

    // ── Percussion clef (two filled rectangles) ───────────────────────────────
    const clefX = Math.round(sx(-78));
    if (clefX > -50 && clefX < W) {
        ctx.fillStyle = '#000';
        ctx.fillRect(clefX,      cy - 2 * LINE_SP, 6, 4 * LINE_SP);
        ctx.fillRect(clefX + 11, cy - 2 * LINE_SP, 6, 4 * LINE_SP);
    }

    // ── Time signature 4/4 ───────────────────────────────────────────────────
    const tsX = Math.round(sx(-44));
    if (tsX > -40 && tsX < W) {
        ctx.fillStyle    = '#000';
        ctx.font         = 'bold 24px Arial, sans-serif';
        ctx.textBaseline = 'middle';
        ctx.fillText('4', tsX, cy - LINE_SP);
        ctx.fillText('4', tsX, cy + LINE_SP);
    }

    // ── Measures ──────────────────────────────────────────────────────────────
    for (let mi = 0; mi < measures.length; mi++) {
        const mAbs = mi * MEASURE_W;
        const mSX  = sx(mAbs);

        if (mSX + MEASURE_W < -NOTE_W || mSX > W + NOTE_W) continue;

        const top = cy - 2 * LINE_SP;
        const bot = cy + 2 * LINE_SP;

        // Bar line – offset left so it sits between measures, not on beat 1
        const barX = Math.round(sx(mAbs - NOTE_W * 0.55));
        ctx.strokeStyle = '#000'; ctx.lineWidth = 2;
        ctx.beginPath(); ctx.moveTo(barX, top); ctx.lineTo(barX, bot); ctx.stroke();

        // Measure number above bar line
        if (barX > -10 && barX < W) {
            ctx.fillStyle    = '#999';
            ctx.font         = '12px Arial, sans-serif';
            ctx.textBaseline = 'alphabetic';
            ctx.fillText(String(mi + 1), barX + 3, top - 4);
        }

        // Subdivision labels (1 e + a) below staff
        ctx.fillStyle    = '#000';
        ctx.font         = 'bold 15px Arial, sans-serif';
        ctx.textBaseline = 'top';
        for (let i = 0; i < 16; i++) {
            const nx = Math.round(sx(mAbs + i * NOTE_W));
            if (nx < 0 || nx > W) continue;
            const lbl = SUB_LABELS[i];
            const tw  = ctx.measureText(lbl).width;
            ctx.fillText(lbl, nx - tw / 2, cy + 2 * LINE_SP + 8);
        }

        // ── Notes & beams (4 groups of 4 sixteenth notes per measure) ─────────
        for (let g = 0; g < 4; g++) {
            const group  = measures[mi].slice(g * 4, g * 4 + 4);
            const gAbs   = mAbs + g * 4 * NOTE_W;
            const headXs = [0,1,2,3].map(n => Math.round(sx(gAbs + n * NOTE_W)));
            const stemXs = headXs.map(x => x + NOTE_R - 1);   // stem on right edge
            const stTop  = cy - NOTE_R - STEM_H;               // top of all stems

            // Beams if any note in group is on-screen
            if (headXs.some(x => x >= -20 && x <= W + 20)) {
                const bw = stemXs[3] - stemXs[0] + 2;
                ctx.fillStyle = '#000';
                ctx.fillRect(stemXs[0], stTop,                     bw, BEAM_H);  // primary
                ctx.fillRect(stemXs[0], stTop + BEAM_H + BEAM_GAP, bw, BEAM_H);  // secondary
            }

            for (let n = 0; n < 4; n++) {
                const hx  = headXs[n];
                const stX = stemXs[n];
                if (hx < -(NOTE_R + 10) || hx > W + NOTE_R + 10) continue;

                // Filled notehead
                ctx.fillStyle = '#000';
                ctx.beginPath();
                ctx.arc(hx, cy, NOTE_R, 0, Math.PI * 2);
                ctx.fill();

                // Stem (from right edge of head up to beam)
                ctx.strokeStyle = '#000'; ctx.lineWidth = 2;
                ctx.beginPath();
                ctx.moveTo(stX, cy - NOTE_R + 2);
                ctx.lineTo(stX, stTop);
                ctx.stroke();

                // Accent mark ">" above beam
                if (group[n]) {
                    const ay = stTop - 9;
                    ctx.strokeStyle = '#000'; ctx.lineWidth = 2;
                    ctx.beginPath();
                    ctx.moveTo(hx - 9, ay - 5);
                    ctx.lineTo(hx + 4, ay);
                    ctx.lineTo(hx - 9, ay + 5);
                    ctx.stroke();
                }
            }
        }
    }

    // ── Final double bar ──────────────────────────────────────────────────────
    const endX = Math.round(sx(measures.length * MEASURE_W - NOTE_W * 0.55));
    if (endX >= 0 && endX <= W) {
        const top = cy - 2 * LINE_SP;
        const bot = cy + 2 * LINE_SP;
        ctx.strokeStyle = '#000';
        ctx.lineWidth = 2;
        ctx.beginPath(); ctx.moveTo(endX,     top); ctx.lineTo(endX,     bot); ctx.stroke();
        ctx.lineWidth = 5;
        ctx.beginPath(); ctx.moveTo(endX + 5, top); ctx.lineTo(endX + 5, bot); ctx.stroke();
    }

    // ── Beat flash (position-based — always frame-accurate) ──────────────────
    // Find how far past the playhead the most recent quarter beat has travelled.
    // Flash intensity is proportional to proximity, so it's perfectly aligned
    // regardless of frame rate or BPM.
    if (playing) {
        const playheadIdx = scrollX / NOTE_W;
        const lastQBeat   = Math.floor(playheadIdx / 4) * 4;   // most recent quarter beat index
        const distPx      = (playheadIdx - lastQBeat) * NOTE_W; // px the beat note has passed playhead
        const fadeWindow  = scrollSpeed() * 0.18;               // fixed 180 ms window at any BPM
        if (distPx < fadeWindow) {
            const intensity = (1 - distPx / fadeWindow) * 0.6;
            const isBeat1   = lastQBeat % 16 === 0;
            ctx.fillStyle   = isBeat1
                ? `rgba(255, 90, 20, ${intensity.toFixed(3)})`
                : `rgba(60, 140, 255, ${intensity.toFixed(3)})`;
            ctx.fillRect(PLAYHEAD_X - 12, 0, 24, H);
        }
    }

    // ── Playhead ──────────────────────────────────────────────────────────────
    ctx.strokeStyle = 'rgba(220, 50, 50, 0.9)';
    ctx.lineWidth   = 2;
    ctx.beginPath();
    ctx.moveTo(PLAYHEAD_X, 5);
    ctx.lineTo(PLAYHEAD_X, H - 10);
    ctx.stroke();
}

// ─── UI ───────────────────────────────────────────────────────────────────────
function updatePositionReadout() {
    const mNum    = Math.floor(scrollX / MEASURE_W) + 1;
    const beat    = Math.floor((scrollX % MEASURE_W) / (NOTE_W * 4)) + 1;
    const totalSec = Math.floor(elapsedTime);
    const mins    = Math.floor(totalSec / 60);
    const secs    = totalSec % 60;
    const timeStr = `${mins}:${secs.toString().padStart(2, '0')}`;
    document.getElementById('position').textContent = `Measure ${mNum}   Beat ${beat}   ${timeStr}`;
}

// ─── Game loop ────────────────────────────────────────────────────────────────
function loop(ts) {
    if (lastTs === null) lastTs = ts;
    const dt = Math.min((ts - lastTs) / 1000, 0.05);
    lastTs = ts;
    update(dt);
    draw();
    updatePositionReadout();
    requestAnimationFrame(loop);
}

// ─── Canvas resize ────────────────────────────────────────────────────────────
function resizeCanvas() {
    canvas.width  = window.innerWidth;
    canvas.height = window.innerHeight - document.getElementById('controls').offsetHeight;
}

// ─── Controls setup ───────────────────────────────────────────────────────────
function initControls() {
    // Start / Stop
    const btnStart = document.getElementById('btn-start');
    btnStart.addEventListener('click', () => {
        ensureAudio();
        playing = !playing;
        if (playing) lastTick = Math.floor(scrollX / NOTE_W) - 1;
        btnStart.textContent = playing ? 'STOP' : 'START';
        btnStart.classList.toggle('on', playing);
    });

    // BPM slider
    const bpmSlider = document.getElementById('bpm-slider');
    const bpmVal    = document.getElementById('bpm-val');
    bpmSlider.addEventListener('input', () => {
        bpm = parseInt(bpmSlider.value);
        bpmVal.textContent = bpm;
    });

    // Metronome: quarter
    const btnQ = document.getElementById('btn-quarter');
    btnQ.addEventListener('click', () => {
        metroQuarter = !metroQuarter;
        btnQ.classList.toggle('on', metroQuarter);
    });

    // Metronome: 16th
    const btn16 = document.getElementById('btn-16th');
    btn16.addEventListener('click', () => {
        metro16th = !metro16th;
        btn16.classList.toggle('on', metro16th);
    });

    // Accent density slider — trim buffer on change so new density applies soon
    const densSlider = document.getElementById('density-slider');
    const densVal    = document.getElementById('density-val');
    densSlider.addEventListener('input', () => {
        const newD = parseInt(densSlider.value) / 100;
        if (newD !== accentDensity) {
            accentDensity = newD;
            const visEnd = Math.floor((scrollX + canvas.width - PLAYHEAD_X) / MEASURE_W) + 2;
            if (measures.length > visEnd) measures.length = visEnd;
        }
        densVal.textContent = densSlider.value;
    });

    // Keyboard shortcuts
    document.addEventListener('keydown', e => {
        if (e.code === 'Space') {
            e.preventDefault();
            btnStart.click();
        } else if (e.code === 'ArrowUp') {
            bpm = Math.min(BPM_MAX, bpm + 5);
            bpmSlider.value    = bpm;
            bpmVal.textContent = bpm;
        } else if (e.code === 'ArrowDown') {
            bpm = Math.max(BPM_MIN, bpm - 5);
            bpmSlider.value    = bpm;
            bpmVal.textContent = bpm;
        }
    });
}

// ─── Init ─────────────────────────────────────────────────────────────────────
function init() {
    canvas = document.getElementById('canvas');
    ctx    = canvas.getContext('2d');

    for (let i = 0; i < 4; i++) measures.push(genMeasure());

    resizeCanvas();
    window.addEventListener('resize', resizeCanvas);

    initControls();
    requestAnimationFrame(loop);
}

window.addEventListener('load', init);
