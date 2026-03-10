
# GNSS PPP Product Naming Conventions

This document summarizes common naming conventions for GNSS products used in Precise Point Positioning (PPP).
Most modern products follow the **IGS long filename convention**, though legacy short filenames are still widely used.

---

# 1. IGS Long Filename Convention

General format:

```
<AC><TYPE>_<YYYYDDDHHMM>_<LEN>_<SMP>_<CNT>.<FMT>
```

| Field       | Description                             | Example            |
| ----------- | --------------------------------------- | ------------------ |
| AC          | Analysis Center                         | IGS, COD, GFZ, WHU |
| TYPE        | Product type                            | ORB, CLK, ERP, BIA |
| YYYYDDDHHMM | Start epoch (year + day-of-year + time) | 20231230000        |
| LEN         | Product length                          | 01D (1 day), 01H   |
| SMP         | Sampling interval                       | 05M, 30S           |
| CNT         | Content descriptor                      | ORB, CLK           |
| FMT         | File format                             | SP3, CLK, ERP      |

Example:

```
IGS0OPSFIN_20231230000_01D_05M_ORB.SP3
```

Meaning:

* IGS analysis center
* Final precise orbit
* Start: day 123 of 2023
* Length: 1 day
* Sampling: 5 minutes
* Product: orbit

---

# 2. Observation Data

### RINEX Observation File

```
ssssDDD0.YYo
```

| Field | Description            | Example |
| ----- | ---------------------- | ------- |
| ssss  | 4-character station ID | P123    |
| DDD   | Day of year            | 123     |
| 0     | Session indicator      | 0       |
| YY    | Year                   | 23      |
| o     | Observation file       | .o      |

Example:

```
p1231230.23o
```

Compressed:

```
p1231230.23d.Z
```

Modern RINEX 3 naming:

```
SSSS00CCC_R_YYYYDDDHHMM_01D_30S_MO.rnx.gz
```

Example:

```
P12300USA_R_20231230000_01D_30S_MO.rnx.gz
```

---

# 3. Precise Orbit Products

### Legacy Naming

```
igsWWWWD.sp3
```

| Field | Description |
| ----- | ----------- |
| WWWW  | GPS week    |
| D     | Day of week |

Example:

```
igs22341.sp3
```

### Modern Naming

```
IGS0OPSFIN_YYYYDDDHHMM_01D_05M_ORB.SP3
```

---

# 4. Satellite Clock Products

Legacy:

```
igsWWWWD.clk
```

Example:

```
igs22341.clk
```

Modern:

```
IGS0OPSFIN_YYYYDDDHHMM_01D_30S_CLK.CLK
```

---

# 5. Earth Rotation Parameters

Legacy:

```
igsWWWWD.erp
```

Modern:

```
IGS0OPSFIN_YYYYDDDHHMM_01D_01D_ERP.ERP
```

---

# 6. Bias Products

Bias products include DCB and OSB corrections.

Typical naming:

```
CAS0MGXRAP_YYYYDDD0000_01D_01D_BIA.BIA
```

| Component | Meaning               |
| --------- | --------------------- |
| CAS       | Analysis center       |
| MGX       | Multi-GNSS experiment |
| RAP       | Rapid product         |
| BIA       | Bias product          |

---

# 7. Ionosphere Products

IONEX format:

Legacy:

```
igsgDDD0.YYi
```

Example:

```
igsg1230.23i
```

Modern:

```
IGS0OPSFIN_YYYYDDD0000_01D_02H_GIM.INX
```

| Product | Meaning               |
| ------- | --------------------- |
| GIM     | Global Ionosphere Map |
| INX     | IONEX file            |

---

# 8. Troposphere Products

Typical naming:

```
AC0OPSFIN_YYYYDDDHHMM_01D_05M_TRO.TRO
```

Example:

```
IGS0OPSFIN_20231230000_01D_05M_TRO.TRO
```

---

# 9. Antenna Calibration Files

ANTEX format:

```
igs20.atx
```

