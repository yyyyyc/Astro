from flask import Flask, render_template, request, jsonify, send_from_directory
import ephem
import math
from datetime import datetime, timedelta
import requests
from timezonefinder import TimezoneFinder
import pytz
import os
import json
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv(override=True)

app = Flask(__name__)

ZODIAC_SIGNS = [
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
]

# Glyph symbols for display
ZODIAC_SYMBOLS = {
    "Aries": "♈", "Taurus": "♉", "Gemini": "♊", "Cancer": "♋",
    "Leo": "♌", "Virgo": "♍", "Libra": "♎", "Scorpio": "♏",
    "Sagittarius": "♐", "Capricorn": "♑", "Aquarius": "♒", "Pisces": "♓",
}

PLANET_SYMBOLS = {
    "Moon": "☽",
}

PLANETS = {
    "Moon": ephem.Moon,
}

# Tertiary progression: one day after birth = one sidereal month of life
SIDEREAL_MONTH_DAYS = 27.321661   # Tertiary I
# Minor progression: one sidereal month after birth = one year of life (converse of Tertiary I)
TROPICAL_YEAR_DAYS  = 365.242190  # Tertiary II


def ecliptic_longitude(planet_class, ephem_date):
    body = planet_class()
    body.compute(ephem_date)
    ecl = ephem.Ecliptic(body, epoch=ephem_date)
    return math.degrees(ecl.lon) % 360


def longitude_to_zodiac(lon_deg):
    sign_index = int(lon_deg / 30) % 12
    degree_in_sign = lon_deg % 30
    degrees = int(degree_in_sign)
    minutes = int((degree_in_sign - degrees) * 60)
    seconds = int(((degree_in_sign - degrees) * 60 - minutes) * 60)
    sign = ZODIAC_SIGNS[sign_index]
    return sign, degrees, minutes, seconds


def to_ephem_date(dt_utc):
    return ephem.Date(dt_utc.strftime("%Y/%m/%d %H:%M:%S"))


def localize(local_tz, naive_dt):
    """Attach local_tz to a naive datetime, resolving DST gaps/overlaps the same way /calculate does."""
    try:
        return local_tz.localize(naive_dt, is_dst=None)
    except pytz.exceptions.AmbiguousTimeError:
        return local_tz.localize(naive_dt, is_dst=False)
    except pytz.exceptions.NonExistentTimeError:
        return local_tz.localize(naive_dt + timedelta(hours=1), is_dst=True)


# ── Moon of Transit ──────────────────────────────────────────────────────────
# The Moon moves at most ~15.4°/day, so a 3-hour step (< 2°) can never skip a 30° sign.
MOON_SEARCH_STEP = timedelta(hours=3)
HOUSE_ORDINALS = ["1st", "2nd", "3rd", "4th", "5th", "6th", "7th", "8th", "9th", "10th", "11th", "12th"]


