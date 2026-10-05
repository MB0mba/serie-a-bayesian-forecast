# =========================================================================
# Serie A 2020/21 - 2025/26
# REPORT: every figure and table used in the written report and the slides.
#
# This script does NOT refit anything. It loads `fits_k_grid.rds`, produced
# by modello.R, and turns it into output. Run modello.R first.
#
# Everything is written to  figure/  (pdf + png) and  tabelle/  (csv).
# The pdf is for the report (vector, scales cleanly), the png for the slides.
# All labels are in English, because the report and the slides are.
# =========================================================================

# setwd("path/to/project")   # set to your own folder

library(nimble)
library(MCMCvis)

FIG <- "figure"; TAB <- "tabelle"
dir.create(FIG, showWarnings = FALSE)
dir.create(TAB, showWarnings = FALSE)

# a single palette, used everywhere, so the report looks like one document
COL_MAIN <- "#1f4e79"   # dark blue  : the model
COL_ACC  <- "#c0504d"   # brick red  : observed reality / warnings
COL_GREY <- "#7f7f7f"
COL_FILL <- "#d6e3f0"

save_fig <- function(name, code, w = 7, h = 5) {
  code <- substitute(code); env <- parent.frame()
  pdf(file.path(FIG, paste0(name, ".pdf")), width = w, height = h)
  eval(code, env); dev.off()
  png(file.path(FIG, paste0(name, ".png")), width = w * 160, height = h * 160,
      res = 160)
  eval(code, env); dev.off()
  eval(code, env)                                   # and on screen
  cat("  figure written:", name, "\n")
}

save_tab <- function(name, x) {
  write.csv(x, file.path(TAB, paste0(name, ".csv")), row.names = FALSE)
  cat("  table written:", name, "\n")
}


# =========================================================================
# 0. REBUILD THE OBJECTS modello.R USED
# =========================================================================

df        <- read.csv("seriea.csv")
seasons   <- sort(unique(df$season))
df$s      <- match(df$season, seasons)
n_seasons <- length(seasons)
n_teams   <- max(c(df$h, df$a))
target    <- n_seasons

team_names <- rbind(data.frame(id = df$h, team = df$home_team),
                    data.frame(id = df$a, team = df$away_team))
team_names <- team_names[!duplicated(team_names$id), ]
team_names <- team_names[order(team_names$id), ]

first_season <- sapply(1:n_teams, function(t) min(df$s[df$h == t | df$a == t]))

table_points <- function(gh, ga, h, a, n_teams) {
  p_home <- (gh > ga) * 3 + (gh == ga) * 1
  p_away <- (ga > gh) * 3 + (gh == ga) * 1
  pts <- numeric(n_teams)
  for (t in 1:n_teams) pts[t] <- sum(p_home[h == t]) + sum(p_away[a == t])
  pts
}

fits   <- readRDS("fits_k_grid.rds")
k_grid <- as.numeric(names(fits))

df6    <- subset(df, s == target)
teams6 <- fits[[1]]$teams
nm6    <- team_names$team[teams6]
obs6   <- table_points(df6$home_gol, df6$away_gol, df6$h, df6$a, n_teams)[teams6]
naive  <- mean(abs(obs6 - mean(obs6)))

cat("\n=== objects rebuilt ===\n")
cat("seasons:", n_seasons, " teams in db:", n_teams,
    " matches:", nrow(df), "\n")


# =========================================================================
# 1. CONVERGENCE
#
#    Rhat compares the spread between chains with the spread within a
#    chain. At 1 the three chains are exploring the same distribution.
# =========================================================================

#    Only the parameters actually reported are checked: home, rho, entry,
#    mu0 and the two precisions. All of them must sit at 1.01 or below.

key  <- c("home", "rho", "entry", "mu0", "tau_att", "tau_def")
conv <- do.call(rbind, lapply(fits, function(f) {
  rh <- MCMCsummary(f$mcmc, Rhat = TRUE, n.eff = TRUE)
  data.frame(k = f$k,
             max_Rhat = round(max(rh[key, "Rhat"]), 3),
             min_ESS  = round(min(rh[key, "n.eff"])))
}))
print(conv, row.names = FALSE)


# =========================================================================
# 2. FIGURE - WHY A POISSON
#
#    The distribution of goals scored by one side in one match, observed,
#    against a Poisson with the same mean. No model, no parameters: this
#    is the assumption on its own, checked against the data.
# =========================================================================

y_all  <- c(df$home_gol, df$away_gol)
lam_mm <- mean(y_all)
kmax   <- 6
obs_p  <- prop.table(table(factor(pmin(y_all, kmax), levels = 0:kmax)))
poi_p  <- c(dpois(0:(kmax - 1), lam_mm), 1 - ppois(kmax - 1, lam_mm))

