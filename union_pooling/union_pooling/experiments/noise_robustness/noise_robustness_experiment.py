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
import csv
import random
import sys
import time
import os
import yaml
from optparse import OptionParser

import numpy
from pylab import rcParams

from nupic.data.generators.pattern_machine import PatternMachine
from nupic.data.generators.sequence_machine import SequenceMachine
from nupic.research.monitor_mixin.monitor_mixin_base import MonitorMixinBase

from experiments.capacity import data_utils
from union_pooling.experiments.union_pooler_experiment import (
    UnionPoolerExperiment)

"""
Noise Robustness Experiment

Data: Sequences generated from an alphabet.

Train Phase: Train network on sequences for some number of repetitions

Test phase: Input sequence pattern by pattern. Sequence-to-sequence
progression is randomly selected. At each step there is a chance that the
next pattern in the sequence is not shown. Specifically the following
perturbations may occur:

  1) random Jump to another sequence
  2) substitution of some other pattern for the normal expected pattern
  3) skipping expected pattern and presenting next pattern in sequence
  4) addition of some other pattern putting off expected pattern one time step

Goal: Characterize the noise robustness of the UnionPooler to various
perturbations. Explore trade-off between remaining stable to noise yet still
changing when sequence actually changes.
"""



_SHOW_PROGRESS_INTERVAL = 200
_PLOT_RESET_SHADING = 0.2
_PLOT_HEIGHT = 6
_PLOT_WIDTH = 9



def plotNetworkState(experiment, plotVerbosity, trainingPasses, phase=""):

  if plotVerbosity >= 1:
    rcParams["figure.figsize"] = _PLOT_WIDTH, _PLOT_HEIGHT

    # Plot Union SDR trace
    dataTrace = experiment.up._mmTraces["activeCells"].data
    unionSizeTrace = [len(datum) for datum in dataTrace]
    x = [i for i in xrange(len(unionSizeTrace))]
    stdDevs = None
    title = "Union Size; {0} training passses vs. Time".format(trainingPasses)
    data_utils.getErrorbarFigure(title, x, unionSizeTrace, stdDevs, "Time",
                                 "Union Size")
    if plotVerbosity >= 2:
      title = "training passes: {0}, phase: {1}".format(trainingPasses, phase)
      experiment.up.mmGetPlotConnectionsPerColumn(title=title)
      experiment.tm.mmGetCellActivityPlot(title=title,
                                          activityType="activeCells",
                                          showReset=True,
                                          resetShading=_PLOT_RESET_SHADING)
      experiment.tm.mmGetCellActivityPlot(title=title,
                                          activityType="predictedActiveCells",
                                          showReset=True,
                                          resetShading=_PLOT_RESET_SHADING)
      experiment.up.mmGetCellActivityPlot(title=title,
                                          showReset=True,
                                          resetShading=_PLOT_RESET_SHADING)



def runTestPhase(experiment, inputSequences, inputCategories, sequenceCount,
                 sequenceLength, testPresentations, perturbationChance):
  """
  Performs a number of presentations of sequences. Sequence selection is random.
  At each step of sequence presentation there is a chance of a perturbation.
  Specifically the following perturbations may occur:
    1) Substitution of expected pattern with some other random pattern among
    the set of sequences
    2) Skipping of expected pattern and advancing to next pattern in the
    sequence
    3) Insertion of some other random pattern (among the set of sequences)
    that delays the expected pattern one time step

  @return
        actualCategories -    A list of the actual categories of the patterns
                              presented during the test phase
        classifiedCategores - A list of the classifications of the categories
                              of each pattern presented during the test phase
  """

  actualCategories = []
  classifiedCategories = []
  # print "Presentation \tPerturbations"
  for presentation in xrange(testPresentations):

    # Randomly select the next sequence to present
    r = random.randint(0, sequenceCount - 1)
    start = r + r * sequenceLength
    end = r + (r + 1) * sequenceLength # Don't want Nones
    selectedSequence = inputSequences[start:end]
    selectedSequenceCatgories = inputCategories[start:end]

    # Present selected sequence to network
    i = 0
    perturbationCount = 0
    while i < len(selectedSequence):

      # Roll to determine if there will be a perturbation of next pattern
      if (selectedSequence[i] is not None and
          random.random() < perturbationChance):
        perturbationCount += 1

        # Randomly select a perturbation type with equal probability
        perturbationType = random.random()
        if perturbationType < 1.0 / 3.0:

          # Substitution with random pattern
          randIdx = getRandomPatternIndex(inputSequences)
          sensorPattern = inputSequences[randIdx]
          actualCategory = inputCategories[randIdx]
          i += 1
        elif perturbationType < 2.0 / 3.0:

          # Skip to next pattern in sequence
          i += 1
          if i == len(selectedSequence):
            break;
          sensorPattern = selectedSequence[i]
          actualCategory = selectedSequenceCatgories[i]
          i += 1
        else:

          # Add in a random pattern
          randIdx = getRandomPatternIndex(inputSequences)
          sensorPattern = inputSequences[randIdx]
          actualCategory = inputCategories[randIdx]

        # TODO Perturbation type 4) Jump to another sequence randomly (Random
        # jump to sequence start or random position?)
      else:
        sensorPattern = selectedSequence[i]
        actualCategory = selectedSequenceCatgories[i]
        i += 1

      experiment.runNetworkOnPattern(sensorPattern,
                                     tmLearn=False,
                                     upLearn=False)
      actualCategories.append(actualCategory)

      # Store classification
      unionSDR = experiment.up.getUnionSDR()
      winningCategory, _, _, _ = experiment.classifier.infer(unionSDR)
      classifiedCategories.append(winningCategory)

    # TODO Record true perturbation rate
    # print "{0} \t\t {1}".format(presentation, perturbationCount)

  return actualCategories, classifiedCategories



