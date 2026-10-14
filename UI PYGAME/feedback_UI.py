import csv
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import pygame


FULLSCREEN = "--fullscreen" in sys.argv or "-f" in sys.argv
WINDOW_SIZE = (1280, 720)
THANKS_MS = 1500

BASE_DIR = Path(__file__).resolve().parent
SCHEDULE_FILE = BASE_DIR / "reservations.json"
CSV_FILE = BASE_DIR / "proof_of_concept.csv"
CSV_ENCODING = "utf-8-sig"
HEADERS = [
    "kabinetas",
    "dėstytojas",
    "paskaita",
    "laikas",
    "atsiliepimas (1-10)",
    "komentaras",
]

# KU-inspired palette: deep Baltic blue, gold, white.
BG = (5, 26, 55)
PANEL = (8, 40, 79)
PANEL_2 = (11, 55, 101)
PANEL_3 = (17, 71, 126)
LINE = (60, 111, 157)
GOLD = (247, 194, 0)
GOLD_DARK = (190, 145, 0)
TEXT = (248, 250, 252)
MUTED = (190, 206, 224)
INK = (4, 17, 34)
WHITE = (255, 255, 255)
WARNING = (255, 220, 95)
ERROR = (255, 148, 148)
SUCCESS = (115, 221, 178)


@dataclass(frozen=True)
class LectureOption:
    room: str
    lecturer: str
    lecture: str
    start: datetime | None = None
    end: datetime | None = None
    manual_time: str | None = None

    @property
    def csv_time(self) -> str:
        if self.manual_time:
            return self.manual_time
        if self.start is None:
            return datetime.now().strftime("%Y-%m-%d %H:%M")
        return self.start.strftime("%Y-%m-%d %H:%M")

    @property
    def time_label(self) -> str:
        if self.manual_time:
            return self.manual_time
        if self.start is None:
            return "Laikas nerastas"
        if self.end is None:
            return self.start.strftime("%Y-%m-%d %H:%M")
        if self.start.date() == self.end.date():
            return f"{self.start:%Y-%m-%d %H:%M}-{self.end:%H:%M}"
        return f"{self.start:%Y-%m-%d %H:%M} - {self.end:%Y-%m-%d %H:%M}"


@dataclass
class Feedback:
    lecture: LectureOption
    rating: int
    comment: str = ""

    def to_row(self) -> list[str | int]:
        return [
            self.lecture.room,
            self.lecture.lecturer,
            self.lecture.lecture,
            self.lecture.csv_time,
            self.rating,
            self.comment.strip(),
        ]


@dataclass
class TextField:
    label: str
    value: str = ""
    placeholder: str = ""
    rect: pygame.Rect = field(default_factory=lambda: pygame.Rect(0, 0, 0, 0))
    multiline: bool = False


def parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d %H:%M")
    except ValueError:
        return None


