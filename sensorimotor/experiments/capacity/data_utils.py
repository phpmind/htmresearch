#!/usr/bin/env python
# ----------------------------------------------------------------------
# Numenta Platform for Intelligent Computing (NuPIC)
# Copyright (C) 2015, Numenta, Inc.  Unless you have an agreement
# with Numenta, Inc., for a separate license for this software code, the
# following terms and conditions apply:
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see http://www.gnu.org/licenses.
#
# http://numenta.org/licenses/
# ----------------------------------------------------------------------
"""
Combines all output files in a directory into a single file
"""

import csv
import glob
import os

import matplotlib.pyplot as plt
from pylab import rcParams



def combineCsvFiles(directoryPath, outputFileName):
  appendHeader = True

  # Create csv output writer
  os.chdir(directoryPath)
  with open(outputFileName, "wb") as outputFile:
    csvWriter = csv.writer(outputFile)

    # Iterate over csv files in directory
    for csvFileName in glob.glob("*.csv"):

      # Ignore and write over old version of the same file name
      if csvFileName != outputFileName:

        # Read each file writing the pertinent file lines to output
        with open(csvFileName, "rb") as inputFile:
          csvReader = csv.reader(inputFile)
          line = next(csvReader)
          if appendHeader:
            csvWriter.writerow(line)
            appendHeader = False
          line = next(csvReader)
          csvWriter.writerow(line)



def wrangleData(path, xDataColumnIdx, yDataColumnIdxs, yStdDevIdxs):
  """
  Gets chart-ready data from the specified csv file
  """
  assert len(yDataColumnIdxs) == len(yStdDevIdxs)

  with open(path, "r") as inputFile:
    csvReader = csv.reader(inputFile)

    # Get DV values
    isHeader = True
    xData = []
    for row in csvReader:
      if isHeader:
        isHeader = False
      else:
        xData.append(float(row[xDataColumnIdx]))

    # Get IVs' values
    allYData = []
    allYStdDevs = []
    plotTitles = []

    for i, yColIdx in enumerate(yDataColumnIdxs):
      # Reset the csv iterator
      inputFile.seek(0)

      # build the y data and y std devs
      yCol = []
      yColStdDev = []
      isHeader = True
      stdDevIdx = yStdDevIdxs[i]
      for row in csvReader:
        if isHeader:
          plotTitles.append(row[yColIdx])
        else:
          yCol.append(float(row[yColIdx]))

        # Std Devs
        if isHeader:
          isHeader = False
        elif stdDevIdx == -1:
          yColStdDev.append(0)
        else:
          yColStdDev.append(float(row[stdDevIdx]))

      allYData.append(yCol)
      allYStdDevs.append(yColStdDev)

  return xData, allYData, allYStdDevs, plotTitles



def plotCsvData(dir, X, Ys, stdDevs, plotTitles, xAxisLabel, yAxisLabels,
                gridFormat, plotFileName="plots.png"):
  """
  Plots the specified data and saved specified plot to file
  """
  rcParams['figure.figsize'] = 15, 15
  fig = plt.figure()
  fig.suptitle(dir)
  fig.subplots_adjust(left=None, right=None, bottom=None, top=None,
                      wspace=None, hspace=0.35)
  plt.ion()
  plt.show()
  rcParams.update({'font.size': 12})

  for i, y in enumerate(Ys):
    ax = fig.add_subplot(gridFormat + 1 + i)
    ax.set_title(plotTitles[i])
    ax.set_xlabel(xAxisLabel)
    ax.set_ylabel(yAxisLabels[i])
    ax.axis([0, max(X) + 10, 0, 20])
    ax.errorbar(X, y, stdDevs[i])

  plt.draw()
  plt.savefig(plotFileName, bbox_inches="tight")
  raw_input("Press enter...")



def plotSensorimotorExperimentResults():
  """
  A utility to plot the data produced by
  sensorimotor/experiments/capacity/run.py
  """
  filesDir = "output/strict-varyElements/slow2_13/slow10xRedo/"
  combinedFileName = "allCombined.csv"
  combineCsvFiles(filesDir, combinedFileName)


  xColumnIdx = 1

  # Following indices are columns in the excel file produced by
  # sensorimotor/experiments/capacity/run.py and represent the following
  # metrics:
  # Mean & Max Stability, Mean & Max Distinctness, Mean & Max Bursting Cols
  yColumnIdxs = [11, 9, 16, 14, 46, 44]
  yStdDevIdxs = [12, -1, 17, -1, 47, -1]
  yAxisLabels = ["Cells", "Cells", "Cells", "Cells", "Cols", "Cols"]
  xAxisLabel = "Elements"

  iv, dvs, stdDevs, metricTitles = wrangleData(combinedFileName, xColumnIdx,
                                               yColumnIdxs, yStdDevIdxs)

  # 3x2 subplot grid
  gridFormat = 320
  plotCsvData(filesDir, iv, dvs, stdDevs, metricTitles, xAxisLabel, yAxisLabels,
              gridFormat)



if __name__ == "__main__":
  plotSensorimotorExperimentResults()