def moon_sign_index(dt_utc):
    return int(ecliptic_longitude(ephem.Moon, to_ephem_date(dt_utc)) // 30) % 12


def moon_sign_boundary(dt_utc, sign_idx, forward=True):
    """Find when the Moon leaves (forward) or entered (backward) sign_idx, to within one second."""
    step = MOON_SEARCH_STEP if forward else -MOON_SEARCH_STEP
    inside, outside = dt_utc, dt_utc + step
    while moon_sign_index(outside) == sign_idx:
        inside, outside = outside, outside + step
    while abs((outside - inside).total_seconds()) > 1:
        mid = inside + (outside - inside) / 2
        if moon_sign_index(mid) == sign_idx:
            inside = mid
        else:
            outside = mid
    # Forward: first moment in the next sign. Backward: first moment in this sign.
    return outside if forward else inside


def resolve_timezone(lat, lon):
    tz_name = TimezoneFinder().timezone_at(lat=lat, lng=lon)
    if not tz_name:
        raise ValueError("Could not determine timezone for this location")
    return pytz.timezone(tz_name)


def moon_of_transit(lat, lon, local_naive):
    """
    Moon of Transit: the tropical sign the Moon occupies at the given location and local date/time.
    Returns {"sign", "start", "end"}, with start/end as timezone-aware datetimes in the location's timezone.
    """
    local_tz = resolve_timezone(lat, lon)
    dt_utc = localize(local_tz, local_naive).astimezone(pytz.utc)
    sign_idx = moon_sign_index(dt_utc)
    return {
        "sign": ZODIAC_SIGNS[sign_idx],
        "start": moon_sign_boundary(dt_utc, sign_idx, forward=False).astimezone(local_tz),
        "end": moon_sign_boundary(dt_utc, sign_idx, forward=True).astimezone(local_tz),
    }


def moon_transit_table(lat, lon, local_naive, count=12):
    """The current Moon of Transit followed by the next count-1 signs, each with local start/end times."""
    current = moon_of_transit(lat, lon, local_naive)
    local_tz = pytz.timezone(current["start"].tzinfo.zone)
    periods = [current]
    while len(periods) < count:
        start = periods[-1]["end"]
        sign_idx = (ZODIAC_SIGNS.index(periods[-1]["sign"]) + 1) % 12
        end = moon_sign_boundary(start.astimezone(pytz.utc), sign_idx, forward=True)
        periods.append({"sign": ZODIAC_SIGNS[sign_idx], "start": start, "end": end.astimezone(local_tz)})
    return periods


def sun_sign_on(date_obj):
    """Natal Sun sign for a date of birth; noon UTC is used since no birth time is given."""
    noon_utc = pytz.utc.localize(datetime(date_obj.year, date_obj.month, date_obj.day, 12))
    sign, _, _, _ = longitude_to_zodiac(ecliptic_longitude(ephem.Sun, to_ephem_date(noon_utc)))
    return sign


# ── Secondary Progression ────────────────────────────────────────────────────
def secondary_progression(lat, lon, birth_naive, target_naive):
    """
    Secondary progression (day-for-a-year): each tropical year of life after birth equals one day
    of ephemeris time after birth. Returns the progressed Moon's sign and degree for target_naive.
    birth_naive and target_naive are local times at the birth location.
    """
    local_tz = resolve_timezone(lat, lon)
    birth_local = localize(local_tz, birth_naive)
    birth_utc = birth_local.astimezone(pytz.utc)
    target_utc = localize(local_tz, target_naive).astimezone(pytz.utc)

    elapsed_days = (target_utc - birth_utc).total_seconds() / 86400.0
    if elapsed_days < 0:
        raise ValueError("Progression date must be after birth date")

    age_years = elapsed_days / TROPICAL_YEAR_DAYS
    progressed_utc = birth_utc + timedelta(days=age_years)
    lon_deg = ecliptic_longitude(ephem.Moon, to_ephem_date(progressed_utc))
    sign, deg, mins, secs = longitude_to_zodiac(lon_deg)
    return {
        "timezone": local_tz.zone,
        "birth_local": birth_local,
        "birth_utc": birth_utc,
        "age_years": age_years,
        "progressed_utc": progressed_utc,
        "longitude": lon_deg,
        "sign": sign,
        "degrees": deg,
        "minutes": mins,
        "seconds": secs,
    }


VERSION_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "version.json")


def read_version():
    """Version and release date-time from version.json (bumped by bump_version.py before each push)."""
    try:
        with open(VERSION_FILE, encoding="utf-8") as f:
            data = json.load(f)
        released = datetime.fromisoformat(data["datetime"]).strftime("%d/%m/%Y %H:%M")
        return {"version": data["version"], "datetime": released}
    except (OSError, ValueError, KeyError):
        return None


def get_engine():
    db_url = os.environ.get("ASTRO_DB_URL")
    if not db_url:
        return None
    if db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "postgresql+psycopg://", 1)
    elif db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql+psycopg://", 1)
    return create_engine(db_url)


