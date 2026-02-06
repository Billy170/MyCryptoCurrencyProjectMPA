try:
    import torch
except ModuleNotFoundError as exc:
    torch = None
    TORCH_IMPORT_ERROR = exc
else:
    TORCH_IMPORT_ERROR = None


def check_gpu():
    if torch is None:
        raise RuntimeError(
            "PyTorch is not installed for this Python version/environment. "
            "Install a compatible torch wheel (see requirements-gpu.txt) to enable GPU mining."
        ) from TORCH_IMPORT_ERROR
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA GPU required")
    props = torch.cuda.get_device_properties(0)
    vram = props.total_memory // (1024 * 1024)
    cores = props.multi_processor_count * 128
    if vram < 4096 or cores < 1350:
        raise RuntimeError("Minimum 4GB VRAM and 1350 CUDA cores required")
    return props.name, cores, vram
