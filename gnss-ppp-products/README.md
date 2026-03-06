# Project Goals

1. ETL requisite GNSS products for a given task/package (i.e. PPP using PRIDE)
2. Dynamically generate config files for a given task/package
3. Store products in a predictable local sink
4. Create an exhaustive resource of queries for GNSS analysis centers and products.


## Analysis Centers

| Code | Analysis Center | Server(s) | Protocol |
|------|-----------------|-----------|----------|
| COD | CODE (Center for Orbit Determination in Europe) | `ftp://ftp.aiub.unibe.ch` | FTP |
| WHU/WUM | Wuhan University (GPS + MGEX) | `ftp://igs.gnsswhu.cn` | FTP |
| GFZ/GBM | GeoForschungsZentrum Potsdam (GPS + MGEX) | `ftp://isdcftp.gfz-potsdam.de` | FTP |
| ESA | European Space Agency | `ftp://gssc.esa.int` | FTP |
| IGS | IGS Combined Solutions | `ftp://igs.ign.fr` (IGN France) | FTP |
| IGS | IGS Central Bureau | `https://files.igs.org` | HTTPS |
| JPL | Jet Propulsion Laboratory | CDDIS/Wuhan mirrors | FTP |
| EMR | Natural Resources Canada | CDDIS/Wuhan mirrors | FTP |
| CDDIS | NASA CDDIS Archive | `ftp://gdc.cddis.eosdis.nasa.gov` | FTPS (TLS) |
| NGS | NOAA National Geodetic Survey | `https://www.ngs.noaa.gov` | HTTPS |
| VMF | TU Wien (Vienna Mapping Functions) | `https://vmf.geo.tuwien.ac.at` | HTTPS |
| KASI | Korea Astronomy and Space Science Institute | `ftp://nfs.kasi.re.kr` | FTP |

## Product Types

### Orbit/Clock Products
| Type | Description | Extensions | Temporal |
|------|-------------|------------|----------|
| SP3 | Precise satellite orbit positions | `.sp3`, `.sp3.gz` | Daily |
| CLK | Precise satellite/station clock corrections | `.clk`, `.clk.gz` | Daily |
| ERP | Earth Rotation Parameters (pole, UT1-UTC, LOD) | `.erp`, `.erp.gz` | Daily |
| BIAS | Satellite differential code/phase biases (DCB/DSB/OSB) | `.bia`, `.BSX.gz` | Daily |
| OBX | ORBEX satellite attitude quaternions | `.obx`, `.obx.gz` | Daily |
| SUM | Solution summary files | `.sum`, `.SUM.gz` | Daily |

### Navigation/Broadcast Products
| Type | Description | Extensions | Temporal |
|------|-------------|------------|----------|
| RINEX3_NAV | RINEX 3.x broadcast navigation (multi-GNSS) | `.rnx`, `MN.rnx.gz` | Daily |
| RINEX2_NAV_GPS | RINEX 2.x GPS broadcast navigation | `.n`, `.n.Z` | Daily |
| RINEX2_NAV_GLONASS | RINEX 2.x GLONASS broadcast navigation | `.g`, `.g.Z` | Daily |
| RINEX2_NAV_MIXED | RINEX 2.x mixed GPS+GLONASS navigation | `.p`, `.p.Z` | Daily |

### Ionosphere Products
| Type | Description | Extensions | Temporal |
|------|-------------|------------|----------|
| GIM | Global Ionosphere Map (VTEC grids, IONEX) | `.i`, `.I.Z`, `.INX.gz` | Daily |

### Troposphere Products
| Type | Description | Extensions | Temporal |
|------|-------------|------------|----------|
| VMF1 | Vienna Mapping Functions 1 | `.H00`, `.H06`, `.H12`, `.H18` | Hourly |
| VMF3 | Vienna Mapping Functions 3 | `.H00`, `.H06`, `.H12`, `.H18` | Hourly |

### Antenna Calibration Products
| Type | Description | Extensions | Temporal |
|------|-------------|------------|----------|
| ATX_IGS | IGS ANTEX antenna phase center calibrations | `.atx` | Epoch |
| ATX_CODE_MGEX | CODE MGEX ANTEX calibrations (M14/M20) | `.ATX` | Epoch |
| ATX_NGS | NGS/NOAA ANTEX antenna calibrations | `.atx` | Epoch |

### Reference Tables
| Type | Description | Extensions | Temporal |
|------|-------------|------------|----------|
| LEAP_SECONDS | UTC-TAI leap second offset table | `.sec`, `.dat` | Static |
| SAT_PARAMETERS | Satellite metadata and properties table | — | Static |

### Orography Products
| Type | Description | Extensions | Temporal |
|------|-------------|------------|----------|
| OROGRAPHY | Ellipsoidal terrain height grids (VMF interpolation) | `_1x1`, `_5x5` | Static |

### LEO Satellite Products (GRACE/GRACE-FO)
| Type | Description | Extensions | Temporal |
|------|-------------|------------|----------|
| GRACE_GNV | GPS navigation Level-1B data | `.dat.gz` | Daily |
| GRACE_ACC | Accelerometer Level-1B data | `.dat.gz` | Daily |
| GRACE_SCA | Star camera Level-1B data | `.dat.gz` | Daily |
| GRACE_KBR | K-Band ranging Level-1B data | `.dat.gz` | Daily |
| GRACE_LRI | Laser Ranging Interferometer Level-1B data | `.dat.gz` | Daily |
| GRACE_CLK | Clock Level-1B data | `.dat.gz` | Daily |
| GRACE_THR | Thruster Level-1B data | `.dat.gz` | Daily |