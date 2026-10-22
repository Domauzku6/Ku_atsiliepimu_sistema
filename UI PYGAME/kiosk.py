import ctypes
import sys
import threading

import pygame

import download_reservations as dl
from calendar_lookup import calendar_lookup, current_time
from create_csv import create_csv, save_to_csv
from feedback_UI import wrap_text

W, H = 1024, 600
CARD_RECT = pygame.Rect(60, 110, W - 120, 220)   # paskaitos kortelė
EXIT_TAPS, EXIT_GAP_MS = 15, 1500                 # slaptas išėjimas: 15 paspaudimų iš eilės
BG, CARD, TEXT, MUTED = (245, 246, 250), (255, 255, 255), (30, 33, 40), (120, 125, 135)
BLUE, RED, GREEN = (40, 100, 220), (210, 60, 60), (40, 160, 90)

# Maketas aprašytas 1024x600 koordinatėmis, bet piešiama tikra ekrano raiška:
# S – mastelis, OX/OY – poslinkis, kad vaizdas būtų ekrano centre.
S, OX, OY = 1.0, 0, 0


def setup_screen():
    global S, OX, OY
    if sys.platform == "win32":
        try:  # kad Windows neištemptų (nesulietų) lango esant 125–200 % mastelio nustatymui
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            ctypes.windll.user32.SetProcessDPIAware()
    screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
    sw, sh = screen.get_size()
    S = min(sw / W, sh / H)
    OX, OY = (sw - W * S) / 2, (sh - H * S) / 2
    return screen


def px(v):
    return round(v * S)


def to_screen(rect):
    x, y, w, h = rect
    return pygame.Rect(round(OX + x * S), round(OY + y * S), px(w), px(h))


def to_design(pos):
    return (pos[0] - OX) / S, (pos[1] - OY) / S


def font(size, bold=False):
    return pygame.font.SysFont("segoeui", px(size), bold=bold)


def rect(screen, color, r, radius, width=0):
    pygame.draw.rect(screen, color, to_screen(r), max(width and 1, px(width)), border_radius=px(radius))


class Button:
    def __init__(self, rect, label, color=BLUE):
        self.rect, self.label, self.color = pygame.Rect(rect), label, color

    def draw(self, screen, f):
        rect(screen, self.color, self.rect, 12)
        center(screen, f, self.label, self.rect.centery, (255, 255, 255), self.rect.centerx)

    def clicked(self, e):
        return e.type == pygame.MOUSEBUTTONDOWN and self.rect.collidepoint(e.pos)


