"""Three source shapes that are NOT columnar, with the breakage each really exhibits.
Purpose: prove bronze's contract is provenance + fidelity, not a file format.
"""
import json, pathlib, random
random.seed(11)
R = pathlib.Path("raw")

# ---------- 1. DELIMITED TEXT: the taxi zone lookup, broken the way real CSVs break ----------
rows = [
    'LocationID,Borough,Zone,service_zone',
    '1,EWR,Newark Airport,EWR',
    '2,Queens,Jamaica Bay,Boro Zone',
    '3,Bronx,"Allerton/Pelham Gardens",Boro Zone',
    '4,Manhattan,Alphabet City,Yellow Zone',
    '5,Staten Island,Arden Heights,Boro Zone',
    '6,Staten Island,"Arrochar/Fort Wadsworth",Boro Zone',
    '7,Queens,Astoria,Boro Zone',
    # -- embedded comma inside quotes
    '12,Manhattan,"Battery Park, Lower",Yellow Zone',
    # -- embedded newline inside quotes (the classic CSV killer)
    '13,Manhattan,"Battery Park\nCity",Yellow Zone',
    # -- cp1252 smart quote, not utf-8
    '14,Brooklyn,Bay Ridge\x92s Edge,Boro Zone',
    # -- thousands separator makes a numeric column non-numeric
    '1,015,Queens,Long Island City,Boro Zone',
    # -- Excel mangled an ID into a date
    'Mar-05,Manhattan,Midtown Center,Yellow Zone',
    # -- ragged row: missing trailing field
    '16,Queens,Bayside',
    # -- entirely blank line
    '',
    # -- sentinel values for null
    '17,Brooklyn,N/A,NULL',
]
R.joinpath("taxi_zone_lookup.csv").write_bytes("\n".join(rows).encode("cp1252", errors="replace"))

# ---------- 2. APPEND-ONLY SEMI-STRUCTURED LOG: JSONL, sparse and drifting ----------
lines = []
for i in range(400):
    rec = {"ts": f"2025-01-{random.randint(1,28):02d}T{random.randint(0,23):02d}:{random.randint(0,59):02d}:00Z",
           "level": random.choice(["INFO","INFO","INFO","WARN","ERROR"]),
           "svc": random.choice(["dispatch","pricing","match"]),
           "msg": random.choice(["trip requested","fare quoted","driver matched","timeout"]),
           "trip_id": random.randint(100000, 999999)}
    if random.random() < 0.35:                      # sparse nested object
        rec["ctx"] = {"lat": round(40.6+random.random()*0.2,5), "lon": round(-74.0+random.random()*0.2,5)}
    if random.random() < 0.15:                      # key that appears only later ("schema drift")
        rec["surge_multiplier"] = round(1+random.random()*2, 2)
    if random.random() < 0.05:                      # type instability: same key, different type
        rec["trip_id"] = str(rec["trip_id"])
    lines.append(json.dumps(rec))
lines.insert(120, '{"ts":"2025-01-09T11:00:00Z","level":"ERROR","svc":"pricing"')   # truncated/corrupt line
lines.insert(300, 'not json at all -- a stray stderr line got into the log')        # non-JSON line
R.joinpath("app-2025-01.jsonl").write_text("\n".join(lines), encoding="utf-8")

# ---------- 3. FREE TEXT: driver/rider reviews. The row IS the payload. ----------
bodies = [
 "Driver was great, took the Willy B instead of the tunnel and saved me 15 minutes.",
 "car smelled like smoke\nand the AC was broken. never again",
 "Excelente servicio, muy amable el conductor.",   # not English
 "4/5 — clean car, but he took the BQE at 5pm?!",
 "",                                                # empty review
 "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" * 40,          # runaway length
 "Charged me $87 for a $30 ride. Disputing this.",
 "👍👍👍",                                            # emoji-only
 "Fine.",
]
recs = []
for i in range(300):
    recs.append({"review_id": 90000+i,
                 "trip_id": random.randint(100000,999999),
                 "stars": random.choice([1,2,3,4,5,5,5,None]),
                 "submitted": random.choice(["2025-01-14","01/14/2025","14-01-2025"]),  # 3 date formats
                 "body": random.choice(bodies)})
R.joinpath("reviews-2025-01.json").write_text(json.dumps(recs, ensure_ascii=False, indent=1), encoding="utf-8")

for p in sorted(R.iterdir()):
    print(f"{p.name:28} {p.stat().st_size:>8,} bytes")
