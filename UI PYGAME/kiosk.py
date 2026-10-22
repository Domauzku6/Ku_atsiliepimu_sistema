import csv
import threading
from datetime import datetime
from pathlib import Path

import pygame

from calendar_lookup import calendar_lookup, current_time
import download_reservations as dl

CSV_FILE = Path(__file__).parent / "proof_of_concept.csv"
HEADERS = ["kabinetas", "dėstytojas", "paskaita", "laikas", "atsiliepimas (1-10)", "komentaras"]

W, H = 1024, 600
BG, CARD, TEXT, MUTED = (245, 246, 250), (255, 255, 255), (30, 33, 40), (120, 125, 135)
BLUE, RED, GREEN = (40, 100, 220), (210, 60, 60), (40, 160, 90)


def save_to_csv(kabinetas, destytojas, paskaita, atsiliepimas, komentaras=""):
    new_file = not CSV_FILE.exists() or CSV_FILE.stat().st_size == 0
    with CSV_FILE.open("a", newline="", encoding="utf-8-sig" if new_file else "utf-8") as f:
        w = csv.writer(f)
        if new_file:
            w.writerow(HEADERS)
        w.writerow([kabinetas, destytojas, paskaita,
                    datetime.now().strftime("%Y-%m-%d %H:%M"), atsiliepimas, komentaras.strip()])


class Button:
    def __init__(self, rect, label, color=BLUE):
        self.rect, self.label, self.color = pygame.Rect(rect), label, color

    def draw(self, screen, font):
        pygame.draw.rect(screen, self.color, self.rect, border_radius=12)
        txt = font.render(self.label, True, (255, 255, 255))
        screen.blit(txt, txt.get_rect(center=self.rect.center))

    def clicked(self, event):
        return event.type == pygame.MOUSEBUTTONDOWN and self.rect.collidepoint(event.pos)


