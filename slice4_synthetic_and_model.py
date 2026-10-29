"""
slice4_synthetic_and_model.py  -  Slice 4: generate data, train an UNSUPERVISED
                                   anomaly model, and detect agent-payment fraud
                                   with NO real fraud data.

WHY THIS EXISTS (the data problem):
  Agentic-payment fraud is brand new, so there is NO labelled historical dataset
  to train a supervised model on (unlike the IEEE-CIS fraud repo). The honest
  answer to "no data" is:
    1. train on NORMAL behaviour only (unsupervised anomaly detection - no fraud
       labels needed), and
    2. GENERATE the data synthetically to bootstrap the build and the eval.

  Caveat kept in view: synthetic attacks only contain patterns we imagined, so this
  proves the MACHINERY works, not that it catches novel real-world attacks. Real
  production telemetry is the eventual moat; this is the bootstrap.

WHAT IT DOES:
  - generate a stream of realistic NORMAL agent payments (per-payee amount profiles)
  - train an IsolationForest on the NORMAL stream only (learns 'what normal looks like')
  - test on a mix of unseen normal payments + labelled ATTACKS (overpay, new-payee,
    duplicate, velocity burst)
  - score precision / recall honestly - same discipline as the fraud repo

Run:  python3 slice4_synthetic_and_model.py   (needs scikit-learn, numpy)
"""
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.metrics import precision_score, recall_score, f1_score

rng = np.random.default_rng(42)       # fixed seed -> reproducible

# ---- each known payee's "normal" profile: typical amount + spread + how often ----
PAYEES = {
    "Lisbon Marriott":  {"mean": 360, "sd": 25, "weight": 3},
    "TAP Air Portugal": {"mean": 430, "sd": 30, "weight": 3},
    "Europcar":         {"mean": 125, "sd": 10, "weight": 2},
    "Shell Petrol":     {"mean":  60, "sd": 12, "weight": 4},
    "Tesco":            {"mean":  45, "sd": 15, "weight": 5},
}
NAMES   = list(PAYEES)
WEIGHTS = np.array([PAYEES[p]["weight"] for p in NAMES], dtype=float)
WEIGHTS /= WEIGHTS.sum()


# ---- feature vector for ONE payment -----------------------------------------
# The model only ever sees numbers. These 4 features are the behavioural signals:
#   amount             - raw size
#   ratio_to_baseline  - amount / this payee's usual mean   (overpayment signal)
#   mins_since_prev    - gap since the previous payment      (velocity signal)
#   payee_seen_count   - how many times we've paid this payee (novelty signal)
def features(amount, payee_mean, mins_since_prev, payee_seen_count):
    return [amount,
            amount / payee_mean,
            mins_since_prev,
            payee_seen_count]


# ---- generate a stream of NORMAL payments -----------------------------------
def make_normal(n):
    rows, seen = [], {}
    for _ in range(n):
        name = rng.choice(NAMES, p=WEIGHTS)
        prof = PAYEES[name]
        amount = max(1.0, rng.normal(prof["mean"], prof["sd"]))   # around the payee's norm
        # realistic gap: a legit agent rarely fires payments seconds apart, so give
        # normal spacing a floor (~8 min min). This is what makes a burst detectable.
        gap    = 8 + rng.exponential(40)
        seen[name] = seen.get(name, 0) + 1
        rows.append(features(amount, prof["mean"], gap, seen[name]))
    return np.array(rows)


# ---- generate labelled ATTACKS (several jittered instances of each kind) -----
def make_attacks(per_kind=12):
    rows, labels, kinds = [], [], []

    def add(f, kind):
        rows.append(f); labels.append(1); kinds.append(kind)

    for _ in range(per_kind):
        # 1. overpay a known payee (amount 2.2-3.2x its normal)
        name = rng.choice(["Lisbon Marriott", "TAP Air Portugal", "Europcar"])
        pm = PAYEES[name]["mean"]
        add(features(pm * rng.uniform(2.2, 3.2), pm, 8 + rng.exponential(40),
                     rng.integers(3, 15)), "overpay")

        # 2. new / unknown payee (never paid before -> seen_count 0)
        add(features(rng.uniform(200, 900), 300, 8 + rng.exponential(40), 0), "new-payee")

        # 3. duplicate / replay (tiny gap, normal-looking amount)
        name = rng.choice(NAMES); pm = PAYEES[name]["mean"]
        add(features(max(1.0, rng.normal(pm, PAYEES[name]["sd"])), pm,
                     rng.uniform(0.05, 0.6), rng.integers(3, 15)), "duplicate")

        # 4. velocity burst (payments seconds apart)
        name = rng.choice(NAMES); pm = PAYEES[name]["mean"]
        add(features(max(1.0, rng.normal(pm, PAYEES[name]["sd"])), pm,
                     rng.uniform(0.02, 0.4), rng.integers(10, 30)), "velocity")

    return np.array(rows), np.array(labels), kinds


