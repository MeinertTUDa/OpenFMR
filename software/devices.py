# -*- coding: utf-8 -*-
"""
 OpenFMR: Device controls.
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
import serial
import socket
import re
import os
import zhinst.ziPython as ziPython
import zhinst.utils as ut
import math

        
class SG30000PRO:
    def __init__(self):
        self.deviceport = None
        self.device = None
        self.delay_short = None
        self.delay_long = None
        self.freq = None
        self.power = None
        self.output = None
        
        # response if a command failed (b makes it into bytes)
        self.badCommandResponse = b'[BADCOMMAND]\r\n' 
           
    def initialize(self, port):
        self.delay_short = 0.01
        self.delay_long = 0.2
        self.deviceport = port
        self.device = serial.Serial("COM8", 115200, timeout=1)
    
    def reset(self):
        print("Resetting the SG30000PRO generator. This takes approximately 10s.")
        self.device.write(b'*RST\n')
        time.sleep(10)
        _ = self.device.readline()
        self.freq = self.get_frequency()
        self.power = self.get_power()
        self.output = self.get_output()
    
    def close(self):
        self.set_output(0)
        self.device.close()
        
    def get_frequency(self):
        self.device.write(b'FREQ:CW?\n')
        time.sleep(self.delay_short)
        response = self.device.readline() 
        if response == self.badCommandResponse:
            return ValueError('Command failed.')
        freq = int(response.decode().replace('HZ\r\n', ''))
        return freq
    
    def set_frequency(self, freq):
        # supply the frequency in Hz!
        # convert to MHz
        freq = int(freq * 1e-6)
        self.device.write(b'FREQ:CW %iMHZ\n' % freq)
        time.sleep(self.delay_short)
  
        
    def get_power(self):
        self.device.write(b'POWER?\n')
        time.sleep(self.delay_short)
        response = self.device.readline() 
        if response == self.badCommandResponse:
            return ValueError('Command failed.')
        
        power = float(response.decode().replace('dBm\r\n', ''))
        return power  

    def set_power(self, power):
        # supply the frequency in dBm
        self.device.write(b'POWER %.2f\n' % power)
        time.sleep(self.delay_long)
        
    def get_output(self):
        self.device.write(b'OUTP:STAT?\n')
        time.sleep(self.delay_short)
        response = self.device.readline() 
        if response == self.badCommandResponse:
            return ValueError('Command failed.')
        
        output = response.decode().replace('\r\n', '')
        if output == "OFF":
            return 0
        elif output == "ON":
            return 1
        else:
            return ValueError("Output error.")
        
    def set_output(self, output):
        if output == 0:
            self.device.write(b'OUTP:STAT OFF\n')
        elif output == 1:
            self.device.write(b'OUTP:STAT ON\n')
        else:
            return ValueError("Output value must be 0 (off) or 1 (on).")
        time.sleep(self.delay_long)
        
    def set_buzzer(self, status):
        if status == 0:
            self.device.write(b'*BUZZER OFF\n')
        elif status == 1:
            self.device.write(b'*BUZZER ON\n')
        else:
            return ValueError("Output value must be 0 (off) or 1 (on).")
        time.sleep(self.delay_long)
        
    def set_temperaturecalibration(self, status):
        if status == 0:
            self.device.write(b'CALTEMP OFF\n')
        elif status == 1:
            self.device.write(b'CALTEMP ON\n')
        else:
            return ValueError("Output value must be 0 (off) or 1 (on).")
        time.sleep(self.delay_long)                  
        
        
class Keithley6500:
    def __init__(self):
        self.deviceport = None
        self.device = None
        self.nplc = None
        self.time_to_wait_in_s = None
        self.filterCount= None
        self.delay = None
        self.function = None
        self.rangE = None
        
    def initialize(self, ip, port):
        """
        defines the device\n

        Parameters
        ----------\n
        ip : String
            "192.168.0.12"
        port : integer
            

        Returns
        -------
        None.
        """
        self.time_to_wait_in_s = 0.0002
        self.max_nplc = 12.
        self.min_nplc = 1e-4
        try:
            self.device = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server_address = (ip, port)
            self.device.connect(server_address)
            self.device.settimeout(1)
            self.reset('all')
        except: print(__class__.__name__,'.initialize(), problem with connecting')

    def reset(self, option):
        try:
            if option not in ["device","variables","all"]: raise ValueError('option only ["device","variables","all"]')
            if option == 'all': option = ["device","variables"]
            if 'device' in option: 
                self.__send('*RST')
                self.__send(':FORMat:ASCii:PRECision MAX')
            if 'variables' in option:
                self.nplc = None
                self.filterCount = None
                self.delay = None
                self.function = None
                self.rangE = None
        except ValueError as e: print(__class__.__name__,'.reset(), invalid input param, ',e)
        except: print(__class__.__name__,'.reset(), problems resetting the device')
            
        
    def close(self):
        try:
            self.__send('TRIG:CONT REST')
            self.device.close()
        except: print(__class__.__name__,'.close(), problem with closing')

    def __send(self, string):
        try:
            s = string + "\n"
            self.device.send(s.encode())
            time.sleep(self.time_to_wait_in_s)
        except: print(__class__.__name__,'.__send(), problem with sending the command '+s)

    def get_measurement(self, function,expectedValue, nplc=0.1, filterCount=0, filterFunction='REP', delay = 'ON', autozero = 'ON'):
        """ This method returns a measurement, one shot\n

        Parameters
        ----------\n
        function : String
            "VOLT:DC" -DC Voltage\n
            "VOLT:AC" -AC Voltage\n
            "CURR:DC" -DC Current\n
            "CURR:AC" -AC Current\n
            "RES" - Resistance
        nplc : float
            1e-4 .. 12
            e.g. nplc=1 -> 20ms(@50Hz)
            from 1.-5. best SNR
        filterCount:int
            0 - turns off the filter\n
            >0 - turns the filter on and set the count of the Filter.
        delay: String
            "OFF" - no Autodelay\n
            "ON" - Autodelay
        filterFunction: String
            'MOV' Moving average
            'REP' repetition
        Returns
        -------
        float
            value.

        """
        try:
            if (filterFunction not in ['REP', 'MOV', 'HYBR']): raise ValueError('filterFunction must be MOV, HYBR or REP')
            if (function not in ["VOLT:DC","VOLT:AC","CURR:DC", "CURR:AC", "RES"]): raise ValueError('ACDC must be "AC" or "DC"')
            if (function[-2:]!="AC"):
                if (float(nplc)<self.min_nplc) or (float(nplc)>self.max_nplc): raise ValueError('nplc must be in range 1e-4 .. 12"')
            if delay not in ["OFF","ON"]: raise ValueError('delay must be ON or OFF')
            
            if (self.function != function):
                self.reset('variables')# If the function doesnt match, all variables have to be set again
                self.function = function
                self.__send('SENSe:FUNCtion "{func}"'.format(func=function))
            if (self.nplc != nplc) and (function[-2:]!="AC"):
                self.__send('SENSe:{func}:NPLCycles {npl}'.format(func=function, npl=nplc))
                self.nplc = nplc
            if self.filterCount != int(filterCount):
                if int(filterCount) == 0:
                    self.__send('SENSe:{func}:AVERage OFF'.format(func=function))
                elif int(filterCount) != 0:
                    self.__send('SENSe:{func}:AVER:COUNT {nbr}'.format(func=function,nbr=filterCount))
                    self.__send('SENSe:{func}:AVER:TCON {filterfunc}'.format(func=function, filterfunc=filterFunction)) #TCON MOV REP
                    self.__send('SENSe:{func}:AVER ON'.format(func=function))
                    if (function[-2:]!="AC"):
                        self.__send('SENSe:{func}:AZER {Azer}'.format(func=function, Azer=autozero))
                self.filterCount = filterCount
            if self.delay != delay:
                self.delay = delay
                self.__send('SENSe:{func}:DELay:AUTO {dela}'.format(func=function,dela=delay))
            if self.rangE != expectedValue:
                self.rangE = expectedValue
                self.__send('SENSe:{func}:RANGe {rang}'.format(func=function,rang=expectedValue))
            self.i = 5 #try 3 times to read data
            return self.__scan()
        except ValueError as e: print(__class__.__name__,'.get_measurement(), invalid input param, ',e)
        except: print(__class__.__name__,'.get_measurement(), problem with reading the voltage')
    
        
      
    def __scan(self):
        try:
            self.__send(':READ?')
            if(self.nplc>1.):
                response = self.__read(self.nplc*.02+0.05)
            else:
                response = self.__read(self.nplc*(self.time_to_wait_in_s))
            
            #print('Hier bin ich',str(response))
            response = response.decode()
            a = self.__convertStrToFloat(response.rstrip())
            #print(a)
            return a
        except Exception as e: 
            print(__class__.__name__,'.__scan(), problem with scanning ',e)
            
    def __read(self, t_wait):
        try:
            self.i = self.i-1
            response = self.device.recv(1024)
            time.sleep(t_wait)
            if response is not None: 
                #print('abc ',response)
                return response
        except:
            if (self.i > 0): 
                self.__read(t_wait)
            

        

    def __convertStrToFloat(self, string):
        ''' extracts the floats of strings. If the string has two floats the first is the Mantisse and the second the exponent to the base of 10\n
        Parameters
        ----------\n
        string : string
            the input string.
        Returns
        -------
        temp : float
            the extracted float of the string

        '''
        temp = [float(s) for s in re.findall(r'-?\d+\.?\d*', string)]
        if len(temp)>1:
            temp = float(str(temp[0])+'e'+str(int(temp[1])))
        elif len(temp)==1:
            temp = float(temp[0])
        return temp
    


class MFLI:
    def __init__(self):
        self.deviceport    = None
        self.deviceid      = 'dev4580'
        self.settings_path = 'C:/Users/schneider/Documents/MasterarbeitDeOliveira/Python/fertigeModule/mfli_settings/'
        self.device        = None
        
    def initialize(self, deviceAdress):
        self.device        = ziPython.ziDAQServer(deviceAdress, 8004, 1)#maybe 80
    
    def listSettings(self):
        SettingsList = os.listdir(self.settings_path)
        SettingsList = [ 4 * ' ' + filename for filename in SettingsList if filename.endswith('.xml')]
        print(*SettingsList, sep = '\n')
        
    def loadSettings(self,filename):
        # load settings from filename into the device
        try:
            ut.load_settings( self.device, self.deviceid, self.settings_path + filename)
        except RuntimeError:
            print('The settings-file \"' + filename + '\" does not exist. Please select one of the following:')
            print('')
            self.listSettings()

    def saveSettings(self,filename):
        # save settings from the device to filename
        try:
            ut.save_settings( self.device, self.deviceid, self.settings_path + filename)
        except RuntimeError:
            print('Error: probably a bad filename')

    def getDemodSample(self, demodulators = (0,1,2,3)):
        result = {}            
        try:
            len(demodulators)
        except:
            demodulators = [demodulators]
            
        for i in demodulators:
            result[i] = self.device.getSample('/%s/demods/%i/sample' % (self.deviceid, i))
        return result
    
    def getOutputVoltage(self, demod, unit = 'Vrms'):
        if unit not in ['Vrms','Vpk']:
            raise ValueError('Voltage unit not recognized. Use \"Vrms\" or \"Vpk\"')
            
        voltage = self.device.getDouble('/%s/sigouts/0/amplitudes/%i' % (self.deviceid, demod))
        
        if unit == 'Vrms':
            amplitude = voltage / math.sqrt(2)
        else:
            amplitude = voltage
        
        return amplitude
    
    def getAuxOutVoltage(self, output):
        voltage = self.device.getDouble('/%s/auxouts/%i/offset' % (self.deviceid, output))
        return voltage
    
    def setLowPassFilter(self, demod, order, TC, sinc = 0, TC_epsilon_factor = 1e-5):
        if demod not in [0,1,2,3]:
            raise ValueError('This MFLI has only 4 demodulators [0,1,2,3]')
        if order not in [1,2,3,4,5,6,7,8]:
            raise ValueError('Filter order can be an integer from 1 to 8')
        if TC > 250.5:
            raise ValueError('Maximum time constant = 250.5 s')
        if TC < 336.6e-9:
            raise ValueError('Minimum time constant = 336.6 ns')
        if sinc not in [0,1]:
            raise ValueError('Sinc-Filter Error: set 0 for Off; set 1 for On.')
        
        self.device.setInt(   '/%s/demods/%i/order'        % (self.deviceid, demod), order)
        self.device.setDouble('/%s/demods/%i/timeconstant' % (self.deviceid, demod), TC)
        self.device.setInt(   '/%s/demods/%i/sinc'         % (self.deviceid, demod), sinc)
        
        time.sleep(0.1) # necessary
        
        setorder = self.device.getInt(   '/%s/demods/%i/order'        % (self.deviceid, demod) )
#        setTC    = self.device.getDouble('/%s/demods/%i/timeconstant' % (self.deviceid, demod) )
        setsinc  = self.device.getInt(   '/%s/demods/%i/sinc'         % (self.deviceid, demod) )
        
        #if abs(setTC - TC) > TC_epsilon_factor * TC:
        #    raise ValueError('TC = %5.2e s cannot be set; used TC = %5.2e s instead' % (TC,setTC) )      
        
        if order != setorder or sinc != setsinc:
            raise ValueError('Setting the new filter settings failed due to an unexpected error')      
    
    def setAuxOutLimits(self, output, limitlower, limitupper, limit_epsilon = 1e-6):
        if output not in [0,1,2,3]:
            raise ValueError('This MFLI has only 4 Aux outputs [0,1,2,3]')
        if limitlower > limitupper:
            raise ValueError('The lower limit has to be lower than the upper limit')
        if abs(limitlower) > 10:
            raise ValueError('The lower limit exceeds the possible range [-10,10] V')
        if abs(limitupper) > 10:
            raise ValueError('The upper limit exceeds the possible range [-10,10] V')
            
        self.device.setDouble('/%s/auxouts/%i/limitlower' % (self.deviceid, output), limitlower)
        self.device.setDouble('/%s/auxouts/%i/limitupper' % (self.deviceid, output), limitupper)
        
        time.sleep(0.1) # necessary
        
        setlimitlower = self.device.getDouble('/%s/auxouts/%i/limitlower' % (self.deviceid, output) )
        setlimitupper = self.device.getDouble('/%s/auxouts/%i/limitupper' % (self.deviceid, output) )
        
        if abs(setlimitlower - limitlower) > limit_epsilon or abs(setlimitupper - limitupper) > limit_epsilon:
            raise ValueError('Epsilon error for Aus output limits')    
            
    def setAuxOutVoltage(self, voltage, output, voltage_epsilon = 1e-3):
        if output not in [0,1,2,3]:
            raise ValueError('This MFLI has only 4 Aux outputs [0,1,2,3]')
        
        # check if Aux channel is set to Manual
        AuxMode = self.device.getInt(   '/%s/auxouts/%i/outputselect' % (self.deviceid, output))
        if AuxMode != -1:
            raise ValueError('Aux output %i (%i in the interface) is not set to manual mode' % (output, output+1) )
                
        # read out the set limits
        limitlower = self.device.getDouble('/%s/auxouts/%i/limitlower' % (self.deviceid, output))
        limitupper = self.device.getDouble('/%s/auxouts/%i/limitupper' % (self.deviceid, output))
        
        if voltage < limitlower or voltage > limitupper:
            raise ValueError('%5.3f V does not fit in the set limits [%5.3f,%5.3f] V of Aux output %i (%i in the interface)' % (voltage,limitlower,limitupper,output, output+1))
        
        self.device.setDouble('/%s/auxouts/%i/offset' % (self.deviceid, output), voltage)
        
        time.sleep(0.1) # necessary
        
        setvoltage = self.getAuxOutVoltage(output) 
        
        if abs(voltage-setvoltage) > voltage_epsilon:
            raise ValueError('Epsilon error for Aux output voltage')        
            
    def setOutputVoltage(self,voltage, demod = 0, unit = 'Vrms', voltage_epsilon_factor = 1e-3):
        if unit not in ['Vrms','Vpk']:
            raise ValueError('Voltage unit not recognized. Use \"Vrms\" or \"Vpk\"')
        if demod not in [0,1,2,3]:
            raise ValueError('This MFLI has only 4 demodulators [0,1,2,3]')
        
        if unit == 'Vrms':
            amplitude = voltage * math.sqrt(2)
        else:
            amplitude = voltage

        diff = self.device.getInt('/%s/sigouts/0/diff' % (self.deviceid) )
        if diff == 0: limit = 10 
        if diff == 1: limit = 20
        
        if amplitude > limit:
            raise ValueError('%6.3f Vpk is to high. The limit is %i Vpk (= %6.3f Vrms) at this differential settings' % (amplitude,limit,limit/math.sqrt(2)) )
                
        if voltage == 0:
            self.device.setInt('/%s/sigouts/0/enables/%i'   % (self.deviceid, demod), 0)
        else:
            self.device.setInt('/%s/sigouts/0/enables/%i'   % (self.deviceid, demod), 1)
            
        self.device.setDouble('/%s/sigouts/0/amplitudes/%i' % (self.deviceid, demod), amplitude)
        
        time.sleep(0.1) # necessary
        
        setamplitude = self.getOutputVoltage(demod, unit = 'Vpk')
                
        if abs(amplitude-setamplitude) > voltage_epsilon_factor * amplitude:
            raise ValueError('Epsilon error for output voltage of demod %i' % demod)
    
    def setOutputOn(self,state):
        if state not in [0,1]:
            raise ValueError('Output Error: set \"0\" for Off; set \"1\" for On')
        
        self.device.setInt('/%s/sigouts/0/on' % (self.deviceid), state)
        
        time.sleep(0.1) # necessary
        
        setstate = self.device.getInt('/%s/sigouts/0/on' % (self.deviceid) )
        
        if setstate != state:
            raise ValueError('Setting the output On option failed due to an unexpected error')
    
    #def autorange_Input(self):        
    #    self.device.setInt('/%s/CURRINS/n/AUTORANGE' % (self.deviceid))
    #    time.sleep(0.1) # necessary
        
    def setOscillator(self, osc, freq, freq_epsilon = 1e-3):
        if osc not in [0,1,2,3]:
            raise ValueError('This MFLI has only 4 oscillators [0,1,2,3]')
        if freq < 0:
            raise ValueError('A frequency has to be positive')
        if freq > 500e3:
            raise ValueError('f = %4.3e Hz is not possible. Enter a frequency below 500 kHz' % freq)
        
        # check if any oscillator is locked to an external reference
        osc1 = self.device.getInt('/%s/demods/1/oscselect' % (self.deviceid))
        osc3 = self.device.getInt('/%s/demods/3/oscselect' % (self.deviceid))
        # id 0 means first demodulator which can be locked to an external reference, so 0 = demod 1 and 1 = demod 3 (number 2 and 4)
        extref1 = self.device.getInt('/%s/extrefs/0/enable'% (self.deviceid)) 
        extref3 = self.device.getInt('/%s/extrefs/1/enable'% (self.deviceid))
        
        if (extref1 == 1 and osc1 == osc) or (extref3 == 1 and osc3 == osc):
            raise ValueError('Oscillator %i (%i in the interface) is locked to an external reference and cannot be manipulated' % (osc,osc+1))
        else:
            self.device.setDouble('/%s/oscs/%i/freq' % (self.deviceid, osc), freq)
        
            time.sleep(0.1) # necessary
            
            setfreq = self.device.getDouble('/%s/oscs/%i/freq' % (self.deviceid, osc) )
            
            if abs(setfreq - freq) > freq_epsilon:
                raise ValueError('Epsilon error for frequency of oscillator %i' % osc)
                
            
    def setDemod(self, demod, phase = 0, harmonic = 1, osc = 0, phase_epsilon = 1e-3):
        if demod not in [0,1,2,3]:
            raise ValueError('This MFLI has only 4 demodulators [0,1,2,3]')
        if osc not in [0,1,2,3]:
            raise ValueError('This MFLI has only 4 oscillators [0,1,2,3]')
        if harmonic < 1 or int(harmonic) != harmonic:
            raise ValueError('Harmonics have to be positive integers')            
        
        phase = phase % 360
        if phase > 180: phase -= 360
        
        self.device.setInt(   '/%s/demods/%i/oscselect'  % (self.deviceid, demod), osc)
        self.device.setDouble('/%s/demods/%i/phaseshift' % (self.deviceid, demod), phase)
        self.device.setDouble('/%s/demods/%i/harmonic'   % (self.deviceid, demod), harmonic)
                
        time.sleep(0.1) # necessary

        setosc      = self.device.getInt(   '/%s/demods/%i/oscselect'  % (self.deviceid, demod) )
        setphase    = self.device.getDouble('/%s/demods/%i/phaseshift' % (self.deviceid, demod) )
        setharmonic = self.device.getDouble('/%s/demods/%i/harmonic'   % (self.deviceid, demod) )
                
        if abs( setphase - phase ) > phase_epsilon:
            raise ValueError('phase = %6.3f ° cannot be set; used phase = %6.3f ° instead' % (phase, setphase) )      
        
        if setosc != osc or setharmonic != harmonic:
            raise ValueError('Setting the demodulator settings failed due to an unexpected error')         
        
#    To set an external reference properly one has to manipulate (or at least check) the signal input settings 
#    as well because the MFLI wont give back any errors (see setOscillator function)
#    Therefore external reference settings should be made only manually in the LabOne interface
#
#    def setExtRef(self, demod, osc, mode):
#        if mode not in ['Manual','ExtRef']:
#            raise ValueError('Only \"Manual\" and \"ExtRef\" are supported modes up to now')
        
    def close(self):
        self.setOutputOn(0)
        #self.device.close()
        return
        




class MagnetPhysik_FH55:
    def __init__(self):
        self.device = None
        self.port = None
        self.measurement_range = None
        self.acdcMode = None
        self.autorange = None
        self.temperatureCorrection = None
  
    def initialize(self, port):
        self.port = port
        self.time_to_wait_in_s_forReading = 0.002
        self.time_to_wait_in_s_forSetting = 0.3
        
        try:
            self.device = serial.Serial(port, 19200, timeout = 0.1)
            time.sleep(self.time_to_wait_in_s_forSetting)
            self.device.write(('?PING'+ chr(13)).encode())
            time.sleep(self.time_to_wait_in_s_forSetting)
            rcv = self.device.read(24).decode()
            if(rcv[0:5]!='ERROR'): raise Exception('Connection error, NO CONNECTION')
            self.reset('setVariables')        
        except Exception as e: print(__class__.__name__,'.initialize(), connection or setting Error ', e)
      
    def reset(self, option):
        try:
            if option not in ["device","nullVariables","setVariables","software"]: raise ValueError('option only ["device","nullVariables","setVariables","software"]')
            if option == 'software': option = ["nullVariables","setVariables"]
            
            if 'nullVariables' in option:
                self.measurement_range = None
                self.acdcMode = None
                self.autorange = None
                self.temperatureCorrection = None
            if 'setVariables' in option: 
                self.set_mode('DC')
                self.set_temperatureCorrectionOn()
                self.set_autorangeOff()
                self.set_range(3)
            if 'device' in option:
                self.__write("INIT")
                time.sleep(12)
                self.reset('software')
        
        except ValueError as e: print(__class__.__name__,'.reset(), invalid input param, ',e)
        except: print(__class__.__name__,'.reset(), problems resetting the device')


        
    def close(self):
        try: self.device.close()
        except: print(__class__.__name__,'.close(), problem with disonnecting')
        
    def __read(self, string):
        try:
            command = "?" + string + chr(13)
            self.device.write(command.encode())
            time.sleep(self.time_to_wait_in_s_forReading)
            answer = ""
            for i in range(24):
                temp = self.device.read()
                if temp == b'\r': break
                answer = answer + temp.decode()
            return answer.lstrip()
        except: print(__class__.__name__,'__read(), could not read')
  
    def __write(self, string):
        try:
            command = "#" + string + chr(13)
            self.device.write(command.encode())
            time.sleep(self.time_to_wait_in_s_forSetting)
            answer = ""
            for timeout in range(20):
                temp = self.device.read()
                if temp == b'\r': break
                answer = answer + temp.decode()
            return answer.lstrip()
        except: print(__class__.__name__,'__write(), could not write')
    
    def set_range(self, expectedMaxValue):
        """
        This method defines the Range of measurement and turns off the autorange\n

        Parameters
        ----------\n
        expectedMaxValue: float
         the range is set to the next possible Value.

        Returns
        -------
        returns the RANGE if it is accepted, otherwise ERROR parameter.

        """
        try:
            if (float(expectedMaxValue)>3) or (float(expectedMaxValue)<0): raise ValueError('0 < expectedMaxValue < 3')
            
            ranges_dict={3:3e-3,4:30e-3,5:300e-3,6:3}
            for k,v in ranges_dict.items(): 
                if v>=float(expectedMaxValue):
                    temp_range = k
                    break
            if temp_range !=self.measurement_range:
                ret = self.__write("RANGE "+ str(temp_range))
                if ret == 'ERROR': raise Exception('Could not change the range')
                else: self.measurement_range = int(ret[-1:])
                time.sleep(2*self.time_to_wait_in_s_forSetting)
        except ValueError as e: print(__class__.__name__,'.set_range(), invald input parameter, ',e)
        except: print(__class__.__name__,'.set_range(), problem with setting the measurement range')
        
    def get_range(self):
        try:
            ranges_dict={3:3e-3,4:30e-3,5:300e-3,6:3}
            return ranges_dict[self.measurement_range]
        except: print('problem getting the range')
    
    def set_mode(self, mode):
        """
        This method determines whether the device is in AC or DC Mode\n

        Parameters
        ----------\n
        mode : String
            'DC' - Mode\n
            'AC' - Mode
            
        Returns
        -------
        None
        """
        try:
            if (mode not in ['AC','DC']): raise ValueError('mode must be "DC" or "AC"')
            if self.acdcMode!=mode:
                if mode=='DC': 
                    ret = self.__write("MODE 0")
                    if ret == 'MODE 0': self.acdcMode='DC'
                    else: raise Exception('Could not set the dc mode set_mode()')
                elif mode=='AC': 
                    ret = self.__write("MODE 1")
                    if ret == 'MODE 1': self.acdcMode='AC'
                    else: raise Exception('Could not set the dc mode set_mode()')
        except ValueError as e: print(__class__.__name__,'.set_mode(), invald input parameter, ',e)
        except: print(__class__.__name__,'.set_mode(), problem with setting the mode')
    
    def set_autorangeOn(self):
        """
        This method turns the autorange on\n

        Returns
        -------\n
        returns accepted, otherwise ERROR parameter.

        """
        try:
            if self.autorange!=1:
                ret = self.__write("AUTO 1")
                if ret == "AUTO 1": self.autorange = 1
                else: raise Exception('Could NOT set the autorange on') 
        except: print(__class__.__name__,'.set_autorangeOn(), problem with setting the autorange on')
    
    def set_autorangeOff(self):
        """
        This method turns the autorange off\n

        Returns
        -------\n
        None

        """
        try:
            if self.autorange!=0:
                ret = self.__write("AUTO 0")
                if ret == "AUTO 0": self.autorange = 0
                else: raise Exception('Could NOT set the autorange off') 
        except: print(__class__.__name__,'.set_autorangeOff(), problem with setting the autorange off')
        
    
    def get_temperature(self):
        """
        This method returns the temperature of the Sensor in celcius-degree\n

        Returns
        -------\n
        returns the temperature of the Sensor in celcius-degree
        """
        try:
            self.__write("TEMP 1")
            return (self.__read("TEMP"))[:-2]
        except: print(__class__.__name__,'.get_temperature(), problem with getting the temperature of the sensor')
        
    def get_singleFieldValue(self):
        """
        This method returns a single field value\n

        Returns
        -------\n
        returns the value of the field in T as a float.

        """
        try:
            field = self.__read("MEAS")
            if field == 'FULL': raise Exception(__class__.__name__,'OVERFLOW')
            elif field[-2:]=="mT": field = float(field[:-3])* (1e-3)
            else: field = float(field[:-2])
            return field
        except Exception as e: print(__class__.__name__,'.get_singleFieldValue(), problem with getting the field value ',e)
        
    def set_temperatureCorrectionOn(self):
        """
        This method switches the temperature correction on\n

        Returns
        -------\n
        accepted, otherwise error

        """
        try:
            if self.temperatureCorrection != 1:
                ret = self.__write("CTEMP 1")
                if "CTEMP 1"==ret: 
                    self.temperatureCorrection = 1
                else: raise Exception('Something went wrong setting the temp correction On')
        except: print(__class__.__name__,'.set_temperatureCorrectionOn(), problem with setting the temperature correction on')
        
    def set_temperatureCorrectionOff(self):
        """
        This method switches the temperature correction off\n

        Returns
        -------\n
        accepted, otherwise error

        """
        try:
            if self.temperatureCorrection != 0:
                ret = self.__write("CTEMP 0")
                if "CTEMP 0" == ret: self.temperatureCorrection = 0
                else: raise Exception('Something went wrong setting the temp correction Off')
        except: print(__class__.__name__,'.set_temperatureCorrectionOff(), problem with setting the temperature correction off')
        

        
class CaenelsFastPS:
    def __init__(self):
        self.deviceport = None
        self.device = None
        self.try_to_connect = 10
        self.mode = None #cc or cv
        self.model = None
        self.ControlMode = None
        self.output_state= None #0(OFF),1(ON)
        self.floating_output = None
        self.slewRateVoltage = None
        self.slewRateCurrent = None
        self.actual_voltage = None
        self.actual_current = None
        
    def initialize(self, ip, port, model):
        """
        defines the device\n

        Parameters
        ----------\n
        ip : String
            "192.168.0.10
        port : integer
            10001

        Returns
        -------
        None.
        """
        
        try:
            if model not in [2040, 3050]: raise ValueError('This model is not known')
            if model==2040:
                self.max_current = 20.0
                self.max_voltage = 40.0
                self.max_slewRateCurrent = 200.0
                self.max_slewRateVoltage = 400.0
                self.time_to_wait_in_s = 0.01
            if model==3050:
                self.max_current = 30.0
                self.max_voltage = 50.0
                self.max_slewRateCurrent = 200.0
                self.max_slewRateVoltage = 400.0
                self.time_to_wait_in_s = 0.01
            server_address = (ip, port)
            self.device = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.device.connect(server_address)
            time.sleep(1)
            self.reset('device')
            self.mode = (self.__query('LOOP:?'))[-3:-2]
            self.__query('PASSWORD:ps-admin')
            self.__query('MWG:90:0x1') #set Interlock 1 as active
            self.model=model
            self.set_outputOff()
            self.get_current()
            self.get_voltage()
            self.set_analogInputMode(False)
            self.floating_output = self.__query('SETFLOAT:?')[-3:-2] #Check the query 
            self.slewRateCurrent = self.__convertStrToFloat((self.__query('MSRI:?'))[-4:-2])
            self.slewRateVoltage = self.__convertStrToFloat((self.__query('MSRV:?'))[-4:-2])

        except:
            if (self.try_to_connect>0):
                print(__class__.__name__,'.initialize(), can not connect, be patient, i will try it again...')
                self.try_to_connect = self.try_to_connect-1
                self.initialize(ip, port, model)
            else: 
                self.device.close()
                print(__class__.__name__,'.initialize(), could not connect after 10 try')

    def reset(self, option):
        try:
            if option not in ["device","variables","all"]: raise ValueError('option only ["device","variables","all"]')
            if option == 'all': option = ["device","variables"]
            if 'device' in option: 
                self.__send('MRESET')
                self.get_current()
                self.get_voltage()
            if 'variables' in option:
                self.output_state= None #0(OFF),1(ON)
                self.floating_output = None
                self.mode = (self.__query('LOOP:?'))[-3:-2]
                self.set_outputOff()
                self.output_state = 0
                self.floating_output = self.__query('SETFLOAT:?')[-3:-2] #Check the query 
            self.slewRateCurrent = self.__convertStrToFloat((self.__query('MSRI:?'))[-4:-2])
            self.slewRateVoltage = self.__convertStrToFloat((self.__query('MSRV:?'))[-4:-2])
        except ValueError as e: print(__class__.__name__,'.reset(), invalid input param, ',e)
        except: print(__class__.__name__,'.reset(), problems resetting the device')

    def close(self):
        try:
            if self.output_state==1:
                if self.mode == 'I': self.set_rampToCurrent(0.0,10)
                elif self.mode == 'V': self.set_rampToVoltage(0.0,15)
            self.set_outputOff()
            self.device.close()
        except: print(__class__.__name__,'.close(), error when closing the device')
        
    
    def __send(self, cmd):
        s = cmd + '\r'
        try: self.device.send(s.encode())
        except: print(__class__.__name__,'.__send(), could not send the command '+cmd)
        finally: time.sleep(self.time_to_wait_in_s)
    
    def __query(self, cmd):
        self.__send(cmd)
        time.sleep(self.time_to_wait_in_s)
        try: 
            ret = self.device.recv(30).decode()
        except: 
            print(__class__.__name__,'.__query(), could not receive data')
            ret = 'Error'
        finally: return ret
    
    def set_outputFloating(self, floatingGround):
        """ This method set if the outout is floating or not\n
        Parameters
        ----------\n
        floatingGround : String
            "floating"
            "ground".
        Returns
        -------\n
        None
        """
        try:
            if floatingGround not in ["floating","ground"]: raise ValueError('floatingGround must be ["floating","ground"]')
            if self.floating_output != floatingGround:
                if floatingGround == 'floating': ret = self.__query('SETFLOAT F')
                elif floatingGround == 'ground': ret = self.__query('SETFLOAT N')
                if "NAK"==ret[1:4]: print('The output state could not be set, see error code '+str(ret[4:7])) 
                elif "AK"==ret[1:3]: self.output_state=1 
        except ValueError as v: print(__class__.__name__,'.set_outputFloating(), invalid input param, ',v)
        except Exception as e:  print(__class__.__name__,'.set_outputFloating(), error: ',e)
                
        
    def set_outputOn(self):
        try:
            if self.output_state!=1:
                ret = self.__query('MON')
                if "NAK"==ret[1:4]: 
                    print('Device could not be turned on, see error code '+str(ret[4:7])) 
                    if(ret[4:7]==':08'):
                        print('Interlock is open, overtemperature of magnet? If it is cooled down and the guard resetted!')
                elif "AK"==ret[1:3]: self.output_state=1 
        except Exception as e: print(__class__.__name__,'.set_outputOn(), error: ', e)
        
    def set_outputOff(self):
        try:
            if self.output_state!=0:
                ret = self.__query('MOFF')
                if "NAK"==ret[1:4]: print('Device could not be turned off, see error code '+str(ret[4:7])) 
                elif "AK"==ret[1:3]: self.output_state=0
        except Exception as e: print(__class__.__name__,'.set_outputOff(), error: ', e)
    
    def get_voltage(self):
        """ This method returns the actual voltage of the output\n

        Returns
        -------\n
        float: the voltage as a float

        """
        try: self.actual_voltage = (self.__convertStrToFloat(str(self.__query('MRV'))))
        except: print(__class__.__name__,'.get_voltage(), error occured')
        finally: return self.actual_voltage
   
    def get_current(self):
        """ returns the current
        Returns:
            float: the actual output current
        """
        try: self.actual_current = (self.__convertStrToFloat(str(self.__query('MRI'))))
        except: print(__class__.__name__,'.get_current(), error occurred')
        finally: return self.actual_current
    
    def set_voltage(self, voltage):
        """ set voltage direct, watch out: if the output is off, it will be switched on\n
        Parameters
        ----------\n
        voltage : float
            the voltage to be applied, in the range V=(+/-) self.max_voltage

        Returns
        -------
        None
        """
        try:
            if abs(float(voltage))>self.max_voltage: raise ValueError('voltage < +/- {}'.format(self.maxVoltage))
            self.set_cvMode()
            self.set_outputOn()
            t_temp = abs(float(voltage)-self.actual_voltage)/self.max_slewRateVoltage    
            ret = self.__query('MWV:'+str(voltage))    
            if (ret[1:4])=='NAK': raise Exception('could not set the device with the specified parameter ',str(voltage))
            if (ret[1:3])=='AK': self.actual_voltage=voltage
            time.sleep(t_temp)
        except ValueError as v: print(__class__.__name__,'.set_voltage(), invalid input param, ',v)
        except Exception as e:  print(__class__.__name__,'.set_voltage(), error: ', e)
            
    def set_current(self, current):
        ''' set current direct, watch out: if the output is off, it will be switched on\n
        Parameters
        ----------\n
        current : float
            the current to be applied, in the range of I=(+/-) self.max_current

        Returns
        -------
        None
        '''
        try:
            if abs(float(current))>self.max_current: raise ValueError('current < +/- {}'.format(self.maxCurrent))
            self.set_ccMode()
            self.set_outputOn()
            t_temp = abs(float(current)-self.actual_current)/self.max_slewRateCurrent
            ret = self.__query('MWI:'+str(current))    
            if (ret[1:4])=='NAK': raise Exception('could not set the device with the specified parameter ',str(current))
            if (ret[1:3])=='AK': self.actual_current=current
            time.sleep(t_temp)
        except ValueError as v: print(__class__.__name__,'.set_current(), invalid input param, ',v)
        except Exception as e:  print(__class__.__name__,'.set_current(), error: ', e)
            
    def set_rampToCurrent(self,current, slewRateAmpPerSec):
        ''' set current, raises with the applied CurrentSlewRate\n        
        Parameters
        ----------\n
        current : float
            the current to be applied\n
        SlewRateAmpPerSec : float
            the slew rate in amp per sec.
        Returns
        -------
        None
        '''
        try: 
            if abs(float(current))>self.max_current: raise ValueError('current < +/- {}'.format(self.max_current))
            self.set_ccMode()
            self.set_outputOn()
            self.set_currentSlewRate(float(slewRateAmpPerSec))
            
            ret = self.__query('MWIR:'+str(current))
            if (ret[1:4])=='NAK': raise Exception('could not set the device with the specified parameter ',str(current))
            if (ret[1:3])=='AK': 
                time.sleep(abs(current-self.actual_current)/float(slewRateAmpPerSec))
                self.actual_current=current
        except ValueError as v: print(__class__.__name__,'.set_rampToCurrent(), invalid input param, ',v)
        except Exception as e:  print(__class__.__name__,'.set_rampToCurrent(), error: ', e)
            
    def set_rampToVoltage(self,voltage, slewRateVoltPerSec):
        ''' set voltage, raises with the applied voltageSlewRate, the device must be in cv-mode\n
        Parameters
        ----------\n
        voltage : float
            the voltage to be applied.

        Returns
        -------
        None
        '''            
        try: 
            if abs(float(voltage))>self.max_voltage: raise ValueError('voltage < +/- {}'.format(self.max_voltage))
            self.set_cvMode()
            self.set_outputOn()
            self.set_voltageSlewRate(float(slewRateVoltPerSec))
            
            ret = self.__query('MWVR:'+str(voltage))
            if (ret[1:4])=='NAK': raise Exception('could not set the device with the specified parameter ',str(voltage))
            if (ret[1:3])=='AK': 
                time.sleep(abs(voltage-self.actual_voltage)/float(slewRateVoltPerSec))
                self.actual_voltage=voltage
        except ValueError as v: print(__class__.__name__,'.set_rampToVoltage(), invalid input param, ',v)
        except Exception as e:  print(__class__.__name__,'.set_rampToVoltage(), error: ',e)
            
    def set_ccMode(self):
        '''sets the constant current mode\n
        Returns
        -------
        None
        '''
        try: 
            if self.mode != 'I':
                self.set_outputOff()
                ret = self.__query('LOOP:I')
                if (ret[1:4])=='NAK': raise Exception('could not set the device to cc-mode')
                if (ret[1:3])=='AK': self.mode = 'I'
        except Exception as e:  print(__class__.__name__,'.set_ccMode(), error: ',e)

    def set_cvMode(self):
        '''sets the constant voltage mode\n
        Returns
        -------
        None
        '''
        try: 
            if self.mode != 'V':
                self.set_outputOff()
                ret = self.__query('LOOP:V')
                if (ret[1:4])=='NAK': raise Exception('could not set the device to cv-mode')
                if (ret[1:3])=='AK': self.mode = 'V'
        except Exception as e:  print(__class__.__name__,'.set_cvMode(), error: ',e)
    
    def set_analogInputMode(self,active):
        try:
            if self.model=='2040' and (self.controlMode!=active):
                if active==1:
                    ret = self.__query('UPMODE:ANALOG')
                    if (ret[1:3])=='AK': self.ControlMode = 'A'
                if active==0:
                    ret = self.__query('UPMODE:NORMAL')
                    if (ret[1:3])=='AK': self.ControlMode = 'N'
                if (ret[1:4])=='NAK': raise Exception('could not set the device to specified control-mode')
        except Exception as e:  print(__class__.__name__,'.set_analogInputMode(), error: ',e)
        
        
    def set_currentSlewRate(self,ampPerSec):
        '''sets the slew rate for the current, the device must be in cc-mode\n
        Parameters
        ----------
        ampPerSec : float
            Ampere per second.
        Returns
        -------
        None
        '''
        try:
            ampPerSec = abs(ampPerSec)
            self.set_ccMode()
            if self.max_slewRateCurrent<ampPerSec : raise ValueError('ampPerSec < {}'.format(self.max_slewRateCurrent))
            if self.slewRateCurrent!=ampPerSec :
                ret = self.__query('MSRI:'+str(ampPerSec))
                if (ret[1:4])=='NAK': raise Exception('could not set the device with the specified parameter ',str(ampPerSec))
                if (ret[1:3])=='AK': self.slewRateCurrent = ampPerSec
        except ValueError as v: print(__class__.__name__,'.set_currentSlewRate(), invalid input param, ',v)
        except Exception as e:  print(__class__.__name__,'.set_currentSlewRate(), error: ',e)
        
    def set_voltageSlewRate(self,voltPerSec):
        '''sets the slew rate for the voltage, the device must be in cv-mode\n
        Parameters
        ----------
        voltPerSec : float
            volts per second.
        Returns
        -------
        None
        '''
        try:
            self.set_cvMode()
            if self.max_slewRateVoltage<voltPerSec : raise ValueError('voltPerSec < {}'.format(self.max_slewRateVoltage))
            if self.slewRateVoltage!=voltPerSec :
                ret = self.__query('MSRV:'+str(voltPerSec))
                if (ret[1:4])=='NAK': raise Exception('could not set the device with the specified parameter ',str(voltPerSec))
                if (ret[1:3])=='AK': self.slewRateVoltage = voltPerSec
        except ValueError as v: print(__class__.__name__,'.set_voltageSlewRate(), invalid input param, ',v)
        except Exception as e:  print(__class__.__name__,'.set_voltageSlewRate(), error: ',e)
               
    def __convertStrToFloat(self, string):
        ''' extracts the floats of strings. If the string has two floats the first is the Mantisse and the second the exponent to the base of 10\n
        Parameters
        ----------
        string : string
            the input string.
        Returns
        -------
        temp : float
            the extracted float of the string

        '''
        try:
            temp = [float(s) for s in re.findall(r'-?\d+\.?\d*', string)]
            if len(temp)>1:
                temp = float(str(temp[0])+'e'+str(int(temp[1])))
            elif len(temp)==1:
                temp = float(temp[0])
        except: 
            print('There is a problem with coverting the string to a float, class CaenelsFastPS, method __convertStrToFloat')
            temp = 999999999
        finally: return temp
   

        
