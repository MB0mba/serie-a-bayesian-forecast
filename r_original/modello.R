# =========================================================================
# Serie A 2020/21 - 2025/26
# Dynamic hierarchical Poisson model, adapted from Baio & Blangiardo (2010)
#
# GOAL: forecast the final 2025/26 table from several points in the season.
#       k = 0  -> pre-season: 2025/26 never enters the likelihood
#       k = 12, 19, 28 -> the first k matchdays are known, the rest simulated
#
#       At every k the model is REFITTED. It is not the same parameters with
#       fewer matches to simulate: att and def themselves change, because
#       the matchdays already played enter the likelihood.
#
# Differences from Baio:
#   1. a per-season intercept mu[s]. His model has none, which forces the
#      average away goals to be exactly 1; over six seasons that fails.
#   2. `- def` instead of `+ def`, so def high = good defence.
#   3. an AR(1) carrying the strengths across seasons.
#   4. an entry effect for teams appearing in Serie A for the first time.
# =========================================================================

# setwd("path/to/project")   # set to your own folder

library(nimble)
library(MCMCvis)


# =========================================================================
# 1. DATA
# =========================================================================

df <- read.csv("seriea.csv")

seasons   <- sort(unique(df$season))
df$s      <- match(df$season, seasons)
n_seasons <- length(seasons)
n_teams   <- max(c(df$h, df$a))
target    <- n_seasons                      # the season being forecast

team_names <- rbind(data.frame(id = df$h, team = df$home_team),
                    data.frame(id = df$a, team = df$away_team))
team_names <- team_names[!duplicated(team_names$id), ]
team_names <- team_names[order(team_names$id), ]
stopifnot(nrow(team_names) == n_teams)

first_season <- sapply(1:n_teams, function(t) min(df$s[df$h == t | df$a == t]))
is_entry     <- matrix(0, n_teams, n_seasons)
for (t in 1:n_teams) if (first_season[t] > 1) is_entry[t, first_season[t]] <- 1

cat("squadre che entrano dopo la prima stagione:", sum(is_entry), "\n")
print(data.frame(team = team_names$team[first_season > 1],
                 entra_in = seasons[first_season[first_season > 1]]),
      row.names = FALSE)


# =========================================================================
# 2. MODEL
#
#   log lambda_home = mu[s] + home + att[h, s] - def[a, s]
#   log lambda_away = mu[s]        + att[a, s] - def[h, s]
#
#   att[t, k] = rho * att[t, k-1] + entry * is_entry[t, k] + shock
#
#   THE SHOCK is everything that changed a team over the summer and that
#   the model cannot see: transfers, a new coach, injuries, a player
#   breaking out. The model does not explain those, it leaves room for them.
#
#   Its size is not free: sd_shock = sigma_att * sqrt(1 - rho^2) is the
#   value that keeps the spread of the strengths CONSTANT across seasons.
#   From Var(att) = rho^2 Var(att) + Var(shock):
#        Var(shock) = Var(att) (1 - rho^2)
#   A larger shock and the league grows more unequal every year forever;
#   a smaller one and every team converges to the average. Neither happens.
#   It also keeps sigma_att readable as "how different the teams are within
#   a season" and rho as a pure "how much carries over".
# =========================================================================