def center(screen, f, text, y, color=TEXT, x=W // 2):
    img = f.render(text, True, color)
    screen.blit(img, img.get_rect(center=(round(OX + x * S), round(OY + y * S))))


def center_fit(screen, text, cy, max_width, size, bold=False, color=TEXT, max_lines=2):
    """Laužo tekstą į eilutes ir mažina šriftą, kol viskas tilps į max_width."""
    while True:
        f = font(size, bold)
        lines = wrap_text(f, text, px(max_width), max_lines)
        if " ".join(lines) == " ".join(text.split()) or size <= 18:
            break
        size -= 2
    line_h = f.get_linesize() / S
    top = cy - line_h * len(lines) / 2
    for i, line in enumerate(lines):
        center(screen, f, line, top + (i + 0.5) * line_h, color)


class App:
    def __init__(self):
        pygame.init()
        create_csv()
        self.screen = setup_screen()
        pygame.display.set_caption("KU atsiliepimai")
        self.clock = pygame.time.Clock()
        self.big, self.mid, self.small = font(44, True), font(30), font(22)
        self.thanks_until = 0
        self.taps, self.last_tap, self.running = 0, 0, True
        self.reset()

        keys = "123456789A0←"
        self.keypad = [Button((W // 2 - 165 + i % 3 * 115, 170 + i // 3 * 85, 100, 70), k)
                       for i, k in enumerate(keys)]
        self.ok_btn = Button((W // 2 - 165, 515, 330, 60), "Toliau", GREEN)
        self.score_btns = [Button((42 + i * 96, 470, 84, 84), str(i + 1), RED if i < 4 else BLUE)
                           for i in range(10)]
        self.back_btn = Button((20, 20, 120, 50), "Atgal", MUTED)
        self.send_btn = Button((W // 2 - 150, 430, 300, 70), "Siųsti", GREEN)

    # ---------- būsenos ----------
    def reset(self):
        self.cabinet, self.lecture, self.error = "", None, ""
        self.next_student("cabinet")

    def next_student(self, page="rating"):
        """Po įvertinimo lieka ta pati paskaita – kitas studentas gali iškart vertinti."""
        self.page, self.score, self.comment = page, None, ""
        pygame.key.stop_text_input()

    def start_lookup(self):
        self.page, self.error = "loading", ""

        def work():
            try:
                self.lecture = calendar_lookup(self.cabinet)
            except Exception as e:
                self.error, self.page = f"Klaida: {e}", "cabinet"
                return
            if self.lecture:
                self.page = "rating"
            else:
                self.error, self.page = f"Kabinete {self.cabinet} dabar paskaitos nėra", "cabinet"

        threading.Thread(target=work, daemon=True).start()

    def finish(self):
        save_to_csv(self.cabinet, self.score, self.comment, lecture=self.lecture)
        self.page, self.thanks_until = "thanks", pygame.time.get_ticks() + 3000

    # ---------- įvykiai ----------
    def handle(self, e):
        if self.page == "cabinet":
            for b in self.keypad:
                if b.clicked(e):
                    self.cabinet = self.cabinet[:-1] if b.label == "←" else (self.cabinet + b.label)[:5]
            if self.ok_btn.clicked(e) and self.cabinet:
                self.start_lookup()

        elif self.page == "rating":
            if self.back_btn.clicked(e):
                self.reset()
            if e.type == pygame.MOUSEBUTTONDOWN and CARD_RECT.collidepoint(e.pos):
                now = pygame.time.get_ticks()
                self.taps = self.taps + 1 if now - self.last_tap < EXIT_GAP_MS else 1
                self.last_tap = now
                if self.taps >= EXIT_TAPS:
                    self.running = False
            for b in self.score_btns:
                if b.clicked(e):
                    self.score = int(b.label)
                    if self.score < 5:
                        self.page = "comment"
                        pygame.key.start_text_input()
                    else:
                        self.finish()

        elif self.page == "comment":
            if e.type == pygame.TEXTINPUT:
                self.comment = (self.comment + e.text)[:200]
            elif e.type == pygame.KEYDOWN and e.key == pygame.K_BACKSPACE:
                self.comment = self.comment[:-1]
            elif self.send_btn.clicked(e) or (e.type == pygame.KEYDOWN and e.key == pygame.K_RETURN):
                if self.comment.strip():
                    self.finish()
            elif self.back_btn.clicked(e):
                self.next_student()

    # ---------- piešimas ----------
    def draw(self):
        s = self.screen
        s.fill(BG)

        if self.page == "cabinet":
            center(s, self.big, "Pasirinkite kabinetą", 38)
            center(s, self.small, self.error, 80, RED)
            rect(s, CARD, (W // 2 - 165, 100, 330, 56), 10)
            center(s, self.big, self.cabinet or "—", 128)
            for b in self.keypad + [self.ok_btn]:
                b.draw(s, self.mid)

        elif self.page == "loading":
            center(s, self.big, "Ieškoma paskaitos...", H // 2)

        elif self.page == "rating":
            lecturer, name = self.lecture
            self.back_btn.draw(s, self.small)
            center(s, self.small, f"{dl.get_todays_date_iso()}  {current_time()}   •   Kab. {self.cabinet}", 60, MUTED)
            rect(s, CARD, CARD_RECT, 16)
            center_fit(s, name, 190, W - 180, 44, bold=True)
            center_fit(s, lecturer or "Dėstytojas nenurodytas", 285, W - 180, 30, color=MUTED, max_lines=1)
            center(s, self.mid, "Kaip vertinate paskaitą?", 420)
            for b in self.score_btns:
                b.draw(s, self.mid)

        elif self.page == "comment":
            self.back_btn.draw(s, self.small)
            center(s, self.big, f"Įvertinote {self.score}/10", 110)
            center(s, self.mid, "Kas nepatiko? Parašykite komentarą:", 180, MUTED)
            box = pygame.Rect(80, 230, W - 160, 150)
            rect(s, CARD, box, 12)
            rect(s, BLUE, box, 12, width=2)
            cursor = "|" if pygame.time.get_ticks() // 500 % 2 else ""
            for i, line in enumerate(wrap_text(self.small, self.comment + cursor, px(box.width - 30), 5)):
                s.blit(self.small.render(line, True, TEXT), to_screen((box.x + 15, box.y + 12 + i * 27, 0, 0)))
            self.send_btn.color = GREEN if self.comment.strip() else MUTED
            self.send_btn.draw(s, self.mid)

        elif self.page == "thanks":
            center(s, self.big, "Ačiū už atsiliepimą!", H // 2 - 20, GREEN)
            center(s, self.small, "Kitas studentas gali vertinti...", H // 2 + 40, MUTED)
            if pygame.time.get_ticks() > self.thanks_until:
                self.next_student()

        pygame.display.flip()

    def run(self):
        while self.running:
            for e in pygame.event.get():
                if e.type == pygame.QUIT or (e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE):
                    self.running = False
                if e.type == pygame.MOUSEBUTTONDOWN:  # paspaudimą verčiame atgal į 1024x600 koordinates
                    e = pygame.event.Event(e.type, pos=to_design(e.pos), button=e.button)
                self.handle(e)
            self.draw()
            self.clock.tick(30)
        pygame.quit()


if __name__ == "__main__":
    App().run()
