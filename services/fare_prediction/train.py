"""Train and register the fare forecast and demand surge models."""

import os

from services.fare_prediction.model import train_models

if __name__ == "__main__":
    run_ids = train_models(int(os.environ.get("MODEL_TRAINING_ROWS", "1200")))
    print(f"Registered {run_ids[0]} and {run_ids[1]}")
