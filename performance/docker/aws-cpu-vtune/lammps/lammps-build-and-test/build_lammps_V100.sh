#!/bin/bash

# This is a build script for LAMMPS to test configurations on Lassen
# Before you run, please set the following variables
# - HOME_BASE: where LAMMPS will be git cloned, built and installed.
#              'make install' step is required as we're building using cmake.
# - MPICC: Set it to the C++ compiler on the system
# - Kokkos_ARCH_VOLTA70: Set this cmake flag to build for V100.
set -xe

HOME_BASE=/g/g92/marathe1/variorum/gpu-benchmarking/benchmarks/lgc-cap-bm/lammps_base
MPICC=mpicxx

LAMMPS_SRC="${HOME_BASE}/lammps_src"
INSTALL_PREFIX="${HOME_BASE}/install_V100"

# Clone just the stable branch of LAMMPS if not already cloned.
if [ ! -d ${LAMMPS_SRC} ]; then
    git clone --single-branch --branch stable https://github.com/lammps/lammps.git ${LAMMPS_SRC}
fi

# Enter the lammps directory.
cd ${LAMMPS_SRC}

# The build instructions have been verified for the following git sha.
# LAMMPS version - 23 June 2022 was tested (may be optional but will need to test it).
git checkout 7d5fc356fe

# Create the build dir .
if [ ! -d build_V100 ]; then
    mkdir build_V100
fi

# This assumes the build directory is empty
cd build_V100

# CMake build statement
cmake \
  -D CMAKE_INSTALL_PREFIX=${INSTALL_PREFIX} \
  -D Kokkos_ARCH_VOLTA70=ON \
  -D CMAKE_BUILD_TYPE=Release \
  -D MPI_CXX_COMPILER=mpicxx \
  -D BUILD_MPI=yes \
  -D CMAKE_CXX_COMPILER=$PWD/../lib/kokkos/bin/nvcc_wrapper \
  -D PKG_ML-SNAP=yes \
  -D PKG_GPU=no \
  -D PKG_KOKKOS=yes \
  -D Kokkos_ENABLE_CUDA=yes \
  ../cmake

# make && make install
make -j16
make install -j16
