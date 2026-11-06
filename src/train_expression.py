
import argparse
import time
import json
from pathlib import Path

import torch
import torch.nn as nn
import matplotlib.pyplot as plt

from torch.optim import Adam
from torch.optim.lr_scheduler import ReduceLROnPlateau

from snn_model import ClassroomSNN
from dataset_loader import get_loaders


# Project directories
PROJECT_ROOT = Path(__file__).resolve().parent.parent
MODELS_DIR = PROJECT_ROOT / "models"
REPORTS_DIR = PROJECT_ROOT / "reports"


def evaluate(model, loader, criterion, device):

    model.eval()

    total_loss = 0.0
    correct = 0
    total = 0

    with torch.inference_mode():

        for images, labels in loader:

            images = images.to(device)
            labels = labels.to(device)

            outputs = model(images)

            loss = criterion(outputs, labels)

            total_loss += loss.item() * labels.size(0)

            predictions = outputs.argmax(dim=1)

            correct += (predictions == labels).sum().item()
            total += labels.size(0)

    average_loss = total_loss / total
    accuracy = 100.0 * correct / total

    return average_loss, accuracy



def calculate_class_weights(dataset, classes):

    original_dataset = dataset.dataset

    targets = torch.tensor(
        original_dataset.targets,
        dtype=torch.long
    )

    subset_targets = targets[dataset.indices]

    class_counts = torch.bincount(
        subset_targets,
        minlength=len(classes)
    ).float()

    weights = len(subset_targets) / (
        len(classes) * class_counts.clamp(min=1)
    )

    weights = weights / weights.mean()

    print("\nClass distribution:")

    for index, class_name in enumerate(classes):
        print(
            f"{class_name}: "
            f"{int(class_counts[index].item())} images | "
            f"Weight: {weights[index].item():.4f}"
        )

    return weights



def save_graphs(results, split_name):

    epochs = [item["epoch"] for item in results]

    train_loss = [item["train_loss"] for item in results]
    val_loss = [item["validation_loss"] for item in results]

    train_acc = [item["train_accuracy"] for item in results]
    val_acc = [item["validation_accuracy"] for item in results]

    # Loss graph
    plt.figure(figsize=(9, 5))

    plt.plot(epochs, train_loss, label="Training Loss")
    plt.plot(epochs, val_loss, label="Validation Loss")

    plt.xlabel("Epoch")
    plt.ylabel("Loss")
    plt.title("CNN-LIF SNN Training and Validation Loss")
    plt.legend()
    plt.grid(True)

    plt.tight_layout()

    plt.savefig(
        REPORTS_DIR / f"snn_lif_loss_curve_{split_name}.png",
        dpi=200
    )

    plt.close()

    # Accuracy graph
    plt.figure(figsize=(9, 5))

    plt.plot(epochs, train_acc, label="Training Accuracy")
    plt.plot(epochs, val_acc, label="Validation Accuracy")

    plt.xlabel("Epoch")
    plt.ylabel("Accuracy (%)")
    plt.title("CNN-LIF SNN Training and Validation Accuracy")
    plt.legend()
    plt.grid(True)

    plt.tight_layout()

    plt.savefig(
        REPORTS_DIR / f"snn_lif_accuracy_curve_{split_name}.png",
        dpi=200
    )

    plt.close()


