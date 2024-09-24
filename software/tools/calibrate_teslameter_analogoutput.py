# -*- coding: utf-8 -*-

"""
 OpenFMR: calibrate the analog output of the MagnetPhysik FH55 gaussmeter
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
    
    
    def teslameter_read_field_analog(self):
        # use the Keithley DMM6500 to read the analog output of the teslameter
        v = self.dmm.get_measurement('VOLT:DC', 10.0, nplc=1, filterCount=4)
        return v * self.teslameter_multiplier  
    
    def teslameter_read_field_digital(self):
        v = self.Teslameter.get_singleFieldValue()
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
        
    def sweep(self, IMax, NSteps, BRange):
        self.field.teslameter_set_range(BRange)
        I = np.linspace(-IMax, IMax, NSteps)
        BA = np.zeros_like(I)
        BD = np.zeros_like(I)
        
        
        self.field.powersupply_output_on()
        self.field.powersupply_ramp_to_current(I[0], 2)
        time.sleep(5)
        
        for i, j in enumerate(I):
            self.field.powersupply_ramp_to_current(j, 1)
            time.sleep(1.0)
            ba = self.field.teslameter_read_field_analog()
            BA[i] = ba
            bd = self.field.teslameter_read_field_digital()
            BD[i] = bd
            print("%12.8f %12.8f %12.8f" % (j, ba, bd))
        
        self.field.powersupply_ramp_to_current(0, 2)
        self.field.powersupply_output_off()
        
        return I, BA, BD

        
            
if __name__ == "__main__":
    C = Calibrate()
    I, BA, BD = C.sweep(30, 61, 3)
    
    # offset correction, subtract zero current field
    #B = B - B[len(B)//2]
    
    C.field.close()
    
    pylab.plot(BD, BA, label="A(D)")
    pylab.xlabel("digital reading (T)")
    pylab.ylabel("analog reading (T)")
    pylab.legend()
    pylab.show()
    
    R = BD / BA
    
    pylab.plot(BD, R, label="D/A")
    pylab.xlabel("digital reading (T)")
    pylab.ylabel("D/A ratio")
    pylab.legend()
    pylab.show()
    
    filename = "FH55.xy"
    
    #np.savetxt(filename, np.array([I, B]).T, fmt="%14.8f", delimiter=" ", header="%12s %14s" % ("current (A)", "field (T)"))

