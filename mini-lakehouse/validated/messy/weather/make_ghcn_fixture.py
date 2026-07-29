"""Spec-faithful GHCN-Daily by_station CSV fixture (NOAA is unreachable from this sandbox).
Format per NOAA GHCND documentation, no header row:
  ID, YYYYMMDD, ELEMENT, VALUE, M-FLAG, Q-FLAG, S-FLAG, OBS-TIME
The real file for NYC Central Park is:
  https://www.ncei.noaa.gov/pub/data/ghcn/daily/by_station/USW00094728.csv
"""
import random, datetime, pathlib
random.seed(5)
ST = "USW00094728"
rows = []
d = datetime.date(2025, 1, 1)
while d < datetime.date(2025, 2, 1):
    ymd = d.strftime("%Y%m%d")
    tmax = random.randint(-30, 110)          # tenths of degrees C
    tmin = tmax - random.randint(20, 70)
    rows.append(f"{ST},{ymd},TMAX,{tmax},,,W,2400")
    rows.append(f"{ST},{ymd},TMIN,{tmin},,,W,2400")
    wet = random.random() < 0.35
    prcp = random.randint(5, 320) if wet else 0     # TENTHS OF MM -- the scaling trap
    rows.append(f"{ST},{ymd},PRCP,{prcp},,,W,2400")
    if wet and tmax < 10:
        rows.append(f"{ST},{ymd},SNOW,{random.randint(10,180)},,,W,")   # SNOW is mm, not tenths
    if random.random() < 0.9:
        rows.append(f"{ST},{ymd},AWND,{random.randint(10,90)},,,W,")    # tenths of m/s
    # a value that FAILED quality control: Q-FLAG non-blank. Must be excluded.
    if random.random() < 0.06:
        rows.append(f"{ST},{ymd},TMAX,9999,,G,W,2400")
    # an element most stations don't have, present sporadically -> sparse pivot
    if random.random() < 0.1:
        rows.append(f"{ST},{ymd},WESD,{random.randint(0,50)},,,W,")
    d += datetime.timedelta(days=1)
random.shuffle(rows)          # real file is not date-ordered per element
pathlib.Path("USW00094728.csv").write_text("\n".join(rows) + "\n")
print(f"{len(rows)} element-days written (long/narrow: one row PER ELEMENT per day)")
print("sample:"); print("\n".join(rows[:5]))
