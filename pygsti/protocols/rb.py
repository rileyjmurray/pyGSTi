""" RB Protocol objects """
#***************************************************************************************************
# Copyright 2015, 2019 National Technology & Engineering Solutions of Sandia, LLC (NTESS).
# Under the terms of Contract DE-NA0003525 with NTESS, the U.S. Government retains certain rights
# in this software.
# Licensed under the Apache License, Version 2.0 (the "License"); you may not use this file except
# in compliance with the License.  You may obtain a copy of the License at
# http://www.apache.org/licenses/LICENSE-2.0 or in the LICENSE file in the root pyGSTi directory.
#***************************************************************************************************

import time as _time
import os as _os
import numpy as _np
import pickle as _pickle
import collections as _collections
import warnings as _warnings
import copy as _copy
import scipy.optimize as _spo
from scipy.stats import chi2 as _chi2

from . import support as _support
from . import protocol as _proto
from .modeltest import ModelTest as _ModelTest
from .. import objects as _objs
from .. import algorithms as _alg
from .. import construction as _construction
from .. import io as _io
from .. import tools as _tools

from ..objects import wildcardbudget as _wild
from ..objects.profiler import DummyProfiler as _DummyProfiler
from ..objects import objectivefns as _objfns

from ..extras import rb as _rb


#Useful to have a base class?
#class RBInput(_proto.ProtocolInput):
#    pass

#Structure:
# MultiInput -> specifies multiple circuit structures on (possibly subsets of) the same data (e.g. collecting into one large dataset the data for multiple protocols)
# MultiProtocol -> runs, on same input circuit structure & data, multiple protocols (e.g. different GST & model tests on same GST data)
#   if that one input is a MultiInput, then it must have the same number of inputs as there are protocols and each protocol is run on the corresponding input.
#   if that one input is a normal input, then the protocols can cache information in a Results object that is handed down.
# SimultaneousInput -- specifies a "qubit structure" for each sub-input
# SimultaneousProtocol -> runs multiple protocols on the same data, but "trims" circuits and data before running sub-protocols
#  (e.g. Volumetric or randomized benchmarks on different subsets of qubits) -- only accepts SimultaneousInputs.

#Inputs:
# Simultaneous: (spec1)
#    Q1: ByDepthData
#    Q2,Q3: ByDepthData
#    Q4: ByDepthData

#Protocols:
# Simultaneous:
#    Q1: Multi
#      VB (aggregate)
#      PredictedModelA
#      PredictedModelB
#      Datasetcomp (between passes)
#    Q2,Q3: VB
#    Q4: VB

#OR: so that auto-running performs the above protocols:
#Inputs:
# Simultaneous: (spec1)
#    Q1: MultiInput(VB, PredictedModelA, PredictedModelB) - or MultiBenchmark?
#       ByDepthData
#    Q2,Q3: VB-ByDepthData
#    Q4: VB-ByDepthData


class ByDepthInput(_proto.CircuitListsInput):
    def __init__(self, depths, circuit_lists, qubit_labels=None):
        assert(len(depths) == len(circuit_lists)), \
            "Number of depths must equal the number of circuit lists!"
        super().__init__(circuit_lists, qubit_labels=qubit_labels)
        self.depths = depths

        
class BenchmarkingInput(ByDepthInput):
    def __init__(self, depths, circuit_lists, ideal_outs, qubit_labels=None):
        assert(len(depths) == len(ideal_outs))
        super().__init__(depths, circuit_lists, qubit_labels)
        self.idealout_lists = ideal_outs
        self.auxfile_types['idealout_lists'] = 'json'


class CliffordRBInput(BenchmarkingInput):

    def __init__(self, pspec, depths, circuits_per_depth, qubit_labels=None, randomizeout=False,
                 citerations=20, compilerargs=[], descriptor='A Clifford RB experiment',
                 verbosity=1, add_default_protocol=False):
        #Translated from clifford_rb_experiment
        if qubit_labels is None: qubit_labels = tuple(pspec.qubit_labels)
        circuit_lists = []
        ideal_outs = []
    
        for lnum, l in enumerate(depths):
            if verbosity > 0:
                print('- Sampling {} circuits at CRB length {} ({} of {} depths)'.format(circuits_per_depth, l,
                                                                                         lnum + 1, len(depths)))
                print('  - Number of circuits sampled = ', end='')
            circuits_at_depth = []
            idealouts_at_depth = []
            for j in range(circuits_per_depth):
                c, iout = _rb.sample.clifford_rb_circuit(pspec, l, subsetQs=qubit_labels, randomizeout=randomizeout,
                                                  citerations=citerations, compilerargs=compilerargs)
                circuits_at_depth.append(c)
                idealouts_at_depth.append(iout)
                if verbosity > 0: print(j + 1, end=',')
            circuit_lists.append(circuits_at_depth)
            ideal_outs.append(idealouts_at_depth)
            if verbosity > 0: print('')

        super().__init__(depths, circuit_lists, ideal_outs, qubit_labels)
        self.circuits_per_depth = circuits_per_depth
        self.randomizeout = randomizeout
        self.citerations = citerations
        self.compilerargs = compilerargs
        self.descriptor = descriptor
        if add_default_protocol:
            self.add_default_protocol(RB(name='RB'))


