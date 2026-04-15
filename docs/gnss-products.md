# GNSS PPP Product Reference

This document covers naming conventions, file formats, and product types used
in Precise Point Positioning (PPP) and PPP with Ambiguity Resolution (PPP-AR).

---

## IGS Long Filename Convention

Most modern products follow the **IGS long filename convention**:

```
<AC><TYPE>_<YYYYDDDHHMM>_<LEN>_<SMP>_<CNT>.<FMT>
```

| Field       | Description                             | Example            |
|-------------|-----------------------------------------|--------------------|
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

---

## Product Types

### Precise Orbit (SP3)

High-accuracy satellite positions replacing broadcast ephemerides.

| Convention | Pattern | Example |
|---|---|---|
| Legacy | `igsWWWWD.sp3` | `igs22341.sp3` |
| Modern | `AC0OPSFIN_YYYYDDDHHMM_01D_05M_ORB.SP3` | `IGS0OPSFIN_20231230000_01D_05M_ORB.SP3` |

### Precise Clock (CLK)

Satellite clock error corrections.

| Convention | Pattern | Example |
|---|---|---|
| Legacy | `igsWWWWD.clk` | `igs22341.clk` |
| Modern | `AC0OPSFIN_YYYYDDDHHMM_01D_30S_CLK.CLK` | `IGS0OPSFIN_20231230000_01D_30S_CLK.CLK` |

### Earth Rotation Parameters (ERP)

Encodes polar motion (x_p, y_p), UT1-UTC, and length-of-day (LOD) for the
transformation between the International Terrestrial Reference Frame (ITRF)
and the International Celestial Reference Frame (ICRF). Required for orbit
integration and precise coordinate transformation in PPP.

| Convention | Pattern | Example |
|---|---|---|
| Legacy | `igsWWWWD.erp` | `igs22341.erp` |
| Modern | `AC0OPSFIN_YYYYDDDHHMM_01D_01D_ERP.ERP` | `IGS0OPSFIN_20231230000_01D_01D_ERP.ERP` |

### Bias Products (BIA)

Three distinct bias types are used in modern GNSS processing:

| Type | Abbreviation | Purpose | Required for |
|---|---|---|---|
| Observable-Specific Bias | OSB | Signal-specific hardware delay (multi-GNSS, multi-frequency) | Float PPP, PPP-AR |
| Fractional Cycle Bias | FCB / phase bias | Fractional part of ambiguity — enables integer fixing | PPP-AR only |
| Differential Code Bias | DCB | Legacy inter-frequency code delay | Ionosphere modeling (legacy) |

OSB supersedes DCB for modern multi-GNSS processing. FCB (or its equivalent under
the integer recovery clock / decoupled clock models) is required to fix carrier-phase
ambiguities to integers in PPP-AR.  Without it, PPP produces a float solution.

| Product | Pattern | Example |
|---|---|---|
| OSB | `AC0MGXFIN_YYYYDDD0000_01D_01D_OSB.BIA` | `WUM0MGXFIN_20231230000_01D_01D_OSB.BIA` |
| Phase Bias / FCB | `AC0MGXRAP_YYYYDDD0000_01D_30S_ABS.BIA` | `CAS0MGXRAP_20231230000_01D_30S_ABS.BIA` |

### Ionosphere Products (IONEX)

Global ionosphere maps providing total electron content models.

| Convention | Pattern | Example |
|---|---|---|
| Legacy | `igsgDDD0.YYi` | `igsg1230.23i` |
| Modern | `AC0OPSFIN_YYYYDDD0000_01D_02H_GIM.INX` | `IGS0OPSFIN_20231230000_01D_02H_GIM.INX` |

### Troposphere Products

Atmospheric delay estimates improving vertical accuracy.

```
AC0OPSFIN_YYYYDDD0000_01D_05M_TRO.TRO
```

### Antenna Calibration (ANTEX)

Phase center offset (PCO) and phase center variation (PCV) models for both
receiver and satellite antennas. Must be consistent with the reference frame
(ITRF realization) used for the orbit and clock products.