def main():

    parser = argparse.ArgumentParser(
        description="Train CNN + LIF Spiking Neural Network"
    )

    parser.add_argument(
        "--split",
        type=float,
        choices=[0.6, 0.8],
        default=0.8
    )

    parser.add_argument("--epochs", type=int, default=5)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--patience", type=int, default=2)

    args = parser.parse_args()

    # CPU training
    device = torch.device("cpu")

    torch.manual_seed(42)

    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(42)

    print("=" * 55)
    print("CNN + LIF SPIKING NEURAL NETWORK TRAINING")
    print("=" * 55)

    print("Device:", device)
    print("Training split:", args.split)
    print("Epochs:", args.epochs)
    print("Batch size:", args.batch_size)

    # Create directories
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    # Load dataset
    train_loader, val_loader, test_loader, classes = get_loaders(
        train_ratio=args.split,
        batch_size=args.batch_size
    )

    print("\nDataset information")
    print("-" * 40)

    print("Classes:", classes)
    print("Training samples:", len(train_loader.dataset))
    print("Validation samples:", len(val_loader.dataset))
    print("Official test samples:", len(test_loader.dataset))

    # Calculate class weights
    class_weights = calculate_class_weights(
        train_loader.dataset,
        classes
    ).to(device)

    # Create model
    model = ClassroomSNN(
        time_steps=10,
        num_classes=len(classes)
    ).to(device)

    print("\nModel parameters:",
          sum(parameter.numel() for parameter in model.parameters()))

    # Weighted loss
    criterion = nn.CrossEntropyLoss(
        weight=class_weights
    )

    # Optimizer
    optimizer = Adam(
        model.parameters(),
        lr=0.0005,
        weight_decay=0.0001
    )

    # Learning-rate scheduler
    scheduler = ReduceLROnPlateau(
        optimizer,
        mode="max",
        factor=0.5,
        patience=1,
        min_lr=0.000001
    )

    # Training configuration
    split_name = str(int(args.split * 100))

    best_model_path = (
        MODELS_DIR / f"expression_snn_lif_{split_name}_best.pth"
    )

    history_path = (
        REPORTS_DIR / f"snn_lif_training_history_{split_name}.json"
    )

    results = []

    best_accuracy = 0.0
    patience_counter = 0

    start_time = time.time()

    # Training loop
    for epoch in range(args.epochs):

        model.train()

        running_loss = 0.0
        correct = 0
        total = 0

        epoch_start = time.time()

        for batch_index, (images, labels) in enumerate(train_loader):

            images = images.to(device)
            labels = labels.to(device)

            optimizer.zero_grad(set_to_none=True)

            outputs = model(images)

            loss = criterion(outputs, labels)

            loss.backward()

            optimizer.step()

            running_loss += loss.item() * labels.size(0)

            predictions = outputs.argmax(dim=1)

            correct += (predictions == labels).sum().item()
            total += labels.size(0)

            if (batch_index + 1) % 100 == 0:

                print(
                    f"Epoch {epoch + 1}/{args.epochs} | "
                    f"Batch {batch_index + 1}/{len(train_loader)} | "
                    f"Loss: {loss.item():.4f}"
                )

        # Training metrics
        train_loss = running_loss / total
        train_accuracy = 100.0 * correct / total

        # Validation metrics
        val_loss, val_accuracy = evaluate(
            model,
            val_loader,
            criterion,
            device
        )

        # Update scheduler
        scheduler.step(val_accuracy)

        current_lr = optimizer.param_groups[0]["lr"]

        epoch_time = time.time() - epoch_start

        print("\n" + "=" * 45)
        print(f"Epoch {epoch + 1}/{args.epochs}")
        print("=" * 45)

        print(f"Training loss:       {train_loss:.4f}")
        print(f"Training accuracy:   {train_accuracy:.2f}%")
        print(f"Validation loss:     {val_loss:.4f}")
        print(f"Validation accuracy: {val_accuracy:.2f}%")
        print(f"Learning rate:       {current_lr:.7f}")
        print(f"Epoch time:          {epoch_time:.2f} seconds")

        # Save epoch results
        results.append({
            "epoch": epoch + 1,
            "train_loss": train_loss,
            "train_accuracy": train_accuracy,
            "validation_loss": val_loss,
            "validation_accuracy": val_accuracy,
            "learning_rate": current_lr,
            "epoch_time": epoch_time
        })

        # Save best model
        if val_accuracy > best_accuracy:

            best_accuracy = val_accuracy
            patience_counter = 0

            torch.save({

                "model_state_dict": model.state_dict(),

                "classes": classes,

                "split": args.split,

                "epochs_completed": epoch + 1,

                "best_validation_accuracy": best_accuracy,

                "model_name": "CNN_LIF_SNN",

                "time_steps": 10

            }, best_model_path)

            print("\nBest model checkpoint saved!")

        else:

            patience_counter += 1

            print(
                f"No validation improvement: "
                f"{patience_counter}/{args.patience}"
            )

        # Early stopping
        if patience_counter >= args.patience:

            print("\nEarly stopping activated.")
            break

        # Save history after every epoch
        with open(history_path, "w") as file:
            json.dump(results, file, indent=4)

    # Final save
    with open(history_path, "w") as file:
        json.dump(results, file, indent=4)

    save_graphs(results, split_name)

    elapsed = time.time() - start_time

    print("\n" + "=" * 55)
    print("TRAINING COMPLETED")
    print("=" * 55)

    print(f"Best validation accuracy: {best_accuracy:.2f}%")
    print("Best model:", best_model_path)
    print("Training history:", history_path)

    print(
        "Loss graph:",
        REPORTS_DIR / f"snn_lif_loss_curve_{split_name}.png"
    )

    print(
        "Accuracy graph:",
        REPORTS_DIR / f"snn_lif_accuracy_curve_{split_name}.png"
    )

    print(f"Total training time: {elapsed / 60:.2f} minutes")


if __name__ == "__main__":
    main()