class DirectRBInput(BenchmarkingInput):

    def __init__(self, pspec, depths, circuits_per_depth, qubit_labels=None, sampler='Qelimination', samplerargs=[],
                 addlocal=False, lsargs=[], randomizeout=False, cliffordtwirl=True, conditionaltwirl=True,
                 citerations=20, compilerargs=[], partitioned=False, descriptor='A DRB experiment',
                 verbosity=1, add_default_protocol=False):

        if qubit_labels is None: qubit_labels = tuple(pspec.qubit_labels)
        circuit_lists = []
        ideal_outs = []

        for lnum, l in enumerate(depths):
            if verbosity > 0:
                print('- Sampling {} circuits at DRB length {} ({} of {} depths)'.format(circuits_per_depth, l,
                                                                                         lnum + 1, len(depths)))
                print('  - Number of circuits sampled = ', end='')
            circuits_at_depth = []
            idealouts_at_depth = []
            for j in range(circuits_per_depth):
                c, iout = _rb.sample.direct_rb_circuit(
                    pspec, l, subsetQs=qubit_labels, sampler=sampler, samplerargs=samplerargs,
                    addlocal=addlocal, lsargs=lsargs, randomizeout=randomizeout,
                    cliffordtwirl=cliffordtwirl, conditionaltwirl=conditionaltwirl,
                    citerations=citerations, compilerargs=compilerargs,
                    partitioned=partitioned)
                circuits_at_depth.append(c)
                idealouts_at_depth.append((''.join(map(str, iout)),))
                if verbosity > 0: print(j + 1, end=',')
            circuit_lists.append(circuits_at_depth)
            ideal_outs.append(idealouts_at_depth)
            if verbosity > 0: print('')

        super().__init__(depths, circuit_lists, ideal_outs, qubit_labels)
        self.circuits_per_depth = circuits_per_depth
        self.randomizeout = randomizeout
        self.citerations = citerations
        self.compilerargs = compilerargs
        self.descriptor = descriptor
        
        self.sampler = sampler
        self.samplerargs = samplerargs
        self.addlocal = addlocal
        self.lsargs = lsargs
        self.cliffordtwirl = cliffordtwirl
        self.conditionaltwirl = conditionaltwirl
        self.partitioned = partitioned
        
        if add_default_protocol:
            self.add_default_protocol(RB(name='RB'))



#TODO: maybe need more input types for simultaneous RB and mirrorRB "experiments"


