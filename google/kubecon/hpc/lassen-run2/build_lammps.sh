#!/bin/bash

git clone --depth 1 --branch stable_29Sep2021_update2 https://github.com/lammps/lammps.git
cd ./lammps
mkdir build bin
cd build
cmake ../cmake -DCMAKE_INSTALL_PREFIX:PATH=../bin -DPKG_REAXFF=yes -DBUILD_MPI=yes -DPKG_OPT=yes -DFFT=FFTW3 
make
make install
