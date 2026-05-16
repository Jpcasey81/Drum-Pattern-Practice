import pygame
import numpy as np
import random
import sys

# --- Window ---
WINDOW_WIDTH  = 1280
WINDOW_HEIGHT = 520
FPS = 60

# --- Colors ---
WHITE      = (255, 255, 255)
BLACK      = (0,   0,   0)
GRAY       = (190, 190, 190)
DARK_GRAY  = (110, 110, 110)
LIGHT_GRAY = (235, 235, 235)
RED        = (210,  50,  50)
GREEN      = ( 60, 155,  60)
BLUE       = ( 90, 130, 210)
BLUE_DARK  = ( 50,  90, 175)
PLAYHEAD_C = (220,  50,  50)

# --- Staff layout ---
CONTROL_H    = 85
STAFF_TOP    = CONTROL_H
STAFF_CY     = CONTROL_H + (WINDOW_HEIGHT - CONTROL_H) // 2 + 15
LINE_SP      = 13        # pixels between staff lines
NOTE_R       = 7         # notehead radius
STEM_H       = 50        # stem height above notehead
BEAM_THICK   = 5
BEAM_GAP     = 7         # gap between primary and secondary beam
NOTE_W       = 44        # pixels per 16th note
MEASURE_W    = NOTE_W * 16
PLAYHEAD_X   = 230

# --- BPM ---
BPM_MIN, BPM_MAX, BPM_DEF = 40, 160, 80

# Subdivision labels under the staff
SUB_LABELS = ["1","e","+","a","2","e","+","a","3","e","+","a","4","e","+","a"]


def gen_measure(density=0.5):
    """Each of the 16 slots independently has `density` probability of being accented."""
    return [random.random() < density for _ in range(16)]


def make_click(freq, dur=0.030, vol=0.85, sr=44100):
    t    = np.linspace(0, dur, int(sr * dur), False)
    wave = np.sin(2 * np.pi * freq * t) * np.exp(-t * 90) * vol
    s    = (wave * 32767).astype(np.int16)
    return pygame.sndarray.make_sound(np.column_stack([s, s]))