# ---- build datasets ----------------------------------------------------------
X_train = make_normal(4000)                      # NORMAL only -> this is what we learn
X_norm_test = make_normal(1000)                  # unseen normal (should NOT be flagged)
X_atk, y_atk, atk_kinds = make_attacks()

X_test = np.vstack([X_norm_test, X_atk])
y_test = np.concatenate([np.zeros(len(X_norm_test)), y_atk])   # 0 = normal, 1 = attack


# ---- train the model on NORMAL behaviour only --------------------------------
# contamination = the fraction of the TRAIN set we allow to be treated as outliers.
# We train on clean normal data, so we keep it small.
model = IsolationForest(n_estimators=300, contamination=0.02, random_state=42)
model.fit(X_train)                               # NOTE: no labels passed - unsupervised

# IsolationForest: predict -1 = anomaly, +1 = normal. Map to our 1 = attack.
pred = (model.predict(X_test) == -1).astype(int)

# ---- score --------------------------------------------------------------------
p = precision_score(y_test, pred, zero_division=0)
r = recall_score(y_test, pred, zero_division=0)
f = f1_score(y_test, pred, zero_division=0)

print("=" * 72)
print("SLICE 4  -  unsupervised anomaly model, trained on NORMAL data only")
print("=" * 72)
print(f"Train: {len(X_train)} normal payments (NO fraud labels used to train)")
print(f"Test : {len(X_norm_test)} unseen normal + {len(X_atk)} labelled attacks\n")

print(f"Precision = {p:.1%}   (of what it flagged, how much was really attack)")
print(f"Recall    = {r:.1%}   (of all attacks, how many it caught)")
print(f"F1        = {f:.1%}\n")

# per-attack-kind breakdown: how many of each kind did we catch?
from collections import defaultdict
by_kind = defaultdict(lambda: [0, 0])     # kind -> [caught, total]
atk_pred = pred[len(X_norm_test):]
for kind, got in zip(atk_kinds, atk_pred):
    by_kind[kind][1] += 1
    by_kind[kind][0] += int(got)
print("Per-attack-kind recall (how many of each caught):")
for kind, (c, t) in sorted(by_kind.items()):
    print(f"   {kind:<10} {c}/{t} caught")

# false alarms on normal traffic
fp = int(pred[:len(X_norm_test)].sum())
print(f"\nFalse alarms on the {len(X_norm_test)} normal payments: {fp} "
      f"({fp/len(X_norm_test):.1%})")

print("=" * 72)
print("""
HONEST READING:
  Trained on NORMAL payments ONLY - no fraud labels, no real attack data. The answer
  to "there is no agentic fraud data": you don't need fraud examples to flag 'not
  normal'. And the results show exactly WHERE that works and where it doesn't:

    overpay   12/12  - amount far above the payee's norm -> clearly abnormal. ML wins.
    new-payee  ~half - caught when the amount is also odd; missed when a new payee
                       pays a normal-looking amount (only one feature is off).
    duplicate   0/12 ) pure TIMING anomalies: normal on amount, payee and ratio, and
    velocity    0/12 ) only the gap is small. A general anomaly model DILUTES a single
                       off-axis feature, so it misses these.

  THE REAL LESSON (hybrid, not either/or):
  Duplicate and velocity are EXACT, COUNTABLE patterns - a deterministic rule catches
  them perfectly and cheaply (Slice 3 already blocks duplicates with one line). ML
  earns its place on the FUZZY deviations (amount-vs-baseline, novelty) that are hard
  to threshold by hand. So the right design is LAYERED: rules for the exact/countable,
  ML for the fuzzy-behavioural. Slice 3's rules and Slice 4's model are complementary,
  not competitors.

  LIMIT: the attacks are synthetic - patterns we chose - so this proves the machinery,
  not robustness to novel real attacks. Real agent telemetry is the next asset, and
  being early is how you get it.
""")
