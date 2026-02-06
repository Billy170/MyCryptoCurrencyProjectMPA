import torch

def check_gpu():
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA GPU required")
    props = torch.cuda.get_device_properties(0)
    vram = props.total_memory // (1024*1024)
    cores = props.multi_processor_count * 128
    if vram < 4096 or cores < 1350:
        raise RuntimeError("Minimum 4GB VRAM and 1350 CUDA cores required")
    return props.name, cores, vram
