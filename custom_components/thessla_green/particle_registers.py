"""Particle+ information and user filter commands from the official protocol."""

FILTER_PROCEDURE_REGISTER = 42
START_FILTER_CHECK = 3
FILTER_MESSAGE_REGISTER = 4398
FILTER_ANSWER_REGISTER = 4400
FILTER_QUESTIONS = {0x36, 0x39}
FILTER_CRITICAL_MESSAGES = {0x38, 0x3B, 0x53, 0x54}
FILTER_BUSY_MESSAGES = {0x42, 0x43}

FILTER_MESSAGES = {
    0: "Brak komunikatu",
    0x30: "Wykryto nowy filtr wstępny",
    0x31: "Wykryto nowy filtr HEPA",
    0x32: "Zbliża się wymiana filtra wstępnego",
    0x33: "Wymień filtr wstępny",
    0x34: "Zbliża się wymiana filtra HEPA",
    0x35: "Wymień filtr HEPA",
    0x36: "Filtr wstępny ma większy opór niż oryginalny — użyć filtra?",
    0x38: "Brak filtra wstępnego — włóż filtr i uruchom ponownie",
    0x39: "Filtr HEPA ma większy opór niż oryginalny — użyć filtra?",
    0x3B: "Brak filtra HEPA — włóż filtr i uruchom ponownie",
    0x3C: "Pozostały czas użytkowania filtra wstępnego: 30 dni",
    0x3D: "Upłynął maksymalny czas użytkowania filtra wstępnego",
    0x3E: "Pozostały czas użytkowania filtra HEPA: 30 dni",
    0x3F: "Upłynął maksymalny czas użytkowania filtra HEPA",
    0x40: "Wymień filtr wstępny",
    0x41: "Wymień filtr HEPA",
    0x42: "Trwa kalibracja filtrów",
    0x43: "Trwa kontrola filtrów",
    0x44: "Kalibracja filtrów — sprawdź alarmy",
    0x45: "Kontrola filtrów — sprawdź alarmy",
    0x46: "Kalibracja filtrów — błąd przepływu",
    0x47: "Kontrola filtrów — błąd przepływu",
    0x48: "Procedura kontroli filtrów zakończona",
    0x49: "Procedura kalibracji filtrów zakończona",
    0x4A: "Nie można uruchomić kontroli filtrów — sprawdź alarmy",
    0x4C: "Błąd wentylatora",
    0x4D: "Pozostały czas użytkowania filtra wstępnego: mniej niż 30 dni",
    0x4E: "Pozostały czas użytkowania filtra HEPA: mniej niż 30 dni",
    0x4F: "Pozostały czas użytkowania filtrów: 30 dni",
    0x50: "Upłynął maksymalny czas użytkowania filtrów",
    0x51: "Wymień filtry",
    0x52: "Pozostały czas użytkowania filtrów: mniej niż 30 dni",
    0x53: "Włóż prawidłowy filtr wstępny i uruchom ponownie",
    0x54: "Włóż prawidłowy filtr HEPA i uruchom ponownie",
}

# Code, mask, description; history uses four consecutive words per alarm.
BASE_ALARMS = (
    ("S2", 0x0001, "Awaria wentylatora"),
    ("PM_OUT", 0x0002, "Brak odczytu PmSensor OUT"),
    ("E4", 0x0004, "Brak odczytu PmSensor IN"),
    ("S255", 0x0008, "Błąd komunikacji EEPROM"),
    ("E64", 0x0010, "Błąd utrzymania przepływu wentylatora"),
    ("E16", 0x0020, "Konieczna wymiana filtra HEPA"),
    ("E17", 0x0040, "Zbliża się wymiana filtra HEPA"),
    ("E18", 0x0080, "Upłynął maksymalny czas użytkowania filtra HEPA"),
    ("S116", 0x0100, "Konieczna wymiana filtra HEPA"),
    ("E32", 0x0200, "Konieczna wymiana filtra wstępnego"),
    ("E33", 0x0400, "Zbliża się wymiana filtra wstępnego"),
    ("E34", 0x0800, "Upłynął maksymalny czas użytkowania filtra wstępnego"),
    ("S132", 0x1000, "Konieczna wymiana filtra wstępnego"),
    ("E127", 0x2000, "Awaria czujnika CF wentylatora"),
    ("E128", 0x4000, "Awaria czujnika CF filtra F7"),
    ("E256", 0x8000, "Awaria czujnika CF filtra H13"),
)
EXTENDED_ALARMS = (
    ("S1", 0x0001, "Brak zewnętrznego zezwolenia na pracę"),
    ("S117", 0x0002, "Brak filtra wstępnego"),
    ("S133", 0x0004, "Brak filtra HEPA"),
)

OPTIONAL_BLOCKS = ((42, 3), (55, 1), (97, 1), (112, 10), (4398, 3), (8128, 3), (8144, 1))
MODERN_BLOCKS = ((98, 1), (8132, 3), (8192, 2), (12352, 1))
HISTORY_BLOCKS = tuple((1536 + offset, 16) for offset in range(0, 64, 16))
MODERN_HISTORY_BLOCKS = ((1600, 12),)
