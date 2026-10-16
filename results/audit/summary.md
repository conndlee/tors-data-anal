# Rosbag Audit Summary

Generated 2026-10-14 from `scripts/topic_matrix.py` and `scripts/audit_bags.py`.
Per-bag details are in the `.txt` files in this folder.

## Bags

| Bag | Tools | Length | Recording gaps (PSM) |
|---|---|---|---|
| 2026-06-15-10-13-45 | 3 mm (assumed) | 130 min | ~11 min lost (largest 5.5 min) |
| 2026-06-16-09-58-51 | 3 mm (assumed) | 155 min | ~4 min lost |
| 2026-08-18-10-10-38 | 8 mm | 84 min | PSM2: one 2 min gap |
| 2026-08-19-12-08-59 | 8 mm | 93 min | PSM1: ~4 min lost |
| 2026-10-07-14-42-15 | 8 mm | 117 min | PSM1: 88 short gaps, ~6 min total |
| 2026-10-08-13-19-59 | 8 mm | 70 min | PSM1: ~30 s |

The tool size is inferred: the June bags log no tool type, and the August/October
bags log da Vinci 8 mm instruments. **This still needs confirming.**

## Topics

In all six bags:

- `/PSM1/measured_js`, `/PSM2/measured_js` (arm and wrist joints)
- `/PSM1/jaw/measured_js`, `/PSM2/jaw/measured_js`
- `/MTML/measured_js`, `/MTMR/measured_js` (surgeon console)

Effort is filled in on every message, in every bag.

Only in the 8 mm bags (143 topics), including:

- Tool type changes (`/PSMx/tool_type`)
- dVRK force estimate (`/PSMx/body/measured_cf`, `/PSMx/spatial/measured_cf`)
- Jacobians, gravity compensation, clutch buttons
- Camera arm (`/ECM/...`) and setup joints (`/SUJ/...`)

Cartesian pose (`measured_cp`): one 3 mm bag (06-16) and all 8 mm bags.

## Data quirks to handle in code

- `measured_js` sometimes has 6 joints and sometimes 7 (with `jaw`), in blocks.
  **Always select joints by name, never by position.**
- Jaw messages sometimes carry old header stamps (up to 12 min old).
  **Use bag receive time, not the header stamp.**
- The dVRK restarted several times inside a bag (06-15 has 4 publishers).
- Recording gaps must be masked out, not interpolated across.