@app.route("/")
def index():
    return render_template("index.html", app_version=read_version())


@app.route("/favicon.ico")
def favicon():
    return send_from_directory(app.static_folder, "favicon.ico", mimetype="image/vnd.microsoft.icon")


@app.route("/geocode")
def geocode():
    query = request.args.get("q", "").strip()
    if len(query) < 2:
        return jsonify([])
    try:
        resp = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": query, "format": "json", "limit": 6, "addressdetails": 1, "accept-language": "en"},
            headers={"User-Agent": "TertiaryProgressionApp/1.0", "Accept-Language": "en"},
            timeout=5,
        )
        data = resp.json()
        results = [
            {
                "name": item["display_name"],
                "lat": float(item["lat"]),
                "lon": float(item["lon"]),
            }
            for item in data
        ]
        return jsonify(results)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/reverse-geocode")
def reverse_geocode():
    try:
        lat = float(request.args.get("lat"))
        lon = float(request.args.get("lon"))
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid coordinates"}), 400
    try:
        resp = requests.get(
            "https://nominatim.openstreetmap.org/reverse",
            params={"lat": lat, "lon": lon, "format": "json", "zoom": 10, "addressdetails": 1, "accept-language": "en"},
            headers={"User-Agent": "TertiaryProgressionApp/1.0", "Accept-Language": "en"},
            timeout=5,
        )
        item = resp.json()
        if "error" in item:
            return jsonify({"error": item["error"]}), 404
        addr = item.get("address", {})
        city = addr.get("city") or addr.get("town") or addr.get("village") or addr.get("municipality") or addr.get("county")
        parts = [p for p in (city, addr.get("state"), addr.get("country")) if p]
        return jsonify({
            "name": ", ".join(parts) if parts else item["display_name"],
            "lat": float(item["lat"]),
            "lon": float(item["lon"]),
        })
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/sun-sign")
def sun_sign_lookup():
    try:
        date_obj = datetime.strptime(request.args.get("date", ""), "%Y-%m-%d").date()
    except ValueError:
        return jsonify({"error": "Invalid date"}), 400
    sign = sun_sign_on(date_obj)
    return jsonify({"sign": sign, "symbol": ZODIAC_SYMBOLS[sign]})


@app.route("/timezone")
def get_timezone():
    try:
        lat = float(request.args.get("lat"))
        lon = float(request.args.get("lon"))
        tf = TimezoneFinder()
        tz_name = tf.timezone_at(lat=lat, lng=lon)
        return jsonify({"timezone": tz_name or "UTC"})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400


@app.route("/moon-transit")
def moon_transit_page():
    return render_template("moon_transit.html")


