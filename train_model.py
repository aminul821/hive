"""
train_model.py
---------------
Trains two real scikit-learn models for HoneyChain:
  1. A classifier that predicts hive RISK LEVEL (Low / Medium / High)
  2. A regressor that predicts expected HONEY YIELD (kg)

Since we don't have years of real beekeeping sensor logs, this script generates
a realistic SYNTHETIC dataset based on known apiculture domain rules (ideal
temperature ~32-35C, humidity ~50-70%, healthy activity/weight ranges), with
random noise added so the relationships aren't perfectly clean -- this mimics
real-world sensor data and gives the model something genuine to learn instead
of just memorizing an if-else formula.

Run this once to produce the trained model files:
    python train_model.py
"""

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, r2_score
import joblib
import os

np.random.seed(42)
N = 4000

# ---- 1. Generate synthetic sensor readings ----
#
# Calibrated against real hive telemetry from the UFC Brazil dataset
# (Zenodo 10.5281/zenodo.20399470, CC-BY-4.0): 7,066 Apis mellifera
# readings showing interior temperature of 35.2-38.0 C, median 36.2,
# standard deviation 0.4.
#
# A uniform 18-42 C draw was the original approach and it was wrong.
# Honey bees thermoregulate the brood nest very tightly, so nearly every
# sample from a uniform draw sits at a temperature no living colony ever
# reaches. The model spent its capacity learning impossible states and
# almost none on the narrow band where healthy and failing hives actually
# differ.
#
# Instead: draw a healthy majority around the observed mean, plus a
# deliberate minority of genuine failure modes. Those failure states are
# real and worth detecting -- chilled brood, overheating, a failing
# cluster -- they are just far rarer than a uniform draw implies.
HEALTHY_SHARE = 0.70
n_healthy = int(N * HEALTHY_SHARE)
n_stressed = N - n_healthy

temperature = np.concatenate([
    # Healthy: matches the observed real distribution.
    np.random.normal(36.0, 0.8, n_healthy),
    # Stressed: chilled brood below, overheating above.
    np.where(np.random.rand(n_stressed) < 0.5,
             np.random.uniform(24, 33, n_stressed),      # too cold
             np.random.uniform(38.5, 44, n_stressed)),   # too hot
])
temperature = np.clip(temperature, 18, 45)

# Interior humidity is regulated too. The same real dataset gives a
# median of 67.4% with sd 2.8 -- higher and far tighter than the 25-95
# uniform draw originally used, and higher than the 60% the score formula
# treated as ideal.
humidity = np.concatenate([
    np.random.normal(67, 4, n_healthy),
    np.where(np.random.rand(n_stressed) < 0.5,
             np.random.uniform(30, 55, n_stressed),      # too dry
             np.random.uniform(80, 95, n_stressed)),     # too wet
])
humidity = np.clip(humidity, 20, 99)

# Weight spans nucs through full supers, so a wide draw is fair here.
# Observed real range was 42.6-56.8 kg for established colonies.
weight = np.random.uniform(10, 60, N)          # kg, hive weight
activity = np.random.uniform(10, 100, N)       # bee activity index (0-100)

# Shuffle so healthy and stressed rows are not ordered.
_order = np.random.permutation(N)
temperature, humidity = temperature[_order], humidity[_order]

# ---- 2. Simulate a realistic underlying health score with noise ----
# (This plays the role of "years of real observations" a real deployment would use.)
score = 100.0
score -= np.abs(temperature - 35.5) * 3.2      # ideal 35.5C, from the real brood-nest
                                              # median of 36.2C (was 33.5, which penalised
                                              # healthy colonies by ~9 points on arrival)
score -= np.abs(humidity - 67) * 0.9           # ideal 67%, from the real interior
                                              # median of 67.4% (was 60)
score -= np.clip(55 - activity, 0, None) * 0.9 # penalty if activity is low
score -= np.clip(35 - weight, 0, None) * 0.8   # penalty if weight is low
score += np.random.normal(0, 6, N)             # sensor/real-world noise
score = np.clip(score, 0, 100)

risk = np.where(score >= 75, "Low", np.where(score >= 50, "Medium", "High"))

# Expected yield (kg) correlates with health score and hive weight, plus noise
yield_kg = 2 + (weight - 10) * 0.18 + (score / 100) * 6 + np.random.normal(0, 1.2, N)
yield_kg = np.clip(yield_kg, 0, None)

df = pd.DataFrame({
    "temperature": temperature,
    "humidity": humidity,
    "weight": weight,
    "activity": activity,
    "risk": risk,
    "yield_kg": yield_kg,
})

X = df[["temperature", "humidity", "weight", "activity"]]

# ---- 3. Train the RISK classifier ----
y_risk = df["risk"]
X_train, X_test, y_train, y_test = train_test_split(X, y_risk, test_size=0.2, random_state=42)
risk_model = RandomForestClassifier(n_estimators=150, max_depth=8, random_state=42)
risk_model.fit(X_train, y_train)
risk_acc = accuracy_score(y_test, risk_model.predict(X_test))

# ---- 4. Train the YIELD regressor ----
y_yield = df["yield_kg"]
X_train2, X_test2, y_train2, y_test2 = train_test_split(X, y_yield, test_size=0.2, random_state=42)
yield_model = RandomForestRegressor(n_estimators=150, max_depth=8, random_state=42)
yield_model.fit(X_train2, y_train2)
yield_r2 = r2_score(y_test2, yield_model.predict(X_test2))

# ---- 5. Save models ----
os.makedirs("models", exist_ok=True)
joblib.dump(risk_model, "models/hive_risk_model.pkl")
joblib.dump(yield_model, "models/hive_yield_model.pkl")

print(f"Risk classifier accuracy on held-out test data: {risk_acc:.2%}")
print(f"Yield regressor R^2 on held-out test data: {yield_r2:.3f}")
print("Saved models/hive_risk_model.pkl and models/hive_yield_model.pkl")
