# GNSS Data Servers

A reference list of major GNSS data and product servers worldwide.

## IGS Analysis Centers (precise products)

| Center | Organization | Server |
|--------|-------------|--------|
| **IGS** | International GNSS Service (combined) | `ftp://igs.ign.fr`, `gdc.cddis.eosdis.nasa.gov` |
| **COD** | CODE, Univ. Bern, Switzerland | `ftp://ftp.aiub.unibe.ch` |
| **GFZ** | GeoForschungsZentrum, Germany | `ftp://ftp.gfz-potsdam.de` |
| **ESA/ESOC** | European Space Agency | `ftp://gssc.esa.int` |
| **JPL** | Jet Propulsion Laboratory, USA | `ftp://sideshow.jpl.nasa.gov` |
| **EMR/NRCan** | Natural Resources Canada | `ftp://ftp.nrcan.gc.ca` |
| **GRG/GRGS** | GRGS, France | `ftp://tab.obs-mip.fr` / `grgs.obs-mip.fr` |
| **MIT** | MIT, USA | `ftp://everest.mit.edu` |
| **NGS** | NOAA/NGS, USA | `ftp://geodesy.noaa.gov` |
| **SIO** | Scripps, USA | `ftp://garner.ucsd.edu` |
| **WUM** | Wuhan University, China | `ftp://igs.gnsswhu.cn` |
| **TUG** | TU Graz, Austria | via CDDIS mirror |
| **SHA/CAS** | Shanghai Astronomical Observatory, China | `ftp://202.127.29.4` |
| **GBM** | GFZ multi-GNSS | `ftp://ftp.gfz-potsdam.de` |
| **IAC** | IAC, Russia (GLONASS) | `ftp://ftp.glonass-iac.ru` |
| **JAXA/JAX** | Japan Aerospace Exploration Agency | via CDDIS |

## Data Archives & Mirrors

| Name | URL |
|------|-----|
| **CDDIS** (NASA) | `ftps://gdc.cddis.eosdis.nasa.gov` |
| **IGN France** | `ftp://igs.ign.fr` |
| **BKG** (Germany) | `ftp://igs.bkg.bund.de` |
| **KASI** (South Korea) | `ftp://nfs.kasi.re.kr` |
| **NGII** (South Korea) | `ftp://gnss.ngii.go.kr` |
| **GA** (Geoscience Australia) | `ftp://ftp.ga.gov.au` |
| **NRCan CSRS** | `ftp://ftp.nrcan.gc.ca` |

## Broadcast / Real-Time (Ntrip)

| Name | URL |
|------|-----|
| **BKG Ntrip** | `https://igs-ip.net` |
| **IGS-IP** | `http://www.igs-ip.net` |
| **EUREF-IP** | `http://www.euref-ip.net` |

## Real-Time PPP Products

| Name | URL |
|------|-----|
| **CNES/CLS** | `ftp://ftpsedr.cls.fr` |
| **IGS RTS** | via BKG/JPL Ntrip streams |

## Navigation & Auxiliary Products

| Name | URL |
|------|-----|
| **MGEX** (multi-GNSS) | `gdc.cddis.eosdis.nasa.gov/gnss/data/campaign/mgex/` |
| **BIPM** (time) | `ftp://ftp2.bipm.org` |
| **IERS** (Earth orientation) | `ftp://ftp.iers.org` |

## Ionosphere & Troposphere

| Name | URL |
|------|-----|
| **VMF** (TU Wien) | `https://vmf.geo.tuwien.ac.at` |
| **JPL IONEX** | `ftp://sideshow.jpl.nasa.gov` |
| **CODE IONEX** | `ftp://ftp.aiub.unibe.ch` |
| **ESA GIM** | `ftp://gssc.esa.int` |
| **IONOLAB** (Turkey) | `http://www.ionolab.org` |

## Regional Networks

| Name | Region | URL |
|------|--------|-----|
| **EUREF/EPN** | Europe | `ftp://epncb.oma.be` |
| **SONEL** | Global sea level | `ftp://ftp.sonel.org` |
| **UNAVCO** | Americas | `ftp://data-out.unavco.org` |
| **CORS/NGS** | USA | `https://geodesy.noaa.gov/corsdata/` |
| **GEONET** | New Zealand | `ftp://ftp.geonet.org.nz` |
| **SOPAC** | Pacific | `ftp://garner.ucsd.edu` |

## Satellite System Operators

| System | Organization | URL |
|--------|-------------|-----|
| **GLONASS** | IAC, Russia | `ftp://ftp.glonass-iac.ru` |
| **BDS-3** | CSNO, China | `http://www.csno-tarc.cn` |
| **Galileo** | GSA/EUSPA, EU | `https://www.gsc-europa.eu` |
| **QZSS** | JAXA, Japan | `https://qzss.go.jp` |
| **NavIC** | ISRO, India | `https://irnss.isro.gov.in` |

---

> **Notes:**
> - Many FTP servers have migrated to FTPS or HTTPS. CDDIS requires NASA Earthdata credentials.
> - Many regional CORS networks require registration before data access.
> - Server availability and paths change over time — use `dev/probe_catalog.py` to verify connectivity.
