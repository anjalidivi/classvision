
import torch
import torch.nn as nn
import snntorch as snn
from snntorch import surrogate


class ClassroomSNN(nn.Module):

    def __init__(self, time_steps=10, num_classes=7):

        super().__init__()

        self.time_steps = time_steps

        beta = 0.9
        spike_grad = surrogate.fast_sigmoid()

        # ----------------------------------
        # CNN FEATURE EXTRACTION - BLOCK 1
        # ----------------------------------

        self.conv1 = nn.Conv2d(
            3, 32, kernel_size=3, padding=1
        )

        self.bn1 = nn.BatchNorm2d(32)

        self.pool1 = nn.MaxPool2d(2)

        self.lif1 = snn.Leaky(
            beta=beta,
            spike_grad=spike_grad
        )

        # ----------------------------------
        # CNN FEATURE EXTRACTION - BLOCK 2
        # ----------------------------------

        self.conv2 = nn.Conv2d(
            32, 64, kernel_size=3, padding=1
        )

        self.bn2 = nn.BatchNorm2d(64)

        self.pool2 = nn.MaxPool2d(2)

        self.lif2 = snn.Leaky(
            beta=beta,
            spike_grad=spike_grad
        )

        # ----------------------------------
        # CNN FEATURE EXTRACTION - BLOCK 3
        # ----------------------------------

        self.conv3 = nn.Conv2d(
            64, 128, kernel_size=3, padding=1
        )

        self.bn3 = nn.BatchNorm2d(128)

        self.pool3 = nn.AdaptiveAvgPool2d((4, 4))

        self.lif3 = snn.Leaky(
            beta=beta,
            spike_grad=spike_grad
        )

        # ----------------------------------
        # CLASSIFICATION LAYERS
        # ----------------------------------

        self.flatten = nn.Flatten()

        self.fc1 = nn.Linear(
            128 * 4 * 4,
            256
        )

        self.dropout = nn.Dropout(0.4)

        self.lif4 = snn.Leaky(
            beta=beta,
            spike_grad=spike_grad
        )

        self.fc2 = nn.Linear(
            256,
            num_classes
        )

    # ----------------------------------
    # FORWARD PASS
    # ----------------------------------

    def forward(self, x):

        mem1 = self.lif1.init_leaky()
        mem2 = self.lif2.init_leaky()
        mem3 = self.lif3.init_leaky()
        mem4 = self.lif4.init_leaky()

        output_membrane = []

        for step in range(self.time_steps):

            # Block 1

            current1 = self.conv1(x)
            current1 = self.bn1(current1)
            current1 = self.pool1(current1)

            spk1, mem1 = self.lif1(
                current1,
                mem1
            )

            # Block 2

            current2 = self.conv2(spk1)
            current2 = self.bn2(current2)
            current2 = self.pool2(current2)

            spk2, mem2 = self.lif2(
                current2,
                mem2
            )

            # Block 3

            current3 = self.conv3(spk2)
            current3 = self.bn3(current3)
            current3 = self.pool3(current3)

            spk3, mem3 = self.lif3(
                current3,
                mem3
            )

            # Classification

            flattened = self.flatten(spk3)

            current4 = self.fc1(flattened)

            current4 = self.dropout(current4)

            spk4, mem4 = self.lif4(
                current4,
                mem4
            )

            output = self.fc2(spk4)

            output_membrane.append(output)

        # Accumulate output over simulation steps.

        return torch.stack(
            output_membrane
        ).mean(dim=0)
