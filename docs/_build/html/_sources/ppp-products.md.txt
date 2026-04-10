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

Transform between Earth-fixed and inertial reference frames.

| Convention | Pattern | Example |
|---|---|---|
| Legacy | `igsWWWWD.erp` | `igs22341.erp` |
| Modern | `AC0OPSFIN_YYYYDDDHHMM_01D_01D_ERP.ERP` | `IGS0OPSFIN_20231230000_01D_01D_ERP.ERP` |

### Code/Phase Bias (BIA)

Correct signal-dependent hardware biases.

| Product | Pattern | Example |
|---|---|---|
| Code Bias (OSB) | `AC0MGXRAP_YYYYDDD0000_01D_01D_BIA.BIA` | `CAS0MGXRAP_20231230000_01D_01D_BIA.BIA` |
| Phase Bias (PPP-AR) | `AC0MGXRAP_YYYYDDD0000_01D_30S_PHS.BIA` | `CAS0MGXRAP_20231230000_01D_30S_PHS.BIA` |

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

Phase center offset and variation models for antennas.

| File       | Meaning             |
|------------|---------------------|
| `igs14.atx` | IGS14 antenna model |
| `igs20.atx` | IGS20 antenna model |

### Reference Frame / SINEX

Weekly SINEX solutions:

| Convention | Pattern | Example |
|---|---|---|
| Legacy | `igsWWWW.snx` | `igs2234.snx` |
| Modern | `AC0OPSFIN_YYYYDDD0000_07D_07D_SOL.SNX` | `IGS0OPSFIN_20231230000_07D_07D_SOL.SNX` |

### Real-Time SSR Streams

Real-time corrections via NTRIP (RTCM 3.x SSR):

| Stream | Contents |
|---|---|
| `IGS03` | Orbit + clock corrections |
| `CLK93` | Clock corrections |
| `SSRA00IGS0` | Multi-signal corrections |

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
| Observations | GNSS Observation Data | Raw measurements (code, phase) | RINEX OBS | 1–30 s | Real-time / daily |
| Satellite Orbits | Precise Orbit Ephemerides | Accurate satellite positions | SP3 | 5–15 min | Ultra-rapid / Rapid / Final |
| Satellite Clocks | Precise Clock Offsets | Satellite clock error correction | RINEX CLK | 5 s / 30 s | Ultra-rapid / Rapid / Final |
| Bias Products | Differential Code Bias (DCB) | Code biases between frequencies | SINEX BIAS | Daily | Rapid / Final |
| Bias Products | Observable Specific Bias (OSB) | Signal-specific biases (multi-GNSS) | SINEX BIAS | Daily | Rapid / Final |
| Phase Bias | Fractional Cycle Bias (FCB) | Integer ambiguity fixing in PPP-AR | FCB / SINEX BIAS | 5 min – 30 s | Rapid / Final |
| Earth Orientation | Earth Rotation Parameters (ERP/EOP) | Terrestrial ↔ inertial frame transform | ERP | Daily | Rapid / Final |
| Reference Frame | Station Coordinates / Frame Solutions | Define reference frame (ITRF) | SINEX | Daily / weekly | Final |
| Troposphere | Zenith Tropospheric Delay (ZTD/ZPD) | Atmospheric delay corrections | SINEX TRO | 5 min – 1 hr | Rapid / Final |
| Ionosphere | Global TEC Maps | Ionospheric delay models | IONEX | 15 min – 2 hr | Rapid / Final |
| Antenna Calibration | Antenna Phase Center Models | Receiver/satellite antenna offsets | ANTEX | Static | Final |
| Satellite Attitude | Satellite Yaw / Attitude | Satellite antenna orientation | ATT / YAW | 5–15 min | Rapid / Final |
| Real-Time Corrections | SSR Corrections | Real-time orbit/clock/bias | RTCM SSR | 1–10 s | Real-time |

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