model_code <- nimbleCode({

  for (i in 1:n_matches) {
    lambda_home[i] <- exp(mu[s[i]] + home + att[h[i], s[i]] - def[a[i], s[i]])
    lambda_away[i] <- exp(mu[s[i]]        + att[a[i], s[i]] - def[h[i], s[i]])

    home_gol[i] ~ dpois(lambda_home[i])
    away_gol[i] ~ dpois(lambda_away[i])
  }

  sigma_att    <- 1 / sqrt(tau_att)
  sigma_def    <- 1 / sqrt(tau_def)
  sd_shock_att <- sigma_att * sqrt(1 - rho * rho)
  sd_shock_def <- sigma_def * sqrt(1 - rho * rho)

  for (t in 1:n_teams) {
    att[t, 1] ~ dnorm(0, sd = sigma_att)
    def[t, 1] ~ dnorm(0, sd = sigma_def)
  }

  for (k in 2:n_seasons) {
    for (t in 1:n_teams) {
      att[t, k] ~ dnorm(rho * att[t, k - 1] + entry * is_entry[t, k],
                        sd = sd_shock_att)
      def[t, k] ~ dnorm(rho * def[t, k - 1] + entry * is_entry[t, k],
                        sd = sd_shock_def)
    }
  }

  sigma_mu <- 1 / sqrt(tau_mu)
  for (k in 1:n_seasons) {
    mu[k] ~ dnorm(mu0, sd = sigma_mu)
  }

  # in nimble the second POSITIONAL argument of dnorm is the precision:
  # `sd =` is written everywhere so there is no ambiguity
  home  ~ dnorm(0, sd = 100)
  mu0   ~ dnorm(0, sd = 100)
  rho   ~ dunif(0, 1)
  entry ~ dnorm(0, sd = 0.5)

  tau_att ~ dgamma(0.01, 0.01)        # as in Baio's appendix
  tau_def ~ dgamma(0.01, 0.01)
  tau_mu  ~ dgamma(0.01, 0.01)
})


# =========================================================================
# 3. HELPERS
# =========================================================================

table_points <- function(gh, ga, h, a, n_teams) {
  p_home <- (gh > ga) * 3 + (gh == ga) * 1
  p_away <- (ga > gh) * 3 + (gh == ga) * 1
  pts <- numeric(n_teams)
  for (t in 1:n_teams) pts[t] <- sum(p_home[h == t]) + sum(p_away[a == t])
  pts
}

make_inits <- function(seed, home0, rho0) {
  set.seed(seed)
  list(home = home0,
       mu   = rnorm(n_seasons, log(1.3), 0.05),
       mu0  = log(1.3),
       rho  = rho0,
       entry = -0.1,
       att = matrix(rnorm(n_teams * n_seasons, 0, 0.10), n_teams, n_seasons),
       def = matrix(rnorm(n_teams * n_seasons, 0, 0.10), n_teams, n_seasons),
       tau_att = 12, tau_def = 12, tau_mu = 100)
}


# =========================================================================
# 4. ONE FIT AT ONE CUT POINT
#
#   Chains are long because rho is the slowest parameter: it rests on only
#   five season-to-season transitions and is coupled with sigma_att through
#   the stationary form. With 15000 iterations Rhat reached 1.08 on rho,
#   which is not acceptable; 40000 brings it back under control.
# =========================================================================

run_k <- function(k, niter = 40000, nburnin = 10000, thin = 10, n_sim = 2000) {

  s6_done <- subset(df, s == target & matchweek <= k)
  s6_todo <- subset(df, s == target & matchweek >  k)

  df_fit <- rbind(subset(df, s < target), s6_done)

  stopifnot(nrow(s6_done) + nrow(s6_todo) == 380)

  mcmc_constants <- list(n_matches = nrow(df_fit),
                         n_teams   = n_teams,
                         n_seasons = n_seasons,
                         h = df_fit$h, a = df_fit$a, s = df_fit$s,
                         is_entry = is_entry)

  mcmc_data <- list(home_gol = df_fit$home_gol,
                    away_gol = df_fit$away_gol)

  out <- nimbleMCMC(
    code      = model_code,
    constants = mcmc_constants,
    data      = mcmc_data,
    inits     = list(make_inits(1,  0.10, 0.5),
                     make_inits(2,  0.30, 0.8),
                     make_inits(3, -0.05, 0.2)),
    monitors  = c("home", "mu", "mu0", "rho", "entry",
                  "tau_att", "tau_def", "tau_mu", "att", "def"),
    niter = niter, nburnin = nburnin, thin = thin, nchains = 3,
    samplesAsCodaMCMC = TRUE, progressBar = FALSE
  )

  draws <- as.matrix(out)

  att6 <- draws[, paste0("att[", 1:n_teams, ", ", target, "]")]
  def6 <- draws[, paste0("def[", 1:n_teams, ", ", target, "]")]
  mu6  <- draws[, paste0("mu[", target, "]")]
  hme  <- draws[, "home"]

  # points already on the board: certain, never simulated
  pts_done <- if (nrow(s6_done) > 0)
    table_points(s6_done$home_gol, s6_done$away_gol,
                 s6_done$h, s6_done$a, n_teams) else numeric(n_teams)

  set.seed(1)
  sel    <- round(seq(1, nrow(draws), length.out = n_sim))
  points <- matrix(NA_real_, n_sim, n_teams)

  for (r in seq_along(sel)) {
    g  <- sel[r]
    lh <- exp(mu6[g] + hme[g] + att6[g, s6_todo$h] - def6[g, s6_todo$a])
    la <- exp(mu6[g]          + att6[g, s6_todo$a] - def6[g, s6_todo$h])
    points[r, ] <- pts_done +
      table_points(rpois(nrow(s6_todo), lh), rpois(nrow(s6_todo), la),
                   s6_todo$h, s6_todo$a, n_teams)
  }

  teams6 <- sort(unique(c(subset(df, s == target)$h, subset(df, s == target)$a)))
  pts6   <- points[, teams6]
  colnames(pts6) <- team_names$team[teams6]

  rh <- MCMCsummary(out, Rhat = TRUE)$Rhat

  list(k = k, draws = draws, mcmc = out, pts = pts6, teams = teams6,
       n_fit = nrow(df_fit), n_sim_matches = nrow(s6_todo),
       worst_Rhat = max(rh, na.rm = TRUE),
       n_above_101 = sum(rh > 1.01, na.rm = TRUE))
}


