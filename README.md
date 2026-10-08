[English version](README.en.md)

# Thessla Green dla Home Assistant

Lokalna integracja rekuperatorów Thessla Green i oczyszczacza Particle+ z Home Assistant.
Pozwala odczytywać pomiary i alarmy, sterować pracą urządzeń oraz edytować
harmonogramy AirPack4 przez bramkę Modbus TCP → RTU.

Najbardziej rozbudowany profil jest przygotowany dla **AirPack4 300h ze sterownikiem
4.89 i modułem TG-02 0.30**. Integracja pokazuje w HA model, numer seryjny
i wersje oprogramowania odczytane z urządzenia.

## Wymagania

- **Home Assistant 2025.10.0 lub nowszy**.
- Dostęp do urządzenia przez bramkę obsługującą **Modbus TCP**.
- Znany adres IP lub nazwa hosta bramki, port TCP oraz adres urządzenia Modbus
  — w formularzu oznaczony jako **slave ID**.
- Poprawnie skonfigurowana strona RTU bramki. Domyślne parametry producenta
  to **9600 bps, 8N1**.

Domyślny port w formularzu to **8899**. Ustaw port używany przez Twoją bramkę.
Przesyłanie surowych ramek RTU przez TCP nie jest obsługiwane.

## Wybór profilu

| Profil w konfiguracji | Domyślny slave ID | Przeznaczenie |
| --- | --- | --- |
| **AirPack4 300h** | 10 | Rozbudowane funkcje użytkownika dla sterownika 4.89 / TG-02 0.30 |
| **Particle+** | 30 | Particle+500 z osobnym adresem Modbus |
| **Rekuperator — profil ogólny** | 10 | Dotychczasowa mapa integracji, zachowana dla istniejących wpisów |

Wybierz profil odpowiadający urządzeniu. Dostępność wyposażenia dodatkowego,
np. GWC, nagrzewnic czy AFC, zależy od instalacji.

## Instalacja

### Przez HACS

1. Otwórz HACS i dodaj repozytorium
   `https://github.com/corapoid/homeassistant-thesslagreen` jako repozytorium niestandardowe
   kategorii **Integracja**.
2. Zainstaluj **Thessla Green**.
3. Zrestartuj Home Assistant.
4. Przejdź do **Ustawienia → Urządzenia i usługi → Dodaj integrację**.
5. Wyszukaj **Thessla Green**, wybierz profil i podaj dane połączenia.