def center(screen, font, text, y, color=TEXT):
    img = font.render(text, True, color)
    screen.blit(img, img.get_rect(center=(W // 2, y)))


def wrap_lines(font, text, max_width):
    lines, line = [], ""
    for word in text.split():
        test = f"{line} {word}".strip()
        if line and font.size(test)[0] > max_width:
            lines.append(line)
            line = word
        else:
            line = test
    return lines + [line]


def center_fit(screen, text, cy, max_width, size, bold=False, color=TEXT, max_lines=2, min_size=18):
    """Centruoja tekstą aplink cy: mažina šriftą ir laužo į kelias eilutes, kad tilptų į max_width."""
    while True:
        font = pygame.font.SysFont("segoeui", size, bold=bold)
        lines = wrap_lines(font, text, max_width)
        if (len(lines) <= max_lines and all(font.size(l)[0] <= max_width for l in lines)) or size <= min_size:
            break
        size -= 2
    line_h = font.get_linesize()
    top = cy - line_h * len(lines) // 2
    for i, ln in enumerate(lines[:max_lines]):
        img = font.render(ln, True, color)
        screen.blit(img, img.get_rect(midtop=(W // 2, top + i * line_h)))


class App:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((W, H))
        pygame.display.set_caption("KU atsiliepimai")
        self.clock = pygame.time.Clock()
        self.big = pygame.font.SysFont("segoeui", 44, bold=True)
        self.mid = pygame.font.SysFont("segoeui", 30)
        self.small = pygame.font.SysFont("segoeui", 22)

        self.page = "cabinet"
        self.cabinet = ""
        self.lecture = None          # (dėstytojas, paskaita)
        self.score = None
        self.comment = ""
        self.error = ""
        self.thanks_until = 0

        # Skaičių klaviatūra kabinetui
        keys = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "A", "0", "⌫"]
        self.keypad = [Button((W // 2 - 165 + (i % 3) * 115, 170 + (i // 3) * 85, 100, 70), k)
                       for i, k in enumerate(keys)]
        self.ok_btn = Button((W // 2 - 165, 515, 330, 60), "Toliau", GREEN)

        # 1–10 įvertinimo mygtukai apačioje
        self.score_btns = [Button((42 + i * 96, 470, 84, 84), str(i + 1),
                                  RED if i < 4 else BLUE) for i in range(10)]
        self.back_btn = Button((20, 20, 120, 50), "Atgal", MUTED)
        self.send_btn = Button((W // 2 - 150, 430, 300, 70), "Siųsti", GREEN)

    # ---------- logika ----------
    def start_lookup(self):
        self.page, self.error = "loading", ""

        def work():
            try:
                result = calendar_lookup(self.cabinet)
            except Exception as e:
                self.error, self.page = f"Klaida: {e}", "cabinet"
                return
            if result is None:
                self.error, self.page = f"Kabinete {self.cabinet} dabar paskaitos nėra", "cabinet"
            else:
                self.lecture, self.page = result, "rating"

        threading.Thread(target=work, daemon=True).start()

    def finish(self):
        lecturer, name = self.lecture
        save_to_csv(self.cabinet, lecturer or "", name, self.score, self.comment)
        self.page, self.thanks_until = "thanks", pygame.time.get_ticks() + 3000

    def next_student(self):
        """Lieka ta pati paskaita – kitas studentas gali iškart vertinti."""
        self.page, self.score, self.comment = "rating", None, ""
        pygame.key.stop_text_input()

    def reset(self):
        self.page, self.cabinet, self.lecture = "cabinet", "", None
        self.score, self.comment, self.error = None, "", ""
        pygame.key.stop_text_input()

    # ---------- įvykiai ----------
    def handle(self, e):
        if self.page == "cabinet":
            for b in self.keypad:
                if b.clicked(e):
                    if b.label == "⌫":
                        self.cabinet = self.cabinet[:-1]
                    elif len(self.cabinet) < 5:
                        self.cabinet += b.label
            if self.ok_btn.clicked(e) and self.cabinet:
                self.start_lookup()

        elif self.page == "rating":
            if self.back_btn.clicked(e):
                self.reset()
            for b in self.score_btns:
                if b.clicked(e):
                    self.score = int(b.label)
                    if self.score < 5:
                        self.page = "comment"
                        pygame.key.start_text_input()
                    else:
                        self.finish()

        elif self.page == "comment":
            if e.type == pygame.TEXTINPUT and len(self.comment) < 200:
                self.comment += e.text
            elif e.type == pygame.KEYDOWN and e.key == pygame.K_BACKSPACE:
                self.comment = self.comment[:-1]
            elif self.send_btn.clicked(e) or (e.type == pygame.KEYDOWN and e.key == pygame.K_RETURN):
                if self.comment.strip():
                    pygame.key.stop_text_input()
                    self.finish()
            elif self.back_btn.clicked(e):
                self.page, self.comment = "rating", ""
                pygame.key.stop_text_input()

    # ---------- piešimas ----------
    def draw(self):
        s = self.screen
        s.fill(BG)

        if self.page == "cabinet":
            center(s, self.big, "Pasirinkite kabinetą", 60)
            pygame.draw.rect(s, CARD, (W // 2 - 165, 100, 330, 56), border_radius=10)
            center(s, self.big, self.cabinet or "—", 128)
            for b in self.keypad:
                b.draw(s, self.mid)
            self.ok_btn.draw(s, self.mid)
            if self.error:
                center(s, self.small, self.error, 88, RED)

        elif self.page == "loading":
            center(s, self.big, "Ieškoma paskaitos...", H // 2)

        elif self.page == "rating":
            lecturer, name = self.lecture
            self.back_btn.draw(s, self.small)
            center(s, self.small, f"{dl.get_todays_date_iso()}  {current_time()}   •   Kab. {self.cabinet}", 60, MUTED)
            pygame.draw.rect(s, CARD, (60, 110, W - 120, 220), border_radius=16)
            card_w = W - 120 - 60        # kortelė su 30 px paraštėmis
            center_fit(s, name, 190, card_w, 44, bold=True)
            center_fit(s, lecturer or "Dėstytojas nenurodytas", 285, card_w, 30, color=MUTED, max_lines=1)
            center(s, self.mid, "Kaip vertinate paskaitą?", 420)
            for b in self.score_btns:
                b.draw(s, self.mid)

        elif self.page == "comment":
            self.back_btn.draw(s, self.small)
            center(s, self.big, f"Įvertinote {self.score}/10", 110)
            center(s, self.mid, "Kas nepatiko? Parašykite komentarą:", 180, MUTED)
            box = pygame.Rect(80, 230, W - 160, 150)
            pygame.draw.rect(s, CARD, box, border_radius=12)
            pygame.draw.rect(s, BLUE, box, 2, border_radius=12)
            cursor = "|" if (pygame.time.get_ticks() // 500) % 2 else ""
            # paprastas eilučių laužymas
            words, lines, line = (self.comment + cursor).split(" "), [], ""
            for w in words:
                if self.small.size(line + w)[0] > box.width - 30:
                    lines.append(line)
                    line = ""
                line += w + " "
            lines.append(line)
            for i, ln in enumerate(lines[-5:]):
                s.blit(self.small.render(ln, True, TEXT), (box.x + 15, box.y + 12 + i * 27))
            self.send_btn.color = GREEN if self.comment.strip() else MUTED
            self.send_btn.draw(s, self.mid)

        elif self.page == "thanks":
            center(s, self.big, "Ačiū už atsiliepimą!", H // 2 - 20, GREEN)
            center(s, self.small, "Kitas studentas gali vertinti...", H // 2 + 40, MUTED)
            if pygame.time.get_ticks() > self.thanks_until:
                self.next_student()

        pygame.display.flip()

    def run(self):
        while True:
            for e in pygame.event.get():
                if e.type == pygame.QUIT or (e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE):
                    pygame.quit()
                    return
                self.handle(e)
            self.draw()
            self.clock.tick(30)


if __name__ == "__main__":
    App().run()
