# -*- coding: utf-8 -*-
"""
 OpenFMR: run a frequency sweep and measure the output voltage
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
"""v

import time 
import numpy as np

import devices
import dsi

import pylab

   
dmm = devices.Keithley6500()
dmm.initialize('192.168.0.2', 5025)         

signalgenerator = dsi.SG30000PRO()
signalgenerator.initialize("COM8")

signalgenerator.set_temperaturecalibration(0) # output drift, but no jumps and hickups
 
# okay, let's try a little frequency sweep
start = 1e9
stop = 30e9
step = 0.25e9
frequencies = np.arange(start, stop+step, step)
voltages = np.zeros_like(frequencies)

signalgenerator.set_frequency(start)
signalgenerator.set_power(12)
signalgenerator.set_output(1)
signalgenerator.set_buzzer(0)


for i in range(frequencies.shape[0]):
    signalgenerator.set_frequency(frequencies[i])
    time.sleep(0.05)
    voltages[i] = dmm.get_measurement('VOLT:DC', 1., nplc=1, filterCount=4)

signalgenerator.set_buzzer(1)
signalgenerator.set_output(0)

pylab.plot(frequencies/1e9, -voltages)
pylab.xlabel("frequency (GHz)")
pylab.ylabel("detector diode voltage (V)")
pylab.yscale("log")

signalgenerator.close()
dmm.close()


