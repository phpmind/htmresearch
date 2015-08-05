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

import random



class SequenceGenerator(object):

  def __init__(self, seed=None):
    self.seed = seed


  def generate(self, order, numPredictions=1):
    symbols = range(order + 1 + (numPredictions * 2))
    random.seed(self.seed)
    random.shuffle(symbols)
    random.seed()

    if order == 0:
      return symbols[0:2]

    subsequence = symbols[0:order-1]

    sequences = []

    for i in xrange(2):
      start = order+i-1

      for j in xrange(numPredictions):
        end = -((numPredictions * i) + j + 1)
        sequence = [symbols[start]] + subsequence + [symbols[end]]
        sequences.append(sequence)

    return sequences



if __name__ == "__main__":
  generator = SequenceGenerator(seed=42)

  print "Examples:"
  print "Order 1, with 5 predictions for each sequence:", generator.generate(1, 5)
  print "Order 4, with 3 predictions for each sequence:", generator.generate(4, 3)
  print "Order 10, with 1 prediction for each sequence:", generator.generate(10, 1)

  print

  print "Edge cases:"
  print "Order 0, with 1 prediction for each sequence:", generator.generate(0, 1)
  print "Order 0, with 5 predictions for each sequence:", generator.generate(0, 5)