class Benchmark(_proto.Protocol):

    summary_datatypes = ('success_counts', 'total_counts', 'hamming_distance_counts',
                         'success_probabilities', 'adjusted_success_probabilities')
    dscmp_datatypes = ('tvds', 'pvals', 'jsds', 'llrs', 'sstvds')

    def __init__(self, name):
        super().__init__(name)

    def compute_summary_data(self, data):

        def success_counts(dsrow, circ, idealout):
            if dsrow.total == 0: return 0  # shortcut?
            return dsrow[idealout]

        def hamming_distance_counts(dsrow, circ, idealout):
            nQ = len(circ.line_labels)  # number of qubits
            assert(nQ == len(idealout[-1]))
            hamming_distance_counts = _np.zeros(nQ + 1, float)
            if dsrow.total > 0:
                for outcome_lbl, counts in dsrow.counts.items():
                    outbitstring = outcome_lbl[-1]
                    hamming_distance_counts[_rb.analysis.hamming_distance(outbitstring, idealout[-1])] += counts
            return list(hamming_distance_counts)  # why a list?

        def adjusted_success_probability(hamming_distance_counts):
            """ TODO: docstring """
            hamming_distance_pdf = _np.array(hamming_distance_counts) / _np.sum(hamming_distance_counts)
            #adjSP = _np.sum([(-1 / 2)**n * hamming_distance_counts[n] for n in range(numqubits + 1)]) / total_counts
            adjSP = _np.sum([(-1 / 2)**n * hamming_distance_pdf[n] for n in range(len(hamming_distance_pdf))])
            return adjSP
        
        def get_summary_values(icirc, circ, dsrow, idealout):
            sc = success_counts(dsrow, circ, idealout)
            tc = dsrow.total
            hdc = hamming_distance_counts(dsrow, circ, idealout)
            
            ret = {'success_counts': sc,
                   'total_counts': tc,
                   'success_probabilities': _np.nan if tc == 0 else sc / tc,
                   'hamming_distance_counts': hdc,
                   'adjusted_success_probabilities': adjusted_success_probability(hdc)}
            return ret

        return self.compute_dict(data, self.summary_datatypes,
                                 get_summary_values, for_passes='all')

    def compute_circuit_data(self, data):
        names = ['success_counts', 'total_counts', 'hamming_distance_counts', 'success_probabilities']

        def get_circuit_values(icirc, circ, dsrow, idealout):
            ret = {'twoQgate_count': circ.twoQgate_count(),
                   'depth': circ.depth(),
                   'target': idealout,
                   'circuit_index': icirc,
                   'width': len(circ.line_labels)}
            ret.update(dsrow.aux)  # note: will only get aux data from *first* pass in multi-pass data
            return ret

        return self.compute_dict(data, names, get_circuit_values, for_passes="first")

    def compute_dscmp_data(self, data, dscomparator):

        def get_dscmp_values(icirc, circ, dsrow, idealout):
            ret = {'tvds':  dscomparator.tvds.get(circ, _np.nan),
                   'pvals': dscomparator.pVals.get(circ, _np.nan),
                   'jsds':  dscomparator.jsds.get(circ, _np.nan),
                   'llrs':  dscomparator.llrs.get(circ, _np.nan)}
            return ret

        return self.compute_dict(data, "dscmpdata", self.dsmp_datatypes, get_dscmp_values, for_passes="none")

    def compute_predicted_probs(self, data, model):

        def get_success_prob(icirc, circ, dsrow, idealout):
            #if set(circ.line_labels) != set(qubits):
            #    trimmedcirc = circ.copy(editable=True)
            #    for q in circ.line_labels:
            #        if q not in qubits:
            #            trimmedcirc.delete_lines(q)
            #else:
            #    trimmedcirc = circ
            return {'success_probabilities': model.probs(circ)[('success',)]}

        return self.compute_dict(data, ('success_probabilities',),
                                 get_success_prob, for_passes="none")

    #def compute_results_qty(self, results, qtyname, component_names, compute_fn, force=False, for_passes="all"):
    def compute_dict(self, data, component_names, compute_fn, for_passes="all"):

        inp = data.input
        ds = data.dataset

        depths = inp.depths
        qty_data = _support.NamedDict('Datatype', 'category', None,
                                      {comp: _support.NamedDict('Depth', 'int', 'float', {depth: [] for depth in depths})
                                       for comp in component_names})

        #loop over all circuits
        for depth, circuits_at_depth, idealouts_at_depth in zip(depths, inp.circuit_lists, inp.idealout_lists):
            for icirc, (circ, idealout) in enumerate(zip(circuits_at_depth, idealouts_at_depth)):
                dsrow = ds[circ] if (ds is not None) else None  # stripOccurrenceTags=True ??
                # -- this is where Tim thinks there's a bottleneck, as these loops will be called for each
                # member of a simultaneous experiment separately instead of having an inner-more iteration
                # that loops over the "structure", i.e. the simultaneous qubit sectors.
                #TODO: <print percentage>

                for component_name, val in compute_fn(icirc, circ, dsrow, idealout).items():
                    qty_data[component_name][depth].append(val)  # maybe use a pandas dataframe here?

        return qty_data

    def create_depthwidth_dict(self, depths, widths, fillfn, seriestype):
        return _support.NamedDict(
            'Depth', 'int', seriestype, {depth: _support.NamedDict(
                'Width', 'int', seriestype, {width: fillfn() for width in widths}) for depth in depths})

    def add_bootstrap_qtys(self, data_cache, num_qtys, finitecounts=True):
        """
        Adds bootstrapped "summary datasets". The bootstrap is over both the finite counts of each
        circuit and over the circuits at each length.

        Note: only adds quantities if they're needed.

        Parameters
        ----------
        num_qtys : int, optional
            The number of bootstrapped datasets to construct.

        Returns
        -------
        None
        """
        key = 'bootstraps' if finitecounts else 'infbootstraps'
        if key in data_cache:
            num_existing = len(data_cache['bootstraps'])
        else:
            data_cache[key] = []
            num_existing = 0

        #extract "base" values from cache, to base boostrap off of
        success_probabilities = data_cache['success_probabilities']
        total_counts = data_cache['total_counts']
        hamming_distance_counts = data_cache['hamming_distance_counts']
        depths = list(success_probabilities.keys())

        for i in range(num_existing, num_qtys):

            component_names = self.summary_datatypes
            bcache = _support.NamedDict(
                'Datatype', 'category', None,
                {comp: _support.NamedDict('Depth', 'int', 'float', {depth: [] for depth in depths})
                 for comp in component_names})  # ~= "RB summary dataset"

            for depth, SPs in success_probabilities.items():
                numcircuits = len(SPs)
                for k in range(numcircuits):
                    ind = _np.random.randint(numcircuits)
                    sampledSP = SPs[ind]
                    totalcounts = total_counts[depth][ind] if finitecounts else None
                    bcache['success_probabilities'][depth].append(sampledSP)
                    if finitecounts:
                        bcache['success_counts'][depth].append(_np.random.binomial(totalcounts, sampledSP))
                        bcache['total_counts'][depth].append(totalcounts)
                    else:
                        bcache['success_counts'][depth].append(sampledSP)

                    #ind = _np.random.randint(numcircuits)  # note: old code picked different random ints
                    #totalcounts = total_counts[depth][ind] if finitecounts else None  # do this again if a different randint
                    sampledHDcounts = hamming_distance_counts[depth][ind]
                    sampledHDpdf = _np.array(sampledHDcounts) / _np.sum(sampledHDcounts)

                    if finitecounts:
                        bcache['hamming_distance_counts'][depth].append(
                            list(_np.random.multinomial(totalcounts, sampledHDpdf)))
                    else:
                        bcache['hamming_distance_counts'][depth].append(sampledHDpdf)

                    # replicates adjusted_success_probability function above
                    adjSP = _np.sum([(-1 / 2)**n * sampledHDpdf[n] for n in range(len(sampledHDpdf))])
                    bcache['adjusted_success_probabilities'][depth].append(adjSP)

            data_cache[key].append(bcache)


