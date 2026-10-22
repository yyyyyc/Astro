# Project Logic — Business Logic Documentation

**Languages:** [English](#english) · [עברית](#hebrew)

**Basis:** written from the actual source code (`app.py`, `templates/*.html`) and the live database
contents, as of version 1.0.3. Labels used throughout:

- ✅ **Implemented**: present and working in the code.
- ❌ **Not implemented**: not found anywhere in the code or database.
- ❓ **Needs clarification**: implemented, but the intended rule is uncertain.

---

<a id="english"></a>

# English

## 1. Purpose of the website

The website gives a person astrological forecasts based on the **position of the Moon**, calculated
with several timing techniques. For each result it shows a ready-made forecast text, in Hebrew, taken
from a database.

It answers four questions, plus a Hebrew landing page for ad campaigns:

| Technique | Page | Question answered | Status |
|---|---|---|---|
| Tertiary I | Main page | Where is my Tertiary I progressed Moon on a given date? | ✅ |
| Tertiary II | Main page | Where is my Tertiary II (minor-progressed) Moon on a given date? | ✅ |
| Secondary Progression | Secondary Progression page | Where is my secondary-progressed (day-for-a-year) Moon on a given date? | ✅ |
| Moon of Transit | Moon of Transit page | Which sign is the real Moon in right now, when does it move on, and what does that mean for me? | ✅ |
| Moon of Transit (landing) | `/lp/moon` | Same as Moon of Transit, as a short guided funnel in Hebrew for visitors from ads (e.g. Facebook) | ✅ |

The site is **free and open**. There are no user accounts, logins or payments (see section 8).

## 2. User workflows

### 2.1 Tertiary I and II (main page)

1. The user opens the main page. Birth date and progression date are pre-filled with today, birth
   time with 12:00, and the place with the user's current location if the browser allows it.
2. The user enters birth date, birth time and place of birth, and chooses a progression date.
   - A Sun-sign symbol appears next to the birth date as it is typed.
   - The place must be picked from the search suggestions.
3. The user clicks **Calculate Tertiary Progressions**.
4. The site shows a summary (timezone, UTC offset at birth, birth time in local and UTC, days elapsed),
   then two results: the **Tertiary I** Moon and the **Tertiary II** Moon. Each shows the sign, the
   degree with minutes and seconds, and the "progressed chart date" it was calculated for.
5. The user **clicks a Moon row** to see the forecast text for that result.

### 2.2 Secondary Progression

1. The user clicks **Secondary Progression** on the main page.
2. The form is the same as the main page and pre-filled the same way.
3. The user clicks **Calculate Secondary Progression**.
4. The site shows a summary (timezone, birth local/UTC, progression date, age in years), the progressed
   Moon's sign and degree, and **the forecast text appears automatically**, with no extra click.

### 2.3 Moon of Transit

1. The user clicks **Moon of Transit** on the main page.
2. On opening, the page fills in the current date and time, detects the current location, and
   **calculates immediately**. The date of birth is pre-filled with the date 30 years ago.
3. The user can change the location (search, or "Use current location"), the date and time, and the
   date of birth (it may also be cleared).
4. The site shows:
   - the sign the Moon is in now, with the date and time it entered and will leave that sign;
   - a table of the current sign and the next 11 signs, each with its start, end and duration;
   - when a date of birth is given, the **house** the Moon occupies in each period, counted from the
     user's Sun sign.
5. The user clicks **Forecast** on any row to see its forecast text. Forecasts need a date of birth;
   without one the buttons are disabled.

### 2.4 Moon of Transit landing page (`/lp/moon`) ✅

A separate, Hebrew-only, right-to-left page with its own design, meant to be opened from ads. The main page
also links to it with the **✦ Landing Page** button.

1. The visitor arrives and an **intro video** plays in the centre of the screen
   (`media/videos/Intro_for_secondary_moon.mp4`). It starts muted, because browsers block autoplay with
   sound; buttons let the visitor turn the sound on or **skip** to the form.
2. When the video ends (or is skipped, or fails to load), it **transforms into a zodiac wheel** and a
   form asks for the **date of birth**.
3. The visitor clicks **שליחה** (Send). The wheel **spins for about 4.5 seconds** and stops with the
   visitor's Sun sign under the pointer.
4. A photo of **Yaron** appears with the message: "הפקתי את התחזית לבני מזל <sign> על פי תאריך הלידה
   שהזנתם", followed by "לצפייה בתחזית הזינו את כתובת המייל שלכם", and an **e-mail** field.
5. After a valid e-mail is entered, the wheel transforms into the **forecast video**, and a short summary
   says which sign the Moon is in now, which house that is for the visitor, and the time frame.
6. The forecast **text is not shown automatically**. The button **הצגת התחזית בטקסט** (Show the forecast
   as text) opens it in a pop-up window.
7. **בדיקה לתאריך לידה אחר** (Try another date of birth) returns to step 2.

## 3. Required user inputs

| Input | Tertiary I/II | Secondary | Moon of Transit | Format and rules |
|---|---|---|---|---|
| Birth date | Required | Required | — | `dd/mm/yyyy` |
| Birth time | Required | Required | — | Local time at the birth place, `HH:MM` |
| Place of birth | Required | Required | — | Must be chosen from the search list |
| Progression date | Required | Required | — | `dd/mm/yyyy`; must be on or after the birth date |
| Location | — | — | Required | Current location or chosen from the search list |
| Date and time | — | — | Required | `dd/mm/yyyy` and `HH:MM`, local to the location |
| Date of birth | — | — | Optional | `dd/mm/yyyy`; needed for houses and forecasts |

On the landing page (`/lp/moon`) the inputs are different:

| Input | Required | Format and rules |
|---|---|---|
| Date of birth | Yes | `dd/mm/yyyy`; a real date, from 1900, not in the future |
| E-mail | Yes | Standard address format, at most 254 characters. **Not stored** (see section 7) |
| Date, time, location | Not asked | The current moment is used; the browser's timezone is used only to display times |

- The **progression time cannot be entered**; it is always 12:00 local time. ❓ See section 9.
- Location is used **only to determine the timezone**. It does not change the Moon's position.

## 4. Supported astrology calculation methods

**Common basis (all methods) ✅**

- **Body:** only the Moon is calculated. The Sun is used only to find the user's Sun sign.
- **Zodiac:** tropical, i.e. signs measured from the spring equinox of the date. Sidereal zodiac is
  not supported.
- **Viewpoint:** geocentric, the centre of the Earth.
- **Times:** all dates and times are local to the entered place and converted to UTC for calculation.
  Daylight-saving time is handled:
  - a time that occurs twice (clocks going back) is treated as standard time;
  - a time that does not exist (clocks going forward) is moved one hour later.

| Method | Rule | Status |
|---|---|---|
| Tertiary I | 1 day after birth = 1 sidereal month (27.321661 days) of life | ✅ ❓ |
| Tertiary II (Minor progression) | 1 sidereal month after birth = 1 year (365.24219 days) of life | ✅ ❓ |
| Secondary Progression | 1 day after birth = 1 year of life | ✅ ❓ |
| Moon of Transit | Real current Moon position, plus whole-sign houses from the Sun sign | ✅ |
| Other planets, Ascendant, house cusps, aspects | — | ❌ |

## 5. Detailed logical flow

### 5.1 Tertiary I ✅

1. Convert birth (date + time) and progression date (at 12:00) to UTC, using the birth place's timezone.
2. `elapsed_days` = progression − birth. If negative → error "Progression date must be after birth date".
3. Progressed moment = birth + `elapsed_days / 27.321661` days.
   Example: at age 36.5, about 13,340 days of life give about 488 days after birth.
4. Calculate the Moon's tropical position at that moment: sign, degree, minutes and seconds.
5. Show it. Clicking the row looks up the forecast by sign + whole degree (section 6).

❓ The month length is the **sidereal** month (27.32 days). Some schools use the synodic month
(29.53 days) for Tertiary I. Confirm which is intended.

### 5.2 Tertiary II ✅

1. Same conversion and `elapsed_days` as Tertiary I.
2. Age in years = `elapsed_days / 365.24219`.
3. Progressed moment = birth + age × 27.321661 days.
   Example: at age 36.5, about 997 days after birth.
4. Calculate the Moon's position and show it. Clicking the row looks up the forecast by sign + whole
   degree.

❓ The page and code call this "Minor progression"; a code comment also describes it as "the converse of
Tertiary I", which it is not mathematically. Confirm that the minor-progression formula is the intended
definition of Tertiary II.

### 5.3 Secondary Progression ✅

1. Same conversion and `elapsed_days`.
2. Age in years = `elapsed_days / 365.24219`.
3. Progressed moment = birth + age **days**.
   Example: at age 36.5, about 36.5 days after birth.
4. Calculate the Moon's position, show it, and **automatically** load the forecast by sign + whole degree.

❓ The original request for this feature mentioned "PCA". The standard day-for-a-year method was
implemented. Confirm that this is what was meant.

### 5.4 "Journaly" ❌ ❓

**No feature named "Journaly" (or journal, or diary) exists** in the code, the templates or the database.

The closest implemented feature is **Moon of Transit**, whose forecasts come from
`tbl_moon_of_transit_daily_forecasts`, a "daily" forecast; "journalier" is French for "daily".
Its logic is documented in section 5.5. ❓ Confirm whether "Journaly" refers to Moon of Transit or
to a feature that is still planned.

### 5.5 Moon of Transit ✅

1. Take the chosen local date and time and convert it to UTC using the location's timezone.
2. Find the sign the Moon is in at that moment.
3. Find when the Moon **entered** that sign and when it **will leave** it, accurate to the minute as shown.
4. Repeat for the next 11 signs, one full lunar cycle of about 27 days. Each period usually lasts
   about 2–2.5 days.
5. If a date of birth is given:
   - **Sun sign** = the Sun's sign on that date, at 12:00 UTC.
   - **House** of each period = count of signs from the Sun sign to the Moon's sign, where the Sun's
     own sign is the 1st house (whole-sign houses from the Sun sign).
     Example: Sun in Aries, Moon in Virgo → 6th house.
6. **Forecast group** of each period:
   - if the chosen date and time is **before the midpoint** of that period → **group 1** (first half);
   - otherwise → **group 2** (second half).
   - Every period after the current one starts after the chosen time, so it **always gets group 1**. ❓
7. Clicking **Forecast** looks up the text by house + group (section 6).

### 5.6 Moon of Transit landing page ✅

1. **Sign step** (`POST /lp/moon/sign`): the date of birth gives the Sun sign (same rule as 5.5, at
   12:00 UTC). The wheel stops on that sign.
2. **Forecast step** (`POST /lp/moon/forecast`), after the e-mail is validated:
   - The Moon's sign is taken for **the current moment** (server clock). No location is needed, because
     the Moon's sign at a given instant is the same everywhere.
   - **House** and **forecast group** follow exactly the rules of 5.5 (whole-sign houses from the Sun
     sign; group 1 before the midpoint of the current sign's time frame, group 2 after).
   - The forecast text is looked up by house + group, as on the Moon of Transit page.
   - The browser's timezone is sent only to format the start and end times. If it is unknown or invalid,
     `Asia/Jerusalem` is used.
3. **Forecast video:** there is no video per forecast yet, so the server picks **one at random** from
   `media/videos/video_demo_*.mp4`. ❓ See section 9.
4. If the database is unavailable, the video and summary still appear, and the text pop-up says the text
   is not available right now.

**Design system** (`static/landing/ds.css`, `static/landing/ds.js`): every landing field uses the same
classes (`ds-field`, `ds-input`, `ds-btn`…) and the same validation rules, declared on the field
(`data-ds-rules="required date"` / `"required email"`). Error messages are in Hebrew, appear under the
field, and are announced to screen readers.

**Accessibility and mobile:** `lang="he" dir="rtl"`; labelled fields with linked hints and errors;
keyboard focus moves to each new step's heading; a skip button for the intro video; the text pop-up is a
native modal dialog (Esc closes it); animations are reduced when the visitor asks for reduced motion;
touch targets are at least 44px; layout works from 320px wide; text inputs are 16px to prevent zoom on
iOS. ❌ The videos have no captions yet.

## 6. Mapping calculation results to forecast texts ✅

Each technique has a mapping table and a texts table. Many results can share the same text.

| Technique | Lookup key | Mapping table | Rows | Distinct texts |
|---|---|---|---|---|
| Tertiary I | Moon sign + whole degree | `tbl_tertiary1_forecasts` | 360 (12 × 30) | 29 |
| Tertiary II | Moon sign + whole degree | `tbl_tertiary2_forecasts` | 360 | 36 |
| Secondary | Moon sign + whole degree | `tbl_secondary_progression_forecasts` | 360 | 27 |
| Moon of Transit | House (1–12) + half (1–2) | `tbl_moon_of_transit_daily_forecasts` | 24 | 24 |

Rules:

- **Whole degree** means the degree is cut down, not rounded. For example, 13°59′ uses degree 13.
- Signs are numbered 1–12 in zodiac order: Aries = 1 … Pisces = 12.
- **Tertiary II data pattern:** each sign is split into three decans (degrees 0–9, 10–19 and 20–29),
  with one text per decan. The `tertiary` column holds the decan number, 1–3.
- **Tertiary I data pattern:** within each sign, texts repeat in a cycle of nine degrees. This comes
  from the data, not from the code.
- If no row is found, the user sees "No forecast found for this sign and degree." (or "…for this house.").
- Texts are in Hebrew and displayed right-to-left.

## 7. Database interactions ✅

- **Read-only.** The site only reads forecast texts. It never inserts, updates or deletes data, and
  stores nothing about users or their calculations.
- The landing page's **e-mail address is validated but not saved anywhere** ❌. There is no table for it.
  ❓ See section 9.
- Database: Supabase PostgreSQL. The connection comes from the `ASTRO_DB_URL` environment variable.
  If it is missing, forecasts show an error, but calculations still work.
- Tables used: the four mapping/text pairs in section 6, plus `tbl_signs` (sign names; used only by
  the `/signs` debug page).
- Calculations themselves do **not** use the database. Only forecast texts come from it.
- Schema details: `docs/database-schema.md`.

## 8. Free versus paid forecast logic ❌

**Not implemented.** Every feature and every forecast is available to everyone without sign-in.
There are no user accounts, subscriptions, payment handling, usage limits or "premium" texts. No
related tables exist in the database.

**Media files:** the `media/` folder is served at `/media/…`. The landing page uses the intro video,
Yaron's photo and the demo videos (section 5.6). The demo audio files are not used.

## 9. Business rules, validations and exceptions

**Validations ✅**

| Rule | Where | Message |
|---|---|---|
| Place must be chosen from the search list | All pages | "Please select a place from the autocomplete list." / "Please select a location from the list." |
| Dates must be `dd/mm/yyyy` | All pages | "Please enter dates as dd/mm/yyyy." |
| Progression date must be on or after birth | Tertiary, Secondary | "Progression date must be after birth date" |
| Required fields present | All calculations | "Missing fields: …" |
| Timezone must be found for the location | All calculations | "Could not determine timezone for this location" |
| Forecasts need a date of birth | Moon of Transit | Forecast buttons disabled: "Enter a date of birth to get forecasts" |
| Sign must be valid; degree 0–29 | Forecast lookups | "Unknown sign" / "Degree must be between 0 and 29" |
| House 1–12; group 1 or 2 | Moon of Transit forecast | "House must be between 1 and 12" / "Forecast group must be 1 or 2" |
| Current location unavailable | Moon of Transit | "Current location unavailable — please type a location." |
| Date of birth required, `dd/mm/yyyy`, real date, from 1900, not in the future | Landing page | "יש להזין תאריך לידה." / "יש להזין תאריך תקין…" / "תאריך הלידה לא יכול להיות בעתיד." (server: "תאריך הלידה אינו תקין.") |
| E-mail required, valid format | Landing page | "יש להזין כתובת מייל." / "יש להזין כתובת מייל תקינה…" (server: "כתובת המייל אינה תקינה.") |

**Business rules ✅**

- The progression time is fixed at **12:00** local time on both progression pages.
- On the main page, the progressed chart dates are shown in UTC (birth is shown in both local time and
  UTC); the subtitle says "All times in UTC via birth-place timezone".
- Moon of Transit always shows **12 periods**, starting with the one that contains the chosen time.
  That first period may have started in the past.

**Items needing clarification ❓**

1. **"Journaly"**: no such feature exists; does it mean Moon of Transit (daily forecasts)? (5.4)
2. **Tertiary I month length**: sidereal (27.32 days) is used; is that intended? (5.1)
3. **Tertiary II definition**: the minor-progression formula is used; is that intended? (5.2)
4. **Secondary Progression and "PCA"**: what did "PCA" refer to? (5.3)
5. **Fixed 12:00 progression time**: should users be able to enter it? It can shift the progressed Moon
   by up to about 0.25° in Tertiary I and 0.5° in Tertiary II.
6. **Moon of Transit future periods** always use forecast group 1. The database allows groups up to
   10, but only 1–2 exist. Are more groups planned?
7. **Sun sign from date of birth** is taken at 12:00 UTC. People born on a day the Sun changes sign may
   get the neighbouring sign. Should a birth time be asked for?
8. **Whole degree by truncation** is used for all forecast lookups; rounding was not chosen. Confirm.
9. **Landing page e-mails** are validated but not stored or sent anywhere. Where should they go (a new
   database table, a mailing service)? Is a marketing-consent checkbox needed?
10. **Landing page forecast videos** are a random demo video. How will each forecast (house + group)
    map to its own video, and will the videos have captions?

---

<a id="hebrew"></a>

<div dir="rtl">

# עברית

## 1. מטרת האתר

האתר מספק לאדם תחזיות אסטרולוגיות המבוססות על **מיקום הירח**, המחושב בכמה שיטות תזמון. לכל תוצאה
הוא מציג טקסט תחזית מוכן בעברית, שנשלף ממסד נתונים.

האתר עונה על ארבע שאלות, ובנוסף יש לו עמוד נחיתה בעברית לקמפיינים:

| שיטה | עמוד | השאלה | סטטוס |
|---|---|---|---|
| Tertiary I ‏(טרשיארי I) | העמוד הראשי | היכן נמצא הירח המתקדם שלי בשיטת Tertiary I בתאריך מסוים? | ✅ |
| Tertiary II ‏(טרשיארי II) | העמוד הראשי | היכן נמצא הירח המתקדם שלי בשיטת Tertiary II (פרוגרסיה מינורית) בתאריך מסוים? | ✅ |
| Secondary Progression ‏(פרוגרסיה סקנדרית) | עמוד הפרוגרסיה הסקנדרית | היכן נמצא הירח המתקדם שלי בשיטת יום-לשנה בתאריך מסוים? | ✅ |
| Moon of Transit ‏(ירח בטרנזיט) | עמוד הירח בטרנזיט | באיזה מזל נמצא הירח האמיתי עכשיו, מתי יעבור הלאה, ומה המשמעות עבורי? | ✅ |
| ירח בטרנזיט (עמוד נחיתה) | `/lp/moon` | כמו ירח בטרנזיט, כתהליך קצר ומודרך בעברית למבקרים שמגיעים ממודעות (למשל פייסבוק) | ✅ |

האתר **חינמי ופתוח**. אין חשבונות משתמש, התחברות או תשלומים (ראו סעיף 8).

## 2. תהליכי עבודה של המשתמש

### 2.1 Tertiary I ו-II (העמוד הראשי)

1. המשתמש פותח את העמוד הראשי. תאריך הלידה ותאריך הפרוגרסיה ממולאים מראש בתאריך של היום, שעת הלידה
   ב-12:00, והמקום במיקום הנוכחי של המשתמש אם הדפדפן מאפשר זאת.
2. המשתמש מזין תאריך לידה, שעת לידה ומקום לידה, ובוחר תאריך פרוגרסיה.
   - סמל מזל השמש מופיע ליד תאריך הלידה בזמן ההקלדה.
   - יש לבחור את המקום מתוך הצעות החיפוש.
3. המשתמש לוחץ על **Calculate Tertiary Progressions**.
4. האתר מציג סיכום (אזור זמן, הפרש מ-UTC בזמן הלידה, זמן הלידה המקומי וב-UTC, ימים שחלפו), ואחריו
   שתי תוצאות: הירח של **Tertiary I** והירח של **Tertiary II**. בכל אחת מוצגים המזל, המעלה עם
   הדקות והשניות, ו"תאריך המפה המתקדמת" שעבורו בוצע החישוב.
5. המשתמש **לוחץ על שורת הירח** כדי לראות את טקסט התחזית של אותה תוצאה.

### 2.2 פרוגרסיה סקנדרית

1. המשתמש לוחץ על **Secondary Progression** בעמוד הראשי.
2. הטופס זהה לטופס של העמוד הראשי וממולא מראש באותו אופן.
3. המשתמש לוחץ על **Calculate Secondary Progression**.
4. האתר מציג סיכום (אזור זמן, זמן הלידה המקומי וב-UTC, תאריך הפרוגרסיה, הגיל בשנים), את המזל
   והמעלה של הירח המתקדם, ו**טקסט התחזית מופיע אוטומטית**, ללא לחיצה נוספת.

### 2.3 ירח בטרנזיט

1. המשתמש לוחץ על **Moon of Transit** בעמוד הראשי.
2. בפתיחה, העמוד ממלא את התאריך והשעה הנוכחיים, מזהה את המיקום הנוכחי ו**מחשב מיד**. תאריך הלידה
   ממולא מראש בתאריך של לפני 30 שנה.
3. המשתמש יכול לשנות את המיקום (חיפוש, או "Use current location"), את התאריך והשעה, ואת תאריך
   הלידה (אפשר גם למחוק אותו).
4. האתר מציג:
   - את המזל שבו הירח נמצא עכשיו, עם התאריך והשעה שבהם נכנס למזל ושבהם יצא ממנו;
   - טבלה של המזל הנוכחי ו-11 המזלות הבאים, עם התחלה, סוף ומשך לכל אחד;
   - כשהוזן תאריך לידה, את **הבית** שבו נמצא הירח בכל תקופה, בספירה ממזל השמש של המשתמש.
5. המשתמש לוחץ על **Forecast** בשורה כלשהי כדי לראות את טקסט התחזית שלה. תחזיות דורשות תאריך
   לידה; בלעדיו הכפתורים מושבתים.

### 2.4 עמוד הנחיתה של ירח בטרנזיט (`/lp/moon`) ✅

עמוד נפרד, בעברית בלבד ומימין לשמאל, עם עיצוב משלו, שמיועד להיפתח ממודעות. העמוד הראשי מקשר אליו גם דרך הכפתור **✦ Landing Page**.

1. המבקר מגיע, ו**סרטון פתיחה** מתנגן במרכז המסך (`media/videos/Intro_for_secondary_moon.mp4`).
   הסרטון מתחיל מושתק, כי דפדפנים חוסמים ניגון אוטומטי עם קול; כפתורים מאפשרים להפעיל קול או
   **לדלג** לטופס.
2. כשהסרטון מסתיים (או כשמדלגים עליו, או כשהוא לא נטען), הוא **הופך לגלגל מזלות** וטופס מבקש את
   **תאריך הלידה**.
3. המבקר לוחץ על **שליחה**. הגלגל **מסתובב כ-4.5 שניות** ונעצר כשמזל השמש של המבקר מתחת למחוג.
4. מופיעה תמונה של **ירון** עם ההודעה: "הפקתי את התחזית לבני מזל <מזל> על פי תאריך הלידה שהזנתם",
   ואחריה "לצפייה בתחזית הזינו את כתובת המייל שלכם", ושדה **מייל**.
5. אחרי הזנת מייל תקין, הגלגל הופך ל**סרטון התחזית**, וסיכום קצר מציין באיזה מזל הירח נמצא עכשיו,
   באיזה בית זה עבור המבקר, ואת טווח הזמן.
6. **טקסט התחזית לא מוצג אוטומטית.** הכפתור **הצגת התחזית בטקסט** פותח אותו בחלון קופץ.
7. **בדיקה לתאריך לידה אחר** מחזיר לשלב 2.

## 3. קלט נדרש מהמשתמש

| קלט | Tertiary I/II | סקנדרית | ירח בטרנזיט | פורמט וכללים |
|---|---|---|---|---|
| תאריך לידה | חובה | חובה | — | `dd/mm/yyyy` |
| שעת לידה | חובה | חובה | — | שעה מקומית במקום הלידה, `HH:MM` |
| מקום לידה | חובה | חובה | — | יש לבחור מתוך רשימת החיפוש |
| תאריך פרוגרסיה | חובה | חובה | — | `dd/mm/yyyy`; לא לפני תאריך הלידה |
| מיקום | — | — | חובה | המיקום הנוכחי או מקום שנבחר מרשימת החיפוש |
| תאריך ושעה | — | — | חובה | `dd/mm/yyyy` ו-`HH:MM`, בשעון המקומי של המיקום |
| תאריך לידה | — | — | אופציונלי | `dd/mm/yyyy`; נדרש לבתים ולתחזיות |

בעמוד הנחיתה (`/lp/moon`) הקלט שונה:

| קלט | חובה | פורמט וכללים |
|---|---|---|
| תאריך לידה | כן | `dd/mm/yyyy`; תאריך אמיתי, מ-1900, לא בעתיד |
| מייל | כן | פורמט כתובת רגיל, עד 254 תווים. **לא נשמר** (ראו סעיף 7) |
| תאריך, שעה, מיקום | לא נשאלים | נעשה שימוש ברגע הנוכחי; אזור הזמן של הדפדפן משמש רק להצגת השעות |

- **אי אפשר להזין את שעת הפרוגרסיה**; היא תמיד 12:00 בשעון המקומי. ❓ ראו סעיף 9.
- המיקום משמש **רק לקביעת אזור הזמן**. הוא אינו משנה את מיקום הירח.

## 4. שיטות החישוב האסטרולוגיות הנתמכות

**בסיס משותף (לכל השיטות) ✅**

- **גוף שמימי:** מחושב רק הירח. השמש משמשת רק למציאת מזל השמש של המשתמש.
- **גלגל המזלות:** טרופי, כלומר המזלות נמדדים מנקודת השוויון האביבית של אותו תאריך. גלגל מזלות
  סידרי אינו נתמך.
- **נקודת מבט:** גאוצנטרית, ממרכז כדור הארץ.
- **זמנים:** כל התאריכים והשעות הם לפי השעון המקומי של המקום שהוזן, ומומרים ל-UTC לצורך החישוב.
  שעון קיץ נלקח בחשבון:
  - שעה שמופיעה פעמיים (חזרה לשעון חורף) נחשבת לשעון חורף;
  - שעה שאינה קיימת (מעבר לשעון קיץ) מוזזת שעה אחת קדימה.

| שיטה | כלל | סטטוס |
|---|---|---|
| Tertiary I | יום אחד אחרי הלידה = חודש סידרי אחד (27.321661 ימים) של חיים | ✅ ❓ |
| Tertiary II (פרוגרסיה מינורית) | חודש סידרי אחד אחרי הלידה = שנה אחת (365.24219 ימים) של חיים | ✅ ❓ |
| פרוגרסיה סקנדרית | יום אחד אחרי הלידה = שנה אחת של חיים | ✅ ❓ |
| ירח בטרנזיט | מיקום הירח האמיתי כעת, ובתים של מזל שלם ממזל השמש | ✅ |
| כוכבי לכת אחרים, אופק עולה, קודקודי בתים, היבטים | — | ❌ |

## 5. זרימה לוגית מפורטת

### 5.1 Tertiary I ✅

1. ממירים את רגע הלידה (תאריך + שעה) ואת תאריך הפרוגרסיה (ב-12:00) ל-UTC, לפי אזור הזמן של מקום הלידה.
2. `elapsed_days` = פרוגרסיה − לידה. אם הערך שלילי ← שגיאה "Progression date must be after birth date".
3. הרגע המתקדם = לידה + `elapsed_days / 27.321661` ימים.
   לדוגמה: בגיל 36.5, כ-13,340 ימי חיים נותנים כ-488 ימים אחרי הלידה.
4. מחשבים את המיקום הטרופי של הירח באותו רגע: מזל, מעלה, דקות ושניות.
5. מציגים את התוצאה. לחיצה על השורה שולפת את התחזית לפי מזל + מעלה שלמה (סעיף 6).

❓ אורך החודש הוא החודש **הסידרי** (27.32 ימים). יש אסכולות שמשתמשות בחודש הסינודי (29.53 ימים)
עבור Tertiary I. יש לאשר מה הכוונה.

### 5.2 Tertiary II ✅

1. אותה המרה ואותו `elapsed_days` כמו ב-Tertiary I.
2. הגיל בשנים = `elapsed_days / 365.24219`.
3. הרגע המתקדם = לידה + גיל × 27.321661 ימים.
   לדוגמה: בגיל 36.5, כ-997 ימים אחרי הלידה.
4. מחשבים את מיקום הירח ומציגים אותו. לחיצה על השורה שולפת את התחזית לפי מזל + מעלה שלמה.

❓ העמוד והקוד קוראים לשיטה "פרוגרסיה מינורית"; הערה בקוד מתארת אותה גם כ"היפוך של Tertiary I",
מה שאינו נכון מתמטית. יש לאשר שנוסחת הפרוגרסיה המינורית היא ההגדרה הרצויה ל-Tertiary II.

### 5.3 פרוגרסיה סקנדרית ✅

1. אותה המרה ואותו `elapsed_days`.
2. הגיל בשנים = `elapsed_days / 365.24219`.
3. הרגע המתקדם = לידה + הגיל ב**ימים**.
   לדוגמה: בגיל 36.5, כ-36.5 ימים אחרי הלידה.
4. מחשבים את מיקום הירח, מציגים אותו, ו**שולפים אוטומטית** את התחזית לפי מזל + מעלה שלמה.

❓ הבקשה המקורית ליכולת הזו הזכירה "PCA". יושמה שיטת יום-לשנה הסטנדרטית. יש לאשר שזו הכוונה.

### 5.4 ‏"Journaly" ❌ ❓

**לא קיימת יכולת בשם "Journaly"** (או journal או יומן) בקוד, בתבניות או במסד הנתונים.

היכולת הקרובה ביותר שמיושמת היא **ירח בטרנזיט**, שהתחזיות שלה מגיעות מהטבלה
`tbl_moon_of_transit_daily_forecasts`, כלומר תחזית "יומית"; "journalier" בצרפתית פירושו "יומי".
הלוגיקה שלה מתוארת בסעיף 5.5. ❓ יש לאשר האם "Journaly" מתייחס לירח בטרנזיט או ליכולת שעדיין
מתוכננת.

### 5.5 ירח בטרנזיט ✅

1. לוקחים את התאריך והשעה המקומיים שנבחרו וממירים אותם ל-UTC לפי אזור הזמן של המיקום.
2. מוצאים את המזל שבו הירח נמצא באותו רגע.
3. מוצאים מתי הירח **נכנס** למזל הזה ומתי **ייצא** ממנו, בדיוק של דקה בתצוגה.
4. חוזרים על כך עבור 11 המזלות הבאים, מחזור ירח מלא של כ-27 ימים. כל תקופה נמשכת בדרך כלל
   כ-2–2.5 ימים.
5. אם הוזן תאריך לידה:
   - **מזל השמש** = המזל של השמש באותו תאריך, בשעה 12:00 UTC.
   - **הבית** של כל תקופה = מספר המזלות ממזל השמש עד מזל הירח, כשהמזל של השמש עצמו הוא הבית
     הראשון (בתים של מזל שלם ממזל השמש).
     לדוגמה: שמש בטלה וירח בבתולה ← בית 6.
6. **קבוצת התחזית** של כל תקופה:
   - אם התאריך והשעה שנבחרו **לפני נקודת האמצע** של התקופה ← **קבוצה 1** (המחצית הראשונה);
   - אחרת ← **קבוצה 2** (המחצית השנייה).
   - כל תקופה שאחרי התקופה הנוכחית מתחילה אחרי הזמן שנבחר, ולכן היא **תמיד מקבלת קבוצה 1**. ❓
7. לחיצה על **Forecast** שולפת את הטקסט לפי בית + קבוצה (סעיף 6).

### 5.6 עמוד הנחיתה של ירח בטרנזיט ✅

1. **שלב המזל** (`POST /lp/moon/sign`): תאריך הלידה נותן את מזל השמש (אותו כלל כמו ב-5.5, ב-12:00
   UTC). הגלגל נעצר על המזל הזה.
2. **שלב התחזית** (`POST /lp/moon/forecast`), אחרי בדיקת תקינות המייל:
   - מזל הירח נלקח עבור **הרגע הנוכחי** (שעון השרת). אין צורך במיקום, כי מזל הירח ברגע נתון זהה
     בכל מקום.
   - **הבית** ו**קבוצת התחזית** נקבעים בדיוק לפי הכללים של 5.5 (בתים של מזל שלם ממזל השמש; קבוצה 1
     לפני נקודת האמצע של טווח הזמן של המזל הנוכחי, קבוצה 2 אחריה).
   - טקסט התחזית נשלף לפי בית + קבוצה, כמו בעמוד הירח בטרנזיט.
   - אזור הזמן של הדפדפן נשלח רק כדי לעצב את שעות ההתחלה והסיום. אם הוא לא ידוע או לא תקין, נעשה
     שימוש ב-`Asia/Jerusalem`.
3. **סרטון התחזית:** עדיין אין סרטון לכל תחזית, ולכן השרת בוחר **אחד באקראי** מתוך
   `media/videos/video_demo_*.mp4`. ❓ ראו סעיף 9.
4. אם מסד הנתונים אינו זמין, הסרטון והסיכום עדיין מוצגים, והחלון הקופץ מודיע שהטקסט אינו זמין כרגע.

**מערכת עיצוב** (`static/landing/ds.css`, `static/landing/ds.js`): כל שדות עמוד הנחיתה משתמשים באותן
מחלקות (`ds-field`, `ds-input`, `ds-btn`…) ובאותם כללי בדיקה, שמוגדרים על השדה עצמו
(`data-ds-rules="required date"` / `"required email"`). הודעות השגיאה בעברית, מופיעות מתחת לשדה ומוקראות
לקוראי מסך.

**נגישות ומובייל:** `lang="he" dir="rtl"`; שדות עם תוויות, ורמזים ושגיאות מקושרים אליהם; פוקוס המקלדת
עובר לכותרת של כל שלב חדש; כפתור דילוג על סרטון הפתיחה; החלון הקופץ הוא חלון מודאלי מובנה (Esc סוגר
אותו); האנימציות מצומצמות כשהמבקר ביקש תנועה מופחתת; אזורי מגע בגודל 44px לפחות; הפריסה עובדת מרוחב
320px; שדות הקלט בגודל 16px כדי למנוע הגדלה ב-iOS. ❌ לסרטונים עדיין אין כתוביות.

## 6. מיפוי תוצאות החישוב לטקסטי תחזית ✅

לכל שיטה יש טבלת מיפוי וטבלת טקסטים. תוצאות רבות יכולות לחלוק את אותו טקסט.

| שיטה | מפתח השליפה | טבלת המיפוי | שורות | טקסטים שונים |
|---|---|---|---|---|
| Tertiary I | מזל הירח + מעלה שלמה | `tbl_tertiary1_forecasts` | ‏360 (12 × 30) | 29 |
| Tertiary II | מזל הירח + מעלה שלמה | `tbl_tertiary2_forecasts` | 360 | 36 |
| סקנדרית | מזל הירח + מעלה שלמה | `tbl_secondary_progression_forecasts` | 360 | 27 |
| ירח בטרנזיט | בית (1–12) + מחצית (1–2) | `tbl_moon_of_transit_daily_forecasts` | 24 | 24 |

כללים:

- **מעלה שלמה** פירושה שהמעלה נחתכת ולא מעוגלת. לדוגמה, ‏13°59′ משתמש במעלה 13.
- המזלות ממוספרים 1–12 לפי סדר המזלות: טלה = 1 … דגים = 12.
- **דפוס הנתונים של Tertiary II:** כל מזל מחולק לשלושה דקאנים (מעלות 0–9, ‏10–19 ו-20–29), עם טקסט
  אחד לכל דקאן. העמודה `tertiary` מכילה את מספר הדקאן, 1–3.
- **דפוס הנתונים של Tertiary I:** בתוך כל מזל, הטקסטים חוזרים במחזור של תשע מעלות. זה נובע מהנתונים,
  לא מהקוד.
- אם לא נמצאה שורה, המשתמש רואה "No forecast found for this sign and degree." (או "…for this house.").
- הטקסטים בעברית ומוצגים מימין לשמאל.

## 7. עבודה מול מסד הנתונים ✅

- **קריאה בלבד.** האתר רק קורא טקסטי תחזית. הוא לעולם אינו מוסיף, מעדכן או מוחק נתונים, ואינו שומר
  דבר על המשתמשים או על החישובים שלהם.
- **כתובת המייל בעמוד הנחיתה נבדקת אך אינה נשמרת בשום מקום** ❌. אין לה טבלה. ❓ ראו סעיף 9.
- מסד הנתונים: Supabase PostgreSQL. פרטי החיבור נלקחים ממשתנה הסביבה `ASTRO_DB_URL`.
  אם הוא חסר, התחזיות מציגות שגיאה, אבל החישובים ממשיכים לעבוד.
- טבלאות בשימוש: ארבעת זוגות טבלאות המיפוי והטקסטים שבסעיף 6, ובנוסף `tbl_signs` (שמות המזלות;
  משמשת רק את עמוד הבדיקה `/signs`).
- החישובים עצמם **אינם** משתמשים במסד הנתונים. רק טקסטי התחזית מגיעים ממנו.
- פרטי המבנה: `docs/database-schema.md`.

## 8. לוגיקת תחזיות חינמיות לעומת בתשלום ❌

**לא מיושם.** כל היכולות וכל התחזיות זמינות לכולם ללא התחברות. אין חשבונות משתמש, מנויים, טיפול
בתשלומים, הגבלות שימוש או טקסטי "פרימיום". אין טבלאות כאלה במסד הנתונים.

**קובצי מדיה:** התיקייה `media/` מוגשת בכתובת `/media/…`. עמוד הנחיתה משתמש בסרטון הפתיחה, בתמונה של
ירון ובסרטוני הדוגמה (סעיף 5.6). קובצי האודיו לדוגמה אינם בשימוש.

## 9. כללים עסקיים, בדיקות תקינות וחריגים

**בדיקות תקינות ✅**

| כלל | היכן | הודעה |
|---|---|---|
| יש לבחור מקום מתוך רשימת החיפוש | כל העמודים | "Please select a place from the autocomplete list." / "Please select a location from the list." |
| תאריכים בפורמט `dd/mm/yyyy` | כל העמודים | "Please enter dates as dd/mm/yyyy." |
| תאריך הפרוגרסיה לא לפני הלידה | טרשיארי, סקנדרית | "Progression date must be after birth date" |
| כל שדות החובה קיימים | כל החישובים | "Missing fields: …" |
| חייב להימצא אזור זמן למיקום | כל החישובים | "Could not determine timezone for this location" |
| תחזיות דורשות תאריך לידה | ירח בטרנזיט | כפתורי התחזית מושבתים: "Enter a date of birth to get forecasts" |
| מזל תקין; מעלה 0–29 | שליפות תחזית | "Unknown sign" / "Degree must be between 0 and 29" |
| בית 1–12; קבוצה 1 או 2 | תחזית ירח בטרנזיט | "House must be between 1 and 12" / "Forecast group must be 1 or 2" |
| המיקום הנוכחי אינו זמין | ירח בטרנזיט | "Current location unavailable — please type a location." |
| תאריך לידה חובה, `dd/mm/yyyy`, תאריך אמיתי, מ-1900, לא בעתיד | עמוד הנחיתה | "יש להזין תאריך לידה." / "יש להזין תאריך תקין…" / "תאריך הלידה לא יכול להיות בעתיד." (בשרת: "תאריך הלידה אינו תקין.") |
| מייל חובה, בפורמט תקין | עמוד הנחיתה | "יש להזין כתובת מייל." / "יש להזין כתובת מייל תקינה…" (בשרת: "כתובת המייל אינה תקינה.") |

**כללים עסקיים ✅**

- שעת הפרוגרסיה קבועה ל-**12:00** בשעון המקומי בשני עמודי הפרוגרסיה.
- בעמוד הראשי, תאריכי המפה המתקדמת מוצגים ב-UTC (זמן הלידה מוצג גם בשעון מקומי וגם ב-UTC);
  כותרת המשנה אומרת "All times in UTC via birth-place timezone".
- ירח בטרנזיט מציג תמיד **12 תקופות**, החל מהתקופה שמכילה את הזמן שנבחר. התקופה הראשונה עשויה
  להתחיל בעבר.

**נושאים שדורשים הבהרה ❓**

1. **"Journaly"**: יכולת כזו לא קיימת; האם הכוונה לירח בטרנזיט (תחזיות יומיות)? (5.4)
2. **אורך החודש ב-Tertiary I**: נעשה שימוש בחודש סידרי (27.32 ימים); האם זו הכוונה? (5.1)
3. **ההגדרה של Tertiary II**: נעשה שימוש בנוסחת הפרוגרסיה המינורית; האם זו הכוונה? (5.2)
4. **פרוגרסיה סקנדרית ו-"PCA"**: למה התייחס "PCA"? (5.3)
5. **שעת פרוגרסיה קבועה ב-12:00**: האם המשתמשים צריכים להיות מסוגלים להזין אותה? היא יכולה להזיז את
   הירח המתקדם בעד כ-0.25° ב-Tertiary I וכ-0.5° ב-Tertiary II.
6. **תקופות עתידיות בירח בטרנזיט** משתמשות תמיד בקבוצת תחזית 1. מסד הנתונים מאפשר קבוצות עד 10,
   אבל קיימות רק 1–2. האם מתוכננות קבוצות נוספות?
7. **מזל השמש לפי תאריך לידה** נלקח ב-12:00 UTC. מי שנולד ביום שבו השמש מחליפה מזל עשוי לקבל את
   המזל הסמוך. האם לבקש גם שעת לידה?
8. **מעלה שלמה בחיתוך** משמשת בכל שליפות התחזית, ולא עיגול. יש לאשר.
9. **כתובות מייל בעמוד הנחיתה** נבדקות אך אינן נשמרות ואינן נשלחות לשום מקום. לאן הן צריכות להגיע
   (טבלה חדשה במסד הנתונים, שירות דיוור)? האם נדרשת תיבת סימון להסכמה לדיוור?
10. **סרטוני התחזית בעמוד הנחיתה** הם סרטון דוגמה אקראי. איך כל תחזית (בית + קבוצה) תמופה לסרטון
    משלה, והאם יהיו לסרטונים כתוביות?

</div>