save_fig("F1_poisson_fit", {
  barplot(rbind(obs_p, poi_p), beside = TRUE,
          names.arg = c(0:(kmax - 1), paste0(kmax, "+")),
          col = c(COL_MAIN, COL_FILL), border = NA,
          ylim = c(0, max(obs_p, poi_p) * 1.18),
          xlab = "goals scored by one team in one match",
          ylab = "relative frequency")
  legend("topright", bty = "n",
         legend = c(sprintf("observed (%d matches)", nrow(df)),
                    sprintf("Poisson(%.2f)", lam_mm)),
         fill = c(COL_MAIN, COL_FILL), border = NA)
  box(bty = "l")
}, w = 7, h = 4.5)

cat("\nmean goals:", round(lam_mm, 3),
    " variance:", round(var(y_all), 3),
    " ratio:", round(var(y_all) / lam_mm, 3), "\n")


# =========================================================================
# 3. FIGURE + TABLE - THE PARAMETERS
# =========================================================================

f0 <- fits[["0"]]

ps <- MCMCsummary(f0$mcmc, Rhat = TRUE, n.eff = TRUE,
                  params = c("home", "rho", "entry", "mu0",
                             "tau_att", "tau_def"))
par_tab <- data.frame(parameter = rownames(ps),
                      mean = round(ps$mean, 3),
                      sd   = round(ps$sd, 3),
                      q2.5 = round(ps$`2.5%`, 3),
                      q97.5 = round(ps$`97.5%`, 3),
                      Rhat = round(ps$Rhat, 3),
                      ESS  = round(ps$n.eff))
print(par_tab, row.names = FALSE)
save_tab("T1_parameters", par_tab)

save_fig("F2_posteriors", {
  par(mfrow = c(1, 3), mar = c(4.2, 4, 3, 1))
  for (p in c("home", "rho", "entry")) {
    d <- density(f0$draws[, p])
    plot(d, main = p, xlab = "", ylab = "posterior density",
         col = COL_MAIN, lwd = 2)
    polygon(d, col = adjustcolor(COL_MAIN, 0.15), border = NA)
    q <- quantile(f0$draws[, p], c(0.025, 0.975))
    abline(v = q, lty = 2, col = COL_GREY)
    abline(v = mean(f0$draws[, p]), col = COL_ACC, lwd = 2)
    mtext(sprintf("mean %.3f   95%% CI [%.3f, %.3f]",
                  mean(f0$draws[, p]), q[1], q[2]), side = 3, cex = 0.62,
          line = 0.2, col = COL_GREY)
  }
  par(mfrow = c(1, 1))
}, w = 10, h = 3.6)

# the shock on a readable scale
sig_a <- mean(1 / sqrt(f0$draws[, "tau_att"]))
rho_m <- mean(f0$draws[, "rho"])
shock <- sig_a * sqrt(1 - rho_m^2)
cat("\nsigma_att:", round(sig_a, 3),
    " rho:", round(rho_m, 3),
    " sd_shock:", round(shock, 4),
    " -> typical summer change:", round(100 * (exp(shock) - 1), 1), "%\n")
cat("home advantage: exp(home) =", round(exp(mean(f0$draws[, "home"])), 3),
    "i.e. +", round(100 * (exp(mean(f0$draws[, "home"])) - 1), 1),
    "% expected goals at home\n")


# =========================================================================
# 4. FIGURE - THE TEAM STRENGTHS (the Baio-style caterpillar plot)
# =========================================================================

att6 <- f0$draws[, paste0("att[", teams6, ", ", target, "]")]
def6 <- f0$draws[, paste0("def[", teams6, ", ", target, "]")]

cat_plot <- function(M, ttl, xlab) {
  m  <- colMeans(M); lo <- apply(M, 2, quantile, 0.05)
  hi <- apply(M, 2, quantile, 0.95); o <- order(m)
  plot(m[o], seq_along(o), pch = 19, col = COL_MAIN, yaxt = "n",
       xlim = range(lo, hi), xlab = xlab, ylab = "", main = ttl,
       cex = 0.9, bty = "n")
  segments(lo[o], seq_along(o), hi[o], seq_along(o), col = COL_MAIN)
  axis(2, at = seq_along(o), labels = nm6[o], las = 1, cex.axis = 0.68,
       tick = FALSE)
  abline(v = 0, lty = 2, col = COL_GREY)
}