class PassStabilityTest(_proto.Protocol):
    pass


class VolumetricBenchmarkGrid(Benchmark):
    #object that can take, e.g. a multiinput or simultaneous input and create a results object with the desired grid of width vs depth numbers

    def __init__(self, depths='all', widths='all', datatype='success_probabilities',
                 paths='all', statistic='mean', aggregate=True, rescaler='auto',
                 dscomparator=None, name=None):

        super().__init__(name)
        self.depths = depths
        self.widths = widths
        self.datatype = datatype
        self.paths = paths if paths == 'all' else sorted(paths)  # need to ensure paths are grouped by common prefix
        self.statistic = statistic
        self.aggregate = aggregate
        self.dscomparator = dscomparator
        self.rescaler = rescaler

        self.auxfile_types['dscomparator'] = 'pickle'
        self.auxfile_types['rescaler'] = 'reset'  # punt for now - fix later

    def run(self, data):
        #Note: implement "run" here, since we want to deal with multi-pass and multi-inputs

        #Since we know that VolumetricBenchmark protocol objects Create a single results just fill
        # in data under the result object's 'volumetric_benchmarks' and 'failure_counts'
        # keys, and these are indexed by width and depth (even though each VolumetricBenchmark
        # only contains data for a single width), we can just "merge" the VB results of all
        # the underlying by-depth datas, so long as they're all for different widths.

        #results.volumetric_benchmarks = vb
        #results.failure_counts = fails

        #Run VB protocol on appropriate paths -> separate_results
        if self.paths == 'all':
            paths = data.get_tree_paths()
            trimmed_data = data
        else:
            paths = self.paths
            trimmed_data = data.filter_paths(self.paths)

        #Then run resulting data normally, giving a results object
        # with "top level" dicts correpsonding to different paths
        VB = VolumetricBenchmark(self.depths, self.datatype, self.statistic,
                                 self.rescaler, self.dscomparator, name=self.name)
        separate_results = _proto.SimpleRunner(VB).run(trimmed_data)
        
        #Process results
        #Merge/flatten the data from different paths into one depth vs width grid
        passnames = list(data.passes.keys()) if data.is_multipass() else [None]
        passresults = []
        for passname in passnames:
            vb = _support.NamedDict('Depth', 'int', None)
            fails = _support.NamedDict('Depth', 'int', None)
            path_for_gridloc = {}
            for path in paths:
                #TODO: need to be able to filter based on widths... - maybe replace .update calls
                # with something more complicated when width != 'all'
                #print("Aggregating path = ", path)  #TODO - show progress something like this later?
                
                #Traverse path to get to root of VB data
                root = separate_results
                for key in path:
                    root = root[key]
                root = root.for_protocol[self.name]
                if passname:  # then we expect final Results are MultiPassResults
                    root = root.passes[passname]  # now root should be a BenchmarkingResults
                assert(isinstance(root, VolumetricBenchmarkingResults))
                assert(isinstance(root.data.input, ByDepthInput)), \
                    "All paths must lead to by-depth inputs, not %s!" % str(type(root.data.input))

                #Get the list of depths we'll extract from this (`root`) sub-results
                depths = root.data.input.depths if (self.depths == 'all') else \
                    filter(lambda d: d in self.depths, root.data.input.depths)
                width = len(root.data.input.qubit_labels)  # sub-results contains only a single width

                for depth in depths:
                    if depth not in vb:  # and depth not in fails
                        vb[depth] = _support.NamedDict('Width', 'int', 'float')
                        fails[depth] = _support.NamedDict('Width', 'int', None)
                        path_for_gridloc[depth] = {}  # just used for meaningful error message

                    if width in path_for_gridloc[depth]:
                        raise ValueError(("Paths %s and %s both give data for depth=%d, width=%d!  Set the `paths`"
                                          " argument of this VolumetricBenchmarkGrid to avoid this.") %
                                         (str(path_for_gridloc[depth][width]), str(path), depth, width))

                    vb[depth][width] = root.volumetric_benchmarks[depth][width]
                    fails[depth][width] = root.failure_counts[depth][width]
                    path_for_gridloc[depth][width] = path

            if self.statistic in ('minmin', 'maxmax') and not self.aggregate:
                self._update_vb_minmin_maxmax(vb)   # aggregate now since we won't aggregate over passes

            #Create Results
            results = VolumetricBenchmarkingResults(data, self)
            results.volumetric_benchmarks = vb
            results.failure_counts = fails
            passresults.append(results)
            
        if self.aggregate and len(passnames) > 1:  # aggregate pass data into a single set of qty dicts
            agg_vb = _support.NamedDict('Depth', 'int', None)
            agg_fails = _support.NamedDict('Depth', 'int', None)
            template = passresults[0].volumetric_benchmarks  # to get widths and depths

            #Get function to aggregate the different per-circuit datatype values
            if self.statistic == 'max' or self.statistic == 'maxmax':
                np_fn = _np.nanmax
            elif self.statistic == 'mean':
                np_fn = _np.nanmean
            elif self.statistic == 'min' or self.statistic == 'minmin':
                np_fn = _np.nanmin
            elif self.statistic == 'dist':
                def np_fn(v): return v  # identity
            else: raise ValueError("Invalid statistic '%s'!" % self.statistic)

            def agg_fn(percircuitdata, width, rescale=True):
                """ Aggregates datatype-data for all circuits at same depth """
                rescaled = self.rescale_function(percircuitdata, width) if rescale else percircuitdata
                if _np.isnan(rescaled).all():
                    return _np.nan
                else:
                    return np_fn(rescaled)

            for depth, template_by_width_data in template.items():
                agg_vb[depth] = _support.NamedDict('Width', 'int', 'float')
                agg_fails[depth] = _support.NamedDict('Width', 'int', None)

                for width in template_by_width_data.keys():
                    # ppd = "per pass data"
                    vb_ppd = [r.volumetric_benchmarks[depth][width] for r in passresults]
                    fail_ppd = [r.failure_counts[depth][width] for r in passresults]

                    successcount = 0
                    failcount = 0
                    for (successcountpass, failcountpass) in fail_ppd:
                        successcount += successcountpass
                        failcount += failcountpass
                    agg_fails[depth][width] = (successcount, failcount)

                    if self.statistic == 'dist':
                        agg_vb[depth][width] = [item for sublist in vb_ppd for item in sublist]
                    else:
                        agg_vb[depth][width] = agg_fn(vb_ppd, width, rescale=False)

            aggregated_results = VolumetricBenchmarkingResults(data, self)
            aggregated_results.volumetric_benchmarks = agg_vb
            aggregated_results.failure_counts = agg_fails

            if self.statistic in ('minmin', 'maxmax'):
                self._update_vb_minmin_maxmax(aggregated_results.qtys['volumetric_benchmarks'])
            return aggregated_results  # replace per-pass results with aggregated results
        elif len(passnames) > 1:
            multipass_results = _proto.MultiPassResults(data, self)
            multipass_results.passes.update({passname: r for passname, r in zip(passnames, passresults)})
            return multipass_results
        else:
            return passresults[0]

    def _update_vb_minmin_maxmax(self, vb):
        for d in vb.keys():
            for w in vb[d].keys():
                for d2 in vb.keys():
                    for w2 in vb[d2].keys():
                        if self.statistic == 'minmin' and d2 <= d and w2 <= w and vb[d2][w2] < vb[d][w]:
                            vb[d][w] = vb[d2][w2]
                        if self.statistic == 'maxmax' and d2 >= d and w2 >= w and vb[d2][w2] > vb[d][w]:
                            vb[d][w] = vb[d2][w2]