| File        | Frame       | Status |
|-------------|-------------|--------|
| `igs14.atx` | IGS14/ITRF2014 | Superseded — deprecated since IGS Repro3 (late 2022) |
| `igs20.atx` | IGS20/ITRF2020 | Current — required when using IGS Repro3 or later products |

> Using `igs14.atx` with Repro3 or post-Repro3 orbit/clock products
> introduces a frame inconsistency of order 1–2 cm. Always match the
> ANTEX to the reference frame of the orbit solution.

### Reference Frame / SINEX

Weekly SINEX solutions:

| Convention | Pattern | Example |
|---|---|---|
| Legacy | `igsWWWW.snx` | `igs2234.snx` |
| Modern | `AC0OPSFIN_YYYYDDD0000_07D_07D_SOL.SNX` | `IGS0OPSFIN_20231230000_07D_07D_SOL.SNX` |

### Satellite Attitude (OBX)

Satellite attitude quaternions used when processing LEO data or when applying
precise antenna orientation corrections beyond the nominal yaw-steering model.

```
AC0OPSFIN_YYYYDDD0000_01D_05M_ATT.OBX
```

> Note: Real-time SSR streams (NTRIP/RTCM) are not supported by this library.

---

## Observation Data (RINEX)

### RINEX 2

```
ssssDDD0.YYo          (observation)
ssssDDD0.YYd.Z        (compressed)
```

### RINEX 3+

```
SSSS00CCC_R_YYYYDDDHHMM_01D_30S_MO.rnx.gz
```

---

## Complete Product Summary

| Product Category | Product Name | Purpose in PPP | Format | Sampling | Latency |
|---|---|---|---|---|---|
| Observations | GNSS Observation | Raw code and carrier-phase measurements | RINEX OBS | 1–30 s | — |
| Precise Orbits | SP3 | Satellite positions in ITRF (replaces broadcast ephemeris) | SP3 | 5–15 min | ULT ≤3 h / RAP ≤17 h / FIN ≥13 d |
| Precise Clocks | CLK | Satellite and receiver clock corrections at RMS < 100 ps (FIN) | RINEX CLK | 30 s (FIN/RAP) / 5 min (ULT) | ULT ≤3 h / RAP ≤17 h / FIN ≥13 d |
| Observable-Specific Bias | OSB | Signal-level hardware delays; supersedes DCB for multi-GNSS/multi-freq | SINEX BIAS | Daily | RAP / FIN |
| Fractional Cycle Bias | FCB / phase bias | Fractional ambiguity terms enabling PPP-AR integer fixing | SINEX BIAS | Daily / 30 s | RAP / FIN |
| Earth Rotation Parameters | ERP | Polar motion (x_p, y_p), UT1-UTC, LOD for ITRF↔ICRF | ERP | Daily | RAP / FIN |
| Ionosphere | GIM (IONEX) | Global TEC grid for single-frequency or ionosphere-constrained PPP | IONEX | 2 h (FIN) / 15 min (RTS) | RAP / FIN |
| Troposphere | VMF1/VMF3 | Vienna Mapping Function grids (superior to Saastamoinen for high accuracy) | GRID | 6 h | FIN |
| Antenna Calibration | ANTEX | PCO/PCV for receiver and satellite antennas; must match orbit frame (igs20) | ANTEX | Static | FIN |
| Satellite Attitude | OBX | Attitude quaternions for LEO processing or precise antenna orientation | OBX | 5–15 min | RAP / FIN |

---

## Typical PPP Processing Directory

```
ppp_run/
├── obs/
│   └── station.rnx
├── products/
│   ├── orbit.sp3
│   ├── clock.clk
│   ├── erp.erp
│   ├── bias.bia
│   ├── ionosphere.inx
│   ├── antenna.atx
│   └── troposphere.tro
└── output/
    ├── position.pos
    └── residuals.txt
```

---

## References

- [IGS File Naming Convention](https://igs.org/formats-and-standards/)
- [RINEX 3 Specification](https://files.igs.org/pub/data/format/)
- [IONEX Format Specification](https://igs.org/formats-and-standards/)
- [SINEX Format Specification](https://www.iers.org/IERS/EN/Organization/AnalysisCoordinator/SinexFormat/sinex.html)