Możesz też otworzyć [formularz dodawania Thessla Green](https://my.home-assistant.io/redirect/config_flow_start/?domain=thessla_green)
bezpośrednio. Jeśli po restarcie nie widzisz pozycji na liście, odśwież interfejs
przeglądarki z pominięciem pamięci podręcznej (`Ctrl+Shift+R` lub `Cmd+Shift+R`).
W aplikacji mobilnej zamknij ją i otwórz ponownie, a w razie potrzeby wyczyść
pamięć podręczną interfejsu. Nazwa na liście to **Thessla Green**, nie nazwa repozytorium.

### Ręcznie

1. Pobierz repozytorium lub sklonuj je:

   ```bash
   git clone --branch v0.4.0 https://github.com/corapoid/homeassistant-thesslagreen.git
   ```

2. Skopiuj **wyłącznie** katalog `custom_components/thessla_green` z repozytorium
   do katalogu konfiguracji HA. Docelowa struktura powinna wyglądać tak:

   ```text
   <katalog konfiguracji HA>/
   └── custom_components/
       └── thessla_green/
           ├── __init__.py
           ├── manifest.json
           └── ...
   ```

3. Zrestartuj Home Assistant i dodaj integrację jak w instalacji przez HACS.

### Aktualizacja istniejącej instalacji

Zaktualizuj integrację i zrestartuj HA. Jeśli masz **AirPack4 300h**, otwórz opcje
istniejącego wpisu i ustaw **Model rekuperatora → AirPack4 300h**. Zapis opcji
automatycznie przeładuje integrację.

Particle+ dodaj jako **osobny wpis integracji**, z jego własnym slave ID.

### Przejście z poprzedniego repozytorium

Projekt jest rozwijany w niezależnym repozytorium **homeassistant-thesslagreen**.
W HACS zastąp poprzedni adres repozytorium adresem podanym powyżej i zainstaluj
aktualne wydanie. Konfiguracja HA nadal używa domeny `thessla_green` oraz tych
samych identyfikatorów encji, więc zachowaj istniejący wpis integracji.

## AirPack4 300h

### Dane urządzenia i pomiary

Na karcie urządzenia oraz w encjach znajdziesz:

- model, numer seryjny, wersję sterownika i TG-02 oraz opcjonalnie wersję Expansion;
- temperatury czerpni, nawiewu, wywiewu, za FPX, kanałową, GWC i otoczenia centrali;
- przepływy powietrza, intensywności wentylacji i stan Constant Flow;
- stan FPX, ERV, bypassu, KOMFORT i GWC;
- potwierdzenie pracy O1, zasilanie wentylatorów oraz stany wejść i wyjść;
- zużycie filtrów, terminy wymiany, aktywne alarmy i ich opisy;
- diagnostykę napięć sterowania i odstępu między odczytami Modbus.

Wersje oprogramowania są **odczytywane z urządzenia**. Model wynika z wybranego
profilu. Zezwolenie na działanie automatyki bypassu jest pokazywane oddzielnie
od faktycznego stanu siłownika i aktywności funkcji bypassu.

### Sterowanie

| Funkcja | Dostępne ustawienia |
| --- | --- |
| Praca centrali | Zasilanie, tryb automatyczny, manualny i chwilowy, sezon lato/zima |
| Wentylacja | Intensywność manualna i chwilowa **10–100%**, nastawy biegów AirS |
| KOMFORT i ERV | EKO/KOMFORT, tryb ERV, temperatury zadane **10–45°C co 0,5°C** |
| Bypass | Zezwolenie, sposób działania, progi temperatur, różnicowanie strumieni i intensywność |
| GWC | Zezwolenie, progi temperatur, regeneracja dobowa/temperaturowa, czas i godziny regeneracji |
| Funkcje specjalne | Ręczne wietrzenie, kominek, otwarte okna, pusty dom oraz parametry tych funkcji i okapu |
| Panel i nazwa | Język Air++ oraz nazwa urządzenia zapisana w sterowniku |

Zmiana nastaw trybu chwilowego zapisuje powiązane wartości w jednej operacji
Modbus. Intensywność manualna jest nastawą **trybu manualnego**.
Stan funkcji uruchamianych przez wejścia lub harmonogram jest dostępny w sensorach.

### Harmonogramy

Każdy dzień tygodnia ma **cztery odcinki czasowe**, oddzielnie dla lata i zimy.
Możesz ustawić godzinę rozpoczęcia, intensywność, temperaturę i aktywację odcinka.
Osobne encje obsługują wietrzenie według harmonogramu oraz w trybie manualnym.

**Encje harmonogramów są domyślnie wyłączone.** Włącz potrzebne encje w ustawieniach
na karcie urządzenia. Tak samo udostępniana jest szczegółowa diagnostyka wejść
i część alarmów.

- Godziny mają rozdzielczość jednej minuty.
- Ustawienie godziny aktywuje odcinek; jego wyłączenie zapisuje znacznik protokołu.
- Ponowne włączenie przywraca zapamiętaną godzinę. Po przeładowaniu integracji
  wyłączony odcinek korzysta z godziny domyślnej.
- Edycja intensywności zachowuje temperaturę w tym samym rejestrze i odwrotnie.
- Harmonogram jest odczytywany **co 5 minut** oraz ponownie po zapisie z HA.
  Zmiany z panelu mogą być widoczne z takim opóźnieniem.

### Filtry

W opcjach integracji wybierz zainstalowany **system kontroli filtrów**:

| Ustawienie | Przyciski potwierdzenia wymiany |
| --- | --- |
| Nieokreślony | Niedostępne |
| Bez AFC | Filtr nawiewny i wywiewny |
| AFC nawiewu | Tylko filtr wywiewny |
| AFC wywiewu | Tylko filtr nawiewny |
| AFC obu filtrów | Niedostępne — filtry są kontrolowane przez AFC |

Integracja udostępnia też kontrolę filtrów i resety alarmów oznaczonych przez
producenta jako resetowalne przez użytkownika. Część przycisków i szczegółowych
alarmów trzeba włączyć w ustawieniach encji.

## Particle+500

Wybierz profil **Particle+** i podaj adres bramki oraz slave ID oczyszczacza
— domyślnie **30**. Może korzystać z tej samej bramki co rekuperator,
ale wymaga osobnego wpisu integracji.

Obsługiwane są:

- stężenie pyłu z czujników **PmSensor OUT / IN**;
- wybór PM10 lub PM2.5, trybu manualnego/automatycznego i sposobu regulacji;
- zasilanie oraz intensywność manualna **10–100%**;
- nastawa bezwzględna **0–200 µg/m³** i stężenia odniesienia **10–300 µg/m³**;
- spadek ciśnienia, zużycie filtrów, wstrzymanie filtracji i alarmy;
- od firmware **3.4.0** także brak zezwolenia na pracę oraz brak filtrów.
- komunikat panelu `slave_screen`, kod komunikatu i stan procedury filtrów;
- osobne kody alarmów, w tym **S116**, oraz zbiorczą listę aktywnych alarmów;
- rzeczywistą wersję sterownika, numer seryjny i parametry portów RTU;
- odczyt nastawy względnej z panelu, rejestrów zegara, rejestracji alarmów
  oraz surowych rejestrów nazwy urządzenia i kompilacji oprogramowania.

Czujniki pokazują **wybrany rodzaj pyłu**, wskazany atrybutem `particle_type`.
Domyślne pomiary urządzenia odbywają się co **10 sekund** w trybie automatycznym
i co **30 minut** w trybie manualnym lub przy wyłączonym oczyszczaczu.
Odświeżanie integracji nie przyspiesza tych pomiarów.

Procentową nastawę regulacji względnej ustawia się na panelu Particle+.
Tryb automatyczny może być niedostępny przy awarii PmSensor OUT.

### Kontrola filtrów i komunikaty Particle+

Przycisk **Particle+ Uruchom kontrolę filtrów** zapisuje wartość **3** do rejestru
**42 / 0x002A**. Nie wymaga kodu serwisowego. Jest niedostępny podczas trwającej
kontroli lub kalibracji. Dzień i godzinę automatycznej kontroli ustawisz osobnymi
encjami; w Particle+ godzina i minuta są dwoma polami bajtowymi rejestru 44.

Wynik obserwuj w sensorach **Particle+ Komunikat kontroli filtrów** i
**Particle+ Kod komunikatu filtrów** — odczytują rejestr **4398 / 0x112E**:

| Kod | Znaczenie |
| --- | --- |
| `0x31` | Wykryto nowy filtr HEPA |
| `0x39` | Opór HEPA jest większy niż oryginalnego; wymagana decyzja TAK/NIE |
| `0x43` | Trwa kontrola filtrów |
| `0x47` | Błąd przepływu podczas kontroli filtrów |
| `0x48` | Procedura kontroli została zakończona |
| `0x4A` | Nie można uruchomić kontroli; sprawdź alarmy |

Integracja rozpoznaje wszystkie komunikaty wymienione w protokole. Dla nieznanego
kodu zachowuje surową wartość, zamiast przypisywać mu wynik kontroli.
Komunikat zakończenia **nie oznacza automatycznie skasowania S116** — jego stan
jest pokazany w osobnej encji **Particle+ S116 — Konieczna wymiana filtra HEPA**.

Odczyt nie kasuje komunikatów. Przycisk **Potwierdź komunikat filtrów** wykonuje
jawny zapis `0` do `4398`; następny komunikat kolejki zostanie odczytany ponownie.
Pytania o zwiększony opór wymagają użycia osobnego przycisku **TAK** lub **NIE**,
który zapisuje decyzję do `4400 / 0x1130`. Krytycznych komunikatów o braku lub
nieprawidłowym filtrze nie można potwierdzić tym przyciskiem.

Resety użytkownika dotyczą tylko S2 i S255. S116 jest alarmem resetowanym przez
sterownik automatycznie i nie ma przycisku wymuszającego jego skasowanie.
Szczegółowe rejestracje alarmów i parametry UART są domyślnie wyłączone w HA;
włącz potrzebne encje na karcie urządzenia. Spakowane daty historii, zegar i
rejestry kompilacji są dostępne jako dane surowe, z opisem pól, bez zgadywania
niedookreślonego w protokole kodowania dat. Rejestracje alarmów są odświeżane
co pięć minut i po poleceniu z HA; bieżące komunikaty i alarmy przy każdym odczycie.

## Sprawność, moc odzysku i COP

Rekuperator udostępnia obliczaną sprawność temperaturową i moc odzysku.
Do obliczenia **COP** wybierz w opcjach integracji sensor **mocy chwilowej w W lub kW**.
Nie wybieraj sensora energii w Wh/kWh.

Sensor mocy jest opcjonalny; jego zmianę lub usunięcie można zapisać w opcjach.
Sprawność wymaga poprawnych temperatur i odpowiedniej różnicy temperatur.
Moc odzysku i COP korzystają z dodatniego pomiaru przepływu CF;
COP wymaga również dodatniej mocy.
Są to wartości wyliczane z odczytów, a nie bezpośredni pomiar wydajności urządzenia.

## Komunikacja i diagnostyka

Standardowy interwał odświeżania wynosi **30 sekund** i jest ustawiany podczas
konfiguracji. Polecenia Modbus są wykonywane kolejno, a pojedyncze żądanie
obejmuje maksymalnie 16 rejestrów.

| Objaw | Co sprawdzić |
| --- | --- |
| Integracja nie uruchamia się | Host, port, slave ID, parametry RTU i dostępność bramki; HA automatycznie ponawia konfigurację |
| Brak integracji na liście po instalacji | Pełny restart HA, odświeżenie interfejsu, bezpośredni formularz oraz obecność `/config/custom_components/thessla_green/manifest.json` |
| Encje są niedostępne | Połączenie, logi integracji, dostępność czujnika lub wyposażenia |
| Brakuje harmonogramów lub szczegółowych alarmów | Włącz odpowiednie encje na karcie urządzenia |
| Nie można potwierdzić wymiany filtra | Ustaw właściwy system AFC w opcjach; przyciski dotyczą filtrów bez AFC |
| COP jest niedostępny | Sensor mocy i jego jednostkę, poprawne temperatury, aktywny CF oraz dodatnią moc/przepływ |
| Zmiana harmonogramu z panelu nie pojawia się od razu | Poczekaj na odczyt harmonogramu — do 5 minut |

W profilu AirPack4 sensor modelu ma atrybut **`unsupported_registers`**.
Zawiera adresy pominięte po jawnej odpowiedzi Modbus **Illegal Data Address**.
Po zmianie wyposażenia lub firmware przeładuj integrację, aby ponowić wykrywanie.
Timeouty i pozostałe błędy urządzenia nie są traktowane jako brak wyposażenia.

Znaczniki braku temperatury `0x8000` i nieaktywnego CF `0xFFFF` nie są publikowane
jako ujemne pomiary ani używane w obliczeniach.

## Rozwój i testy

Użyj wersji Pythona obsługiwanej przez instalowane wydanie Home Assistant:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-test.txt
python -m pytest -q
```

Minimalne środowisko CI można odtworzyć z **Pythonem 3.13**:

```bash
python3.13 -m venv .venv-min
.venv-min/bin/python -m pip install -r requirements-test.txt \
  -c tests/constraints-ha-2025.10.txt \
  "homeassistant==2025.10.0" "pymodbus==3.11.2"
.venv-min/bin/python -m pytest -q
```

Testy obejmują dekodowanie danych, sterowanie, harmonogramy, błędy komunikacji,
cykl życia integracji, rejestr urządzeń HA oraz lokalne bramki TCP obsługiwane
przez rzeczywistego klienta pymodbus. CI sprawdza minimalne i aktualne wersje zależności.

## Status projektu i źródła

Aktualne wydanie: **v0.4.0**. Archiwum integracji i plik `SHA256SUMS` są dostępne
na stronie wydania. Dokumentacja i pliki wydania pochodzą z tego samego tagu.

Zmiany oczekujące na publikację są oznaczone jako **Unreleased** w
[CHANGELOG.md](CHANGELOG.md). Weryfikacja na fizycznych urządzeniach pozostaje
do wykonania; zakres profili opiera się na dokumentacji producenta i testach automatycznych.

- [Wydania integracji](https://github.com/corapoid/homeassistant-thesslagreen/releases)
- [Zgłoszenia błędów](https://github.com/corapoid/homeassistant-thesslagreen/issues)
- [Protokół Modbus AirPack4](https://thesslagreen.com/wp-content/uploads/MODBUS_USER_AirPack_4_10.2022.01.pdf)
- [Protokół Modbus Particle+](https://thesslagreen.com/wp-content/uploads/MODBUS_USER_Particle_08.2021.01.pdf)

Profil AirPack4 obejmuje funkcje użytkownika. Kalibracja instalatora, klucz
produktu i zmiana parametrów portów Modbus pozostają poza jego zakresem.

## Licencja

Projekt jest udostępniany na [licencji MIT](LICENSE).

Historia projektu i wkład autorów pochodzą z
[ThesslaGreen_HA autorstwa aLAN-LDZ](https://github.com/aLAN-LDZ/ThesslaGreen_HA).
Niezależne repozytorium zachowuje tę historię oraz wcześniejsze tagi.

### Publikowanie wydania

Wersja w `manifest.json` i sekcja w changelogu muszą odpowiadać tagowi `vX.Y.Z`.
Lokalne pakowanie i kontrolę wersji wykonasz poleceniem:

```bash
python scripts/build_release.py v0.4.0 --output-dir dist
```

Wypchnięcie tagu uruchamia workflow **Release**. Po przejściu testów i walidacji
HACS/hassfest workflow publikuje GitHub release z archiwum, opisem z changelogu
oraz sumą SHA256. Tag z sufiksem, np. `v0.4.0-beta.1`, jest publikowany jako prerelease.