@app.route("/moon-transit/calculate", methods=["POST"])
def moon_transit_calculate():
    data = request.get_json() or {}

    required = ["lat", "lon", "date", "time"]
    missing = [f for f in required if f not in data or str(data[f]).strip() == ""]
    if missing:
        return jsonify({"error": f"Missing fields: {', '.join(missing)}"}), 400

    try:
        lat = float(data["lat"])
        lon = float(data["lon"])
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid coordinates"}), 400

    try:
        local_naive = datetime.strptime(f"{data['date']} {data['time']}", "%Y-%m-%d %H:%M")
    except ValueError:
        return jsonify({"error": "Invalid date or time"}), 400

    sun_sign = None
    if str(data.get("dob") or "").strip():
        try:
            sun_sign = sun_sign_on(datetime.strptime(data["dob"], "%Y-%m-%d").date())
        except ValueError:
            return jsonify({"error": "Invalid date of birth"}), 400

    try:
        periods = moon_transit_table(lat, lon, local_naive)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    def fmt(dt):
        return dt.strftime("%a %d/%m/%Y %H:%M")

    selected = localize(pytz.timezone(periods[0]["start"].tzinfo.zone), local_naive)

    rows = []
    for p in periods:
        midpoint = p["start"] + (p["end"] - p["start"]) / 2
        row = {
            "sign": p["sign"],
            "sign_symbol": ZODIAC_SYMBOLS[p["sign"]],
            "start": fmt(p["start"]),
            "end": fmt(p["end"]),
            "midpoint": fmt(midpoint.astimezone(p["start"].tzinfo)),
            "duration_hours": round((p["end"] - p["start"]).total_seconds() / 3600, 1),
            # 1 = selected date/time falls in the first half of this sign's time frame, 2 = second half
            "forecast_group": 1 if selected < midpoint else 2,
        }
        if sun_sign:
            house = (ZODIAC_SIGNS.index(p["sign"]) - ZODIAC_SIGNS.index(sun_sign)) % 12
            row["house"] = HOUSE_ORDINALS[house]
            row["house_number"] = house + 1
        rows.append(row)

    current = periods[0]
    return jsonify(
        {
            "timezone": str(current["start"].tzinfo.zone),
            "selected_local": local_naive.strftime("%a %d/%m/%Y %H:%M"),
            "current": rows[0],
            "sun_sign": sun_sign,
            "sun_sign_symbol": ZODIAC_SYMBOLS.get(sun_sign, ""),
            "periods": rows,
        }
    )


@app.route("/secondary-progression")
def secondary_progression_page():
    return render_template("secondary_progression.html")


@app.route("/secondary-progression/calculate", methods=["POST"])
def secondary_progression_calculate():
    data = request.get_json() or {}

    required = ["lat", "lon", "birth_date", "birth_time", "progression_date"]
    missing = [f for f in required if f not in data or str(data[f]).strip() == ""]
    if missing:
        return jsonify({"error": f"Missing fields: {', '.join(missing)}"}), 400

    try:
        lat = float(data["lat"])
        lon = float(data["lon"])
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid coordinates"}), 400

    prog_time_str = data.get("progression_time", "12:00") or "12:00"
    try:
        birth_naive = datetime.strptime(f"{data['birth_date']} {data['birth_time']}", "%Y-%m-%d %H:%M")
        target_naive = datetime.strptime(f"{data['progression_date']} {prog_time_str}", "%Y-%m-%d %H:%M")
    except ValueError:
        return jsonify({"error": "Invalid date or time"}), 400

    try:
        p = secondary_progression(lat, lon, birth_naive, target_naive)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    return jsonify(
        {
            "timezone": p["timezone"],
            "birth_local": p["birth_local"].strftime("%Y-%m-%d %H:%M %Z"),
            "birth_utc": p["birth_utc"].strftime("%Y-%m-%d %H:%M UTC"),
            "progression_date": data["progression_date"],
            "age_years": round(p["age_years"], 4),
            "progressed_chart_date_utc": p["progressed_utc"].strftime("%Y-%m-%d %H:%M:%S UTC"),
            "moon": {
                "planet": "Moon",
                "symbol": PLANET_SYMBOLS["Moon"],
                "longitude": round(p["longitude"], 4),
                "sign": p["sign"],
                "sign_symbol": ZODIAC_SYMBOLS[p["sign"]],
                "degrees": p["degrees"],
                "minutes": p["minutes"],
                "seconds": p["seconds"],
            },
        }
    )