def compact_room(name: str | None) -> str:
    if not name:
        return "Nežinomas kabinetas"
    value = re.sub(r"\baud\.?\b", "", name, flags=re.IGNORECASE)
    value = value.replace("(", "").replace(")", "")
    value = re.sub(r"\s*,\s*", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def load_lectures(path: Path = SCHEDULE_FILE) -> tuple[list[LectureOption], str | None]:
    if not path.exists():
        return [], f"Nerastas {path.name}"

    try:
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        return [], f"Nepavyko perskaityti {path.name}: {exc}"

    lectures: list[LectureOption] = []
    for room in data.get("data", []):
        reservations_by_day = room.get("reservations", {})
        for reservations in reservations_by_day.values():
            for reservation in reservations:
                reservable = reservation.get("reservable") or {}
                responsible = reservation.get("responsible") or reservation.get("user") or {}
                lectures.append(
                    LectureOption(
                        room=compact_room(reservable.get("name")),
                        lecturer=responsible.get("name") or "Nežinomas dėstytojas",
                        lecture=reservation.get("name") or "Nežinoma paskaita",
                        start=parse_dt(reservation.get("from")),
                        end=parse_dt(reservation.get("to")),
                    )
                )

    lectures.sort(key=lambda item: item.start or datetime.max)
    if not lectures:
        return [], f"{path.name} neturi paskaitų"
    return lectures, None


def choose_initial_lecture(lectures: list[LectureOption], now: datetime | None = None) -> int:
    now = now or datetime.now()
    for index, lecture in enumerate(lectures):
        if lecture.start and lecture.end and lecture.start <= now <= lecture.end:
            return index

    timed = [(index, lecture.start) for index, lecture in enumerate(lectures) if lecture.start]
    if not timed:
        return 0

    today = [(index, start) for index, start in timed if start.date() == now.date()]
    pool = today or timed
    index, _ = min(pool, key=lambda item: abs((item[1] - now).total_seconds()))
    return index


def ensure_csv_header() -> None:
    if not CSV_FILE.exists() or CSV_FILE.stat().st_size == 0:
        with CSV_FILE.open("w", newline="", encoding=CSV_ENCODING) as f:
            csv.writer(f).writerow(HEADERS)
        return

    raw = CSV_FILE.read_bytes()
    has_bom = raw.startswith(b"\xef\xbb\xbf")
    with CSV_FILE.open(newline="", encoding=CSV_ENCODING) as f:
        rows = list(csv.reader(f))
    if rows and rows[0] == HEADERS and has_bom:
        return

    old_rows = rows[1:] if rows else []
    with CSV_FILE.open("w", newline="", encoding=CSV_ENCODING) as f:
        writer = csv.writer(f)
        writer.writerow(HEADERS)
        for row in old_rows:
            writer.writerow((row + [""] * len(HEADERS))[: len(HEADERS)])


def save_feedback(feedback: Feedback) -> None:
    ensure_csv_header()
    with CSV_FILE.open("a", newline="", encoding=CSV_ENCODING) as f:
        csv.writer(f).writerow(feedback.to_row())


def fit_text(font: pygame.font.Font, text: str, max_width: int) -> str:
    if font.size(text)[0] <= max_width:
        return text
    ellipsis = "..."
    low, high = 0, len(text)
    while low < high:
        mid = (low + high + 1) // 2
        if font.size(text[:mid] + ellipsis)[0] <= max_width:
            low = mid
        else:
            high = mid - 1
    return text[:low].rstrip() + ellipsis


def wrap_text(font: pygame.font.Font, text: str, max_width: int, max_lines: int) -> list[str]:
    words = text.replace("\n", " ").split()
    lines: list[str] = []
    current = ""

    for word in words:
        candidate = f"{current} {word}".strip()
        if not current or font.size(candidate)[0] <= max_width:
            current = candidate
            continue
        lines.append(current)
        current = word
        if len(lines) == max_lines:
            break

    if current and len(lines) < max_lines:
        lines.append(current)

    if len(lines) == max_lines and words:
        original = " ".join(words)
        if " ".join(lines) != original:
            lines[-1] = fit_text(font, lines[-1] + "...", max_width)
    return lines or [""]


def draw_text(
    screen: pygame.Surface,
    font: pygame.font.Font,
    text: str,
    color: tuple[int, int, int],
    pos: tuple[int, int],
) -> pygame.Rect:
    label = font.render(text, True, color)
    rect = label.get_rect(topleft=pos)
    screen.blit(label, rect)
    return rect


def draw_centered(
    screen: pygame.Surface,
    font: pygame.font.Font,
    text: str,
    color: tuple[int, int, int],
    rect: pygame.Rect,
) -> None:
    label = font.render(text, True, color)
    screen.blit(label, label.get_rect(center=rect.center))


def draw_button(
    screen: pygame.Surface,
    font: pygame.font.Font,
    rect: pygame.Rect,
    label: str,
    active: bool = True,
    selected: bool = False,
) -> None:
    fill = GOLD if selected else PANEL_3
    if not active:
        fill = (49, 86, 122)
    pygame.draw.rect(screen, fill, rect, border_radius=8)
    pygame.draw.rect(screen, GOLD_DARK if selected else LINE, rect, width=1, border_radius=8)
    draw_centered(screen, font, label, INK if selected else TEXT, rect)


def set_display(fullscreen: bool) -> pygame.Surface:
    if fullscreen:
        return pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
    return pygame.display.set_mode(WINDOW_SIZE, pygame.RESIZABLE)


def make_fonts(width: int, height: int) -> dict[str, pygame.font.Font]:
    scale = max(0.84, min(width / 1280, height / 720, 1.08))
    family = "segoeui"

    def font(size: int, bold: bool = False) -> pygame.font.Font:
        return pygame.font.SysFont(family, max(12, int(size * scale)), bold=bold)

    return {
        "logo": font(30, True),
        "hero": font(34, True),
        "title": font(27, True),
        "body": font(20),
        "body_bold": font(21, True),
        "small": font(17),
        "tiny": font(14),
        "rating": font(36, True),
    }


def draw_header(
    screen: pygame.Surface,
    fonts: dict[str, pygame.font.Font],
    fullscreen: bool,
    reserve_right: int = 0,
) -> pygame.Rect:
    width = screen.get_width()
    screen.fill(BG)
    logo_rect = pygame.Rect(44, 26, 72, 54)
    pygame.draw.rect(screen, GOLD, logo_rect, border_radius=8)
    draw_centered(screen, fonts["logo"], "KU", INK, logo_rect)
    draw_text(screen, fonts["hero"], "Paskaitų vertinimai", TEXT, (132, 25))
    draw_text(screen, fonts["small"], "Klaipėdos universitetas", MUTED, (134, 66))
    fullscreen_rect = pygame.Rect(width - reserve_right - 232, 34, 188, 44)
    draw_button(screen, fonts["small"], fullscreen_rect, "Langas" if fullscreen else "Pilnas ekranas")
    return fullscreen_rect


def draw_tabs(
    screen: pygame.Surface,
    fonts: dict[str, pygame.font.Font],
    active_source: str,
) -> dict[str, pygame.Rect]:
    schedule_rect = pygame.Rect(44, 104, 190, 44)
    custom_rect = pygame.Rect(246, 104, 160, 44)
    draw_button(screen, fonts["body"], schedule_rect, "Tvarkaraštis", selected=active_source == "schedule")
    draw_button(screen, fonts["body"], custom_rect, "Rankinis", selected=active_source == "custom")
    return {"schedule": schedule_rect, "custom": custom_rect}


def draw_lecture_row(
    screen: pygame.Surface,
    rect: pygame.Rect,
    lecture: LectureOption,
    fonts: dict[str, pygame.font.Font],
    selected: bool,
) -> None:
    fill = PANEL_3 if selected else PANEL_2
    pygame.draw.rect(screen, fill, rect, border_radius=8)
    pygame.draw.rect(screen, GOLD if selected else LINE, rect, width=2 if selected else 1, border_radius=8)

    x = rect.x + 20
    y = rect.y + 12
    room_w = 250
    left_w = max(260, rect.width - room_w - 48)
    room_rect = pygame.Rect(rect.right - room_w - 18, rect.y + 18, room_w, rect.height - 36)

    draw_text(screen, fonts["tiny"], fit_text(fonts["tiny"], lecture.time_label, left_w), GOLD, (x, y))
    draw_text(screen, fonts["body_bold"], fit_text(fonts["body_bold"], lecture.lecture, left_w), TEXT, (x, y + 27))
    draw_text(screen, fonts["small"], fit_text(fonts["small"], lecture.lecturer, left_w), MUTED, (x, rect.bottom - 31))
    draw_centered(screen, fonts["small"], fit_text(fonts["small"], lecture.room, room_w), WHITE, room_rect)


def draw_scrollbar(
    screen: pygame.Surface,
    rect: pygame.Rect,
    total: int,
    visible: int,
    offset: int,
) -> pygame.Rect | None:
    if total <= visible:
        return None
    pygame.draw.rect(screen, (19, 63, 109), rect, border_radius=8)
    thumb_h = max(44, int(rect.height * visible / total))
    max_offset = max(1, total - visible)
    thumb_y = rect.y + int((rect.height - thumb_h) * offset / max_offset)
    thumb = pygame.Rect(rect.x, thumb_y, rect.width, thumb_h)
    pygame.draw.rect(screen, GOLD, thumb, border_radius=8)
    return thumb


def draw_schedule_select(
    screen: pygame.Surface,
    lectures: list[LectureOption],
    selected_index: int,
    scroll_offset: int,
    status: str | None,
    fonts: dict[str, pygame.font.Font],
) -> dict[str, object]:
    width, height = screen.get_size()
    panel = pygame.Rect(44, 164, width - 88, height - 196)
    pygame.draw.rect(screen, PANEL, panel, border_radius=8)
    pygame.draw.rect(screen, LINE, panel, width=1, border_radius=8)

    title_rect = draw_text(screen, fonts["title"], "Esamos paskaitos", TEXT, (panel.x + 22, panel.y + 18))
    if status:
        draw_text(screen, fonts["small"], fit_text(fonts["small"], status, 640), WARNING, (title_rect.right + 18, panel.y + 28))

    rows: list[tuple[int, pygame.Rect]] = []
    row_h = 94
    gap = 10
    list_top = panel.y + 72
    list_bottom = panel.bottom - 24
    visible = max(3, min(6, (list_bottom - list_top + gap) // (row_h + gap)))
    row_w = panel.width - 68

    if not lectures:
        empty = pygame.Rect(panel.x + 22, list_top, panel.width - 44, 160)
        pygame.draw.rect(screen, PANEL_2, empty, border_radius=8)
        pygame.draw.rect(screen, LINE, empty, width=1, border_radius=8)
        draw_centered(screen, fonts["body"], "Tvarkaraštis tuščias", MUTED, empty)
    else:
        max_offset = max(0, len(lectures) - visible)
        scroll_offset = max(0, min(scroll_offset, max_offset))
        for row, index in enumerate(range(scroll_offset, min(scroll_offset + visible, len(lectures)))):
            rect = pygame.Rect(panel.x + 22, list_top + row * (row_h + gap), row_w, row_h)
            rows.append((index, rect))
            draw_lecture_row(screen, rect, lectures[index], fonts, selected=index == selected_index)

    track_h = visible * row_h + (visible - 1) * gap
    track = pygame.Rect(panel.right - 32, list_top, 12, track_h)
    thumb = draw_scrollbar(screen, track, len(lectures), visible, scroll_offset)
    return {"rows": rows, "scroll_track": track, "scroll_thumb": thumb, "visible": visible}


def draw_text_field(
    screen: pygame.Surface,
    fonts: dict[str, pygame.font.Font],
    field_obj: TextField,
    rect: pygame.Rect,
    active: bool,
) -> None:
    field_obj.rect = rect
    pygame.draw.rect(screen, PANEL_2, rect, border_radius=8)
    pygame.draw.rect(screen, GOLD if active else LINE, rect, width=2 if active else 1, border_radius=8)
    draw_text(screen, fonts["tiny"], field_obj.label, GOLD if active else MUTED, (rect.x + 14, rect.y + 9))

    display = field_obj.value if field_obj.value else field_obj.placeholder
    color = TEXT if field_obj.value else (139, 163, 190)
    lines = wrap_text(fonts["body"], display, rect.width - 28, 2 if field_obj.multiline else 1)
    y = rect.y + 34
    for line in lines:
        draw_text(screen, fonts["body"], fit_text(fonts["body"], line, rect.width - 28), color, (rect.x + 14, y))
        y += 28


def draw_custom_select(
    screen: pygame.Surface,
    custom_fields: list[TextField],
    active_custom: int | None,
    fonts: dict[str, pygame.font.Font],
) -> dict[str, object]:
    width, height = screen.get_size()
    panel = pygame.Rect(44, 164, width - 88, height - 196)
    pygame.draw.rect(screen, PANEL, panel, border_radius=8)
    pygame.draw.rect(screen, LINE, panel, width=1, border_radius=8)
    draw_text(screen, fonts["title"], "Rankinė paskaita", TEXT, (panel.x + 22, panel.y + 18))

    field_w = (panel.width - 64) // 2
    field_h = 86
    positions = [
        pygame.Rect(panel.x + 22, panel.y + 82, field_w, field_h),
        pygame.Rect(panel.x + 42 + field_w, panel.y + 82, field_w, field_h),
        pygame.Rect(panel.x + 22, panel.y + 190, field_w, field_h),
        pygame.Rect(panel.x + 42 + field_w, panel.y + 190, field_w, field_h),
    ]

    for index, rect in enumerate(positions):
        draw_text_field(screen, fonts, custom_fields[index], rect, active_custom == index)

    ready = all(field_obj.value.strip() for field_obj in custom_fields)
    button_rect = pygame.Rect(panel.x + 22, panel.bottom - 86, 220, 52)
    draw_button(screen, fonts["body"], button_rect, "Vertinti", active=ready, selected=ready)
    note_color = MUTED if ready else ERROR
    draw_text(screen, fonts["small"], "Užpildykite visus laukus", note_color, (button_rect.right + 18, button_rect.y + 16))
    return {"custom_fields": positions, "custom_submit": button_rect, "custom_ready": ready}


def custom_lecture_from_fields(custom_fields: list[TextField]) -> LectureOption:
    room, lecturer, lecture, time_text = [field_obj.value.strip() for field_obj in custom_fields]
    return LectureOption(
        room=room,
        lecturer=lecturer,
        lecture=lecture,
        start=parse_dt(time_text),
        end=None,
        manual_time=time_text,
    )


def draw_selected_lecture(
    screen: pygame.Surface,
    rect: pygame.Rect,
    lecture: LectureOption,
    fonts: dict[str, pygame.font.Font],
) -> None:
    pygame.draw.rect(screen, PANEL, rect, border_radius=8)
    pygame.draw.rect(screen, LINE, rect, width=1, border_radius=8)
    x = rect.x + 22
    y = rect.y + 18
    draw_text(screen, fonts["small"], "Vertinama paskaita", GOLD, (x, y))
    for line in wrap_text(fonts["title"], lecture.lecture, rect.width - 44, 2):
        y += 34
        draw_text(screen, fonts["title"], line, TEXT, (x, y))
    y = rect.bottom - 62
    draw_text(screen, fonts["body"], fit_text(fonts["body"], lecture.lecturer, rect.width - 44), WHITE, (x, y))
    draw_text(screen, fonts["small"], fit_text(fonts["small"], f"{lecture.room}  |  {lecture.time_label}", rect.width - 44), MUTED, (x, y + 32))


def draw_rating_slider(
    screen: pygame.Surface,
    track: pygame.Rect,
    rating: int,
    fonts: dict[str, pygame.font.Font],
) -> pygame.Rect:
    pygame.draw.rect(screen, (20, 67, 113), track, border_radius=8)
    ratio = (rating - 1) / 9
    filled = pygame.Rect(track.x, track.y, int(track.width * ratio), track.height)
    if filled.width:
        pygame.draw.rect(screen, GOLD, filled, border_radius=8)

    for number in range(1, 11):
        x = track.x + int(track.width * (number - 1) / 9)
        pygame.draw.line(screen, WHITE if number == rating else MUTED, (x, track.y - 10), (x, track.y + 22), 2)
        label = fonts["tiny"].render(str(number), True, WHITE if number == rating else MUTED)
        screen.blit(label, label.get_rect(center=(x, track.y + 44)))

    knob_x = track.x + int(track.width * ratio)
    knob = pygame.Rect(0, 0, 42, 42)
    knob.center = (knob_x, track.centery)
    pygame.draw.ellipse(screen, GOLD, knob)
    pygame.draw.ellipse(screen, WHITE, knob, width=3)
    draw_centered(screen, fonts["small"], str(rating), INK, knob)
    return knob


def draw_review(
    screen: pygame.Surface,
    lecture: LectureOption,
    rating: int,
    comment_field: TextField,
    comment_active: bool,
    saved_until: int,
    error_until: int,
    error_message: str,
    fonts: dict[str, pygame.font.Font],
    fullscreen: bool,
) -> dict[str, object]:
    width, height = screen.get_size()
    fullscreen_rect = draw_header(screen, fonts, fullscreen, reserve_right=168)

    back_rect = pygame.Rect(width - 190, 34, 146, 44)
    draw_button(screen, fonts["body"], back_rect, "Atgal")

    lecture_rect = pygame.Rect(44, 112, width - 88, 178)
    draw_selected_lecture(screen, lecture_rect, lecture, fonts)

    slider_label = pygame.Rect(44, 318, 210, 42)
    draw_text(screen, fonts["title"], "Įvertinimas", TEXT, (slider_label.x, slider_label.y))
    value_box = pygame.Rect(width - 144, 312, 100, 62)
    pygame.draw.rect(screen, GOLD, value_box, border_radius=8)
    draw_centered(screen, fonts["rating"], str(rating), INK, value_box)

    track = pygame.Rect(110, 400, width - 220, 12)
    knob = draw_rating_slider(screen, track, rating, fonts)

    comment_rect = pygame.Rect(44, 492, width - 88, 94)
    draw_text_field(screen, fonts, comment_field, comment_rect, comment_active)

    save_rect = pygame.Rect(width - 264, height - 82, 220, 52)
    draw_button(screen, fonts["body"], save_rect, "Išsaugoti", selected=True)

    now = pygame.time.get_ticks()
    if now < saved_until:
        status_rect = pygame.Rect(44, height - 82, 430, 52)
        pygame.draw.rect(screen, (14, 91, 71), status_rect, border_radius=8)
        pygame.draw.rect(screen, SUCCESS, status_rect, width=1, border_radius=8)
        draw_centered(screen, fonts["body"], "Išsaugota į proof_of_concept.csv", SUCCESS, status_rect)
    elif now < error_until:
        status_rect = pygame.Rect(44, height - 82, 560, 52)
        pygame.draw.rect(screen, (100, 37, 48), status_rect, border_radius=8)
        pygame.draw.rect(screen, ERROR, status_rect, width=1, border_radius=8)
        draw_centered(screen, fonts["small"], error_message, TEXT, status_rect)

    return {
        "back": back_rect,
        "fullscreen": fullscreen_rect,
        "slider_track": track,
        "slider_knob": knob,
        "comment": comment_rect,
        "save": save_rect,
    }


def rating_from_mouse(track: pygame.Rect, mouse_x: int) -> int:
    ratio = (mouse_x - track.x) / track.width
    ratio = max(0, min(1, ratio))
    return max(1, min(10, round(1 + ratio * 9)))


def handle_text_input(field_obj: TextField, event: pygame.event.Event) -> None:
    if event.type == pygame.TEXTINPUT:
        field_obj.value += event.text
    elif event.type == pygame.KEYDOWN:
        if event.key == pygame.K_BACKSPACE:
            field_obj.value = field_obj.value[:-1]
        elif event.key == pygame.K_RETURN and field_obj.multiline:
            field_obj.value += " "


def main() -> None:
    pygame.init()
    pygame.key.start_text_input()
    fullscreen = FULLSCREEN
    screen = set_display(fullscreen)
    pygame.display.set_caption("KU paskaitų vertinimai")

    fonts = make_fonts(*screen.get_size())

    lectures, status = load_lectures()
    selected_index = choose_initial_lecture(lectures) if lectures else 0
    scroll_offset = max(0, min(selected_index - 2, max(0, len(lectures) - 6)))

    custom_fields = [
        TextField("Kabinetas", placeholder="311 bijunu 17"),
        TextField("Dėstytojas", placeholder="Andrius Stulgys"),
        TextField("Paskaita", placeholder="Kompiuterių ir pramoniniai tinklai"),
        TextField("Laikas", datetime.now().strftime("%Y-%m-%d %H:%M"), "2026-09-29 11:30"),
    ]
    comment_field = TextField("Komentaras", placeholder="Komentaras apie paskaitą", multiline=True)

    source_mode = "schedule"
    screen_mode = "select"
    active_custom: int | None = None
    comment_active = False
    current_lecture: LectureOption | None = None
    rating = 8
    dragging_slider = False
    saved_until = 0
    error_until = 0
    error_message = ""
    return_after_save = False
    controls: dict[str, object] = {}

    clock = pygame.time.Clock()
    running = True

    while running:
        now_ticks = pygame.time.get_ticks()
        if return_after_save and now_ticks >= saved_until:
            screen_mode = "select"
            comment_field.value = ""
            comment_active = False
            return_after_save = False

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
                continue

            if event.type == pygame.VIDEORESIZE and not fullscreen:
                screen = pygame.display.set_mode(event.size, pygame.RESIZABLE)
                fonts = make_fonts(*screen.get_size())
                continue

            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                if screen_mode == "review":
                    screen_mode = "select"
                    comment_active = False
                    dragging_slider = False
                else:
                    running = False
                continue

            if event.type == pygame.KEYDOWN and event.key == pygame.K_F11:
                fullscreen = not fullscreen
                screen = set_display(fullscreen)
                fonts = make_fonts(*screen.get_size())
                continue

            if screen_mode == "select":
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    tabs = controls.get("tabs", {})
                    if controls.get("fullscreen") and controls["fullscreen"].collidepoint(event.pos):
                        fullscreen = not fullscreen
                        screen = set_display(fullscreen)
                        fonts = make_fonts(*screen.get_size())
                    elif tabs and tabs["schedule"].collidepoint(event.pos):
                        source_mode = "schedule"
                        active_custom = None
                    elif tabs and tabs["custom"].collidepoint(event.pos):
                        source_mode = "custom"
                    elif source_mode == "schedule":
                        for index, rect in controls.get("rows", []):
                            if rect.collidepoint(event.pos):
                                selected_index = index
                                current_lecture = lectures[index]
                                rating = 8
                                comment_field.value = ""
                                screen_mode = "review"
                                break
                    elif source_mode == "custom":
                        active_custom = None
                        for index, rect in enumerate(controls.get("custom_fields", [])):
                            if rect.collidepoint(event.pos):
                                active_custom = index
                                break
                        submit = controls.get("custom_submit")
                        if submit and submit.collidepoint(event.pos) and controls.get("custom_ready"):
                            current_lecture = custom_lecture_from_fields(custom_fields)
                            rating = 8
                            comment_field.value = ""
                            screen_mode = "review"
                            active_custom = None

                elif event.type == pygame.MOUSEWHEEL and source_mode == "schedule" and lectures:
                    visible = int(controls.get("visible", 6))
                    max_offset = max(0, len(lectures) - visible)
                    scroll_offset = max(0, min(max_offset, scroll_offset - event.y))

                elif event.type == pygame.KEYDOWN and source_mode == "schedule" and lectures:
                    visible = int(controls.get("visible", 6))
                    if event.key in (pygame.K_DOWN, pygame.K_RIGHT):
                        selected_index = min(len(lectures) - 1, selected_index + 1)
                    elif event.key in (pygame.K_UP, pygame.K_LEFT):
                        selected_index = max(0, selected_index - 1)
                    elif event.key == pygame.K_RETURN:
                        current_lecture = lectures[selected_index]
                        rating = 8
                        comment_field.value = ""
                        screen_mode = "review"
                    scroll_offset = max(0, min(scroll_offset, selected_index))
                    if selected_index >= scroll_offset + visible:
                        scroll_offset = selected_index - visible + 1

                elif source_mode == "custom" and active_custom is not None:
                    if event.type == pygame.KEYDOWN and event.key == pygame.K_TAB:
                        active_custom = (active_custom + 1) % len(custom_fields)
                    elif event.type in (pygame.TEXTINPUT, pygame.KEYDOWN):
                        handle_text_input(custom_fields[active_custom], event)

            elif screen_mode == "review" and current_lecture is not None:
                saved_locked = now_ticks < saved_until

                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and not saved_locked:
                    if controls.get("fullscreen") and controls["fullscreen"].collidepoint(event.pos):
                        fullscreen = not fullscreen
                        screen = set_display(fullscreen)
                        fonts = make_fonts(*screen.get_size())
                    elif controls.get("back") and controls["back"].collidepoint(event.pos):
                        screen_mode = "select"
                        comment_active = False
                        dragging_slider = False
                    elif controls.get("comment") and controls["comment"].collidepoint(event.pos):
                        comment_active = True
                    else:
                        comment_active = False

                    track = controls.get("slider_track")
                    knob = controls.get("slider_knob")
                    if track and (track.inflate(0, 34).collidepoint(event.pos) or knob.collidepoint(event.pos)):
                        rating = rating_from_mouse(track, event.pos[0])
                        dragging_slider = True

                    if controls.get("save") and controls["save"].collidepoint(event.pos):
                        feedback = Feedback(current_lecture, rating, comment_field.value)
                        try:
                            save_feedback(feedback)
                        except OSError:
                            error_message = "Uždarykite proof_of_concept.csv Excel'yje ir bandykite dar kartą."
                            error_until = pygame.time.get_ticks() + 3000
                        else:
                            print("Saved feedback")
                            saved_until = pygame.time.get_ticks() + THANKS_MS
                            return_after_save = True
                        dragging_slider = False

                elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                    dragging_slider = False

                elif event.type == pygame.MOUSEMOTION and dragging_slider and not saved_locked:
                    track = controls.get("slider_track")
                    if track:
                        rating = rating_from_mouse(track, event.pos[0])

                elif event.type == pygame.KEYDOWN and not saved_locked:
                    if event.key in (pygame.K_LEFT, pygame.K_DOWN):
                        rating = max(1, rating - 1)
                    elif event.key in (pygame.K_RIGHT, pygame.K_UP):
                        rating = min(10, rating + 1)
                    elif event.key == pygame.K_RETURN and pygame.key.get_mods() & pygame.KMOD_CTRL:
                        feedback = Feedback(current_lecture, rating, comment_field.value)
                        try:
                            save_feedback(feedback)
                        except OSError:
                            error_message = "Uždarykite proof_of_concept.csv Excel'yje ir bandykite dar kartą."
                            error_until = pygame.time.get_ticks() + 3000
                        else:
                            print("Saved feedback")
                            saved_until = pygame.time.get_ticks() + THANKS_MS
                            return_after_save = True
                    elif comment_active:
                        handle_text_input(comment_field, event)

                elif event.type == pygame.TEXTINPUT and comment_active and not saved_locked:
                    handle_text_input(comment_field, event)

        if screen_mode == "review" and current_lecture is not None:
            controls = draw_review(
                screen,
                current_lecture,
                rating,
                comment_field,
                comment_active,
                saved_until,
                error_until,
                error_message,
                fonts,
                fullscreen,
            )
        else:
            fullscreen_rect = draw_header(screen, fonts, fullscreen)
            tabs = draw_tabs(screen, fonts, source_mode)
            if source_mode == "schedule":
                controls = draw_schedule_select(screen, lectures, selected_index, scroll_offset, status, fonts)
            else:
                controls = draw_custom_select(screen, custom_fields, active_custom, fonts)
            controls["tabs"] = tabs
            controls["fullscreen"] = fullscreen_rect

        pygame.display.flip()
        clock.tick(60)

    pygame.quit()


if __name__ == "__main__":
    main()