# =========================================================================
# 5. THE GRID
#    Four separate fits, roughly nine minutes each.
#    Run ONE first and check Rhat before committing to all four.
# =========================================================================

k_grid <- c(0, 12, 19, 28)

fits <- list()
for (kk in k_grid) {
  cat("\n==== k =", kk, "====\n")
  t0 <- Sys.time()
  fits[[as.character(kk)]] <- run_k(kk)
  cat("  fatto in", round(difftime(Sys.time(), t0, units = "secs")), "secondi",
      " | worst Rhat:", round(fits[[as.character(kk)]]$worst_Rhat, 3),
      " | sopra 1.01:", fits[[as.character(kk)]]$n_above_101, "\n")
}

saveRDS(fits, "fits_k_grid.rds")

# NOTHING below should be read if worst_Rhat is above 1.01
sapply(fits, function(f) c(k = f$k, Rhat = f$worst_Rhat, sopra = f$n_above_101))


# =========================================================================
# 6. COMPARISON ACROSS k
# =========================================================================

df6  <- subset(df, s == target)
obs  <- table_points(df6$home_gol, df6$away_gol, df6$h, df6$a, n_teams)
obs6 <- obs[fits[[1]]$teams]

summary_k <- do.call(rbind, lapply(fits, function(f) {
  pred <- colMeans(f$pts)
  lo   <- apply(f$pts, 2, quantile, 0.05)
  hi   <- apply(f$pts, 2, quantile, 0.95)
  data.frame(
    k                = f$k,
    partite_usate    = f$n_fit,
    partite_simulate = f$n_sim_matches,
    correlazione     = cor(obs6, pred),
    errore_medio     = mean(abs(pred - obs6)),
    ampiezza_media   = mean(hi - lo),
    copertura_90     = mean(obs6 >= lo & obs6 <= hi),
    p_dispersione    = mean(apply(f$pts, 1, sd) >= sd(obs6))
  )
}))

print(summary_k, row.names = FALSE, digits = 3)

cat("\nbenchmark banale (tutti alla media):",
    round(mean(abs(obs6 - mean(obs6))), 2), "punti\n")

par(mfrow = c(1, 2))
plot(summary_k$k, summary_k$errore_medio, type = "b", pch = 19,
     xlab = "giornata di taglio (k)", ylab = "errore medio assoluto",
     main = "Quanto migliora la previsione")
abline(h = mean(abs(obs6 - mean(obs6))), lty = 2, col = "grey50")
plot(summary_k$k, summary_k$ampiezza_media, type = "b", pch = 19,
     xlab = "giornata di taglio (k)", ylab = "ampiezza media dell'intervallo",
     main = "Quanto si stringe")
par(mfrow = c(1, 1))


# =========================================================================
# 7. HOW att AND def MOVE AS k GROWS
#
#   att[t, 6] is always a compromise between two sources:
#     - the AR(1) prior, centred on rho * att[t, 5]
#     - the likelihood of the matchdays already played in 2025/26
#   The weight shifts towards the second as k grows. This block measures
#   the shift instead of taking it on trust.
# =========================================================================

