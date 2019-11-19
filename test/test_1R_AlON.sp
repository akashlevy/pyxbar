.title <test_1R.sp>

** Model fitted to data from VLSI paper on N-doped AlOx RRAM **

** Load RRAM model **
.hdl ../models/rram_wp_paper.va

.option post=2
*.option converge=0
*.option RUNLVL=6
*.option METHOD=GEAR 
*.option INGOLD=1
.option accurate delmax=1e-8

** Sweep parameters **
.param vsweep_min=-2V vsweep_max=3V

** Create RRAM cell **
Xrram te gnd gap RRAM_v0 a0=0.4 tox=15 I0=3e-6 Beta=2.35 g0=0.175 V0=0.4 gamma0=14.5 Vel0=18

** Initialize RRAM cell
.ic gap 1.7

** Sweep voltage (bipolar mode) **
Vin te 0 PWL(0s 0V 100us vsweep_max 300us vsweep_min 400us 0V) R

** Generate butterfly curve **
.tran 0.01us 1600us
.probe PAR('abs(V(te)/I(Vin))') PAR('abs(I(Vin))')

.end