@app.route("/calculate", methods=["POST"])
def calculate():
    data = request.get_json()

    required = ["lat", "lon", "birth_date", "birth_time", "progression_date"]
    missing = [f for f in required if f not in data or str(data[f]).strip() == ""]
    if missing:
        return jsonify({"error": f"Missing fields: {', '.join(missing)}"}), 400

    try:
        lat = float(data["lat"])
        lon = float(data["lon"])
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid coordinates"}), 400

    tf = TimezoneFinder()
    tz_name = tf.timezone_at(lat=lat, lng=lon)
    if not tz_name:
        return jsonify({"error": "Could not determine timezone for this location"}), 400

    local_tz = pytz.timezone(tz_name)

    try:
        birth_naive = datetime.strptime(
            f"{data['birth_date']} {data['birth_time']}", "%Y-%m-%d %H:%M"
        )
        birth_local = local_tz.localize(birth_naive, is_dst=None)
    except pytz.exceptions.AmbiguousTimeError:
        # Ambiguous due to DST — ask client to specify; default to DST=False (standard time)
        birth_naive = datetime.strptime(
            f"{data['birth_date']} {data['birth_time']}", "%Y-%m-%d %H:%M"
        )
        birth_local = local_tz.localize(birth_naive, is_dst=False)
    except pytz.exceptions.NonExistentTimeError:
        # Clocks skipped this hour (spring forward) — shift forward
        birth_naive = datetime.strptime(
            f"{data['birth_date']} {data['birth_time']}", "%Y-%m-%d %H:%M"
        )
        birth_local = local_tz.localize(birth_naive + timedelta(hours=1), is_dst=True)

    birth_utc = birth_local.astimezone(pytz.utc)

    prog_time_str = data.get("progression_time", "12:00") or "12:00"
    try:
        prog_naive = datetime.strptime(
            f"{data['progression_date']} {prog_time_str}", "%Y-%m-%d %H:%M"
        )
        prog_local = local_tz.localize(prog_naive, is_dst=None)
    except pytz.exceptions.AmbiguousTimeError:
        prog_naive = datetime.strptime(
            f"{data['progression_date']} {prog_time_str}", "%Y-%m-%d %H:%M"
        )
        prog_local = local_tz.localize(prog_naive, is_dst=False)
    except pytz.exceptions.NonExistentTimeError:
        prog_naive = datetime.strptime(
            f"{data['progression_date']} {prog_time_str}", "%Y-%m-%d %H:%M"
        )
        prog_local = local_tz.localize(prog_naive + timedelta(hours=1), is_dst=True)

    prog_utc = prog_local.astimezone(pytz.utc)

    elapsed_days = (prog_utc - birth_utc).total_seconds() / 86400.0
    if elapsed_days < 0:
        return jsonify({"error": "Progression date must be after birth date"}), 400

    def compute_planets(progressed_utc):
        ephem_date = to_ephem_date(progressed_utc)
        planets_out = []
        for name, planet_class in PLANETS.items():
            try:
                lon = ecliptic_longitude(planet_class, ephem_date)
                sign, deg, mins, secs = longitude_to_zodiac(lon)
                planets_out.append(
                    {
                        "planet": name,
                        "symbol": PLANET_SYMBOLS.get(name, ""),
                        "longitude": round(lon, 4),
                        "sign": sign,
                        "sign_symbol": ZODIAC_SYMBOLS.get(sign, ""),
                        "degrees": deg,
                        "minutes": mins,
                        "seconds": secs,
                        "position": f"{deg}° {mins:02d}' {secs:02d}\" {sign}",
                    }
                )
            except Exception as exc:
                planets_out.append({"planet": name, "error": str(exc)})
        return planets_out

    # Tertiary I: 1 sidereal month of life = 1 day after birth
    t1_offset = elapsed_days / SIDEREAL_MONTH_DAYS
    t1_utc = birth_utc + timedelta(days=t1_offset)

    # Tertiary II (Minor progression): 1 year of life = 1 sidereal month after birth
    age_years = elapsed_days / TROPICAL_YEAR_DAYS
    t2_offset = age_years * SIDEREAL_MONTH_DAYS
    t2_utc = birth_utc + timedelta(days=t2_offset)

    # UTC offset at birth time for display
    utc_offset = birth_local.utcoffset()
    offset_hours = int(utc_offset.total_seconds() // 3600)
    offset_mins = int((utc_offset.total_seconds() % 3600) // 60)
    offset_str = f"UTC{offset_hours:+03d}:{offset_mins:02d}"

    return jsonify(
        {
            "timezone": tz_name,
            "utc_offset_at_birth": offset_str,
            "birth_local": birth_local.strftime("%Y-%m-%d %H:%M %Z"),
            "birth_utc": birth_utc.strftime("%Y-%m-%d %H:%M UTC"),
            "progression_date": data["progression_date"],
            "elapsed_days": round(elapsed_days, 4),
            "tertiary1": {
                "label": "Tertiary I (Sidereal Month)",
                "offset_days": round(t1_offset, 6),
                "progressed_chart_date_utc": t1_utc.strftime("%Y-%m-%d %H:%M:%S UTC"),
                "planets": compute_planets(t1_utc),
            },
            "tertiary2": {
                "label": "Tertiary II (Minor Progression)",
                "offset_days": round(t2_offset, 6),
                "progressed_chart_date_utc": t2_utc.strftime("%Y-%m-%d %H:%M:%S UTC"),
                "planets": compute_planets(t2_utc),
            },
        }
    )


def parse_sign_degree(args):
    sign_name = args.get("sign", "").strip()
    degree_raw = args.get("degree")

    if sign_name not in ZODIAC_SIGNS:
        return None, None, (jsonify({"error": "Unknown sign"}), 400)
    try:
        degree = int(degree_raw)
    except (TypeError, ValueError):
        return None, None, (jsonify({"error": "Invalid degree"}), 400)
    if not 0 <= degree <= 29:
        return None, None, (jsonify({"error": "Degree must be between 0 and 29"}), 400)

    sign_id = ZODIAC_SIGNS.index(sign_name) + 1
    return sign_name, sign_id, degree


@app.route("/forecast/tertiary1")
def tertiary1_forecast():
    sign_name, sign_id, degree = parse_sign_degree(request.args)
    if sign_name is None:
        return degree  # (response, status) error tuple

    engine = get_engine()
    if engine is None:
        return jsonify({"error": "ASTRO_DB_URL environment variable is not set."}), 500

    try:
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT t.forecast_text
                    FROM tbl_tertiary1_forecasts f
                    JOIN tbl_tertiary1_forecasts_texts t ON t.forecast_id = f.forecast_id
                    WHERE f.sign_id = :sign_id AND f.degree = :degree
                    """
                ),
                {"sign_id": sign_id, "degree": degree},
            ).fetchone()
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500

    if row is None:
        return jsonify({"error": "No forecast found for this sign and degree."}), 404

    return jsonify(
        {
            "sign": sign_name,
            "degree": degree,
            "forecast_text": row.forecast_text,
        }
    )


@app.route("/forecast/tertiary2")
def tertiary2_forecast():
    sign_name, sign_id, degree = parse_sign_degree(request.args)
    if sign_name is None:
        return degree  # (response, status) error tuple

    engine = get_engine()
    if engine is None:
        return jsonify({"error": "ASTRO_DB_URL environment variable is not set."}), 500

    try:
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT f.tertiary, t.forecast_text
                    FROM tbl_tertiary2_forecasts f
                    JOIN tbl_tertiary2_forecasts_texts t ON t.forecast_id = f.forecast_id
                    WHERE f.sign_id = :sign_id AND f.degree = :degree
                    """
                ),
                {"sign_id": sign_id, "degree": degree},
            ).fetchone()
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500

    if row is None:
        return jsonify({"error": "No forecast found for this sign and degree."}), 404

    return jsonify(
        {
            "sign": sign_name,
            "degree": degree,
            "tertiary": row.tertiary,
            "forecast_text": row.forecast_text,
        }
    )


