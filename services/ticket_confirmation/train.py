"""Train and register the ticket confirmation model."""

import os

from services.ticket_confirmation.model import train_model

if __name__ == "__main__":
    run_id = train_model(int(os.environ.get("MODEL_TRAINING_ROWS", "1200")))
    print(f"Registered {run_id}")