def getRandomPatternIndex(patterns):
  rand = random.randint(0, len(patterns)-1)
  while patterns[rand] is None:
    rand = random.randint(0, len(patterns)-1)
  return rand



def run(params, paramDir, outputDir, plotVerbosity=0, consoleVerbosity=0):
  """
  Runs the noise robustness experiment.

  :param params: A dict containing the following experiment parameters:

        patternDimensionality - Dimensionality of sequence patterns
        patternCardinality - Cardinality (# ON bits) of sequence patterns
        sequenceLength - Length of sequences shown to network
        numberOfSequences - Number of unique sequences used
        trainingPasses - Number of times Temporal Memory is trained on each
        sequence
        testPresentations - Number of sequences presented in test phase
        perturbationChance - Chance of sequence perturbations during test phase
        temporalMemoryParams - A dict of Temporal Memory parameter overrides
        unionPoolerParams - A dict of Union Pooler parameter overrides
        classifierParams - A dict of KNNClassifer parameter overrides

  :param paramDir: Path of parameter file
  :param outputDir: Output will be written to this path
  :param plotVerbosity: Plotting verbosity
  :param consoleVerbosity: Console output verbosity
  """
  startTime = time.time()
  print "Running Noise robustness experiment...\n"
  print "Params dir: {0}".format(os.path.join(os.path.dirname(__file__),
                                              paramDir))
  print "Output dir: {0}\n".format(os.path.join(os.path.dirname(__file__),
                                                outputDir))

  patternDimensionality = params["patternDimensionality"]
  patternCardinality = params["patternCardinality"]
  sequenceLength = params["sequenceLength"]
  numberOfSequences = params["numberOfSequences"]
  trainingPasses = params["trainingPasses"]
  testPresentations = params["testPresentations"]
  perturbationChance = params["perturbationChance"]
  tmParamOverrides = params["temporalMemoryParams"]
  upParamOverrides = params["unionPoolerParams"]
  classifierOverrides = params["classifierParams"]

  # Generate a sequence list and an associated labeled list (both containing a
  # set of sequences separated by None)
  print "Generating sequences..."
  patternAlphabetSize = sequenceLength * numberOfSequences
  patternMachine = PatternMachine(patternDimensionality, patternCardinality,
                                  patternAlphabetSize)
  sequenceMachine = SequenceMachine(patternMachine)

  numbers = sequenceMachine.generateNumbers(numberOfSequences, sequenceLength)
  inputSequences = sequenceMachine.generateFromNumbers(numbers)

  inputCategories = []
  for i in xrange(numberOfSequences):
    for _ in xrange(sequenceLength):
      inputCategories.append(i)
    inputCategories.append(None)

  # Set up the Temporal Memory and Union Pooler network
  print "\nCreating network..."
  experiment = UnionPoolerExperiment(tmParamOverrides, upParamOverrides,
                                     classifierOverrides)

  # Training only the Temporal Memory on the generated sequences
  if trainingPasses > 0:
    print "\nTraining Temporal Memory..."
    if consoleVerbosity > 0:
      print "\nPass\tMean\t\tStdDev\t\tMax\t\t(Bursting Columns)"

  for i in xrange(trainingPasses):
    experiment.runNetworkOnSequences(inputSequences,
                                     inputCategories,
                                     tmLearn=True,
                                     upLearn=None,
                                     classifierLearn=False,
                                     verbosity=consoleVerbosity,
                                     progressInterval=_SHOW_PROGRESS_INTERVAL)
    if consoleVerbosity > 0:
      stats = experiment.getBurstingColumnsStats()
      print "{0}\t{1}\t{2}\t{3}".format(i, stats[0], stats[1], stats[2])

    if plotVerbosity >= 2:
      plotNetworkState(experiment, plotVerbosity, trainingPasses,
                       phase="Training")

  print
  print MonitorMixinBase.mmPrettyPrintMetrics(
      experiment.tm.mmGetDefaultMetrics())
  print

  # With Temporal Memory learning off and Union Pooler running without learning,
  # train the classifier.
  experiment.runNetworkOnSequences(inputSequences,
                                   inputCategories,
                                   tmLearn=False,
                                   upLearn=False,
                                   classifierLearn=True,
                                   verbosity=consoleVerbosity,
                                   progressInterval=_SHOW_PROGRESS_INTERVAL)

  print "\nRunning test phase..."
  actualCategories, classifiedCategories = runTestPhase(experiment,
                                                        inputSequences,
                                                        inputCategories,
                                                        numberOfSequences,
                                                        sequenceLength,
                                                        testPresentations,
                                                        perturbationChance)
  # print
  # print MonitorMixinBase.mmPrettyPrintMetrics(
  #     experiment.tm.mmGetDefaultMetrics() +
  #     experiment.up.mmGetDefaultMetrics())
  # print

  print "\nWriting results to file..."
  outputFileName = "{0}tests_{1}perturbationRate.txt".format(
    testPresentations, perturbationChance)
  writeClassificationTrace(actualCategories, classifiedCategories, outputDir,
                           outputFileName)

  elapsed = int(time.time() - startTime)
  print "\nFinished. Total time: {0:2} seconds.".format(elapsed)

  # if plotVerbosity >= 1:
  #   raw_input("\nPress any key to exit...")