@app.route("/forecast/secondary")
def secondary_forecast():
    sign_name, sign_id, degree = parse_sign_degree(request.args)
    if sign_name is None:
        return degree  # (response, status) error tuple

    engine = get_engine()
    if engine is None:
        return jsonify({"error": "ASTRO_DB_URL environment variable is not set."}), 500

    try:
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT t.forecast_text
                    FROM tbl_secondary_progression_forecasts f
                    JOIN tbl_secondary_progression_forecasts_texts t ON t.forecast_id = f.forecast_id
                    WHERE f.sign_id = :sign_id AND f.degree = :degree
                    """
                ),
                {"sign_id": sign_id, "degree": degree},
            ).fetchone()
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500

    if row is None or not row.forecast_text:
        return jsonify({"error": "No forecast found for this sign and degree."}), 404

    return jsonify(
        {
            "sign": sign_name,
            "degree": degree,
            "forecast_text": row.forecast_text,
        }
    )


@app.route("/forecast/moon-transit")
def moon_transit_forecast():
    try:
        house = int(request.args.get("house"))
        group = int(request.args.get("group"))
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid house or forecast group"}), 400
    if not 1 <= house <= 12:
        return jsonify({"error": "House must be between 1 and 12"}), 400
    if group not in (1, 2):
        return jsonify({"error": "Forecast group must be 1 or 2"}), 400

    engine = get_engine()
    if engine is None:
        return jsonify({"error": "ASTRO_DB_URL environment variable is not set."}), 500

    try:
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT t.forecast_text
                    FROM tbl_moon_of_transit_daily_forecasts f
                    JOIN tbl_moon_of_transit_daily_forecasts_texts t ON t.forecast_id = f.forecast_id
                    WHERE f.moon_location = :house AND f.forecast_group = :group
                    """
                ),
                {"house": house, "group": group},
            ).fetchone()
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500

    if row is None or not row.forecast_text:
        return jsonify({"error": "No forecast found for this house."}), 404

    return jsonify(
        {
            "house": HOUSE_ORDINALS[house - 1],
            "forecast_group": group,
            "forecast_text": row.forecast_text,
        }
    )