class VolumetricBenchmark(Benchmark):

    def __init__(self, depths='all', datatype='success_probabilities',
                 statistic='mean', rescaler='auto', dscomparator=None, name=None):

        assert(statistic in ('max', 'mean', 'min', 'dist', 'maxmax', 'minmin'))

        super().__init__(name)
        self.depths = depths
        #self.widths = widths  # widths='all',
        self.datatype = datatype
        self.statistic = statistic
        self.dscomparator = dscomparator
        self.rescaler = rescaler

        self.auxfile_types['dscomparator'] = 'pickle'
        self.auxfile_types['rescale_function'] = 'none'  # don't serialize this, so need _set_rescale_function
        self._set_rescale_function()

    def _init_unserialized_attributes(self):
        self._set_rescale_function()

    def _set_rescale_function(self):
        rescaler = self.rescaler
        if isinstance(rescaler, str):
            if rescaler == 'auto':
                if self.datatype == 'success_probabilities':
                    def rescale_function(data, width):
                        return list((_np.array(data) - 1 / 2**width) / (1 - 1 / 2**width))
                else:
                    def rescale_function(data, width):
                        return data
            elif rescaler == 'none':
                def rescale_function(data, width):
                    return data
            else:
                raise ValueError("Unknown rescaling option!")
        else:
            rescale_function = rescaler
        self.rescale_function = rescale_function

    def run(self, data):

        inp = data.input

        #Note: can only take/put things ("results") in data.cache that *only* depend on the input
        # and dataset (i.e. the DataProtocol object).  Protocols must be careful of this in their implementation!
        if self.datatype in self.summary_datatypes:
            if self.datatype not in data.cache:
                summary_data_dict = self.compute_summary_data(data)
                data.cache.update(summary_data_dict)
        elif self.datatype in self.dscmp_datatypes:
            if self.datatype not in data.cache:
                dscmp_data = self.compute_dscmp_data(data, self.dscomparator)
                data.cache.update(dscmp_data)
        else:
            raise ValueError("Invalid datatype: %s" % self.datatype)
        src_data = data.cache[self.datatype]

        #self.compute_circuit_data(results)
        #self.compute_predicted_probs(results, qtyname, model)

        #Get function to aggregate the different per-circuit datatype values
        if self.statistic == 'max' or self.statistic == 'maxmax':
            np_fn = _np.nanmax
        elif self.statistic == 'mean':
            np_fn = _np.nanmean
        elif self.statistic == 'min' or self.statistic == 'minmin':
            np_fn = _np.nanmin
        elif self.statistic == 'dist':
            def np_fn(v): return v  # identity
        else: raise ValueError("Invalid statistic '%s'!" % self.statistic)

        def agg_fn(percircuitdata, width, rescale=True):
            """ Aggregates datatype-data for all circuits at same depth """
            rescaled = self.rescale_function(percircuitdata, width) if rescale else percircuitdata
            if _np.isnan(rescaled).all():
                return _np.nan
            else:
                return np_fn(rescaled)

        def failcnt_fn(percircuitdata):
            """ Returns (nSucceeded, nFailed) for all circuits at same depth """
            nCircuits = len(percircuitdata)
            failcount = int(_np.sum(_np.isnan(percircuitdata)))
            return (nCircuits - failcount, failcount)

        #TODO REMOVE
        #BEFORE SimultaneousInputs: for qubits in inp.get_structure():        
        #width = len(qubits)

        data_per_depth = src_data
        if self.depths == 'all':
            depths = data_per_depth.keys()
        else:
            depths = filter(lambda d: d in data_per_depth, self.depths)
        width = len(inp.qubit_labels)

        vb = self.create_depthwidth_dict(depths, (width,), lambda: None, 'float')
        fails = self.create_depthwidth_dict(depths, (width,), lambda: None, None)

        for depth in depths:
            percircuitdata = data_per_depth[depth]
            fails[depth][width] = failcnt_fn(percircuitdata)
            vb[depth][width] = agg_fn(percircuitdata, width)

        results = VolumetricBenchmarkingResults(data, self)  # 'Qty', 'category'
        results.volumetric_benchmarks = vb
        results.failure_counts = fails
        return results


