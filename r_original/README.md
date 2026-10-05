# Original course version (R + nimble)

The project started as the take-home assignment for *Applied Statistical Modelling*
(Università degli Studi di Bergamo, 2025/26). These are the original scripts:

- `modello.R` — the model in nimble, the four fits at matchdays 0, 12, 19, 28 of 2025/26,
  saved to `fits_k_grid.rds` (each fit: 3 chains × 40,000 iterations, 10,000 burn-in, thinning 10)
- `report.R` — every figure and table of the written report, from the saved fits

They read a file `seriea.csv` with columns
`season, matchweek, home_team, away_team, home_gol, away_gol, h, a`. The original was
scraped from FBref and is not redistributed here; `data/seriea_2020_2027.csv` has the same
columns and identical results for 2020/21–2025/26 (keep only those seasons).

The Python package in this repository implements the same model. Refitting the 2025/26
pre-season forecast gives the same answer as nimble:

| | R / nimble | Python / PyMC |
|---|---|---|
| home | 0.145 | 0.144 |
| ρ | 0.945 | 0.949 |
| entry | −0.223 | −0.226 |
| MAE vs final table | 7.96 | 7.91 |
| coverage of the 90% intervals | 0.85 | 0.85 |
