# Data sources, attribution, and licensing

**This repository contains no data.** `scripts/01_download_data.sh` fetches everything from
the original publishers at runtime. That is deliberate: there is no redistribution to reason
about, and data files do not belong in version control regardless.

## NOAA GHCN-Daily — formal citation required

NOAA asks users to cite both the dataset and the overview paper. This is not optional.

> Menne, M.J., I. Durre, B. Korzeniewski, S. McNeill, K. Thomas, X. Yin, S. Anthony, R. Ray,
> R.S. Vose, B.E. Gleason, and T.G. Houston (2012): *Global Historical Climatology Network -
> Daily (GHCN-Daily), Version 3*. [subset used: station USW00094728, NY City Central Park].
> NOAA National Climatic Data Center. doi:10.7289/V5D21VHZ. [accessed: DATE]

> Menne, M.J., I. Durre, R.S. Vose, B.E. Gleason, and T.G. Houston, 2012: An overview of the
> Global Historical Climatology Network-Daily Database. *Journal of Atmospheric and Oceanic
> Technology*, 29, 897–910. doi:10.1175/JTECH-D-11-00103.1

Station: `USW00094728` (NY City Central Park).
File: `https://www.ncei.noaa.gov/pub/data/ghcn/daily/by_station/USW00094728.csv`

## NYC TLC Trip Record Data

Source: <https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page>

TLC's own disclaimer is worth reproducing, because it is a teaching point rather than mere
boilerplate:

> The data was collected and provided to the NYC Taxi and Limousine Commission (TLC) by
> technology providers authorized under the Taxicab & Livery Passenger Enhancement Programs
> (TPEP/LPEP). The trip data was not created by the TLC, and TLC makes no representations as
> to the accuracy of these data.

The publisher is explicitly telling you to validate before trusting. That is the argument for
module 3 in one sentence, made by the data owner.

## Not used, but referenced

- **NYC 311 Service Requests** (NYC Open Data / Socrata, no API key) — real free text, real
  bureaucratic mess. Never downloaded here.
- **Loghub** (logpai, via Zenodo) — genuinely real system logs, distributed **for research
  purposes**. Mentioned only. If you ever add it, check the licence first.

## Software licences

Code in this repo: see `LICENSE`.

Note that **SeaweedFS is Apache 2.0** while the documented fallback object store **Garage is
AGPL-3.0**. Swapping the object store changes what you inherit.
