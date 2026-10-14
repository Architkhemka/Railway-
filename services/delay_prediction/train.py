"""Train and register the delay and disruption model."""

import os

from services.delay_prediction.model import train_model

if __name__ == "__main__":
    run_id = train_model(int(os.environ.get("MODEL_TRAINING_ROWS", "1200")))
    print(f"Registered {run_id}")
