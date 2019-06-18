import unittest
import pygsti
import numpy as np
import warnings
import pickle
import os
import copy

from pygsti.construction import std1Q_XYI as std

from ..testutils import BaseTestCase, compare_files, temp_files

# This class is for unifying some models that get used in this file and in testGateSets2.py
class ResultsEstimateTestCase(BaseTestCase):

    def setUp(self):
        super(ResultsEstimateTestCase, self).setUp()

    def test_load_old_results(self):
        vs = "v2" if self.versionsuffix == "" else "v3"
        #pygsti.obj.results.enable_old_python_results_unpickling()
        with pygsti.io.enable_old_object_unpickling():
            with open(compare_files + "/pygsti0.9.6.results.pkl.%s" % vs,'rb') as f:
                results = pickle.load(f)
        #pygsti.obj.results.disable_old_python_results_unpickling()
        #pygsti.io.disable_old_object_unpickling()
        with open(temp_files + "/repickle_old_results.pkl.%s" % vs,'wb') as f:
            #pickle.dump(results.estimates['TP'].models['single'], f) # Debug
            pickle.dump(results, f)

        with pygsti.io.enable_old_object_unpickling("0.9.7"):
            with open(compare_files + "/pygsti0.9.7.results.pkl.%s" % vs,'rb') as f:
                results = pickle.load(f)
        with open(temp_files + "/repickle_old_results.pkl.%s" % vs,'wb') as f:
            pickle.dump(results, f)



if __name__ == '__main__':
    unittest.main(verbosity=2)
