# -*- coding: utf-8 -*-

"""
 OpenFMR: Data acquisition script.
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


import time 
import numpy as np

import devices

import pylab

import zipfile

import warnings
from scipy.interpolate import interp1d
import os

# physical constants
mu0 = 1.2566e-6
muB = 9.274e-24
h = 6.626e-34
e = 1.602e-19
me = 9.11e-31
            
class System():
    def __init__(self):

        self.signalgenerator = devices.SG30000PRO()
        self.signalgenerator.initialize("COM8")
        self.signalgenerator.set_temperaturecalibration(0) # must switch off to avoid jumps in the output

        self.mfli = devices.MFLI()
        self.mfli.initialize("192.168.0.16")  
        self.timeconstant_multiplier = 15 # multiply time constant with this number to allow for lock-in signal settling
    
        # with Kemo M032S amplifier
        self.modulation_volt_per_field = 100  #  100 mV_RMS / 1.0 mT_RMS @ 20mm gap | 423 Hz (phase shift approx 0°)
        self.modulator_frequency = 423  # Hz
        
        
    def lockin_read_XY(self):
        mfli_sample = self.mfli.getDemodSample(demodulators=(0))
        x, y = mfli_sample[0]['x'][0], mfli_sample[0]['y'][0]
        return x, y
    
    
    def lockin_settings(self, lowpass, frequency, output_voltage_rms, output):      
        self.mfli.setLowPassFilter(0, 4, lowpass)
        self.mfli.setOscillator(0, self.modulator_frequency)
        self.mfli.setOutputVoltage(output_voltage_rms, demod = 0, unit = 'Vrms')
        self.mfli.setOutputOn(output)
        
        
    def signalgenerator_settings(self, frequency, power, output):
        self.signalgenerator.set_power(power)
        self.signalgenerator.set_frequency(frequency)
        self.signalgenerator.set_output(output)


    def signalgenerator_power(self, frequency):
        # helper function to determine the best power as a function of frequency
        # you have to tune this, so that the diode detector voltage remains
        # approximately constant across all frequencies, while maxing out the power
        # at maximum frequency
        f0 = 1e9
        fmax = 30e9
        P0 = 0.5
        Pmax = 15
        
        P = P0 + (Pmax - P0) / (fmax - f0) * frequency
        # round to closest multiple of 0.5
        return round(P*2)/2
    
    
    def close(self):
        # only serial connections have to be closed, will block otherwise
        self.signalgenerator.close()
        

class Field():
    def __init__(self):
        
        # magnet power supply
        self.Caenels = devices.CaenelsFastPS()
        self.Caenels.initialize("192.168.0.11", 10001, 3050) #1K5 30-50
        
        # Teslameter remote control
        self.Teslameter = devices.MagnetPhysik_FH55()
        self.Teslameter.initialize("COM9")
        time.sleep(1)
        self.Teslameter.set_range(300e-3)
        time.sleep(1)
        self.teslameter_multiplier = 0.1
        
        # Keithley DMM 6500 for analog readout of the Teslameter (faster!)
        self.dmm = devices.Keithley6500()
        self.dmm.initialize('192.168.0.20', 5025)

        # magnet calibration file (can be changed from command line or script/GUI)
        self.calibration_file = "DXWD-80_20mm"
        #self.calibration_file = "DXWD-80_5mm"
    
    
    def get_current_from_field(self, field, kind='linear'):
        current_path = os.getcwd()
        data = np.loadtxt(current_path+'\\'+self.calibration_file+'.xy', unpack=True)
        i ,f = data
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            current_interp = interp1d(f, i, kind=kind)
            curr = current_interp(field,)
        return curr

    
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
    
    
    def teslameter_read_field_ac(self):
        self.Teslameter.set_mode("AC")
        time.sleep(1)
        self.teslameter_set_range(30e-3)
        time.sleep(1)
        v = self.Teslameter.get_singleFieldValue()
        self.Teslameter.set_mode("DC")
        time.sleep(1)
        return v
        
            
    def teslameter_set_acdc(self, mode):
        if mode in ["AC", "DC"]:
            self.Teslameter.set_mode(mode)
            time.sleep(1)
        return
            
    
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


class FMR():
    
    def __init__(self):
        self.system = System()
        self.field = Field()
        self.STOP = False
        
        
    def stop(self):
        print("\n\n STOP signal received! Stopping script execution.\n\n")
        self.STOP = True
        
        
    def kittel_resonance_field_ip(self, f, M, gamma_prime):
        return - mu0*M/2 + np.sqrt(mu0**2 * M**2 / 4 + f**2 / gamma_prime**2)
    
    
    def kittel_resonance_field_oop(self, f, M, gamma_prime):
        return abs(f / gamma_prime + mu0*M)
    
    
    def calc_B_range(self, B0, deltaB, multiplier=8, sampling=6, offset=0.0):
        start = B0 - multiplier*deltaB
        stop = B0 + multiplier*deltaB
        step = deltaB / sampling
        if start < 0.0:
            start = 0.0
        B = np.arange(start, stop+step, step) + offset
        return B
    
    
    def delta_B(self, f, alpha, deltaB0, gamma_prime):
        return alpha * f / gamma_prime + deltaB0    
    
        
    def complex_rotate_array(self, X, Y, phase):
        # phase in degrees!
        p = phase / 180 * np.pi
        C = X + 1j * Y
        r = complex( np.cos(p), np.sin(p) )
        V = r*C
        return V.real, V.imag
    
    
    def autophase(self, X, Y):
        # brute-force the phase to minimize the quadrature component (Y) over the full measurement
        PHI = np.linspace(-90,90,181)
        RMS = []
        for phi in PHI:
            X_, Y_ = self.complex_rotate_array(X, Y, phi)
            rms = np.sqrt(np.sum(Y_**2))
            RMS.append(rms)
        i = np.argmin(np.array(RMS))
        X_max, Y_min = self.complex_rotate_array(X, Y, PHI[i])
        print("\n\nAutophase correction: %i degree\n\n" % PHI[i])
        return X_max
    
    
    def get_offset(self):
        delay = 0.2
        B = np.linspace(-0.015, 0.015, 31)
        
        # get the corresponding magnet currents by interpolation
        X = np.array([self.field.get_current_from_field(b) for b in B])
        dX = np.mean(np.abs(X[1:] - X[:-1]))
        
        fields = np.zeros_like(B)
        
        print("\nOFFSET MEASUREMENT\n")
        
        print("Minimum field: %.4fT | Maximum field: %.4fT | Field step: %.5fT" % (min(B), max(B), (max(B) - min(B))/(len(B)-1)))
        print()
        
        print("Setting Teslameter to 300mT.")
        self.field.teslameter_set_range(300e-3)
        
        print("Beginning measurement...")
        
        print(" Ramp to initial field...")
        
        self.field.powersupply_output_on()
        self.field.powersupply_ramp_to_current(X[0], 0.5)
        time.sleep(1.0)
        _ = self.field.teslameter_read_field()
    
    
        for i in range(B.shape[0]):
            if self.STOP:
                break
            self.field.powersupply_ramp_to_current(X[i], dX/(.1*delay))
            time.sleep(.9*delay)
            fields[i] = self.field.teslameter_read_field()
    
            print("\r Field nominal: %8.5fT  | Field actual: %8.5fT | Progress: %5.1f%%" % (B[i], fields[i], i/B.shape[0]*100), end="")
    
        print("\nDone.")
        print()
    
        self.field.powersupply_ramp_to_current(0, 0.5)
        self.field.powersupply_output_off()
    
        
        p = np.polyfit(B[2:], fields[2:], 1)
        
        print("Offset: %8.5fT" % (-p[1]))
        
        return -p[1]
    
    
    def field_sweep(self, f, M, alpha, g, deltaB0, mode="ip", rampdown=True, offset=0.0, lowpass=0.05, delay=0.1, accuracy="fine", GUI=False):
        # estimate \gamma' from sample estimates
        gamma_prime = g*e/(2*me) / (2*np.pi)
        
        if accuracy == "low":
            multiplier, sampling = 12, 4
        elif accuracy == "medium":
            multiplier, sampling = 8, 6
        elif accuracy == "high":
            multiplier, sampling = 6, 8
        else:
            raise ValueError("Accuracy not recognized. Must be 'low', 'medium', or 'high'.")
        
        if mode == "ip":
            B0 = self.kittel_resonance_field_ip(f, M, gamma_prime)
        elif mode == "oop":
            B0 = self.kittel_resonance_field_oop(f, M, gamma_prime)
            
        print("\n\nExpected resonance field: %8.4f T \n\n " % B0)
        
        if B0 > 0.3:
            offset = 0
            print("High-field (>0.3T) measurement, disabling offset correction.\n\n")
            
        B = self.calc_B_range(B0, self.delta_B(f, alpha, deltaB0, gamma_prime), multiplier=multiplier, sampling=sampling, offset=offset)
        
        # get the corresponding magnet currents by interpolation
        X = np.array([self.field.get_current_from_field(b) for b in B])

        dX = np.mean(np.abs(X[1:] - X[:-1]))
        
        voltages = np.zeros_like(B)
        VX = np.zeros_like(B)
        VY = np.zeros_like(B)
        fields = np.zeros_like(B)
        times = np.zeros_like(B)
        
        print("Minimum field: %.4fT | Maximum field: %.4fT | Field step: %.5fT" % (min(B), max(B), (max(B) - min(B))/(len(B)-1)))
        
        print()
        print("Checking Teslameter range...")
        B_absmax = max(abs(min(B)), abs(max(B)))
        if B_absmax > 0.25:
            print("  Set to 3T.")
            self.field.teslameter_set_range(3000e-3)
        else:
            print("  Set to 300mT.")
            self.field.teslameter_set_range(300e-3)
        
        print()
        print("Beginning measurement...")
        
        print("Ramp to initial field...")
        
        self.field.powersupply_output_on()
        self.field.powersupply_ramp_to_current(X[0], 0.5)
        time.sleep(2.0)
        _ = self.field.teslameter_read_field()

        if GUI:
            print("\n<NEW_MEASUREMENT>\n")
        
        starttime = time.time()
        for i in range(B.shape[0]):
            if self.STOP:
                rampdown = True
                break
            
            self.field.powersupply_ramp_to_current(X[i], dX/(.2*delay))
            time.sleep(.8 * delay)

            time.sleep(lowpass * self.system.timeconstant_multiplier)

            fields[i] = self.field.teslameter_read_field()

            x, y = self.system.lockin_read_XY()
            VX[i] = x
            VY[i] = y
            if GUI:
                print("\r<> Field: %8.5f T  | X: %12.8f V | Y: %12.8f V | Progress: %5.1f%% </>" % (fields[i], x, y, i/B.shape[0]*100), end="")
            else:
                print("\r Field: %8.5f T  | X: %12.8f V | Y: %12.8f V | Progress: %5.1f%% " % (fields[i], x, y, i/B.shape[0]*100), end="")
                
            times[i] = time.time()
    
        voltages = self.autophase(VX, VY)
    
        print("\nDone.")
        endtime = time.time()
        print()
        
        time.sleep(0.5)
        
        if rampdown:
            self.field.powersupply_ramp_to_current(0, 0.5)
            self.field.powersupply_output_off()
    
        timing = endtime - starttime
        
        time_diffs = times[1:] - times[0:-1]
        time_per_step_avg = np.average(time_diffs)
        time_per_step_med = np.median(time_diffs)
        time_per_step_sdev = np.std(time_diffs)
        time_per_step_max = np.max(time_diffs)
        time_per_step_min = np.min(time_diffs)
        
        print()
        print("Measurement loop timing : %.2fs" % timing)
        print("  Time per step avg     : %.4fs" % time_per_step_avg)
        print("  Time per step median  : %.4fs" % time_per_step_med)
        print("  Time per step sdev    : %.4fs" % time_per_step_sdev)
        print("  Time per step min     : %.4fs" % time_per_step_min)
        print("  Time per step max     : %.4fs" % time_per_step_max)
        print()
        
        return fields, voltages
    
    
    def writedatafile(self, zipfilename, filename, fields, voltages):
        string = ""
        for f, v in zip(fields, voltages):
            string += "%14.10f %14.10f\n" % (f, v)
            
        zf = zipfile.ZipFile(zipfilename + ".zip", mode="a")    
    
        zf.writestr(filename, string)
    
        zf.close()
        return
    
    
    def fmr_measurement(self, zipfilename, M, alpha, g, deltaB0, magnet="DXWD-80_20mm", mode="ip", accuracy="medium", delay=0.25, modulation_field_rms=5e-4, lowpass=10e-3, freqmin=2.5e9, freqstep=2.5e9, freqmax=30e9, GUI=False):

        self.field.magnet = magnet        
        output_voltage_rms = modulation_field_rms * self.system.modulation_volt_per_field


        if not self.STOP:
            offset = self.get_offset()

        if not self.STOP:
            initial_delay = 5
            
            print("\nFMR MEASUREMENT\n")
            
            print("Selected magnet: %s" % magnet)
            print("Selected mode: %s" % mode)
            print()
            
            self.field.calibration_file = magnet
            
            frequencies = np.arange(freqmin, freqmax+1, freqstep)
            print("Frequencies (GHz):")
            print(frequencies/1e9)
            
            datasets = []
        
            power = self.system.signalgenerator_power(frequencies[0])
            self.system.signalgenerator_settings(frequencies[0], power, 1)
            
            
            self.system.lockin_settings(lowpass, self.system.modulator_frequency, output_voltage_rms, 1)
            
            print("Outputs on, wait %is." % initial_delay)
            time.sleep(initial_delay)

        if not self.STOP:
            
            print("\nMeasuring modulation field...")
            Brms = self.field.teslameter_read_field_ac()
            print("  modulation field (RMS) : %6.2f mT\n" % (Brms*1000))
            time.sleep(2)
        
        if not self.STOP:
            for f in frequencies:
                if self.STOP:
                    break
                print("\nFrequency: %.2fGHz\n" % (f * 1e-9))
                power = self.system.signalgenerator_power(f)
                self.system.signalgenerator_settings(f, power, 1)
                
                
                fields, voltages = self.field_sweep(f, M, alpha, g, deltaB0, mode=mode, rampdown=False, offset=offset, lowpass=lowpass, delay=delay, accuracy=accuracy, GUI=GUI)
                
                datasets.append([fields, voltages])
                
                filename = "%.2fGHz.txt" % (f * 1e-9)
                self.writedatafile(zipfilename, filename, fields, voltages)
                
                if not GUI:
                    pylab.plot(fields, voltages, label=filename)
                    pylab.legend()
                    pylab.show()
        
        # graceful shutdown
        
        print("\n Ramp field down to zero.")
        self.field.powersupply_ramp_to_current(0, 1)
        
        print("\nRF output off.")
        self.system.signalgenerator.set_output(0)
        self.system.signalgenerator_settings(10e9, 0, 0)

        self.system.lockin_settings(lowpass, self.system.modulator_frequency, output_voltage_rms, 0)
        
        self.field.close()
        self.system.close()
        
        if not self.STOP:
            for i in range(len(frequencies)):
                fields, voltages = datasets[i]
                if not GUI:
                    pylab.plot(fields, voltages, label="%5.2fGHz" % (frequencies[i]/1e9))
            
            if not GUI:
                pylab.legend()
                pylab.xlabel("magnetic field (T)")
                pylab.ylabel("detector diode derivative signal (arb. u.)")
                pylab.show()


if __name__ == "__main__":
    
    zipfilename = "testsample"

    # sample estimates
    
    Meff = 1000e3
    alpha = 0.006
    g = 2.1
    deltaB0 = 0.001
    
    # measurement parameters
    
    mode = "ip" # or "oop"
    accuracy='low' # or 'medium' or 'high' 
    
    freqmin = 2.5e9
    freqmax = 30.0e9
    freqstep = 2.5e9
    
    lowpass = 20e-3
    
    delay=0.25
    
    modulation_field_rms = 1.0e-3
    
    # run the measurement
    fmr = FMR()
    fmr.fmr_measurement(zipfilename, Meff, alpha, g, deltaB0, mode=mode, accuracy=accuracy, delay=delay, \
                    modulation_field_rms=modulation_field_rms, lowpass=lowpass, \
                        freqmin=freqmin, freqstep=freqstep, freqmax=freqmax)