save_fig("F3_team_strengths", {
  par(mfrow = c(1, 2), mar = c(4.2, 6.4, 3, 0.8))
  cat_plot(att6, "Attack  (higher = scores more)",   expression(att[t]))
  cat_plot(def6, "Defence  (higher = concedes less)", expression(def[t]))
  par(mfrow = c(1, 1))
}, w = 10, h = 6)

strengths <- data.frame(team = nm6,
                        att = round(colMeans(att6), 3),
                        att_sd = round(apply(att6, 2, sd), 3),
                        def = round(colMeans(def6), 3),
                        def_sd = round(apply(def6, 2, sd), 3))
strengths <- strengths[order(-strengths$att), ]
save_tab("T2_strengths_2025_26", strengths)


# =========================================================================
# 5. FIGURE + TABLE - THE FORECAST AT k = 0
# =========================================================================

forecast_of <- function(f) {
  data.frame(team      = nm6,
             predicted = colMeans(f$pts),
             lo        = apply(f$pts, 2, quantile, 0.05),
             hi        = apply(f$pts, 2, quantile, 0.95),
             actual    = obs6,
             promoted  = ifelse(first_season[teams6] == target, "yes", ""))
}

fc0 <- forecast_of(f0)
fc0$error  <- round(fc0$predicted - fc0$actual, 1)
fc0$inside <- ifelse(fc0$actual >= fc0$lo & fc0$actual <= fc0$hi, "yes", "NO")
fc0 <- fc0[order(-fc0$predicted), ]
fc0[, 2:4] <- round(fc0[, 2:4], 1)
print(fc0, row.names = FALSE)
save_tab("T3_forecast_k0", fc0)

save_fig("F4_predicted_vs_actual", {
  p <- forecast_of(f0)
  par(mar = c(4.5, 4.5, 3, 1))
  plot(p$predicted, p$actual, type = "n",
       xlim = range(p$lo, p$hi), ylim = range(p$lo, p$hi),
       xlab = "points predicted before matchday 1 (posterior mean)",
       ylab = "points actually obtained",
       main = "Pre-season forecast, Serie A 2025/26", bty = "l")
  abline(0, 1, lty = 2, col = COL_GREY)
  segments(p$lo, p$actual, p$hi, p$actual,
           col = adjustcolor(COL_MAIN, 0.35), lwd = 3)
  out <- p$actual < p$lo | p$actual > p$hi
  points(p$predicted, p$actual, pch = 19, cex = 1.1,
         col = ifelse(out, COL_ACC, COL_MAIN))
  text(p$predicted, p$actual, p$team, pos = 3, cex = 0.52,
       col = ifelse(out, COL_ACC, "black"))
  legend("topleft", bty = "n", cex = 0.78,
         legend = c("inside the 90% interval", "outside",
                    "bar = 90% predictive interval"),
         pch = c(19, 19, NA), lty = c(NA, NA, 1), lwd = c(NA, NA, 3),
         col = c(COL_MAIN, COL_ACC, adjustcolor(COL_MAIN, 0.35)))
}, w = 7.5, h = 6.5)


# =========================================================================
# 6. FIGURE + TABLE - HOW THE FORECAST IMPROVES WITH k
# =========================================================================

summary_k <- do.call(rbind, lapply(fits, function(f) {
  pred <- colMeans(f$pts)
  lo <- apply(f$pts, 2, quantile, 0.05); hi <- apply(f$pts, 2, quantile, 0.95)
  data.frame(k = f$k,
             matches_used      = f$n_fit,
             matches_simulated = f$n_sim_matches,
             correlation   = round(cor(obs6, pred), 3),
             MAE           = round(mean(abs(pred - obs6)), 2),
             mean_width    = round(mean(hi - lo), 1),
             coverage_90   = round(mean(obs6 >= lo & obs6 <= hi), 2))
}))
print(summary_k, row.names = FALSE)
save_tab("T4_summary_by_k", summary_k)

save_fig("F5_error_vs_k", {
  par(mfrow = c(1, 2), mar = c(4.5, 4.5, 3, 1))
  plot(summary_k$k, summary_k$MAE, type = "b", pch = 19, lwd = 2,
       col = COL_MAIN, ylim = c(0, naive * 1.08), bty = "l",
       xlab = "cut-off matchday k", ylab = "mean absolute error (points)",
       main = "How much it improves")
  abline(h = naive, lty = 2, col = COL_ACC)
  text(max(summary_k$k), naive, "naive benchmark", pos = 1, cex = 0.7,
       col = COL_ACC)
  plot(summary_k$k, summary_k$mean_width, type = "b", pch = 19, lwd = 2,
       col = COL_MAIN, ylim = c(0, max(summary_k$mean_width) * 1.08),
       bty = "l", xlab = "cut-off matchday k",
       ylab = "mean width of the 90% interval (points)",
       main = "How much it narrows")
  par(mfrow = c(1, 1))
}, w = 10, h = 4.5)