def writeClassificationTrace(actualCategories, classifiedCategories, outputDir,
                             outputFileName):
  """
  Write classification trace to output file.
  :param actualCategories: True categories
  :param classifiedCategories: Classified categories
  :param outputDir: dir where output file will be written
  :param outputFileName: filename of output file
  """
  if not os.path.exists(outputDir):
    os.makedirs(outputDir)

  filePath = os.path.join(outputDir, outputFileName)
  with open(filePath, "wb") as outputFile:
    csvWriter = csv.writer(outputFile)

    csvWriter.writerow(actualCategories)
    csvWriter.writerow(classifiedCategories)

    correct = 0.0
    for i in xrange(len(actualCategories)):
      if actualCategories[i] == classifiedCategories[i]:
        correct += 1

    correctRate = correct / len(actualCategories)
    csvWriter.writerow([correctRate])

    outputFile.flush()



def _getArgs():
  parser = OptionParser(usage="%prog PARAMS_DIR OUTPUT_DIR [options]"
                              "\n\nRun noise robustness experiment using "
                              "params in PARAMS_DIR (relative to this file) "
                              "and outputting results to OUTPUT_DIR.")
  parser.add_option("-p",
                    "--plot",
                    type=int,
                    default=0,
                    dest="plotVerbosity",
                    help="Plotting verbosity: 0 => none, 1 => summary plots, "
                         "2 => detailed plots")
  parser.add_option("-c",
                    "--console",
                    type=int,
                    default=0,
                    dest="consoleVerbosity",
                    help="Console message verbosity: 0 => none")
  (options, args) = parser.parse_args(sys.argv[1:])
  if len(args) < 2:
    parser.print_help(sys.stderr)
    sys.exit()

  absPath = os.path.join(os.path.dirname(__file__), args[0])
  with open(absPath) as paramsFile:
    params = yaml.safe_load(paramsFile)

  return options, args, params



if __name__ == "__main__":
  (_options, _args, _params) = _getArgs()
  run(_params, _args[0], _args[1], _options.plotVerbosity,
      _options.consoleVerbosity)
