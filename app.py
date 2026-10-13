from flask import Flask, render_template, request, jsonify
import ephem
import math
from datetime import datetime, timedelta
import requests
from timezonefinder import TimezoneFinder
import pytz
import os
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
    return render_template("index.html")


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
