# -*- coding: utf-8 -*-
"""
 OpenFMR: routine to calibrate the magnet for a simple interpolation
 Copyright (C) 2024  Markus Meinert, Tiago de Oliveira Schneider

 This program is free software: you can redistribute it and/or modify
 it under the terms of the GNU General Public License as published by
 the Free Software Foundation, either version 3 of the License, or
 (at your option) any later version.

 This program is distributed in the hope that it will be useful,
 but WITHOUT ANY WARRANTY; without even the implied warranty of
 MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 GNU General Public License for more details.

 You should have received a copy of the GNU General Public License
 along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

import numpy as np
import time
import devices
import pylab

class Field():
    def __init__(self):
        # magnet power supply
        self.Caenels = devices.CaenelsFastPS()
        # Teslameter remote control
        self.Teslameter = devices.MagnetPhysik_FH55()
        # Keithley DMM 6500 for analog readout of the Teslameter (faster!)
        self.dmm = devices.Keithley6500()


        self.Caenels.initialize("192.168.0.11", 10001, 3050) #1K5 30-50


        self.Teslameter.initialize("COM9")
        time.sleep(1)
        self.Teslameter.set_range(300e-3)
        time.sleep(1)
        self.teslameter_multiplier = 0.1

        self.dmm.initialize('192.168.0.20', 5025)
    
    
    def teslameter_set_range(self, fieldrange):
        if abs(fieldrange) <= 0.03:
            self.Teslameter.set_range(30e-3)
            time.sleep(1)
            self.teslameter_multiplier = 0.01
        elif abs(fieldrange) <= 0.3:
            self.Teslameter.set_range(300e-3)
            time.sleep(1)
            self.teslameter_multiplier = 0.1          
        else:
            self.Teslameter.set_range(3000e-3)
            time.sleep(1)
            self.teslameter_multiplier = 1.0
        return
    
    
    def teslameter_read_field(self):
        # use the Keithley DMM6500 to read the analog output of the teslameter
        v = self.dmm.get_measurement('VOLT:DC', 10.0, nplc=1, filterCount=4)
        v = v * self.teslameter_multiplier
        # nonlinearity correction for the FH55
        c = 1 - 0.065/3*np.abs(v)
        v = v*c
        return v
    
            
    def powersupply_output_on(self):
        self.Caenels.set_outputOn()
        return

    def powersupply_output_off(self):
        self.Caenels.set_outputOff()
        return    
    
    def powersupply_ramp_to_current(self, current, slewrate):
        self.Caenels.set_rampToCurrent(current, slewrate)
        return
    
    def close(self):
        self.Teslameter.close()
        self.dmm.close()
        self.Caenels.close()
        
        
class Calibrate():
    def __init__(self):
        self.field = Field()
        
    def hysteresis(self, IMax, NSteps, BRange):
        self.field.teslameter_set_range(BRange)
        I = np.linspace(-IMax, IMax, NSteps)
        I2 = np.concatenate([I, np.flipud(I)])
        B2 = np.zeros_like(I2)
        
        self.field.powersupply_output_on()
        self.field.powersupply_ramp_to_current(I2[0], 2)
        time.sleep(5)
        
        for i, j in enumerate(I2):
            self.field.powersupply_ramp_to_current(j, 1)
            time.sleep(0.5)
            b = self.field.teslameter_read_field()
            B2[i] = b
            print("%12.8f %12.8f" % (j, b))
        
        self.field.powersupply_ramp_to_current(0, 2)
        self.field.powersupply_output_off()
        
        return I2, B2

    def average(self, I2, B2):
        
        Ba = B2[0:len(B2)//2]
        Bb = B2[len(B2)//2:]
        
        Ia = I2[0:len(I2)//2]

        B = np.mean([Ba, np.flipud(Bb)], axis=0)
        I = Ia
        
        return I, B
        
            
if __name__ == "__main__":
    C = Calibrate()
    I2, B2 = C.hysteresis(30, 61, 3)
    I, B = C.average(I2, B2)
    
    # offset correction, subtract zero current field
    B = B - B[len(B)//2]
    
    C.field.close()
    
    pylab.plot(I2, B2, label="hysteresis")
    pylab.plot(I, B, label="average")
    pylab.xlabel("current (A)")
    pylab.ylabel("magnetic field (T)")
    pylab.legend()
    pylab.show()
    
    filename = "DXWD-80_5mm.xy"
    
    np.savetxt(filename, np.array([I, B]).T, fmt="%14.8f", delimiter=" ", header="%12s %14s" % ("current (A)", "field (T)"))

