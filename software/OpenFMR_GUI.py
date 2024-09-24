"""
 OpenFMR: GUI for the data acquisition script.
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

import sys
import os
#import time
from PyQt5 import QtWidgets
from PyQt5.QtCore import pyqtSignal, QObject, Qt

from PyQt5.QtGui import QTextCursor
import threading

import pyqtgraph as pg

import zipfile




# streaming class for live update of the message window
class Stream(QObject):
    newText = pyqtSignal(str)

    def write(self, text):
        self.newText.emit(str(text))

    def flush(self):
        pass



class MainApp(QtWidgets.QMainWindow):
        
    def __init__(self):
        super().__init__()

        self.infotext = \
            "OpenFMR Version 1.0\n \
\nSteps to take a measurement:\n \
  1. Ensure the underlying fmr_classes.py script runs properly from the command line.\n \
  2. Set the folder and filename for your measurement.\n \
  3. Control the measurement with estimated parameters of your sample. The field ranges for each frequency are estimated using the estimated parameters. The accuracy controls how tight these parameters are and enables wider or narrower measurement windows. Choose larger alpha initially to ensure that you find the resonances.\n\
  4. Measurement are stored by the fmr_classes.py script as .zip files.\n\
  5. Perform the data analysis with OpenFMR_Fit.py.\n\
\nNote : Adjust the modulation field strength according to the linewidths. The modulation field should aways be significantly smaller than the linewidth to avoid broadening and distortion.\n \
Note II: For PMA samples, Meff is negative."


        self.magnets = ["DXWD-80_20mm", "DXWD-80_5mm"]


        self.initUI()


        # Original stdout
        self.original_stdout = sys.stdout
        self.original_stderr = sys.stderr

        # Redirect stdout
        self.stream = Stream()
        self.stream.newText.connect(self.on_new_text)
        
        self.fmr = None
        
        self.stop_button.setEnabled(False)
        
        self.livedata = [[],[],[]]
        
                

    def initUI(self):


        self.setWindowTitle("OpenFMR Ferromagnetic Resonance Measurement")



        widget = QtWidgets.QWidget(self)
        main_layout = QtWidgets.QHBoxLayout()  # Main layout for two columns

        # Graphs layout
        graphs_layout = QtWidgets.QVBoxLayout()  # Vertical layout for graphs and message window

        # Main Plot Window
        self.plot_window = pg.PlotWidget()
        self.setup_plot_style(self.plot_window)
        self.plot_window.setLabel('bottom', 'Field', units='T')
        self.plot_window.setLabel('left', 'Lock-In signals', units='V')

        graphs_layout.addWidget(self.plot_window)

        
        # Message window
        message_layout = QtWidgets.QHBoxLayout()  

        self.message_window = QtWidgets.QTextEdit(self)
        self.message_window.setReadOnly(True)
        message_layout.addWidget(self.message_window)
        
        
        graphs_layout.addLayout(message_layout)


        # Controls and Messages
        control_layout = QtWidgets.QVBoxLayout()
        control_layout.setAlignment(Qt.AlignTop)

        # File Handling frame
        self.file_handling_frame = QtWidgets.QGroupBox("File handling")
        file_handling_layout = QtWidgets.QVBoxLayout()


        # Folder display and selection
        self.folder_input = QtWidgets.QLineEdit(self)
        self.folder_input.setReadOnly(True)
        self.folder_button = QtWidgets.QPushButton("Folder")
        self.folder_button.clicked.connect(self.select_folder)

        file_handling_layout.addWidget(self.folder_input)
        file_handling_layout.addWidget(self.folder_button)


        # Filename input
        self.filename_label = QtWidgets.QLabel("Filename:")
        self.filename_input = QtWidgets.QLineEdit(self)
        filename_layout = QtWidgets.QHBoxLayout()
        filename_layout.addWidget(self.filename_label)
        filename_layout.addWidget(self.filename_input)
        file_handling_layout.addLayout(filename_layout)        
        


        # Measurement controls frame
        self.control_frame = QtWidgets.QGroupBox("Measurement controls")
        frame_layout = QtWidgets.QVBoxLayout()


        # Magnet selection
        magnet_layout = QtWidgets.QHBoxLayout()
        self.magnet_label = QtWidgets.QLabel("Magnet:")
        self.magnet_combobox = QtWidgets.QComboBox(self)
        self.magnet_combobox.addItems(self.magnets)
        magnet_layout.addWidget(self.magnet_label)
        magnet_layout.addWidget(self.magnet_combobox)
        frame_layout.addLayout(magnet_layout)


        # Mode controls
        mode_layout = QtWidgets.QHBoxLayout()
        self.mode_label = QtWidgets.QLabel("Mode:")
        self.mode_combobox = QtWidgets.QComboBox(self)
        self.mode_combobox.addItems(["in-plane", "out-of-plane"])
        mode_layout.addWidget(self.mode_label)
        mode_layout.addWidget(self.mode_combobox)
        frame_layout.addLayout(mode_layout)
        
        
        # Magnetization and g text input
        self.magnetization_label = QtWidgets.QLabel("M_eff (kA/m):")
        self.magnetization_input = QtWidgets.QLineEdit("1050")  
        self.g_label = QtWidgets.QLabel("g:")
        self.g_input = QtWidgets.QLineEdit("2.10")
        magnetization_layout = QtWidgets.QHBoxLayout()
        magnetization_layout.addWidget(self.magnetization_label)
        magnetization_layout.addWidget(self.magnetization_input)
        magnetization_layout.addWidget(self.g_label)
        magnetization_layout.addWidget(self.g_input)
        frame_layout.addLayout(magnetization_layout)




        # Alpha and Delta B0 text input
        self.alpha_label = QtWidgets.QLabel("alpha:")
        self.alpha_input = QtWidgets.QLineEdit("0.005")
        self.dB0_label = QtWidgets.QLabel("Delta B0:")
        self.dB0_input = QtWidgets.QLineEdit("0.001")
        alpha_layout = QtWidgets.QHBoxLayout()
        alpha_layout.addWidget(self.alpha_label)
        alpha_layout.addWidget(self.alpha_input)
        alpha_layout.addWidget(self.dB0_label)
        alpha_layout.addWidget(self.dB0_input)
        frame_layout.addLayout(alpha_layout)



        # Frequency controls
        frequency_layout = QtWidgets.QHBoxLayout()
        self.frequency_label = QtWidgets.QLabel("f (GHz): Start | Stop | Step")
        self.start_frequency_input = QtWidgets.QLineEdit("5")
        self.stop_frequency_input = QtWidgets.QLineEdit("30")
        self.step_frequency_input = QtWidgets.QLineEdit("5")
        
        frequency_layout.addWidget(self.frequency_label)
        frequency_layout.addWidget(self.start_frequency_input)
        frequency_layout.addWidget(self.stop_frequency_input)
        frequency_layout.addWidget(self.step_frequency_input)
        frame_layout.addLayout(frequency_layout)


        # Modulation amplitude controls
        modulation_layout = QtWidgets.QHBoxLayout()
        self.modulation_label = QtWidgets.QLabel("Modulation field RMS (mT):")
        self.modulation_input = QtWidgets.QLineEdit("1.0")
        modulation_layout.addWidget(self.modulation_label)
        modulation_layout.addWidget(self.modulation_input)
        frame_layout.addLayout(modulation_layout)


        # time constant and DAQ delay controls
        timing_layout = QtWidgets.QHBoxLayout()
        self.tc_label = QtWidgets.QLabel("Time constant (ms):")
        self.tc_input = QtWidgets.QLineEdit("20")
        timing_layout.addWidget(self.tc_label)
        timing_layout.addWidget(self.tc_input)
        
        self.delay_label = QtWidgets.QLabel("DAQ delay (ms):")
        self.delay_input = QtWidgets.QLineEdit("250")
        timing_layout.addWidget(self.delay_label)
        timing_layout.addWidget(self.delay_input)
        frame_layout.addLayout(timing_layout)

        
        # Accuracy controls
        accuracy_layout = QtWidgets.QHBoxLayout()
        self.accuracy_label = QtWidgets.QLabel("Accuracy:")
        self.accuracy_combobox = QtWidgets.QComboBox(self)
        self.accuracy_combobox.addItems(["low", "medium", "high"])

        accuracy_layout.addWidget(self.accuracy_label)
        accuracy_layout.addWidget(self.accuracy_combobox)
        frame_layout.addLayout(accuracy_layout)


        # Start and Stop buttons side-by-side
        control_buttons_layout = QtWidgets.QHBoxLayout()
        self.start_button = QtWidgets.QPushButton("Start", self)
        self.stop_button = QtWidgets.QPushButton("Stop", self)
        
        self.start_button.clicked.connect(self.on_run)
        self.stop_button.clicked.connect(self.on_stop)

        control_buttons_layout.addWidget(self.start_button)
        control_buttons_layout.addWidget(self.stop_button)
        frame_layout.addLayout(control_buttons_layout)


        # Info frame
        self.info_frame = QtWidgets.QGroupBox("Information")
        info_layout = QtWidgets.QVBoxLayout()
        self.info_label = QtWidgets.QLabel(self.infotext)
        self.info_label.setFixedWidth(550)
        self.info_label.setWordWrap(True)
        info_layout.addWidget(self.info_label)
        
        
        # Setting the frame layout
        self.file_handling_frame.setLayout(file_handling_layout)
        control_layout.addWidget(self.file_handling_frame)

        self.control_frame.setLayout(frame_layout)
        control_layout.addWidget(self.control_frame)
        
        self.info_frame.setLayout(info_layout)
        control_layout.addWidget(self.info_frame)



        # Adding layouts to the main layout
        main_layout.addLayout(control_layout)
        main_layout.addLayout(graphs_layout)

        widget.setLayout(main_layout)
        self.setCentralWidget(widget)



    def append_message(self, message):
        self.message_window.append(message)

    def initialize_device(self):
        self.device_controls.initialize()
        self.message_window.append("Device initialized.")


    def stop_measurement(self):
        message = self.device_controls.stop_measurement()
        self.append_message(message)

    def setup_plot_style(self, plot_widget):
        plot_widget.setBackground('w')  # Set background to white
        # Set axis colors
        plot_widget.getAxis('left').setPen(color='k', width=1)    # Black color, width 1
        plot_widget.getAxis('bottom').setPen(color='k', width=1)  # Black color, width 1
        # Set axis label colors
        plot_widget.getAxis('left').setTextPen('k')   # Black color
        plot_widget.getAxis('bottom').setTextPen('k') # Black color


    def update_plot(self, data):
        # For now, just plotting the 'Signal' against 'Field'
        self.plot_window.plot(data[0], data[1], clear=True, pen=pg.mkPen('r', width=1))
        self.plot_window.plot(data[0], data[2], pen=pg.mkPen('b', width=1))


    def select_folder(self):
        folder = QtWidgets.QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder:
            self.folder_input.setText(folder)



    def show_warning(self, text):
        msg = QtWidgets.QMessageBox()
        msg.setIcon(QtWidgets.QMessageBox.Warning)
        msg.setWindowTitle("Warning")
        msg.setText(text)
        msg.setStandardButtons(QtWidgets.QMessageBox.Ok)
        msg.exec_()




    def parse_data(self, line):
        p = line.split("|")
        v1 = float(p[0].split()[2])
        v2 = float(p[1].split()[1])
        v3 = float(p[2].split()[1])
        self.livedata[0].append(v1)
        self.livedata[1].append(v2)
        self.livedata[2].append(v3)


    def on_new_text(self, text):
        self.message_window.moveCursor(QTextCursor.End)
        self.message_window.insertPlainText(text)
        
        message_window_current_text = str(self.message_window.toPlainText())
        lines = message_window_current_text.splitlines()

        if lines[-1].startswith("<>") and lines[-1].endswith("</>"):
            self.parse_data(lines[-1])
            self.update_plot(self.livedata)
            
        if lines[-1] == "<NEW_MEASUREMENT>":
            self.livedata = [[],[],[]]

                    
        
        
    def on_run(self):
        # check if the file path already exists
        foldername = self.folder_input.text()
        zipfilename = self.filename_input.text()

        path = foldername + "/" + zipfilename + ".zip"
        if os.path.exists(path):
            self.show_warning("File exists, please choose a different filename.")
            return

        # Start the script in a new thread
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)

        self.livedata = [[],[],[]]

        self.message_window.clear()     

        threading.Thread(target=self.run_script, daemon=True).start()
        
 
        
        
    def on_stop(self):
        if self.fmr:
            self.fmr.stop()
            self.start_button.setEnabled(True)
            self.stop_button.setEnabled(False)
            

    def run_script(self):

        # get parameters from the GUI
        
        foldername = self.folder_input.text()
        zipfilename = self.filename_input.text()

        magnet = self.magnet_combobox.currentText()
        mode_select = self.mode_combobox.currentText()
        m = {'in-plane': 'ip', 'out-of-plane': 'oop'}
        mode = m[mode_select]

        Meff = float(self.magnetization_input.text()) * 1e3
        alpha = float(self.alpha_input.text())
        g = float(self.g_input.text())
        deltaB0 = float(self.dB0_input.text())


        freqmin = float(self.start_frequency_input.text()) * 1e9
        freqmax = float(self.stop_frequency_input.text()) * 1e9
        freqstep = float(self.step_frequency_input.text()) * 1e9
     
        modulation_field_rms = float(self.modulation_input.text()) * 1e-3

        lowpass = float(self.tc_input.text()) * 1e-3
        delay = float(self.delay_input.text()) * 1e-3
        

        accuracy = self.accuracy_combobox.currentText()
        
        path = foldername + "/" + zipfilename

        
        parameters  = "FMR MEASUREMENT PARAMETERS:\n"
        parameters += " Folder name: %s\n" % foldername
        parameters += " Zip file name: %s\n" % zipfilename
        parameters += " Magnet: %s\n" % magnet
        parameters += " Mode: %s\n" % mode_select
        parameters += " Meff: %8.3f kA/m\n" % (Meff * 1e-3)
        parameters += " alpha: %8.3f \n" % alpha
        parameters += " g: %8.4f\n" % g
        parameters += " deltaB0: %8.4f T\n" % deltaB0
        parameters += " Freq (Start | Stop | Step): %6.2f | %6.2f | %6.2f GHz\n" % (freqmin*1e-9, freqmax*1e-9, freqstep*1e-9)
        parameters += " Modulation field: %8.4f mT\n" % (modulation_field_rms * 1e3)
        parameters += " Lock-In time constant: %8.2f ms\n" % (lowpass * 1e3)
        parameters += " Delay: %8.2f ms\n" % (delay * 1e3)
        parameters += " Accuracy: %s\n\n" % accuracy
        
        self.stream.write(parameters)
        
        # Redirect stdout and stderr to the stream
        sys.stdout = self.stream
        sys.stderr = self.stream
        
        
        # real measurement starts here
        
        # reimport fmr_classes module to help making quick changes to the
        # script without restarting the GUI
        import fmr
        self.fmr = fmr.FMR()

        # run the measurement
        self.fmr.fmr_measurement(path, Meff, alpha, g, deltaB0, magnet=magnet, mode=mode, accuracy=accuracy, delay=delay, \
                modulation_field_rms=modulation_field_rms, lowpass=lowpass, \
                    freqmin=freqmin, freqstep=freqstep, freqmax=freqmax, GUI=True)

        
        # Reset stdout and stderr
        sys.stdout = self.original_stdout
        sys.stderr = self.original_stderr
        
        # Reset start/stop buttons
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        
        # write the log
        log = str(self.message_window.toPlainText())
        self.writedatafile(path+".zip", "logfile.log", log)  


            
    def writedatafile(self, zipfilename, filename, string):
        zf = zipfile.ZipFile(zipfilename, mode="a")    
        zf.writestr(filename, string)
        zf.close()
        

if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    main = MainApp()
    main.show()
    sys.exit(app.exec_())
