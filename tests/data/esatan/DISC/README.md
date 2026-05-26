# ESATAN model of a disc in a spherical enclosure

## GMM
The geometry is "DISC.erg". The model is a 10 x 10 nodes disc of Delrin with a thickness of 10 mm and 100 mm radius. The disc and the enclosure have an emissivity of 0.4. So basically, the GR matrix is fully populated. 

## TMM
The TMMs are fully defined in the .d files. There are two .d files. The model is the same in both, one is a steady state analysis and the other is a transient one.

- DISCTR_STEADY
    - Steady-state analysis. 10 W dissipated in a middle ring of the disc. All the heat is dissipated to the radiative boundary condition, which is at -10 degC.
    - RELXCA set to 1.0E-10, so the discrepancy between pycanha and ESATAN should only be due to the precission set at the pycanha side
    - Stephan-Boltwmann constant redefined in ESATAN to match the one used in pycanha.
    - The DISCTR_STEADY.TMD has the model with the ESATAN calculated temperatures. 

- DISCTR_TRANSIENT
    - Transient analysis (SLCRNC). Starting with everything at -10 degC, 10 W are dissipated in a middle ring of the disc (same as in the steady-state). All the heat is dissipated to the radiative boundary condition, which is at -10 degC.
    - RELXCA set to 1.0E-10, so the discrepancy between pycanha and ESATAN should only be due to the precission set at the pycanha side
    - Stephan-Boltwmann constant redefined in ESATAN to match the one used in pycanha.
    - TIMEND = 10000.0
    - DTIMEI = 1.0
    - OUTINT = 100.0
    - The DISCTR_TRANSIENT.TMD has the model with the ESATAN calculated temperatures. 