@app.route("/signs")
def signs():
    engine = get_engine()
    if engine is None:
        return "<h2>ASTRO_DB_URL environment variable is not set.</h2>", 500
    try:
        with engine.connect() as conn:
            rows = conn.execute(text("SELECT id, sign_id, sign_name FROM tbl_signs ORDER BY id")).fetchall()
    except Exception as exc:
        return f"<h2>Database error:</h2><pre>{exc}</pre>", 500

    rows_html = "".join(
        f"<tr><td>{r.id}</td><td>{r.sign_id}</td><td>{r.sign_name}</td></tr>"
        for r in rows
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <title>Zodiac Signs</title>
  <link rel="icon" href="/static/favicon.svg" type="image/svg+xml"/>
  <style>
    body {{ font-family: 'Segoe UI', system-ui, sans-serif; background:#0d0d1a; color:#e2e0ff; padding:2rem; }}
    h1 {{ color:#a78bfa; margin-bottom:1.5rem; }}
    table {{ border-collapse:collapse; width:100%; max-width:600px; }}
    th {{ background:#1a1a38; color:#8884aa; text-transform:uppercase; font-size:0.75rem;
          letter-spacing:0.08em; padding:0.65rem 1rem; text-align:left;
          border-bottom:2px solid #2e2e5e; }}
    td {{ padding:0.7rem 1rem; border-bottom:1px solid #2e2e5e; font-size:0.92rem; }}
    tr:hover td {{ background:#1a1a38; }}
    a {{ color:#7c6fcd; text-decoration:none; }}
    a:hover {{ color:#a78bfa; }}
  </style>
</head>
<body>
  <h1>&#9890; Zodiac Signs</h1>
  <table>
    <thead><tr><th>ID</th><th>Sign ID</th><th>Sign Name</th></tr></thead>
    <tbody>{rows_html}</tbody>
  </table>
  <p style="margin-top:1.5rem"><a href="/">&#8592; Back to calculator</a></p>
</body>
</html>"""


if __name__ == "__main__":
    app.run(debug=True)