class PredictedData(_proto.Protocol):
    #maybe just a function??

    def __init__(self, name):
        super().__init__(name)

    def run(self, data):

        for i, ((circ, dsrow), auxdict, (pcirc, pdsrow)) in enumerate(iterator):
            if pcirc is not None:
                if not circ == pcirc:
                    print('-{}-'.format(i))
                    pdsrow = predds[circ]
                    _warnings.warn("Predicted DataSet is ordered differently to the main DataSet!"
                                   + "Reverting to potentially slow dictionary hashing!")

        #Similar to above but only on first dataset... see create_summary_data
            

class RB(Benchmark):
    def __init__(self, seed=(0.8, 0.95), bootstrap_samples=200, asymptote='std', rtype='EI',
                 datatype='success_probabilities', depths='all', name=None):
        super().__init__(name)

        assert(datatype in self.summary_datatypes), "Unknown data type: %s!" % str(datatype)
        assert(datatype in ('success_probabilities', 'adjusted_success_probabilities')), \
            "Data type '%s' must be 'success_probabilities' or 'adjusted_success_probabilities'!" % str(datatype)

        self.seed = seed
        self.depths = depths
        self.bootstrap_samples = bootstrap_samples
        self.asymptote = asymptote
        self.rtype = rtype
        self.datatype = datatype  #TIM: old code had an 'auto' option and used different vals, e.g. 'raw' - CHECK THIS

    def run(self, data):

        inp = data.input

        if self.datatype not in data.cache:
            summary_data_dict = self.compute_summary_data(data)
            data.cache.update(summary_data_dict)
        src_data = data.cache[self.datatype]
        data_per_depth = src_data

        if self.depths == 'all':
            depths = list(data_per_depth.keys())
        else:
            depths = filter(lambda d: d in data_per_depth, self.depths)

        nQubits = len(inp.qubit_labels)

        if isinstance(self.asymptote, str):
            assert(self.asymptote == 'std'), "If `asymptote` is a string it must be 'std'!"
            if self.datatype == 'success_probabilities':
                asymptote = 1 / 2**nQubits
            elif self.datatype == 'adjusted_success_probabilities':
                asymptote = 1 / 4**nQubits
            else:
                raise ValueError("No 'std' asymptote for %s datatype!" % self.asymptote)

        #if datatype == 'adjusted':
        #    ASPs = RBSdataset.adjusted_ASPs
        #if datatype == 'raw':
        #    ASPs = RBSdataset.ASPs

        def get_rb_fits(circuitdata_per_depth):
            ASPs = []
            for depth in depths:
                percircuitdata = circuitdata_per_depth[depth]
                ASPs.append(_np.mean(percircuitdata))  # average [adjusted] success probabilities

            full_fit_results, fixed_asym_fit_results = _rb.analysis.std_least_squares_data_fitting(
                depths, ASPs, nQubits, seed=self.seed, asymptote=asymptote,
                ftype='full+FA', rtype=self.rtype)

            return full_fit_results, fixed_asym_fit_results

        #do RB fit on actual data
        FF_results, FAF_results = get_rb_fits(data_per_depth)

        if self.bootstrap_samples > 0:

            parameters = ['A', 'B', 'p', 'r']
            bootstraps_FF = {p: [] for p in parameters}
            bootstraps_FAF = {p: [] for p in parameters}
            failcount_FF = 0
            failcount_FAF = 0

            #Store bootstrap "cache" dicts (containing summary keys) as a list under data.cache
            if 'bootstraps' not in data.cache or len(data.cache['bootstraps']) < self.bootstrap_samples:
                self.add_bootstrap_qtys(data.cache, self.bootstrap_samples, finitecounts=True)  #TIM - finite counts always True here?
            bootstrap_caches = data.cache['bootstraps']  # if finitecounts else 'infbootstraps'

            for bootstrap_cache in bootstrap_caches:
                BS_FF_results, BS_FAF_results = get_rb_fits(bootstrap_cache[self.datatype])

                if BS_FF_results['success']:
                    for p in parameters:
                        bootstraps_FF[p].append(BS_FF_results['estimates'][p])
                else:
                    failcount_FF += 1
                if BS_FAF_results['success']:
                    for p in parameters:
                        bootstraps_FAF[p].append(BS_FAF_results['estimates'][p])
                else:
                    failcount_FAF += 1

            failrate_FF = failcount_FF / self.bootstrap_samples
            failrate_FAF = failcount_FAF / self.bootstrap_samples

            std_FF = {p: _np.std(_np.array(bootstraps_FF[p])) for p in parameters}
            std_FAF = {p: _np.std(_np.array(bootstraps_FAF[p])) for p in parameters}

        else:
            bootstraps_FF = None
            std_FF = None
            failrate_FF = None

            bootstraps_FAF = None
            std_FAF = None
            failrate_FAF = None

        fits = _support.NamedDict('FitType', 'category')
        fits['full'] = _rb.analysis.FitResults(
            'LS', FF_results['seed'], self.rtype, FF_results['success'], FF_results['estimates'],
            FF_results['variable'], stds=std_FF, bootstraps=bootstraps_FF,
            bootstraps_failrate=failrate_FF)

        fits['A-fixed'] = _rb.analysis.FitResults(
            'LS', FAF_results['seed'], self.rtype, FAF_results['success'],
            FAF_results['estimates'], FAF_results['variable'], stds=std_FAF,
            bootstraps=bootstraps_FAF, bootstraps_failrate=failrate_FAF)

        return RandomizedBenchmarkingResults(data, self, fits, depths)


