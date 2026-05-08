import torch
print(f"PyTorch Version: {torch.__version__}")
print(f"CUDA verfügbar: {torch.cuda.is_available()}")
print(f"CUDA Version in Torch: {torch.version.cuda}")
print(f"Grafikkarte: {torch.cuda.get_device_name(0)}")