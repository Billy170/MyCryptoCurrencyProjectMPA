#include <cuda_runtime.h>
#include <iostream>
extern void mpa_ethash_shared(const uint32_t*, uint32_t, uint64_t, uint32_t*);
int main(){
    const uint32_t DAG_SIZE = 256*1024*1024;
    uint32_t *d_dag, *d_out;
    cudaMalloc(&d_dag,DAG_SIZE*sizeof(uint32_t));
    cudaMalloc(&d_out,1024*sizeof(uint32_t));
    int threads=256; int blocks=80; size_t shared=threads*sizeof(uint32_t);
    mpa_ethash_shared<<<blocks,threads,shared>>>(d_dag,DAG_SIZE,0,d_out);
    cudaDeviceSynchronize();
    std::cout<<"MPA GPU kernel executed\n";
}
