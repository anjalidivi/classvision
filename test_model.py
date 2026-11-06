
import torch
from src.snn_model import ClassroomSNN

print("Starting 7-class SNN test...")

model = ClassroomSNN(num_classes=7)

sample_input = torch.rand(2, 3, 64, 64)

output = model(sample_input)

predictions = torch.argmax(output, dim=1)

print("Output shape:", output.shape)
print("Predictions:", predictions)
print("Seven-class SNN test successful!")