# =========================================================================
# 6b. FIGURE - EVERY TEAM, EVERY CUT-OFF POINT
#
#     One row per team, four bars inside it: the 90% predictive interval
#     at k = 0, 12, 19 and 28, from pale to dark. The red line is what the
#     team actually achieved. Reading down a team's four bars shows both
#     things at once: the interval narrowing, and its centre sliding
#     towards the truth.
# =========================================================================

kcols <- c("#c3d3e6", "#8fabcc", "#4c76a8", "#1f4e79")   # pale -> dark

ev <- lapply(fits, function(f)
  list(k  = f$k,
       m  = colMeans(f$pts),
       lo = apply(f$pts, 2, quantile, 0.05),
       hi = apply(f$pts, 2, quantile, 0.95)))

save_fig("F6_forecast_by_k", {
  ord <- order(obs6)                       # worst at the bottom
  xr  <- range(unlist(lapply(ev, function(e) c(e$lo, e$hi))), obs6)
  par(mar = c(4.6, 7.2, 3.6, 1.2))
  plot(NULL, xlim = xr, ylim = c(0.4, length(ord) + 0.6), yaxt = "n", bty = "n",
       xlab = "points", ylab = "",
       main = "Every team, every cut-off point")
  abline(v = pretty(xr), col = "grey93")

  for (i in seq_along(ord)) {
    t <- ord[i]
    # the truth: one red line crossing the team's four bars
    segments(obs6[t], i - 0.46, obs6[t], i + 0.46, col = COL_ACC, lwd = 2.8)
    for (j in seq_along(ev)) {
      y <- i + (2.5 - j) * 0.19               # k = 0 on top, k = 28 at the bottom
      segments(ev[[j]]$lo[t], y, ev[[j]]$hi[t], y, col = kcols[j], lwd = 4,
               lend = 1)
      points(ev[[j]]$m[t], y, pch = 19, col = "white", cex = 0.72)
      points(ev[[j]]$m[t], y, pch = 19, col = kcols[j], cex = 0.42)
    }
  }
  axis(2, at = seq_along(ord), labels = nm6[ord], las = 1, cex.axis = 0.82,
       tick = FALSE, line = -0.4)
  legend("topleft", bty = "n", cex = 0.8, horiz = FALSE,
         legend = c(paste("after matchday", k_grid), "actual points"),
         lwd = c(rep(4, length(k_grid)), 2.8),
         col = c(kcols[seq_along(k_grid)], COL_ACC))
  mtext("each bar is a 90% predictive interval; the dot is the forecast",
        side = 3, line = 0.2, cex = 0.76, col = COL_GREY)
}, w = 8.5, h = 9.5)

# =========================================================================
# 7. THE ERROR FLOOR
#
#    Freeze the strengths at the best values available, wipe the points,
#    replay the season 2000 times. Whatever spread survives is pure Poisson
#    randomness: the error no model can remove.
# =========================================================================

f28 <- fits[[as.character(max(k_grid))]]
ah <- colMeans(f28$draws[, paste0("att[", 1:n_teams, ", ", target, "]")])
dh <- colMeans(f28$draws[, paste0("def[", 1:n_teams, ", ", target, "]")])
mh <- mean(f28$draws[, paste0("mu[", target, "]")])
hh <- mean(f28$draws[, "home"])

lh <- exp(mh + hh + ah[df6$h] - dh[df6$a])
la <- exp(mh      + ah[df6$a] - dh[df6$h])

set.seed(3)
pts_luck <- t(replicate(2000,
  table_points(rpois(nrow(df6), lh), rpois(nrow(df6), la),
               df6$h, df6$a, n_teams)))[, teams6]
colnames(pts_luck) <- nm6

floor_mae <- mean(abs(pts_luck - matrix(colMeans(pts_luck), nrow(pts_luck),
                                        length(teams6), byrow = TRUE)))
mae_k0 <- summary_k$MAE[summary_k$k == 0]

cat("\n=== the error floor ===\n")
cat("sd of points from chance alone, averaged over teams:",
    round(mean(apply(pts_luck, 2, sd)), 2), "points\n")
cat("naive benchmark   :", round(naive, 2), "\n")
cat("model, k = 0      :", round(mae_k0, 2), "\n")
cat("floor (chance)    :", round(floor_mae, 2), "\n")
cat("share of the closable gap actually closed:",
    round(100 * (naive - mae_k0) / (naive - floor_mae)), "%\n")

