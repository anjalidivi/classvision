
import torch
from torch.utils.data import DataLoader, Subset
from torchvision import datasets, transforms
from sklearn.model_selection import train_test_split
from pathlib import Path


# Project dataset location
DATA_DIR = Path("dataset/expressions")

# FER-2013 preprocessing
transform = transforms.Compose([
    transforms.Resize((64, 64)),
    transforms.Grayscale(num_output_channels=3),
    transforms.ToTensor(),
    transforms.Normalize(
        mean=(0.5, 0.5, 0.5),
        std=(0.5, 0.5, 0.5)
    )
])


def get_loaders(train_ratio=0.8, batch_size=32):

    if train_ratio not in (0.6, 0.8):
        raise ValueError("Use train_ratio=0.6 or 0.8")

    train_path = DATA_DIR / "train"
    test_path = DATA_DIR / "test"

    if not train_path.exists() or not test_path.exists():
        raise FileNotFoundError(
            "Check dataset/expressions/train and test folders"
        )

    # Load original training and testing datasets
    full_train = datasets.ImageFolder(
        train_path, transform=transform
    )

    test_dataset = datasets.ImageFolder(
        test_path, transform=transform
    )

    # Verify class order is identical
    if full_train.class_to_idx != test_dataset.class_to_idx:
        raise ValueError("Train and test class folders do not match")

    labels = full_train.targets
    indices = list(range(len(full_train)))

    # Stratified train/validation split
    train_indices, validation_indices = train_test_split(
        indices,
        train_size=train_ratio,
        random_state=42,
        stratify=labels
    )

    train_dataset = Subset(full_train, train_indices)
    validation_dataset = Subset(full_train, validation_indices)

    train_loader = DataLoader(
        train_dataset,
        batch_size=batch_size,
        shuffle=True,
        num_workers=0
    )

    validation_loader = DataLoader(
        validation_dataset,
        batch_size=batch_size,
        shuffle=False,
        num_workers=0
    )

    test_loader = DataLoader(
        test_dataset,
        batch_size=batch_size,
        shuffle=False,
        num_workers=0
    )

    return (
        train_loader,
        validation_loader,
        test_loader,
        full_train.classes
    )


if __name__ == "__main__":

    train_loader, val_loader, test_loader, classes = get_loaders(
        train_ratio=0.8
    )

    images, labels = next(iter(train_loader))

    print("Dataset loaded successfully!")
    print("Classes:", classes)
    print("Training images:", len(train_loader.dataset))
    print("Validation images:", len(val_loader.dataset))
    print("Official test images:", len(test_loader.dataset))
    print("Image batch shape:", images.shape)
    print("Label batch shape:", labels.shape)
