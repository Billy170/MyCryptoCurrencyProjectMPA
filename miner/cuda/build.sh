#!/bin/bash
# Compile CUDA miner for Linux
nvcc mpa_ethash.cu main.cpp -o mpa_miner
echo "Build complete: mpa_miner"
