"""
 OpenFMR: Graphical data analysis program.
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
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QTabWidget, QLineEdit, QTextEdit, QListWidgetItem
from PyQt5.QtWidgets import QVBoxLayout, QHBoxLayout, QPushButton, QFileDialog, QListWidget, QComboBox, QLabel, QMessageBox
from PyQt5.QtGui import QFont
from PyQt5.QtCore import Qt

import pyqtgraph as pg
import zipfile

import scipy.optimize
import scipy.special
import scipy.signal
import scipy.integrate

import numpy as np

import fnmatch


# physical constants
mu0 = 1.2566e-6
muB = 9.274e-24
h = 6.626e-34
e = 1.602e-19
me = 9.11e-31


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.datasets = []  # store datasets
        self.frequencies = []  # store frequencies
        self.fitparameters = []  # store fit parameters/results
        self.linefits = [] # store the line fits
        self.fitPlotItems = []  # store references to fit plot items
        self.DataPlotItems = []  # store references to fit plot items
        self.checked = []  # store the checked status of each dataset
        self.initUI()
        
        # To store the Kittel analysis, first list is extracted resonances, second list is the fit.
        self.KittelAnalysis = [[], []] 
        # To store the Linewidth analysis, first list is extracted line widths
        # (either [f, gamma]) or [f, gamma, sigma], second list is the damping fit.   
        self.LinewidthAnalysis = [[], []] 
        
        # the text report of the Kittel and linewidth analysis
        self.report = ""
        

    def initUI(self):
        # Main widget and layout
        self.centralWidget = QWidget(self)
        self.setCentralWidget(self.centralWidget)
        self.mainLayout = QHBoxLayout(self.centralWidget)

        # Left side - Plot panels
        self.plotLayout = QVBoxLayout()

        
        # Left side - Tabbed plot panels
        self.plotLayout = QVBoxLayout()
        self.tabWidget = QTabWidget()
        self.allPlot = self.createPlotWidget("All Data")
        self.tabWidget.addTab(self.allPlot, "All")
        
        self.plotLayout.addWidget(self.tabWidget)

        # Sub Plot Layout
        self.subPlotLayout = QHBoxLayout()
        
        # Kittel plot
        self.KittelPlot = pg.PlotWidget(title="Kittel plot")
        styles = {'color':'#000', 'font-size':'12px'}

        self.KittelPlot.setLabel('bottom', "resonance field (T)", **styles)
        self.KittelPlot.setLabel('left', "resonance frequency (GHz)", **styles)
        
        self.KittelPlot.setBackground('w')  # Set background to white
        self.KittelPlot.getAxis('left').setPen(color='#000000')
        self.KittelPlot.getAxis('bottom').setPen(color='#000000')
        
        self.subPlotLayout.addWidget(self.KittelPlot)
        
        # linewidth analysis plot       
        self.linewidthPlot = pg.PlotWidget(title="Linewidth Analysis")

        self.linewidthPlot.setLabel('bottom', "resonance frequency (GHz)", **styles)
        self.linewidthPlot.setLabel('left', "HWHM linewidth (T)", **styles)

        self.linewidthPlot.setBackground('w')  # Set background to white
        self.linewidthPlot.getAxis('left').setPen(color='#000000')
        self.linewidthPlot.getAxis('bottom').setPen(color='#000000')        
        
        self.subPlotLayout.addWidget(self.linewidthPlot)
        
        # Add Sub Plot Layout to Main Plot Layout
        self.plotLayout.addLayout(self.subPlotLayout)

        # Right side - Controls and Data Overview
        self.controlLayout = QVBoxLayout()

        # Textbox for displaying the filename
        self.fileNameTextbox = QLineEdit("No file selected")
        self.fileNameTextbox.setReadOnly(True)
        
        # File selection button
        self.fileButton = QPushButton("Select Data File")
        self.fileButton.clicked.connect(self.openFileDialog)
        
        # Data Overview
        self.dataOverview = QListWidget()

        # Adding widgets to the control layout
        self.controlLayout.addWidget(self.fileNameTextbox)
        self.controlLayout.addWidget(self.fileButton)
        self.controlLayout.addWidget(QLabel("Loaded Data:"))
        self.controlLayout.addWidget(self.dataOverview)

        # Dropdown for Mode selection
        self.modeLabel = QLabel("Mode:")
        self.modeComboBox = QComboBox()
        self.modeComboBox.addItems(["in-plane", "out-of-plane"])

        # Dropdown for Fit Profile selection
        self.fitProfileLabel = QLabel("Fit Profile:")
        self.fitProfileComboBox = QComboBox()
        self.fitProfileComboBox.addItems(["Asymmetric Lorentz", "Lorentz", "Voigt"])

        # Button for executing Fit All routine
        self.fitAllButton = QPushButton("Fit All")
        self.fitAllButton.clicked.connect(self.fitAll)

        # QTextEdit for displaying fit parameters
        self.fitResultTextEdit = QTextEdit()
        self.fitResultTextEdit.setReadOnly(True)
        monospaceFont = QFont("Courier", 8)  # You can choose any monospaced font and size
        self.fitResultTextEdit.setFont(monospaceFont)
        self.fitResultTextEdit.setPlaceholderText("Fit Parameters: Not yet calculated")


        # Button for executing data export routine
        self.exportButton = QPushButton("Export Data")
        self.exportButton.clicked.connect(self.export)
 
        # Adding widgets to the control layout
        self.controlLayout.addWidget(self.modeLabel)
        self.controlLayout.addWidget(self.modeComboBox)
        self.controlLayout.addWidget(self.fitProfileLabel)
        self.controlLayout.addWidget(self.fitProfileComboBox)
        self.controlLayout.addWidget(self.fitAllButton)
        self.controlLayout.addWidget(self.fitResultTextEdit)
        self.controlLayout.addWidget(self.exportButton)

        # Add layouts to main layout
        self.mainLayout.addLayout(self.plotLayout, 70)  # 70% of the space for plots
        self.mainLayout.addLayout(self.controlLayout, 30)  # 30% of the space for controls

        self.setWindowTitle("OpenFMR Ferromagnetic Resonance Data Analysis")
        self.setGeometry(100, 100, 1400, 900)


    def createPlotWidget(self, title):
        plotWidget = pg.PlotWidget(title=title)
        plotWidget.setBackground('w')  # Set background to white
        styles = {'color':'#000', 'font-size':'12px'}
        plotWidget.getAxis('left').setPen(color='#000000')
        plotWidget.getAxis('bottom').setPen(color='#000000')
        plotWidget.setLabel('left', "detector lock-in voltage (V)", **styles)
        plotWidget.setLabel('bottom', "field (T)", **styles)
        return plotWidget
    
    
    def openFileDialog(self):
        fileName, _ = QFileDialog.getOpenFileName(self, "Open Data File", "", "Zip Files (*.zip)")
        if fileName:
            self.fileNameTextbox.setText(fileName)
            self.loadData(fileName)

    
    def loadData(self, fileName):
        self.datasets, self.frequencies, frequency_files = self.loadDatasets(fileName)
        self.dataOverview.clear()
        self.DataPlotItems.clear()
        
        # Clear existing tabs except for the "All" tab
        for i in range(self.tabWidget.count() - 1, 0, -1):
            self.tabWidget.removeTab(i)
    
        # Reset the "All" plot
        self.allPlot.clear()
    
        for i, file in enumerate(frequency_files):
            # Add item with a checkbox
            item = QListWidgetItem(file)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)  # Enable checkbox
            item.setCheckState(Qt.Checked)  # Set the checkbox to checked by default
            self.dataOverview.addItem(item)
    
            # Create a new tab with a plot for each file
            plotWidget = self.createPlotWidget(file)
            pen = pg.mkPen(pg.intColor(i, len(self.datasets)), width=2)
            plotItem = plotWidget.plot(self.datasets[i][0], self.datasets[i][1], pen=pen)
            self.tabWidget.addTab(plotWidget, file)
            self.DataPlotItems.append(plotItem)
    
            # Plot the data in the "All" tab with the same pen
            self.allPlot.plot(self.datasets[i][0], self.datasets[i][1], pen=pen)


    def loadDatasets(self, zipfilename):
        zf = zipfile.ZipFile(zipfilename, mode="r")
        files = zf.namelist()

        frequency_files = []
        frequencies = []
        datasets = []

        for file in files:
            if file.endswith(".txt"):
                frequency_files.append(file)
                frequencies.append(float(file.strip("GHz.txt")))
                handle = zf.open(file)
                content = handle.read()
                handle.close()
                c = content.decode()
                lines = c.split("\n")
                fields, voltages = [], []
                for line in lines[0:-1]:
                    f, v = line.split()
                    fields.append(float(f))
                    voltages.append(float(v))
                datasets.append([fields, voltages])

        return datasets, frequencies, frequency_files
    
    
    def fitAll(self):
        fitProfile = self.fitProfileComboBox.currentText()
        mode = self.modeComboBox.currentText()

        # Clear previous fit results
        self.fitparameters.clear()
        self.clearAndReplotOriginalData()
        self.KittelPlot.clear()
        self.linewidthPlot.clear()
        self.linefits.clear()

        self.checked = []
                
        # Fitting routine for resonance lines
        for i, dataset in enumerate(self.datasets):
            if self.dataOverview.item(i).checkState() != Qt.Checked:
                self.checked.append(False)
                continue
            else:
                self.checked.append(True)
            fit = Fit()
            fit_result = fit.LineFit(dataset, fitProfile)
            self.fitparameters.append(fit_result)
            # oversample the fit x-axis and fit
            x = np.linspace(dataset[0][0], dataset[0][-1], len(dataset[0]) * 4)
            fitted_y = fit.calculateFittedLine(x, fit_result[0], fitProfile)
            
            # store line fit
            self.linefits.append([x, fitted_y])
            
            # Get the plot widget for the corresponding dataset and plot fit
            plotWidget = self.tabWidget.widget(i + 1)  # +1 because the first tab is "All Data"
            fitPlotItem = plotWidget.plot(x, fitted_y, pen=pg.mkPen('k', width=1))  # Plot in black with a width of 1 pixels
            self.fitPlotItems.append(fitPlotItem)
         
        resonance_fields = [fit_param[0][1] for fit_param in self.fitparameters]  
        resonance_frequencies = np.array(self.frequencies)[self.checked]

        # Plotting the fit results as big blue circles in the Kittel plot
        self.KittelPlot.plot(resonance_fields, resonance_frequencies, symbol='o', symbolSize=8, pen=None, symbolBrush='b')

        # Perform and plot Kittel fit
        # Plot Kittel fit curve
        resonance_fields = [fit_param[0][1] for fit_param in self.fitparameters]  
        fit = Fit()
        x_fit, y_fit, p, pcov = fit.KittelFit(resonance_fields, resonance_frequencies, mode)
        errors = np.sqrt(np.diagonal(pcov))

        g = p[1]*1e9

        self.KittelPlot.plot(x_fit, y_fit, pen=pg.mkPen('r', width=2))
        
        # store the Kittel results
        self.KittelAnalysis = [[resonance_fields, resonance_frequencies], [x_fit, y_fit]] 

        message = "Line profile: %s\n\n" % fitProfile 
        message += "KITTEL ANALYSIS:\n"
        message += "Magnetization : %10.3f +/- %10.3f kA/m\n" % (p[0] / 1e3, errors[0] / 1e3)
        message += "g-factor      : %10.3f +/- %10.3f\n" % (g, errors[1]*1e9)
        
        # Plotting the fit results as big circles in the linewidth plot
        self.linewidthPlot.addLegend()
        
        gammas, sigmas = None, None
        
        if fitProfile == "Lorentz" or fitProfile == "Asymmetric Lorentz":
             gammas = [fit_param[0][2] for fit_param in self.fitparameters]
             widths = gammas
             self.linewidthPlot.plot(resonance_frequencies, gammas, symbol='o', symbolSize=8, pen=None, symbolBrush='r', name="gamma")
                     
        else: # Voigt profile
            gammas = [fit_param[0][2] for fit_param in self.fitparameters]  
            sigmas = [fit_param[0][3] for fit_param in self.fitparameters] 
            widths = gammas
            self.linewidthPlot.plot(resonance_frequencies, gammas, symbol='o', symbolSize=8, pen=None, symbolBrush='r', name="gamma")
            self.linewidthPlot.plot(resonance_frequencies, sigmas, symbol='o', symbolSize=8, pen=None, symbolBrush='b', name="sigma")
            
        # perform and plot the linewidth linear fit
        gamma_prime = g*e/(2*me) / (2*np.pi)
        
        x_fit, y_fit, p, pcov = fit.DampingFit(np.array(resonance_frequencies)*1e9, widths, gamma_prime)
        errors = np.sqrt(np.diagonal(pcov))

        message += "\n\nLINEWIDTH ANALYSIS:\n"
        message += "alpha          : %8.5f +- %8.5f\n" % (p[0], errors[0])
        message += "DeltaB(0) HWHM : %8.5f +- %8.5f T\n" % (p[1], errors[1])
        
        self.linewidthPlot.plot(x_fit/1e9, y_fit, pen=pg.mkPen('g', width=2))
        
        # store the linewidth analysis 
        if sigmas == None:
            self.LinewidthAnalysis = [[resonance_frequencies, gammas], [x_fit, y_fit]] 
        else: # only relevant for Voigt profil
            self.LinewidthAnalysis = [[resonance_frequencies, gammas, sigmas], [x_fit, y_fit]] 
        
        if fitProfile == "Asymmetric Lorentz":
            message += "\n\nASYMMETRIC LORENTZ ANALYSIS:\n"
            betas = [fit_param[0][4] for fit_param in self.fitparameters]
            message += "%12s %12s\n" % ("f (GHz)", "beta")
            for f, beta in zip (resonance_frequencies, betas):
                message += "%12.2f %12.6f\n" % (f, beta)
             
        self.fitResultTextEdit.setText(message)
        self.report = message
        
            
    def clearAndReplotOriginalData(self):
        for i, plotItem in enumerate(self.DataPlotItems):
            plotWidget = self.tabWidget.widget(i + 1)  # +1 for "All Data" tab
            plotWidget.clear()  # Clear the plot
            plotWidget.addItem(plotItem)  # Re-add the original plot item


    def writedatafile(self, zipfilename, filename, string):
        zf = zipfile.ZipFile(zipfilename, mode="a")    
        zf.writestr(filename, string)
        zf.close()
        
        
    def remove_files_from_zip(self, zip_filename, patterns):
        # Create a temporary ZIP file
        temp_zip_filename = zip_filename + '.tmp'
        
        with zipfile.ZipFile(zip_filename, 'r') as zip_read:
            # Create a new ZIP file
            with zipfile.ZipFile(temp_zip_filename, 'w') as zip_write:
                # Copy all files, except those matching any of the patterns
                for item in zip_read.infolist():
                    # Check if the file matches any of the patterns
                    if not any(fnmatch.fnmatch(item.filename, pattern) for pattern in patterns):
                        data = zip_read.read(item.filename)
                        zip_write.writestr(item, data)
        
        # Replace the old ZIP file with the new one (optional)
        os.remove(zip_filename)
        os.rename(temp_zip_filename, zip_filename)
        

    def export(self):
        # clean up the existing file to remove previously stored fits and report
        remove_patterns = ["*.xy", "Report.log"]
        self.remove_files_from_zip(self.fileNameTextbox.text(), remove_patterns)
        
        # export the line fits
        freqs = np.array(self.frequencies)[self.checked].tolist()
        for i, freq in enumerate(freqs):
            fname = "%.2fGHz.xy" % freq
            string = ""
            for b, f in zip(self.linefits[i][0], self.linefits[i][1]):
                string += "%14.10f %14.10f\n" % (b, f)
            self.writedatafile(self.fileNameTextbox.text(), fname, string)
                    
        # export the Kittel data
        string = "# resonance field (T), resonance frequency (GHz)\n"
        for b, f in zip(self.KittelAnalysis[0][0], self.KittelAnalysis[0][1]):
            string += "%14.10f %14.10f\n" % (b, f)
        self.writedatafile(self.fileNameTextbox.text(), "KittelData.xy", string)
        
        # export the Kittel fit
        string = "# resonance field (T), resonance frequency (GHz)\n"
        for b, f in zip(self.KittelAnalysis[1][0], self.KittelAnalysis[1][1]):
            string += "%14.10f %14.10f\n" % (b, f)
        self.writedatafile(self.fileNameTextbox.text(), "KittelFit.xy", string)
        
        
        # export the linewidth data
        string = "# resonance frequency (GHz), linewidth (T)\n"
        for b, f in zip(self.LinewidthAnalysis[0][0], self.LinewidthAnalysis[0][1]):
            string += "%14.10f %14.10f\n" % (b, f)
        self.writedatafile(self.fileNameTextbox.text(), "LinewidthData.xy", string)
        
        # export the linewidth fit
        string = "# resonance frequency (GHz), linewidth (T)\n"
        for b, f in zip(self.LinewidthAnalysis[1][0], self.LinewidthAnalysis[1][1]):
            string += "%14.10f %14.10f\n" % (b*1e-9, f)
        self.writedatafile(self.fileNameTextbox.text(), "LinewidthFit.xy", string)        
        
        # export the report
        self.writedatafile(self.fileNameTextbox.text(), "Report.log", self.report)        

        # show confirmation message
        msgBox = QMessageBox()
        msgBox.setWindowTitle("Export Confirmation")
        msgBox.setText("Data exported to %s." % self.fileNameTextbox.text())
        msgBox.setStandardButtons(QMessageBox.Ok)
        msgBox.exec_()        


        return

class Fit:
    def __init__(self):
        pass


    def LineFit(self, dataset, fitProfile):
        # Implement the fitting algorithm based on self.mode and self.fitProfile
        # Use self.dataset as the data to be fitted
        # Return the fit results (parameters, statistics, etc.)
        
        x = dataset[0]
        y = dataset[1]
        p, pcov = self.fit_derivative(x, y, fitProfile)
        
        return p, pcov


    def calculateFittedLine(self, x, p, fitProfile):
        x = np.array(x)
        if fitProfile == "Lorentz":
            y = self.lorentz_derivative(x, *p)
        elif fitProfile == "Asymmetric Lorentz":
            y = self.asymmetric_lorentz_derivative(x, *p)
        else:            
            y = self.voigt_derivative(x, *p)
        return y


    # https://journals.aps.org/prb/pdf/10.1103/PhysRevB.84.054423
    def lorentz_derivative(self, B, A, B0, Gamma, offset):
        return A * Gamma**2 * (B0 - B) / ((B - B0)**2 + Gamma**2)**2 + offset
    
    
    # idea taken from https://www.sciencedirect.com/science/article/pii/S1875389216300906
    def voigt_derivative(self, B, A, B0, Gamma, sigma, offset):
        # Use a Voigt profile to deconvolve homogenous (Lorentzian)
        # and inhomogenous (Gaussian) contributions.
        # Calculate the derivative for the fit numerically with second-order finite differences.
        v = A * Gamma**2 * scipy.special.voigt_profile((B-B0), sigma, Gamma)
        v_diff = np.gradient(v, B, edge_order=2) + offset
        return v_diff
    
    
    # https://pubs.aip.org/aip/jap/article/117/14/143902/138614/Eddy-current-interactions-in-a-ferromagnet-normal
    def asymmetric_lorentz_derivative(self, B, A, B0, Gamma, offset, beta):
        # asymmetric Lorentz line shape
        l = A * Gamma**2 * (1 + 2 * beta * (B0 - B)/Gamma) / ((B0 - B)**2 + Gamma**2)
        l_diff = np.gradient(l, B, edge_order=2) + offset
        return l_diff
     
    
    def fit_derivative(self, x, y, fitProfile):
        # dispersive line shape
    
        offset = np.mean(y) # quick estimate

        # half-width estimate
        width = np.abs(x[np.argmax(y)] - x[np.argmin(y)]) / 2 * np.sqrt(3)
        
        
        # check the order of the derivative peaks 
        # then find the position of the peak in the integral
        # and determine the scale
        integral = scipy.integrate.cumtrapz((y-offset), x)
        
        # "down-up" profile
        if np.argmin(y) < np.argmax(y):
            center = x[np.argmin(integral)]
            scale = y[np.argmin(integral)] - offset
        # "up-down" profile
        else:
            center = x[np.argmax(integral)]
            scale = y[np.argmax(integral)] - offset
            
        
        if fitProfile == "Voigt":
            scale *= 10
            
        if fitProfile == "Lorentz":
            scale *= 1e-2
     
        if fitProfile == "Asymmetric Lorentz":
            scale *= 1e-2

        # do the fit with the selected line profile
        if fitProfile == "Lorentz":
            p0 = np.array([scale, center, width, offset])
            p, pcov = scipy.optimize.curve_fit(self.lorentz_derivative, x, y, p0=p0, bounds=([-np.inf, 0, 0, -np.inf], [np.inf, np.inf, np.inf, np.inf]))

        elif fitProfile == "Asymmetric Lorentz":
            p0 = np.array([scale, center, width, offset, 0])
            p, pcov = scipy.optimize.curve_fit(self.asymmetric_lorentz_derivative, x, y, p0=p0, bounds=([-np.inf, 0, 0, -np.inf, -np.inf], [np.inf, np.inf, np.inf, np.inf, np.inf]))
        
        else: # Voigt
            p0 = np.array([scale, center, width, 0.001, offset])
            p, pcov = scipy.optimize.curve_fit(self.voigt_derivative, x, y, p0=p0, bounds=([-np.inf, 0, 0, 0, -np.inf], [np.inf, np.inf, np.inf, np.inf, np.inf]))
        return p, pcov
    

    def KittelFit(self, x, y, mode):
        # Extract data for Kittel fit
        resonance_fields = x
        resonance_frequencies = y

        x_fit = np.linspace(0, max(resonance_fields), 100)

        
        if mode == "in-plane":
            p0 = [1000e3, 2.1]  
            p, pcov = scipy.optimize.curve_fit(self.kittel_fitfunction_inplane, resonance_fields, resonance_frequencies, p0=p0)
            y_fit = self.kittel_fitfunction_inplane(x_fit, *p)

        elif mode == "out-of-plane":
            # initial guess for M
            gamma_prime = 2.1*e/(2*me) / (2*np.pi)
            M = 1/mu0 * np.mean( np.array(resonance_fields) - np.array(resonance_frequencies)*1e9 / gamma_prime)
            p0 = [M, 2.1]
            p, pcov = scipy.optimize.curve_fit(self.kittel_fitfunction_outofplane, resonance_fields, resonance_frequencies, p0=p0)
            y_fit = self.kittel_fitfunction_outofplane(x_fit, *p)

        return x_fit, y_fit, p, pcov


    def kittel_fitfunction_inplane(self, B, M, g):
        gamma_prime = g*e/(2*me) / (2*np.pi)
        return gamma_prime * np.sqrt((B) * (B + mu0 * M))


    def kittel_fitfunction_outofplane(self, B, M, g):
        gamma_prime = g*e/(2*me) / (2*np.pi)
        return gamma_prime * (B - mu0 * M)
    
    
    def DampingFit(self, frequencies, widths, gamma_prime):
        damping_fitfunction_curry = lambda f, alpha, deltaB0: self.damping_fitfunction(f, alpha, deltaB0, gamma_prime)
        
        p0 = [0.005, 0.0]
        p, pcov = scipy.optimize.curve_fit(damping_fitfunction_curry, frequencies, widths, p0=p0)
        x_fit = np.linspace(0, max(frequencies), 100)
        y_fit = damping_fitfunction_curry(x_fit, *p)
        
        return x_fit, y_fit, p, pcov
    
    
    def damping_fitfunction(self, f, alpha, deltaB0, gamma_prime):
        return alpha * f / gamma_prime + deltaB0
    
    
def main():
    app = QApplication(sys.argv)
    mainWindow = MainWindow()
    mainWindow.show()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