save_fig("F7_error_floor", {
  v <- c(naive, mae_k0, floor_mae)
  par(mar = c(6.5, 4.5, 3, 1))
  bp <- barplot(v, col = c(COL_GREY, COL_MAIN, COL_FILL), border = NA,
                ylim = c(0, max(v) * 1.2),
                ylab = "mean absolute error (points)",
                main = "How much of the error can be removed")
  axis(1, at = bp, tick = FALSE, line = 0.4, cex.axis = 0.72,
       labels = c("naive benchmark\n(every team at the mean)",
                  "model\nbefore matchday 1",
                  "theoretical floor\n(strengths known, chance only)"),
       padj = 0.7)
  text(bp, v, sprintf("%.2f", v), pos = 3, cex = 0.95, font = 2)
  box(bty = "l")
}, w = 7, h = 5)


# =========================================================================
# 8. WHY THE SAME TEAM DOES NOT ALWAYS WIN
#
#    Same teams, same strengths, 2000 replays of the same season.
#    The title changes hands on Poisson noise alone.
# =========================================================================

champ <- table(colnames(pts_luck)[apply(pts_luck, 1, which.max)]) / nrow(pts_luck)
champ <- sort(champ[champ >= 0.005], decreasing = TRUE)
print(round(champ, 3))
save_tab("T5_simulated_title",
         data.frame(team = names(champ),
                    probability = round(as.numeric(champ), 3)))

save_fig("F8_title_race", {
  par(mar = c(6.2, 4.5, 3.4, 1))
  bp <- barplot(as.numeric(champ), col = COL_MAIN, border = NA,
                ylim = c(0, max(champ) * 1.2), ylab = "probability of winning",
                main = "2000 replays of the same season, identical strengths")
  axis(1, at = bp, labels = names(champ), las = 2, tick = FALSE,
       cex.axis = 0.78, line = -0.4)
  text(bp, as.numeric(champ), sprintf("%.0f%%", 100 * as.numeric(champ)),
       pos = 3, cex = 0.8)
  mtext("the remaining uncertainty is Poisson randomness alone",
        side = 3, line = 0.2, cex = 0.75, col = COL_GREY)
  box(bty = "l")
}, w = 7.5, h = 5)


# =========================================================================
# 9. WHERE THE MODEL FAILS, AND WHY
#
#    The AR(1) lets a team move by sd_shock from one season to the next.
#    A team that breaks that budget cannot be predicted. Fiorentina is the
#    clearest case: it is not bad luck in converting chances, the goals
#    themselves collapsed.
# =========================================================================

season_goals <- function(nm) {
  tid <- team_names$id[team_names$team == nm]
  t(sapply(1:n_seasons, function(k) {
    d <- subset(df, s == k & (h == tid | a == tid))
    if (nrow(d) == 0) return(c(scored = NA, conceded = NA, points = NA))
    c(scored   = sum(ifelse(d$h == tid, d$home_gol, d$away_gol)),
      conceded = sum(ifelse(d$h == tid, d$away_gol, d$home_gol)),
      points   = table_points(d$home_gol, d$away_gol, d$h, d$a, n_teams)[tid])
  }))
}

fio <- season_goals("Fiorentina")
rownames(fio) <- seasons
print(fio)
save_tab("T6_fiorentina", data.frame(season = seasons, fio))

save_fig("F9_fiorentina", {
  par(mar = c(4.5, 4.5, 3.4, 1))
  matplot(1:n_seasons, fio[, c("scored", "conceded")], type = "b",
          pch = c(19, 17), lty = 1, lwd = 2, col = c(COL_MAIN, COL_ACC),
          xaxt = "n", bty = "l",
          ylim = c(0, max(fio[, 1:2], na.rm = TRUE) * 1.15),
          xlab = "", ylab = "goals in the season",
          main = "Fiorentina: not bad luck, the goals themselves collapsed")
  axis(1, at = 1:n_seasons, labels = seasons, cex.axis = 0.78)
  legend("bottomleft", bty = "n", horiz = TRUE, cex = 0.85,
         legend = c("scored", "conceded"), pch = c(19, 17), lwd = 2,
         col = c(COL_MAIN, COL_ACC))
  text(n_seasons, fio[n_seasons, 1], fio[n_seasons, 1], pos = 1, cex = 0.8,
       col = COL_MAIN, font = 2)
}, w = 7, h = 4.8)


# =========================================================================

cat("\n=== done. figures in", FIG, "/ tables in", TAB, "===\n")
