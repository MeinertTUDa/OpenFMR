# OpenFMR
Open Ferromagnetic Resonance Broadband Spectrometer

The OpenFMR system enables broadband ferromagnetic resonance measurements with relatively cheap off-the-shelf components. It is capable of measuring the FMR of thin films as thin as 1nm of CoFeB and maybe even less.

![setup](https://github.com/user-attachments/assets/59dd475f-b8d3-4a38-b9b1-059cbb78c223)

To assemble the system, you will have to get suitable hardware components, make some 3D prints, send the PCB layout files for production to obtain the grounded coplanar waveguide, and install the Python software on your computer. The software in this repository is optimized for usage with the following components:

- DS Instruments SG30000PRO RF signal generator
- Krytar 203BK Schottky detector
- Thorlabs KMM24 cables
- WithWave 2.92mm End Launch Connectors (Narrow Block)
- Zurich Instruments MFLI Lock-in Amplifier
- CAENels FAST-PS 1k5 50V 30A bipolar power supply
- Xiamen Dexing Magnet Tech DXWD-80 C-frame magnet
- Magnet-Physik FH55 gaussmeter
- 0.2mm wire (10m) for the modulation coils
- Kemo M032S audio amplifier for the modulation coils

The document Supplemental Material.pdf in the preprint folder contains a list of viable alternatives for the various components. In our design, the lock-in amplifier and the bipolar power supply for the electromagnet are two somewhat costly devices. These can be replaced with cheaper alternatives, such as a unipolar power supply for the magnet. The software will require modifications accordingly, which should be straightforward, though.


## Grounded Coplanar Waveguide
![GCPW](https://github.com/user-attachments/assets/1494eb1d-11bd-4152-9d6b-fb0694fe8716)
The grounded coplanar waveguide is manufactured on a 200µm Rogers 4003C prepreg substrate. The manufacturing process should be performed as follows:
- attach to 1mm FR4 support
- mill the contour
- drill the blind via holes
- deposit copper
- etch the waveguide
- immersion tin surface finish (no Ni/Au plating!)

## Modulation Coils
![modulation_coils](https://github.com/user-attachments/assets/85482b52-3020-4d32-b007-3f6006c4cf32)
The modulation coils need a support structure, which we create by 3D printing. There are two different designs available, for in-plane and out-of-plane measurements, respectively. The 0.2mm copper magnet wire (10m long) is wound by hand onto the support structure and connected to stronger cables via screw terminals, which are mounted with M2 threaded inserts into the support structure. These are clamped between the tapered poles, which are supposed to have a 30mm pole cap diameter. For other pole shapes, the designs may have to be adapted or made from scratch. All 3D designs are available as Autodesk Inventor files.

A stand for the GCPW is also available as a 3D print. This will require modification with a different magnet. 

## Python Software
![OpenFMR_GUI](https://github.com/user-attachments/assets/14840879-f4bb-474f-bf24-6616761397e6)
The python based software requires a number of modules to work. It is advisable to use a recent version of the Anaconda package. The following modules have to be installed:
- PyQt5
- pyqtgraph
- zipfile
- numpy
- scipy
- matplotlib / pylab
- fnmatch
- pyserial
- zhinst

Set the device ports in fmr.py, the MFLI and the FastPS have IP interfaces, the SG30000PRO has a serial interface. It is advisable to run the IP devices on a separate network with a router or a switch and use static IP addresses. Correspondingly, the PC should be equipped with two networking interfaces.

Once the hardware is set up, a calibration file has to be obtained for the magnet, which relates the magnet current to the measured magnetic field in the pole gap. Use the calibrate_magnet.py script in the tools folder. Once this is done for both the in-plane and the out-of-plane modulation coils, you should be able to perform your first measurements!

![OpenFMR_Data_Analysis](https://github.com/user-attachments/assets/59f50b8b-adac-486d-97d7-9ec7de8aeb8b)

The data analysis software runs independently and requires a smaller number of dependencies. This can be run by the users on their personal computers. Measured data is stored in zip files, which also contain the analysis results. The data within the zip file container are easily accessible text files.