teams6 <- fits[[1]]$teams

att6_by_k <- sapply(fits, function(f)
  colMeans(f$draws[, paste0("att[", teams6, ", ", target, "]")]))
def6_by_k <- sapply(fits, function(f)
  colMeans(f$draws[, paste0("def[", teams6, ", ", target, "]")]))
sd6_by_k  <- sapply(fits, function(f)
  apply(f$draws[, paste0("att[", teams6, ", ", target, "]")], 2, sd))

dimnames(att6_by_k) <- list(team_names$team[teams6], paste0("k=", k_grid))
dimnames(def6_by_k) <- dimnames(att6_by_k)
dimnames(sd6_by_k)  <- dimnames(att6_by_k)

cat("\n--- att[t, 2025/26]: media a posteriori ---\n")
print(round(att6_by_k, 3))

cat("\n--- att[t, 2025/26]: deviazione standard a posteriori ---\n")
print(round(sd6_by_k, 3))
# deve SCENDERE al crescere di k: piu' dati, meno incertezza sulla forza

# quanto le forze stimate si avvicinano a quello che le squadre hanno
# davvero fatto nel 2025/26
gol_fatti <- sapply(teams6, function(t)
  sum(df6$home_gol[df6$h == t]) + sum(df6$away_gol[df6$a == t]))
gol_subiti <- sapply(teams6, function(t)
  sum(df6$away_gol[df6$h == t]) + sum(df6$home_gol[df6$a == t]))

cat("\n--- correlazione con i gol realmente fatti / subiti ---\n")
print(round(rbind(
  att_vs_gol_fatti   = apply(att6_by_k, 2, function(x) cor(x, gol_fatti)),
  def_vs_gol_subiti  = apply(def6_by_k, 2, function(x) cor(x, gol_subiti))
), 3))
# att sale verso 1, def scende verso -1: le forze convergono sulla realta'

matplot(k_grid, t(att6_by_k), type = "b", pch = 19, lty = 1,
        col = grey(seq(0.1, 0.75, length.out = length(teams6))),
        xlab = "giornata di taglio (k)", ylab = "att[t, 2025/26]",
        main = "Le forze si separano man mano che arrivano i dati")


# =========================================================================
# 8. DETAIL FOR ONE CUT POINT
# =========================================================================

f <- fits[["0"]]        # cambia in "12", "19", "28"

MCMCsummary(f$mcmc, Rhat = TRUE, n.eff = TRUE,
            params = c("home", "mu", "mu0", "rho", "entry",
                       "tau_att", "tau_def", "tau_mu"))

MCMCtrace(f$mcmc, pdf = FALSE, ind = TRUE,
          params = c("home", "rho", "entry", "tau_att"))

# the shock, on the readable scale
sig   <- mean(1 / sqrt(f$draws[, "tau_att"]))
rhom  <- mean(f$draws[, "rho"])
shock <- sig * sqrt(1 - rhom^2)
c(sigma_att = sig, rho = rhom, sd_shock = shock,
  variazione_tipica_pct = 100 * (exp(shock) - 1))

forecast <- data.frame(
  team        = colnames(f$pts),
  previsto    = colMeans(f$pts),
  lo          = apply(f$pts, 2, quantile, 0.05),
  hi          = apply(f$pts, 2, quantile, 0.95),
  p_scudetto  = colMeans(t(apply(f$pts, 1, function(x) x == max(x)))),
  osservato   = obs6,
  neopromossa = ifelse(first_season[f$teams] == target, "si", "")
)
forecast$errore <- forecast$previsto - forecast$osservato
forecast <- forecast[order(-forecast$previsto), ]

print(forecast, row.names = FALSE, digits = 3)

plot(forecast$previsto, forecast$osservato, pch = 19,
     xlab = "punti previsti", ylab = "punti osservati",
     main = paste0("Previsione 2025/26 a giornata k = ", f$k))
abline(0, 1, lty = 2, col = "grey50")
text(forecast$previsto, forecast$osservato, forecast$team, pos = 3, cex = 0.6)