class RandomizedBenchmarkingResults(_proto.ProtocolResults):
    def __init__(self, data, protocol_instance, fits, depths):
        """
        Initialize an empty Results object.
        TODO: docstring
        """
        super().__init__(data, protocol_instance)

        self.depths = depths  # Note: can be different from protocol_instance.depths (which can be 'all')
        self.rtype = protocol_instance.rtype  # replicated for convenience?
        self.fits = fits
        self.auxfile_types['fits'] = 'pickle'  # b/c NamedDict don't json

    def plot(self, fitkey=None, decay=True, success_probabilities=True, size=(8, 5), ylim=None, xlim=None,
             legend=True, title=None, figpath=None):
        """
        Plots RB data and, optionally, a fitted exponential decay.

        Parameters
        ----------
        fitkey : dict key, optional
            The key of the self.fits dictionary to plot the fit for. If None, will
            look for a 'full' key (the key for a full fit to A + Bp^m if the standard
            analysis functions are used) and plot this if possible. It otherwise checks
            that there is only one key in the dict and defaults to this. If there are
            multiple keys and none of them are 'full', `fitkey` must be specified when
            `decay` is True.

        decay : bool, optional
            Whether to plot a fit, or just the data.

        success_probabilities : bool, optional
            Whether to plot the success probabilities distribution, as a violin plot. (as well
            as the *average* success probabilities at each length).

        size : tuple, optional
            The figure size

        ylim, xlim : tuple, optional
            The x and y limits for the figure.

        legend : bool, optional
            Whether to show a legend.

        title : str, optional
            A title to put on the figure.

        figpath : str, optional
            If specified, the figure is saved with this filename.
        """

        # Future : change to a plotly plot.
        try: import matplotlib.pyplot as _plt
        except ImportError: raise ValueError("This function requires you to install matplotlib!")

        if decay and fitkey is None:
            allfitkeys = list(self.fits.keys())
            if 'full' in allfitkeys: fitkey = 'full'
            else:
                assert(len(allfitkeys) == 1), \
                    "There are multiple fits and none have the key 'full'. Please specify the fit to plot!"
                fitkey = allfitkeys[0]

        ASPs = []
        data_per_depth = self.data.cache[self.protocol_instance.datatype]
        for depth in self.depths:
            percircuitdata = data_per_depth[depth]
            ASPs.append(_np.mean(percircuitdata))  # average [adjusted] success probabilities

        _plt.figure(figsize=size)
        _plt.plot(self.depths, ASPs, 'o', label='Average success probabilities')

        if decay:
            lengths = _np.linspace(0, max(self.depths), 200)
            A = self.fits[fitkey].estimates['A']
            B = self.fits[fitkey].estimates['B']
            p = self.fits[fitkey].estimates['p']
            _plt.plot(lengths, A + B * p**lengths,
                      label='Fit, r = {:.2} +/- {:.1}'.format(self.fits[fitkey].estimates['r'],
                                                              self.fits[fitkey].stds['r']))

        if success_probabilities:
            all_success_probs_by_depth = [data_per_depth[depth] for depth in self.depths]
            _plt.violinplot(all_success_probs_by_depth, self.depths, points=10, widths=1.,
                            showmeans=False, showextrema=False, showmedians=False)  # , label='Success probabilities')

        if title is not None: _plt.title(title)
        _plt.ylabel("Success probability")
        _plt.xlabel("RB sequence length $(m)$")
        _plt.ylim(ylim)
        _plt.xlim(xlim)

        if legend: _plt.legend()

        if figpath is not None: _plt.savefig(figpath, dpi=1000)
        else: _plt.show()

        return


class VolumetricBenchmarkingResults(_proto.ProtocolResults):
    def __init__(self, data, protocol_instance):
        """
        Initialize an empty Results object.
        TODO: docstring
        """
        super().__init__(data, protocol_instance)

        self.volumetric_benchmarks = {}
        self.failure_counts = {}

        self.auxfile_types['volumetric_benchmarks'] = 'pickle'  # b/c NamedDicts don't json
        self.auxfile_types['failure_counts'] = 'pickle'  # b/c NamedDict don't json


RBResults = RandomizedBenchmarkingResults  # shorthand
VBResults = VolumetricBenchmarkingResults  # shorthand