class App:
    def __init__(self):
        pygame.init()
        pygame.mixer.init(44100, -16, 2, 512)

        self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        pygame.display.set_caption("Drum Pattern Practice")
        self.clock  = pygame.time.Clock()

        self.font       = pygame.font.SysFont("Arial", 15)
        self.font_lg    = pygame.font.SysFont("Arial", 22, bold=True)
        self.font_sm    = pygame.font.SysFont("Arial", 12)
        self.font_count = pygame.font.SysFont("Arial", 15, bold=True)

        # Playback state
        self.bpm      = BPM_DEF
        self.playing  = False
        self.scroll_x = 0.0   # total pixels scrolled
        self.last_tick = -1   # last 16th-note index where metronome fired

        # Metronome options
        self.metro_q   = True   # quarter-note click
        self.metro_16  = False  # 16th-note subdivision click

        # Accent density (0.0–1.0 probability per note)
        self.accent_density = 0.5

        # Measure buffer – start with 4 measures pre-generated
        self.measures = [gen_measure(self.accent_density) for _ in range(4)]

        # Clicks: beat-1 accent, quarter, 16th
        self.click_1   = make_click(1550, vol=0.90)
        self.click_q   = make_click(1000, vol=0.65)
        self.click_16  = make_click(600,  vol=0.38)

        # Beat flash
        self.flash_alpha  = 0.0    # 0–255, decays each frame
        self.flash_beat1  = False  # True when flash is for measure beat 1

        # UI rects (populated in draw_controls each frame)
        self.btn_start    = pygame.Rect(20, 17, 100, 50)
        self.btn_q        = pygame.Rect(0, 0, 1, 1)
        self.btn_16       = pygame.Rect(0, 0, 1, 1)
        self.slider_r     = pygame.Rect(185, 52, 270, 12)
        self.density_r    = pygame.Rect(920, 52, 240, 12)
        self.dragging     = None   # None | 'bpm' | 'density'

    # ------------------------------------------------------------------ update
    def scroll_speed(self):
        """px/s at current BPM (one 16th-note = NOTE_W px)."""
        return NOTE_W * self.bpm * 4 / 60

    def update(self, dt):
        if not self.playing:
            return

        self.scroll_x    += self.scroll_speed() * dt
        self.flash_alpha  = max(0.0, self.flash_alpha - dt * 1400)

        # Fire metronome for every 16th-note boundary we've crossed
        cur = int(self.scroll_x / NOTE_W)
        for i in range(self.last_tick + 1, cur + 1):
            self._metro_tick(i)
        self.last_tick = max(self.last_tick, cur)

        # Extend measure buffer far enough ahead
        needed = self.scroll_x + (WINDOW_WIDTH - PLAYHEAD_X) + MEASURE_W * 2
        while len(self.measures) * MEASURE_W < needed:
            self.measures.append(gen_measure(self.accent_density))

    def _metro_tick(self, idx):
        pos = idx % 16
        if pos == 0 and (self.metro_q or self.metro_16):
            self.click_1.play()
        elif pos % 4 == 0 and self.metro_q:
            self.click_q.play()
        elif self.metro_16 and pos % 4 != 0:
            self.click_16.play()

        # Visual flash on every quarter-note boundary
        if pos % 4 == 0:
            self.flash_alpha = 255.0
            self.flash_beat1 = (pos == 0)

    # ----------------------------------------------------------------- drawing
    def _screen_x(self, abs_x):
        return abs_x - self.scroll_x + PLAYHEAD_X

    def draw_staff(self):
        # --- Five staff lines ---
        line_ys = [STAFF_CY + i * LINE_SP for i in range(-2, 3)]
        for y in line_ys:
            pygame.draw.line(self.screen, BLACK, (0, y), (WINDOW_WIDTH, y), 1)

        # --- Percussion clef (two filled rectangles) ---
        clef_sx = int(self._screen_x(-75))
        if -50 < clef_sx < WINDOW_WIDTH:
            top = STAFF_CY - 2 * LINE_SP
            bot = STAFF_CY + 2 * LINE_SP
            pygame.draw.rect(self.screen, BLACK, (clef_sx,      top, 6, bot - top))
            pygame.draw.rect(self.screen, BLACK, (clef_sx + 11, top, 6, bot - top))

        # --- Time signature 4/4 ---
        ts_sx = int(self._screen_x(-40))
        if -35 < ts_sx < WINDOW_WIDTH:
            self.screen.blit(self.font_lg.render("4", True, BLACK),
                             (ts_sx, STAFF_CY - 2 * LINE_SP - 1))
            self.screen.blit(self.font_lg.render("4", True, BLACK),
                             (ts_sx, STAFF_CY))

        # --- Measures ---
        for m_idx, measure in enumerate(self.measures):
            m_abs = m_idx * MEASURE_W
            sx    = self._screen_x(m_abs)

            # Skip fully off-screen measures
            if sx + MEASURE_W < -NOTE_W or sx > WINDOW_WIDTH + NOTE_W:
                continue

            # Bar line – placed halfway between last note of prev measure and beat 1
            bar_sx = int(self._screen_x(m_abs - int(NOTE_W * 0.55)))
            top = STAFF_CY - 2 * LINE_SP
            bot = STAFF_CY + 2 * LINE_SP
            pygame.draw.line(self.screen, BLACK, (bar_sx, top), (bar_sx, bot), 2)

            # Measure number (follows bar line)
            if -10 < bar_sx < WINDOW_WIDTH:
                mn = self.font_sm.render(str(m_idx + 1), True, DARK_GRAY)
                self.screen.blit(mn, (bar_sx + 3, top - 17))

            # Subdivision labels below staff
            for i, lbl in enumerate(SUB_LABELS):
                nx = int(self._screen_x(m_abs + i * NOTE_W))
                if 0 <= nx <= WINDOW_WIDTH:
                    surf = self.font_count.render(lbl, True, BLACK)
                    self.screen.blit(surf, (nx - surf.get_width() // 2,
                                            STAFF_CY + 2 * LINE_SP + 8))

            # Notes & beams – group by beat (4 groups of 4 16th notes)
            for g in range(4):
                group  = measure[g * 4 : g * 4 + 4]
                g_abs  = m_abs + g * 4 * NOTE_W

                # Screen x of each notehead center; stem x = right side of head
                head_xs = [int(self._screen_x(g_abs + n * NOTE_W)) for n in range(4)]
                stem_xs = [x + NOTE_R - 1 for x in head_xs]
                stem_top_y = STAFF_CY - NOTE_R - STEM_H

                # Draw beams if at least one note is on-screen
                if any(-20 <= x <= WINDOW_WIDTH + 20 for x in head_xs):
                    bx0 = stem_xs[0]
                    bw  = stem_xs[3] - stem_xs[0] + 2
                    # Primary beam (8th-note level)
                    pygame.draw.rect(self.screen, BLACK,
                                     (bx0, stem_top_y, bw, BEAM_THICK))
                    # Secondary beam (16th-note level)
                    pygame.draw.rect(self.screen, BLACK,
                                     (bx0, stem_top_y + BEAM_THICK + BEAM_GAP, bw, BEAM_THICK))

                for n, accented in enumerate(group):
                    hx = head_xs[n]
                    sx_stem = stem_xs[n]

                    if hx < -(NOTE_R + 10) or hx > WINDOW_WIDTH + NOTE_R + 10:
                        continue

                    # Filled notehead
                    pygame.draw.circle(self.screen, BLACK, (hx, STAFF_CY), NOTE_R)

                    # Stem (right edge of head → beam)
                    pygame.draw.line(self.screen, BLACK,
                                     (sx_stem, STAFF_CY - NOTE_R + 2),
                                     (sx_stem, stem_top_y), 2)

                    # Accent mark ">" above beam
                    if accented:
                        ay = stem_top_y - 9
                        w  = 9
                        pygame.draw.line(self.screen, BLACK,
                                         (hx - w, ay - 5), (hx + 4, ay), 2)
                        pygame.draw.line(self.screen, BLACK,
                                         (hx - w, ay + 5), (hx + 4, ay), 2)

        # Final double bar at very end of generated content
        end_sx = int(self._screen_x(len(self.measures) * MEASURE_W))
        if 0 <= end_sx <= WINDOW_WIDTH:
            top = STAFF_CY - 2 * LINE_SP
            bot = STAFF_CY + 2 * LINE_SP
            pygame.draw.line(self.screen, BLACK, (end_sx,     top), (end_sx,     bot), 2)
            pygame.draw.line(self.screen, BLACK, (end_sx + 4, top), (end_sx + 4, bot), 5)

        # --- Beat flash ---
        if self.flash_alpha > 0:
            flash_w    = 24
            flash_surf = pygame.Surface((flash_w, WINDOW_HEIGHT - STAFF_TOP), pygame.SRCALPHA)
            color      = (255, 90, 20) if self.flash_beat1 else (60, 140, 255)
            flash_surf.fill((*color, int(self.flash_alpha * 0.55)))
            self.screen.blit(flash_surf, (PLAYHEAD_X - flash_w // 2, STAFF_TOP))

        # --- Playhead ---
        pygame.draw.line(self.screen, PLAYHEAD_C,
                         (PLAYHEAD_X, STAFF_TOP + 5),
                         (PLAYHEAD_X, WINDOW_HEIGHT - 10), 2)

    def draw_controls(self):
        pygame.draw.rect(self.screen, LIGHT_GRAY, (0, 0, WINDOW_WIDTH, CONTROL_H))
        pygame.draw.line(self.screen, GRAY, (0, CONTROL_H), (WINDOW_WIDTH, CONTROL_H), 1)

        # Start / Stop button
        bc  = GREEN if not self.playing else RED
        lbl = "START" if not self.playing else "STOP"
        pygame.draw.rect(self.screen, bc, self.btn_start, border_radius=6)
        surf = self.font_lg.render(lbl, True, WHITE)
        self.screen.blit(surf, surf.get_rect(center=self.btn_start.center))

        # BPM label
        self.screen.blit(self.font.render(f"BPM: {self.bpm}", True, BLACK), (140, 20))

        # BPM slider track
        pygame.draw.rect(self.screen, GRAY, self.slider_r, border_radius=6)
        # Knob
        ratio = (self.bpm - BPM_MIN) / (BPM_MAX - BPM_MIN)
        kx    = int(self.slider_r.x + ratio * self.slider_r.w)
        pygame.draw.circle(self.screen, BLUE_DARK, (kx, self.slider_r.centery), 10)
        # Min/max labels
        self.screen.blit(self.font_sm.render(str(BPM_MIN), True, DARK_GRAY), (140, 55))
        self.screen.blit(self.font_sm.render(str(BPM_MAX), True, DARK_GRAY), (460, 55))
        # Arrow-key hint
        self.screen.blit(self.font_sm.render("↑↓ keys: ±5", True, DARK_GRAY), (140, 68))

        # Metronome section
        mx = 520
        self.screen.blit(self.font.render("Metronome:", True, BLACK), (mx, 18))

        self.btn_q = pygame.Rect(mx, 40, 100, 28)
        qc = BLUE_DARK if self.metro_q else BLUE
        pygame.draw.rect(self.screen, qc, self.btn_q, border_radius=5)
        self.screen.blit(self.font_sm.render("Quarter (q)", True, WHITE), (mx + 7, 49))

        self.btn_16 = pygame.Rect(mx + 112, 40, 90, 28)
        sc = BLUE_DARK if self.metro_16 else BLUE
        pygame.draw.rect(self.screen, sc, self.btn_16, border_radius=5)
        self.screen.blit(self.font_sm.render("16th (e/+/a)", True, WHITE), (mx + 118, 49))

        # Position readout
        m_num = int(self.scroll_x / MEASURE_W) + 1
        beat  = int((self.scroll_x % MEASURE_W) / (NOTE_W * 4)) + 1
        self.screen.blit(
            self.font_sm.render(f"Measure {m_num}   Beat {beat}", True, DARK_GRAY),
            (760, 32))
        self.screen.blit(self.font_sm.render("Space: start/stop", True, DARK_GRAY), (760, 48))

        # Accent density slider
        pct = int(self.accent_density * 100)
        self.screen.blit(self.font.render(f"Accent Density: {pct}%", True, BLACK), (920, 20))
        pygame.draw.rect(self.screen, GRAY, self.density_r, border_radius=6)
        dk = int(self.density_r.x + self.accent_density * self.density_r.w)
        pygame.draw.circle(self.screen, BLUE_DARK, (dk, self.density_r.centery), 10)
        self.screen.blit(self.font_sm.render("0%",   True, DARK_GRAY), (895, 55))
        self.screen.blit(self.font_sm.render("100%", True, DARK_GRAY), (1164, 55))

    # --------------------------------------------------------------- events
    def handle_events(self):
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                return False

            if ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_SPACE:
                    self._toggle_play()
                elif ev.key == pygame.K_UP:
                    self.bpm = min(BPM_MAX, self.bpm + 5)
                elif ev.key == pygame.K_DOWN:
                    self.bpm = max(BPM_MIN, self.bpm - 5)

            if ev.type == pygame.MOUSEBUTTONDOWN:
                mx, my = ev.pos
                if self.btn_start.collidepoint(mx, my):
                    self._toggle_play()
                elif self.btn_q.collidepoint(mx, my):
                    self.metro_q = not self.metro_q
                elif self.btn_16.collidepoint(mx, my):
                    self.metro_16 = not self.metro_16
                elif self.slider_r.inflate(0, 18).collidepoint(mx, my):
                    self.dragging = 'bpm'
                    self._set_bpm_x(mx)
                elif self.density_r.inflate(0, 18).collidepoint(mx, my):
                    self.dragging = 'density'
                    self._set_density_x(mx)

            if ev.type == pygame.MOUSEBUTTONUP:
                self.dragging = None

            if ev.type == pygame.MOUSEMOTION and self.dragging:
                if self.dragging == 'bpm':
                    self._set_bpm_x(ev.pos[0])
                elif self.dragging == 'density':
                    self._set_density_x(ev.pos[0])

        return True

    def _toggle_play(self):
        self.playing = not self.playing
        if self.playing:
            # Sync metronome to current position so it doesn't re-fire old ticks
            self.last_tick = int(self.scroll_x / NOTE_W) - 1

    def _set_bpm_x(self, mx):
        r = (mx - self.slider_r.x) / self.slider_r.w
        self.bpm = int(BPM_MIN + max(0.0, min(1.0, r)) * (BPM_MAX - BPM_MIN))

    def _set_density_x(self, mx):
        r = (mx - self.density_r.x) / self.density_r.w
        new_density = round(max(0.0, min(1.0, r)), 2)
        if new_density != self.accent_density:
            self.accent_density = new_density
            # Trim buffer to just past the visible window so new density fills in immediately
            visible_end = int((self.scroll_x + WINDOW_WIDTH - PLAYHEAD_X) / MEASURE_W) + 2
            if len(self.measures) > visible_end:
                del self.measures[visible_end:]

    # ------------------------------------------------------------------- run
    def run(self):
        running = True
        while running:
            dt      = min(self.clock.tick(FPS) / 1000.0, 0.05)
            running = self.handle_events()
            self.update(dt)
            self.screen.fill(WHITE)
            self.draw_staff()
            self.draw_controls()
            pygame.display.flip()
        pygame.quit()
        sys.exit()


if __name__ == "__main__":
    App().run()
