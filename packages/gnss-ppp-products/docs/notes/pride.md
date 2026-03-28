# PRIDE-PPP AR GNSS Product Catalog (Summary)

PRIDE-PPP AR uses a collection of GNSS data products that provide geometric, clock, atmospheric, and hardware corrections required for Precise Point Positioning (PPP) and PPP with Ambiguity Resolution (PPP-AR). Each product follows a structured naming convention, usually based on the modern IGS long-filename standard.

---

## Product Types and Naming Conventions

| Product | Purpose | Typical Filename | Filename Fields |
|---|---|---|---|
| **Precise Orbit (SP3)** | High-accuracy satellite positions replacing broadcast ephemerides | `AC0OPSFIN_YYYYDDDHHMM_01D_05M_ORB.SP3` | `AC` analysis center • `OPS` operational product • `FIN` final solution • `YYYYDDDHHMM` start epoch • `01D` duration • `05M` sampling interval • `ORB` orbit product • `.SP3` precise orbit format |
| **Precise Clock (CLK)** | Satellite clock error corrections | `AC0OPSFIN_YYYYDDDHHMM_01D_30S_CLK.CLK` | `AC` analysis center • `OPS` operational • `FIN` final solution • `YYYYDDDHHMM` start epoch • `01D` duration • `30S` sampling interval • `CLK` clock product • `.CLK` RINEX clock format |
| **Earth Rotation Parameters (ERP)** | Parameters used to transform between Earth-fixed and inertial reference frames | `AC0OPSFIN_YYYYDDDHHMM_01D_01D_ERP.ERP` | `AC` analysis center • `OPS` operational product • `FIN` final solution • `YYYYDDDHHMM` start epoch • `01D` product duration • `01D` sampling interval • `ERP` Earth rotation parameters • `.ERP` ERP format |
| **Code Bias / OSB** | Correct signal-dependent hardware biases affecting pseudorange measurements | `AC0MGXRAP_YYYYDDD0000_01D_01D_BIA.BIA` | `AC` analysis center • `MGX` multi-GNSS dataset • `RAP` rapid solution • `YYYYDDD0000` start epoch • `01D` duration • `01D` sampling • `BIA` bias product • `.BIA` bias file format |
| **Phase Bias (PPP-AR)** | Enables integer ambiguity resolution for faster PPP convergence | `AC0MGXRAP_YYYYDDD0000_01D_30S_PHS.BIA` | `AC` analysis center • `MGX` multi-GNSS dataset • `RAP` rapid solution • `YYYYDDD0000` start epoch • `01D` duration • `30S` sampling interval • `PHS` phase bias product • `.BIA` bias format |
| **Ionosphere Products (IONEX)** | Global ionosphere maps providing total electron content models | `AC0OPSFIN_YYYYDDD0000_01D_02H_GIM.INX` | `AC` analysis center • `OPS` operational • `FIN` final solution • `YYYYDDD0000` start epoch • `01D` duration • `02H` sampling interval • `GIM` global ionosphere map • `.INX` IONEX format |
| **Troposphere Products** | Atmospheric delay estimates improving vertical accuracy | `AC0OPSFIN_YYYYDDD0000_01D_05M_TRO.TRO` | `AC` analysis center • `OPS` operational • `FIN` final solution • `YYYYDDD0000` start epoch • `01D` duration • `05M` sampling interval • `TRO` troposphere solution • `.TRO` format |
| **Antenna Calibration (ANTEX)** | Phase center offset and variation models for antennas | `igs20.atx` | `igs` International GNSS Service • `20` reference frame generation • `.atx` ANTEX antenna calibration format |
| **Reference Frame / SINEX** | Defines global reference frame and station coordinates | `AC0OPSFIN_YYYYDDD0000_07D_07D_SOL.SNX` | `AC` analysis center • `OPS` operational • `FIN` final solution • `YYYYDDD0000` start epoch • `07D` solution span • `07D` sampling • `SOL` solution • `.SNX` SINEX format |

---
