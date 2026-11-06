
import torch
import cv2

from pathlib import Path
from PIL import Image
from torchvision import transforms

from snn_model import ClassroomSNN


PROJECT_ROOT = Path(__file__).resolve().parent.parent

MODEL_PATH = (
    PROJECT_ROOT
    / "models"
    / "expression_snn_lif_80_best.pth"
)

DEVICE = torch.device("cpu")

CLASS_NAMES = [
    "angry",
    "disgust",
    "fear",
    "happy",
    "neutral",
    "sad",
    "surprise"
]


# Same preprocessing used during FER-2013 training
PREPROCESS = transforms.Compose([
    transforms.Resize((64, 64)),
    transforms.Grayscale(num_output_channels=3),
    transforms.ToTensor(),
    transforms.Normalize(
        mean=(0.5, 0.5, 0.5),
        std=(0.5, 0.5, 0.5)
    )
])


class ExpressionPredictor:

    def __init__(self):

        if not MODEL_PATH.exists():
            raise FileNotFoundError(
                f"Trained SNN checkpoint not found: {MODEL_PATH}"
            )

        self.model = ClassroomSNN(
            time_steps=10,
            num_classes=7
        ).to(DEVICE)

        checkpoint = torch.load(
            MODEL_PATH,
            map_location=DEVICE
        )

        self.model.load_state_dict(
            checkpoint["model_state_dict"]
        )

        self.classes = checkpoint.get(
            "classes",
            CLASS_NAMES
        )

        if list(self.classes) != CLASS_NAMES:
            raise ValueError(
                "Checkpoint class order does not match "
                "the expected FER-2013 class order."
            )

        self.model.eval()

        print("Expression model loaded successfully!")
        print("Classes:", self.classes)

    def predict(self, face_crop):

        if face_crop is None or face_crop.size == 0:
            return None

        # OpenCV BGR to RGB
        rgb_face = cv2.cvtColor(
            face_crop,
            cv2.COLOR_BGR2RGB
        )

        # Convert to PIL image
        pil_image = Image.fromarray(rgb_face)

        # Apply training preprocessing
        image_tensor = PREPROCESS(pil_image)

        image_tensor = image_tensor.unsqueeze(0).to(DEVICE)

        with torch.inference_mode():

            outputs = self.model(image_tensor)

            probabilities = torch.softmax(
                outputs,
                dim=1
            )

            confidence, predicted_index = (
                probabilities.max(dim=1)
            )

        expression = self.classes[
            predicted_index.item()
        ]

        return {
            "expression": expression,
            "confidence": round(
                confidence.item(),
                4
            ),
            "probabilities": {
                name: round(value, 4)
                for name, value in zip(
                    self.classes,
                    probabilities[0].tolist()
                )
            }
        }
