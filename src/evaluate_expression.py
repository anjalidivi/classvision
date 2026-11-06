import json
import time
from pathlib import Path

import torch
import matplotlib.pyplot as plt

from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    confusion_matrix,
    classification_report,
    balanced_accuracy_score,
    roc_auc_score,
    matthews_corrcoef,
    cohen_kappa_score,
    log_loss
)

from snn_model import ClassroomSNN
from dataset_loader import get_loaders


def calculate_specificity(cm):
    specificities = []

    for i in range(len(cm)):
        true_positive = cm[i, i]
        false_positive = cm[:, i].sum() - true_positive
        false_negative = cm[i, :].sum() - true_positive
        true_negative = cm.sum() - (
            true_positive + false_positive + false_negative
        )

        denominator = true_negative + false_positive

        specificity = (
            true_negative / denominator if denominator > 0 else 0
        )

        specificities.append(specificity)

    return sum(specificities) / len(specificities)


def main():

    device = torch.device("cpu")

    model_path = Path("models/expression_snn_lif_80_best.pth")
    output_dir = Path("reports")
    output_dir.mkdir(exist_ok=True)

    if not model_path.exists():
        raise FileNotFoundError(f"Model not found: {model_path}")

    print("Loading official FER-2013 test dataset...")

    _, _, test_loader, classes = get_loaders(
        train_ratio=0.8,
        batch_size=16
    )

    checkpoint = torch.load(
        model_path,
        map_location=device,
        weights_only=False
    )

    model = ClassroomSNN(
        time_steps=10,
        num_classes=len(classes)
    )

    model.load_state_dict(checkpoint["model_state_dict"])
    model.to(device)
    model.eval()

    print("Model loaded successfully!")
    print("Classes:", classes)
    print("Official test images:", len(test_loader.dataset))

    all_labels = []
    all_predictions = []
    all_probabilities = []

    print("\nStarting model evaluation...")

    start_time = time.perf_counter()

    with torch.inference_mode():

        for batch_index, (images, labels) in enumerate(test_loader):

            images = images.to(device)

            outputs = model(images)

            probabilities = torch.softmax(outputs, dim=1)
            predictions = outputs.argmax(dim=1)

            all_labels.extend(labels.numpy().tolist())
            all_predictions.extend(predictions.cpu().numpy().tolist())
            all_probabilities.extend(probabilities.cpu().numpy().tolist())

            if (batch_index + 1) % 50 == 0:
                print(
                    f"Processed batches: "
                    f"{batch_index + 1}/{len(test_loader)}"
                )

    inference_time = time.perf_counter() - start_time

    print("\nCalculating evaluation metrics...")

    cm = confusion_matrix(
        all_labels,
        all_predictions,
        labels=list(range(len(classes)))
    )

    accuracy = accuracy_score(all_labels, all_predictions)

    precision = precision_score(
        all_labels, all_predictions, average="macro", zero_division=0
    )

    recall = recall_score(
        all_labels, all_predictions, average="macro", zero_division=0
    )

    f1 = f1_score(
        all_labels, all_predictions, average="macro", zero_division=0
    )

    specificity = calculate_specificity(cm)

    balanced_accuracy = balanced_accuracy_score(
        all_labels, all_predictions
    )

    auc = roc_auc_score(
        all_labels,
        all_probabilities,
        labels=list(range(len(classes))),
        multi_class="ovr",
        average="macro"
    )

    mcc = matthews_corrcoef(all_labels, all_predictions)

    kappa = cohen_kappa_score(all_labels, all_predictions)

    loss = log_loss(
        all_labels,
        all_probabilities,
        labels=list(range(len(classes)))
    )

    total_images = len(all_labels)
    average_inference_time = inference_time / total_images
    fps = total_images / inference_time

    metrics = {
        "model": "ClassroomSNN",
        "dataset": "FER-2013 Official Test Set",
        "test_images": total_images,
        "accuracy": accuracy,
        "macro_precision": precision,
        "macro_recall": recall,
        "macro_f1_score": f1,
        "macro_specificity": specificity,
        "balanced_accuracy": balanced_accuracy,
        "macro_roc_auc_ovr": auc,
        "matthews_correlation_coefficient": mcc,
        "cohen_kappa": kappa,
        "log_loss": loss,
        "total_inference_time_seconds": inference_time,
        "average_inference_time_per_image_seconds": average_inference_time,
        "throughput_fps": fps
    }

    print("\n========== SNN TEST RESULTS ==========")

    for name, value in metrics.items():
        if isinstance(value, float):
            print(f"{name}: {value:.4f}")
        else:
            print(f"{name}: {value}")

    print("\n========== CLASSIFICATION REPORT ==========")

    report = classification_report(
        all_labels,
        all_predictions,
        target_names=classes,
        zero_division=0
    )

    print(report)

    # Save confusion matrix
    plt.figure(figsize=(9, 7))

    plt.imshow(cm, interpolation="nearest")
    plt.title("Classroom SNN - Confusion Matrix")
    plt.colorbar()

    positions = range(len(classes))

    plt.xticks(positions, classes, rotation=45)
    plt.yticks(positions, classes)

    plt.xlabel("Predicted Expression")
    plt.ylabel("Actual Expression")

    for i in range(len(classes)):
        for j in range(len(classes)):
            plt.text(j, i, str(cm[i, j]), ha="center", va="center")

    plt.tight_layout()

    confusion_path = output_dir / "snn_confusion_matrix_80.png"
    plt.savefig(confusion_path, dpi=300)
    plt.close()

    # Save metrics and classification report
    metrics["classification_report"] = classification_report(
        all_labels,
        all_predictions,
        target_names=classes,
        output_dict=True,
        zero_division=0
    )

    metrics_path = output_dir / "snn_lif_evaluation_80.json"

    with open(metrics_path, "w") as file:
        json.dump(metrics, file, indent=4)

    print("\nEvaluation completed successfully!")
    print("Metrics saved:", metrics_path)
    print("Confusion matrix saved:", confusion_path)


if __name__ == "__main__":
    main()
