@echo off
REM Compile CUDA miner for Windows
nvcc mpa_ethash.cu main.cpp -o mpa_miner.exe
echo Build complete: mpa_miner.exe
pause