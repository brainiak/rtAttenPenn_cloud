# rtAttenPenn

## Overview:
This project is to port the matlab version of rtAttenPenn (the real-time attention fMRI study) to python.

## Process:
We will start with the existing matlab code and incrementally convert portions to python (python can be called from Matlab and vice versa). We will also have a testing framework which will run to compare to an original expected_output generated from the original matlab version. Then continue incrementally converting to python and validating the output for each change.

## Running:
Initial Matlab version:
<path_to_matlab>/bin/matlab -nodisplay -nosplash -nodesktop -nojvm -r RealTimePunisherFileProcess

## Data Dirs:
The code expects a data/ directory
- data/input  -- holds necessary input files like the mask
- data/output -- receives output files from the run
  - data/patternsdata* -- initial patterns
- data/expected_output -- the data files that should be generated by a correct run

## Issues
- Parallelize ```highpass.pyx```
- MATLAB to use virtualenv python
- Figure out how to automatically pull in Python changes when running from MATLAB
- ~~Make highpass.py much faster~~