| File      | Meaning             |
| --------- | ------------------- |
| igs14.atx | IGS14 antenna model |
| igs20.atx | IGS20 antenna model |

---

# 10. Reference Frame / SINEX

Weekly SINEX solutions:

```
igsWWWW.snx
```

Example:

```
igs2234.snx
```

Modern:

```
IGS0OPSFIN_YYYYDDD0000_07D_07D_SOL.SNX
```

---

# 11. Real-Time SSR Streams

Real-time corrections are typically distributed via NTRIP streams.

Typical stream names:

```
IGS03
CLK93
SSRA00IGS0
```

These streams contain:

* orbit corrections
* clock corrections
* code biases
* phase biases

Format:

```
RTCM 3.x SSR
```

---

# 12. Summary of Common PPP Product File Types

| Product             | Format     | Typical Extension |
| ------------------- | ---------- | ----------------- |
| Observation data    | RINEX      | .rnx / .obs       |
| Precise orbit       | SP3        | .sp3              |
| Satellite clocks    | RINEX CLK  | .clk              |
| Earth rotation      | ERP        | .erp              |
| Bias products       | SINEX BIAS | .bia              |
| Ionosphere maps     | IONEX      | .inx              |
| Troposphere         | SINEX TRO  | .tro              |
| Antenna calibration | ANTEX      | .atx              |
| Reference frame     | SINEX      | .snx              |

---

# 13. Typical PPP Processing Directory

```
ppp_run/

obs/
   station.rnx

products/
   orbit.sp3
   clock.clk
   erp.erp
   bias.bia
   ionosphere.inx
   antenna.atx
   troposphere.tro

output/
   position.pos
   residuals.txt
```

---

# References

* IGS File Naming Convention
* RINEX 3 Specification
* IONEX Format Specification
* SINEX Format Specification



| Product Category | Product Name | Purpose in PPP | Typical Format | Sampling | Latency Classes |
|---|---|---|---|---|---|
| Observations | GNSS Observation Data | Raw measurements used by PPP estimator (code, phase) | RINEX OBS | 1–30 s | Real-time / daily |
| Satellite Orbits | Precise Orbit Ephemerides | Accurate satellite positions replacing broadcast ephemerides | SP3 | 5–15 min | Ultra-rapid / Rapid / Final |
| Satellite Clocks | Precise Clock Offsets | Correct satellite clock errors | RINEX CLK | 5 s / 30 s | Ultra-rapid / Rapid / Final |
| Bias Products | Differential Code Bias (DCB) | Correct code biases between frequencies/signals | SINEX BIAS / BIA | Daily | Rapid / Final |
| Bias Products | Observable Specific Bias (OSB) | Signal-specific biases used in multi-GNSS PPP | SINEX BIAS | Daily | Rapid / Final |
| Phase Bias | Fractional Cycle Bias (FCB) | Enables integer ambiguity fixing in PPP-AR | FCB / SINEX BIAS | 5 min – 30 s | Rapid / Final |
| Earth Orientation | Earth Rotation Parameters (ERP/EOP) | Transform between terrestrial and inertial frames | ERP | Daily | Rapid / Final |
| Reference Frame | Station Coordinates / Frame Solutions | Define reference frame (e.g., ITRF) | SINEX | Daily / weekly | Final |
| Troposphere | Zenith Tropospheric Delay (ZTD/ZPD) | Atmospheric delay corrections | SINEX TRO | 5 min – 1 hr | Rapid / Final |
| Ionosphere | Global TEC Maps | Ionospheric delay models (single-frequency PPP) | IONEX | 15 min – 2 hr | Rapid / Final |
| Antenna Calibration | Antenna Phase Center Models | Correct receiver and satellite antenna offsets | ANTEX | Static | Final |
| Satellite Attitude | Satellite Yaw / Attitude | Model satellite antenna orientation | ATT / YAW | 5–15 min | Rapid / Final |
| Real-Time Corrections | State Space Representation (SSR) Corrections | Real-time orbit/clock/bias corrections | RTCM SSR | 1–10 s | Real-time |