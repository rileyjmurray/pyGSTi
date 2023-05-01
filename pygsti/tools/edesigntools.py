"""
Tools for working with ExperimentDesigns
"""
#***************************************************************************************************
# Copyright 2015, 2019 National Technology & Engineering Solutions of Sandia, LLC (NTESS).
# Under the terms of Contract DE-NA0003525 with NTESS, the U.S. Government retains certain rights
# in this software.
# Licensed under the Apache License, Version 2.0 (the "License"); you may not use this file except
# in compliance with the License.  You may obtain a copy of the License at
# http://www.apache.org/licenses/LICENSE-2.0 or in the LICENSE file in the root pyGSTi directory.
#***************************************************************************************************

import numpy as _np
import pygsti.baseobjs as _baseobjs
from math import ceil
from mpi4py import MPI

def calculate_edesign_estimated_runtime(edesign, gate_time_dict=None, gate_time_1Q=None,
                                        gate_time_2Q=None, measure_reset_time=0.0,
                                        interbatch_latency=0.0, total_shots_per_circuit=1000,
                                        shots_per_circuit_per_batch=None, circuits_per_batch=None):
    """Estimate the runtime for an ExperimentDesign from gate times and batch sizes.

    The rough model is that the required circuit shots are split into batches,
    where each batch runs a subset of the circuits for some fraction of the needed shots.
    One round consists of running all batches once, i.e. collecting some shots for all circuits,
    and rounds are repeated until the required number of shots is met for all circuits.

    In addition to gate times, the user can also provide the time at the end of each circuit
    for measurement and/or reset, as well as the latency between batches for classical upload/
    communication of the next set of circuits. Since times are user-provided, this function
    makes no assumption on the units of time, only that a consistent unit is used for all times.

    Parameters
    ----------
    edesign: ExperimentDesign
        An experiment design containing all required circuits.

    gate_time_dict: dict
        Dictionary with keys as either gate names or gate labels (for qubit-specific overrides)
        and values as gate time in user-specified units. All operations in the circuits of
        `edesign` must be specified. Either `gate_time_dict` or both `gate_time_1Q` and `gate_time_2Q`
        must be specified.

    gate_time_1Q: float
        Gate time in user-specified units for all operations acting on one qubit. Either `gate_time_dict`
        or both `gate_time_1Q` and `gate_time_2Q` must be specified.

    gate_time_2Q: float
        Gate time in user-specified units for all operations acting on more than one qubit.
        Either `gate_time_dict` or both `gate_time_1Q` and `gate_time_2Q` must be specified.

    measure_reset_time: float
        Measurement and/or reset time in user-specified units. This is applied once for every circuit.

    interbatch_latency: float
        Time between batches in user-specified units.

    total_shots_per_circuit: int
        Total number of shots per circuit. Together with `shots_per_circuit_per_batch`, this will
        determine the total number of rounds needed.

    shots_per_circuit_per_batch: int
        Number of shots to do for each circuit within a batch. Together with `total_shots_per_circuit`,
        this will determine the total number of rounds needed. If None, this is set to the total shots,
        meaning that only one round is done.

    circuits_per_batch: int
        Number of circuits to include in each batch. Together with the number of circuits in `edesign`,
        this will determine the number of batches in each round. If None, this is set to the total number
        of circuits such that only one batch is done.

    Returns
    -------
    float
        The estimated time to run the experiment design.
    """
    assert gate_time_dict is not None or \
        (gate_time_1Q is not None and gate_time_2Q is not None), \
        "Must either specify a gate_time_dict with entries for every gate name or label, " + \
        "or specify gate_time_1Q and gate_time_2Q for one-qubit and two-qubit gate times, respectively"

    def layer_time(layer):
        gate_times = []
        for comp in layer.components:
            if gate_time_dict is not None:
                # Use specific gate times for each gate
                comp_time = gate_time_dict.get(comp, None)  # Start with most specific key first
                if comp_time is None:
                    comp_time = gate_time_dict.get(comp.name, None)  # Try gate name only next

                assert comp_time is not None, f"Could not look up gate time for {comp}"
            else:
                # Use generic one/two qubit gate times
                comp_qubits = len(comp.sslbls)
                comp_time = gate_time_2Q if comp_qubits > 1 else gate_time_1Q

            gate_times.append(comp_time)

        if len(gate_times) == 0:
            return 0

        return max(gate_times)

    total_circ_time = 0.0
    for circ in edesign.all_circuits_needing_data:
        circ_time = measure_reset_time + sum([layer_time(l) for l in circ])
        total_circ_time += circ_time * total_shots_per_circuit

    # Default assume all in one batch
    if circuits_per_batch is None:
        circuits_per_batch = len(edesign.all_circuits_needing_data)

    # Default assume all in one round
    if shots_per_circuit_per_batch is None:
        shots_per_circuit_per_batch = total_shots_per_circuit

    num_rounds = _np.ceil(total_shots_per_circuit / shots_per_circuit_per_batch)
    num_batches = _np.ceil(len(edesign.all_circuits_needing_data) / circuits_per_batch)

    total_upload_time = interbatch_latency * num_batches * num_rounds

    return total_circ_time + total_upload_time


def calculate_fisher_information_per_circuit(regularized_model, circuits, approx=False, verbosity=1, comm = None, mem_limit = None, shared_memory=False):
    """Helper function to calculate all Fisher information terms for each circuit.

    This function can be used to pre-generate a cache for the
    calculate_fisher_information_matrix() function, and this should be done for
    computational efficiency when computing many Fisher information matrices.

    Parameters
    ----------
    regularized_model: OpModel
        The model used to calculate the terms of the Fisher information matrix.
        This model must already be "regularized" such that there are no small probabilities,
        usually by adding a small amount of SPAM error.

    circuits: list
        List of circuits to compute Fisher information for.
        
    approx: bool, optional (default False)
        When set to true use the approximate fisher information where we drop the 
        hessian term. Significantly faster to compute than when including the hessian.
        
    verbosity: int, optional (default 1)
        Used to control the level of output printed by a VerbosityPrinter object.

    comm : mpi4py.MPI.Comm, optional
        When not None, an MPI communicator for distributing the computation
        across multiple processors.
        
    mem_limit : int, optional
        A rough memory limit in bytes which is used to determine job allocation
        when there are multiple processors.

    Returns
    -------
    fisher_info_terms: dict
        Dictionary where keys are circuits and values are (num_params, num_params) Fisher information
        matrices for a single circuit.
    """
    
    printer = _baseobjs.VerbosityPrinter.create_printer(verbosity, comm)
    
    num_params = regularized_model.num_params
    outcomes = regularized_model.sim.probs(()).keys()
    
    resource_alloc = _baseobjs.ResourceAllocation(comm= comm, mem_limit = mem_limit)
    
    import time
    
    start = time.time()
    printer.log('Calculating Probabilities, Jacobians and Hessians (if not using approx FIM).', 2)
    printer.log('Calculating Probabilities.', 3)
    ps = regularized_model.sim.bulk_probs(circuits, resource_alloc)
    printer.log('Calculating Jacobians.', 3)
    js = regularized_model.sim.bulk_dprobs(circuits, resource_alloc)
    #if approx is true we  add in the hessian term as well.
    if not approx:
        printer.log('Calculating Hessians.', 3)
        hs = regularized_model.sim.bulk_hprobs(circuits, resource_alloc)
        total_hterm = {}
        
    end = time.time()
    
    printer.log(f'Elapsed time: {end-start}', 3)
    
    if comm is not None:
    #divide the job of doing the accumulation among the ranks:
        if comm.Get_rank() ==0:
            printer.log('Prepping data for scatter on rank 0.', 3)
            start = time.time()
            num_procs = comm.Get_size()
            #Possible edge case when length of circuit list is less than the number of processors?
            split_circuit_list = _np.array_split(_np.asarray(circuits, dtype = object), num_procs)
            #need to make this hashable so mpi4py can scatter the sublists using pickle:
            split_circuit_list = [tuple(sublist) for sublist in split_circuit_list]
            
            #The other ranks also don't have a copy of the p, j and h dictionaries as
            #the forward simulator only returns those on rank 0. Need to distribute these too.
            split_ps = []
            for sublist in split_circuit_list:
                ps_for_sublist = {}
                for ckt in sublist:
                    ps_for_sublist[ckt] = ps[ckt]
                split_ps.append(ps_for_sublist)
            split_js = []
            for sublist in split_circuit_list:
                js_for_sublist = {}
                for ckt in sublist:
                    js_for_sublist[ckt] = js[ckt]
                split_js.append(js_for_sublist)
            if not approx:
                split_hs = []
                for sublist in split_circuit_list:
                    hs_for_sublist = {}
                    for ckt in sublist:
                        hs_for_sublist[ckt] = hs[ckt]
                    split_hs.append(hs_for_sublist)
            end = time.time()
            printer.log(f'Elapsed time {end-start}', 3)
        else:
            split_circuit_list = None
            split_ps = None
            split_js = None
            if not approx:
                split_hs = None
            #ps, js and hs should already be initialized to None by the forward sim calls.
        #scatter these lists among the procs
        
        printer.log('Scattering among ranks.', 3)
        start=time.time()
        split_circuit_list = comm.scatter(split_circuit_list, root=0)
        ps = comm.scatter(split_ps, root=0)
        js = comm.scatter(split_js, root=0)
        if not approx:
            hs = comm.scatter(split_hs, root=0)
            
        end = time.time()
        printer.log(f'Elapsed time {end-start}', 3)
        
        #now that we have scattered them we don't need the split lists for p, j and h anymore
        del split_ps, split_js
        if not approx:
            del split_hs
        
        #print(f'Rank {comm.Get_rank()} {split_circuit_list}')
        
    #helper function for distribution using MPI
    def accumulate_fim_matrix_per_circuit(subcircuits):
        printer.log('Accumulating terms for per-circuit FIM.', 3)
        fisher_info_terms = _np.zeros([len(subcircuits),num_params, num_params])
        if not approx:
            total_hterm = _np.zeros([len(subcircuits), num_params, num_params])
        
        for k, circuit in enumerate(subcircuits):
            p = ps[circuit]
            j = js[circuit]
            if not approx:
                h = hs[circuit]
            for i, outcome in enumerate(outcomes):
                if not approx:
                    fisher_info_terms[k,:,:] += _np.outer(j[outcome], j[outcome]) / p[outcome] - h[outcome]
                    total_hterm[k,:,:] += h[outcome]
                else:
                    #fisher_info_terms[circuit] += _np.outer(j[outcome], j[outcome]) / p[outcome]
                    #faster outer product
                    jvec = (1/_np.sqrt(p[outcome]))*j[outcome]
                    fisher_info_terms[k,:,:] +=_np.dot(jvec, jvec.T)
        if approx:
            return fisher_info_terms
        else:
            return fisher_info_terms, total_hterm
            
    if comm is not None:    
        #now calculate the fisher information terms on each rank:
        printer.log('Distributed accumulation of FIM.')
        start = time.time()
        if approx:
            split_fisher_info_terms = accumulate_fim_matrix_per_circuit(split_circuit_list)
        else:
            split_fisher_info_terms, total_hterm = accumulate_fim_matrix_per_circuit(split_circuit_list)
        end = time.time()
        
        printer.log(f'Elapsed time {end-start}', 3)

        #gather these back onto rank 0.
        #This should return a list of dictionaries to rank 0.
        printer.log('Gathering accumulated FIMs', 3)
        start = time.time()
        #intialize a buffer to gather the data on rank 0.
        #get the sizes of the returned ndarrays on each rank for split_fisher_info_terms:
        # Collect local array sizes using the high-level mpi4py gather on rank 0
        printer.log('Scattering split fisher term sizes', 4)
        split_fisher_info_terms_size = split_fisher_info_terms.size
        split_fisher_info_terms_sizes = comm.allgather(split_fisher_info_terms_size)
        
        printer.log('Scattered split fisher term sizes', 4)
        
        if not shared_memory:
            if comm.Get_rank() == 0:
                #1D buffer long enough to hold every element, will then reshape this later.
                fisher_info_recv_buffer = _np.empty(_np.sum(split_fisher_info_terms_sizes), dtype= _np.double)
                if not approx:
                    #hterms are same size as fisher info terms
                    total_hterm_recv_buffer = _np.empty(_np.sum(split_fisher_info_terms_sizes), dtype= _np.double)
            else:
                fisher_info_recv_buffer = None
                if not approx:
                    total_hterm_recv_buffer = None
            #Gatherv on rank 0:
            comm.Gatherv(sendbuf=split_fisher_info_terms, recvbuf=(fisher_info_recv_buffer, split_fisher_info_terms_sizes), root=0)
            if not approx:
                comm.Gatherv(sendbuf=total_hterm, recvbuf=(total_hterm_recv_buffer, split_fisher_info_terms_sizes), root=0)
        #if using shared memory allocate a shared buffer and have the ranks write into it with their corresponding fisher infos:
        else:
            printer.log('Using shared memory for gathering.', 4)
            # create a shared array of size 1000 elements of type double
            size = _np.sum(split_fisher_info_terms_sizes)
            itemsize = MPI.DOUBLE.Get_size() 
            if comm.Get_rank() == 0: 
                nbytes = size * itemsize 
            else: 
                nbytes = 0
            
            start1 = time.time()
            printer.log('Allocating shared memory', 4)
            # on rank 0, create the shared block
            # on other ranks get a handle to it (known as a window in MPI speak)
            fisher_win = MPI.Win.Allocate_shared(nbytes, itemsize, comm=comm) 
            if not approx:
                hterm_win = MPI.Win.Allocate_shared(nbytes, itemsize, comm=comm) 
            comm.Barrier()
            end1= time.time()
            printer.log(f'Elapsed time {end1-start1}',4)
            
            printer.log('Putting ndarrays in shared memory', 4)
            start1= time.time()
            # create a numpy array whose data points to the shared mem
            buf_fisher, itemsize_fisher = fisher_win.Shared_query(0)
            assert itemsize_fisher == MPI.DOUBLE.Get_size()
            shared_fisher_info_array = _np.ndarray(buffer=buf_fisher, dtype=_np.double, shape=(size,)) 
            
            if not approx:
                buf_hterm, itemsize_hterm = hterm_win.Shared_query(0)
                assert itemsize_hterm == MPI.DOUBLE.Get_size()
                shared_hterm_array = _np.ndarray(buffer=buf_hterm, dtype=_np.double, shape=(size,)) 
            end1= time.time()
            printer.log(f'Elapsed time: {end1-start1}', 4)
            #Now have the ranks write into the shared arrays:
            #each rank has an array of size split_fisher_info_terms_sizes[rank]
            start_indices =  _np.array([0]+list(_np.cumsum(split_fisher_info_terms_sizes[1:])))
            end_indices = start_indices + split_fisher_info_terms_sizes
            
            current_rank = comm.Get_rank()
            
            printer.log('Assigning shared memory on all ranks', 4)
            start1 = time.time()
            #reshape(-1) is a view into the flattened array
            shared_fisher_info_array[start_indices[current_rank]:end_indices[current_rank]] = split_fisher_info_terms.reshape(-1)
            if not approx:
                shared_hterm_array[start_indices[current_rank]:end_indices[current_rank]] = total_hterm.reshape(-1)
            end1= time.time()
            printer.log(f'Elapsed time: {end1-start1}', 4)
            
            #wait for all ranks to finish
            comm.Barrier()
            
        #Reshape the array:
        if comm.Get_rank()==0:
            
            printer.log('Reshaping Fisher Info Arrays on rank 0', 4)
            start1= time.time()
            if not shared_memory:
                reshaped_fisher_info_view= fisher_info_recv_buffer.reshape((len(circuits), num_params, num_params))
                if not approx:
                    reshaped_hterm_view= total_hterm_recv_buffer.reshape((len(circuits), num_params, num_params))
            else:
                #despite name let's actually make this a copy
                reshaped_fisher_info_view= shared_fisher_info_array.reshape((len(circuits), num_params, num_params)).copy()
                if not approx:
                    reshaped_hterm_view= shared_hterm_array.reshape((len(circuits), num_params, num_params)).copy()
            end1= time.time()
            printer.log(f'Elapsed time {end1-start1}', 4)
        #fisher_info_terms_list = comm.gather(split_fisher_info_terms, root=0)
        end = time.time()
        
        printer.log(f'Elapsed time: {end-start}', 3)
        
        #free up memory now that we've gathered things.
        del split_fisher_info_terms
        if not approx:
            del total_hterm
                
        #on rank 0 we'll reconstruct a single dictionary for the term dict from the numpy array.
        if comm.Get_rank() == 0:
            #if approx we have only a single return value,
            #otherwise the elements of fisher_info_terms_list will be a 2-tuple with the second
            #element being the hessian term dictionary.
            printer.log('Re-combining term dicts on rank 0.')
            start = time.time()
            fisher_info_terms = {ckt: reshaped_fisher_info_view[i,:,:] for i, ckt in enumerate(circuits)}
            if not approx:
                total_hterm = {ckt: reshaped_hterm_view[i,:,:] for i, ckt in enumerate(circuits)}
            #if approx:
            #    fisher_info_terms = fisher_info_terms_list[0]
            #    for other_fisher_info_terms in fisher_info_terms_list[1:]:
            #        fisher_info_terms.update(other_fisher_info_terms)
            #else:
            #    fisher_info_terms = fisher_info_terms_list[0][0]
            #    for other_fisher_info_terms, _ in fisher_info_terms_list[1:]:
            #        fisher_info_terms.update(other_fisher_info_terms)
            #    total_hterm = fisher_info_terms_list[0][1]
            #    for _, other_hterms in fisher_info_terms_list[1:]:
            #        total_hterm.update(other_hterms)    
            end = time.time()
            printer.log(f'Elapsed time: {end-start}',3)
            
            #deallocate shared memory window:
            if shared_memory:
                fisher_win.Free()
                if not approx:
                    hterm_win.Free()
                comm.Barrier()
            
        else:
            fisher_info_terms = None
            if approx:
                total_hterm= None
    
    #otherwise do things without splitting up among multiple cores.
    else:
        if approx:
            fisher_info_terms = accumulate_fim_matrix_per_circuit(circuits)
        else:
            fisher_info_terms, total_hterm = accumulate_fim_matrix_per_circuit(circuits)
    
        fisher_info_terms = {ckt: fisher_info_terms[i,:,:] for i, ckt in enumerate(circuits)}
        if not approx:
            total_hterm = {ckt: total_hterm[i,:,:] for i, ckt in enumerate(circuits)}
        
    
    if approx:
        return fisher_info_terms
    else:
        return fisher_info_terms, total_hterm


def calculate_fisher_information_matrix(model, circuits, num_shots=1, term_cache=None,
                                        regularize_spam=True, approx= False, mem_efficient_mode= False, 
                                        circuit_chunk_size = 100, verbosity=1, comm = None, mem_limit = None):
    """Calculate the Fisher information matrix for a set of circuits and a model.

    Note that the model should be regularized so that no probability should be very small
    for numerical stability. This is done by default for models with a dense SPAM parameterization,
    but must be done manually if this is not the case (e.g. CPTP parameterization).

    Parameters
    ----------
    model: OpModel
        The model used to calculate the terms of the Fisher information matrix.

    circuits: list
        List of circuits in the experiment design.

    num_shots: int or dict
        If int, specifies how many shots each circuit gets. If dict, keys must be circuits
        and values are per-circuit counts.

    term_cache: dict or None
        If provided, should have circuits as keys and per-circuit Fisher information matrices
        as values, i.e. the output of calculate_fisher_information_per_circuit(). This cache
        will be updated with any additional circuits that need to be calculated in the given
        circuit list.

    regularize_spam: bool
        If True, depolarizing SPAM noise is added to prevent 0 probabilities for numerical
        stability. Note that this may fail if the model does not have a dense SPAM
        paramerization. In that case, pass an already "regularized" model and set this to False.
        
    approx: bool, optional (default False)
        When set to true use the approximate fisher information where we drop the 
        hessian term. Significantly faster to compute than when including the hessian.

    mem_efficient_mode: bool, optional (default False)
        If true avoid constructing the intermediate term cache to save on memory.
        
    circuit_chunk_size, int, optional (default 100)
        Used in conjunction with mem_efficient_mode. This sets the maximum number of circuits to
        simultaneously construct the per-circuit contributions to the fisher information for
        at any one time.
        
    verbosity: int, optional (default 1)
        Used to control the level of output printed by a VerbosityPrinter object.

    comm : mpi4py.MPI.Comm, optional
        When not None, an MPI communicator for distributing the computation
        across multiple processors.
        
    mem_limit : int, optional
        A rough memory limit in bytes which is used to determine job allocation
        when there are multiple processors.
        
    Returns
    -------
    fisher_information: numpy.ndarray
        Fisher information matrix of size (num_params, num_params)
    """
    
    printer = _baseobjs.VerbosityPrinter.create_printer(verbosity, comm)
    
    # Regularize model
    regularized_model = model.copy()
    if regularize_spam:
        regularized_model = regularized_model.depolarize(spam_noise=1e-3)
    num_params = regularized_model.num_params

    if isinstance(num_shots, dict):
        assert _np.all([c in num_shots for c in circuits]), \
            "If a dict, num_shots must have an entry for every circuit in the list"
    else:
        num_shots = {c: num_shots for c in circuits}

    # Calculate all needed terms
    if not mem_efficient_mode:
        if term_cache is None:
            term_cache = {}
        needed_circuits = [c for c in circuits if c not in term_cache]
        if len(needed_circuits):
            printer.log('Adding needed terms to the per-circuit term cache.',2)
            new_terms = calculate_fisher_information_per_circuit(regularized_model, needed_circuits, 
                                                                 approx, verbosity=verbosity, comm=comm, mem_limit=mem_limit)
            term_cache.update(new_terms)

        # Collect all terms, do this on rank zero:
        if comm is None or comm.Get_rank() == 0: 
            printer.log('Accumulating per-circuit contributions to fisher information.', 2)
            fisher_information = _np.zeros((num_params, num_params))
            for circ in circuits:
                fisher_information += term_cache[circ] * num_shots[circ]
        else:
            fisher_information = None
    #if working in memory efficient mode get the terms we need in smaller
    #chunks and build up the fisher information matrix as we go along.
    else:
        #initialize the empty fisher information matrix on rank 0:
        if comm is None or comm.Get_rank() == 0: 
            fisher_information = _np.zeros((num_params, num_params))
        else:
            fisher_information = None
        #divide up the list of circuits into chunks of size at most circuit_chunk_size
        chunked_circuit_lists= _np.array_split(_np.asarray(circuits, dtype=object), ceil(len(circuits)/circuit_chunk_size))
        #now loop through the chunked circuit lists and proceed similarly as above, but freeing up
        #memory as we go along.
        with printer.progress_logging(2):
            for i, ckt_chunk in enumerate(chunked_circuit_lists):
                printer.show_progress(iteration = i, total=len(chunked_circuit_lists), bar_length=50, 
                                      suffix= f'Circuit chunk {i} out of {len(chunked_circuit_lists)}')
                new_terms = calculate_fisher_information_per_circuit(regularized_model, ckt_chunk, 
                                                                     approx, verbosity=verbosity, comm=comm, mem_limit=mem_limit)
                # Collect all terms, do this on rank zero:
                if comm is None or comm.Get_rank() == 0:
                    for circ in ckt_chunk:
                        fisher_information += new_terms[circ] * num_shots[circ]
                #free up the memory from new_terms:
                del new_terms
    #The fisher information matrices looks to sometimes be larger than the default allowed buffer size for
    #MPI messages, which breaks the broadcasting. For now we don't actually need the fisher information
    #matrices to be returned on all of the ranks so let's skip this broadcast until we have implemented
    #a way to chunk out the MPI messages so that they are small enough.
    #if comm is not None:
    #    fisher_information = comm.bcast(fisher_information, root=0)
    
    return fisher_information


def calculate_fisher_information_matrices_by_L(model, circuit_lists, Ls, num_shots=1, term_cache=None,
                                               regularize_spam=True, cumulative=True, approx = False,
                                               mem_efficient_mode= False, circuit_chunk_size = 100,
                                               verbosity= 1,
                                               comm = None, mem_limit = None):
    """Calculate a set of Fisher information matrices for a set of circuits grouped by iteration.

    Parameters
    ----------
    model: OpModel
        The model used to calculate the terms of the Fisher information matrix.

    circuit_lists: list of lists of circuits or CircuitLists
        Circuit lists for the experiment design for each L. Most likely from the value of
        the `circuit_lists` attribute of most experiment design objects.

    num_shots: int or dict
        If int, specifies how many shots each circuit gets. If dict, keys must be circuits
        and values are per-circuit counts.

    term_cache: dict or None
        If provided, should have circuits as keys and per-circuit Fisher information matrices
        as values, i.e. the output of calculate_fisher_information_per_circuit(). This cache
        will be updated with any additional circuits that need to be calculated in the given
        circuit list.

    regularize_spam: bool
        If True, depolarizing SPAM noise is added to prevent 0 probabilities for numerical
        stability. Note that this may fail if the model does not have a dense SPAM
        paramerization. In that case, pass an already "regularized" model and set this to False.

    cumulative: bool
        Whether to include Fisher information matrices for lower L (True) or not.
        
    approx: bool, optional (default False)
        When set to true use the approximate fisher information where we drop the 
        hessian term. Significantly faster to compute than when including the hessian.
        
    mem_efficient_mode: bool, optional (default False)
        If true avoid constructing the intermediate term cache to save on memory.
        
    circuit_chunk_size, int, optional (default 100)
        Used in conjunction with mem_efficient_mode. This sets the maximum number of circuits to
        simultaneously construct the per-circuit contributions to the fisher information for
        at any one time.
        
    verbosity: int, optional (default 1)
        Used to control the level of output printed by a VerbosityPrinter object.

    comm : mpi4py.MPI.Comm, optional
        When not None, an MPI communicator for distributing the computation
        across multiple processors.
        
    mem_limit : int, optional
        A rough memory limit in bytes which is used to determine job allocation
        when there are multiple processors.

    Returns
    -------
    fisher_information_by_L: dict
        Dictionary with keys as circuit length L and value as Fisher information matrices
    """
    
    printer = _baseobjs.VerbosityPrinter.create_printer(verbosity, comm)
    
    # Regularize model
    regularized_model = model.copy()
    if regularize_spam:
        regularized_model = regularized_model.depolarize(spam_noise=1e-3)

    if isinstance(num_shots, dict):
        assert _np.all([c in num_shots for ckt_list in circuit_lists for c in ckt_list]), \
            "If a dict, num_shots must have an entry for every circuit in the list"
    else:
        num_shots = {c: num_shots for ckt_list in circuit_lists for c in ckt_list}

    # Calculate all needed terms
    
    if not mem_efficient_mode:
        if term_cache is None:
            term_cache = {}
        needed_circuits = [c for ckt_list in circuit_lists for c in ckt_list if c not in term_cache]
        if len(needed_circuits):
            new_terms = calculate_fisher_information_per_circuit(regularized_model, needed_circuits, approx, verbosity=verbosity, 
                                                                 comm=comm, mem_limit=mem_limit)
            term_cache.update(new_terms)
        #should have already used the comm in the construction of the term cache, so this is just and accumulation
        #step so do this on rank 0 and broadcast.
        if comm is None or comm.Get_rank() == 0:
            fisher_information_by_L = {}
            for L, ckt_list in zip(Ls, circuit_lists):
                printer.log(f'Computing fisher information matrix for L={L}',2)
                fisher_information_by_L[L] = calculate_fisher_information_matrix(regularized_model, ckt_list, num_shots,
                                                               term_cache=term_cache, regularize_spam=False, verbosity=verbosity)
        else:
            fisher_information_by_L = None
        
        if comm is not None:
            fisher_information_by_L = comm.bcast(fisher_information_by_L, root=0)
        
    else:
        fisher_information_by_L = {}
        #get the unique ckts for each circuit list:
        unique_circuit_lists = [circuit_lists[0]] + [list(set(circuit_lists[i])-set(circuit_lists[i-1])) for i in range(1,len(circuit_lists))]
        assert(len(unique_circuit_lists) == len(circuit_lists))
        
        for i, (L, ckt_list) in enumerate(zip(Ls, unique_circuit_lists)):
            if i==0:
                fisher_information_by_L[L] = calculate_fisher_information_matrix(regularized_model, ckt_list, num_shots,
                                                               term_cache=None, regularize_spam=False,
                                                               approx = approx, 
                                                               mem_efficient_mode=mem_efficient_mode,
                                                               circuit_chunk_size = circuit_chunk_size,
                                                               verbosity = verbosity,
                                                               comm=comm, mem_limit=mem_limit)
            else:
                fisher_information_by_L[L] = fisher_information_by_L[Ls[i-1]] + \
                                             calculate_fisher_information_matrix(regularized_model, ckt_list, num_shots,
                                                               term_cache=None, regularize_spam=False,
                                                               approx = approx, 
                                                               mem_efficient_mode=mem_efficient_mode,
                                                               circuit_chunk_size = circuit_chunk_size,
                                                               verbosity = verbosity,
                                                               comm=comm, mem_limit=mem_limit)
    
    #In memory efficient mode the fisher information is None on any rank other than 0 when using MPI.    
    return fisher_information_by_L

def pad_edesign_with_idle_lines(edesign, line_labels):
    """Utility to explicitly pad out ExperimentDesigns with idle lines.

    Parameters
    ----------
    edesign: ExperimentDesign
        The edesign to be padded.

    line_labels: tuple of int or str
        Full line labels for the padded edesign.

    Returns
    -------
    ExperimentDesign
        An edesign where all circuits have been padded out with missing idle lines
    """
    from pygsti.protocols import CombinedExperimentDesign as _CombinedDesign
    from pygsti.protocols import SimultaneousExperimentDesign as _SimulDesign

    if set(edesign.qubit_labels) == set(line_labels):
        return edesign
    
    if isinstance(edesign, _CombinedDesign):
        new_designs = {}
        for subkey, subdesign in edesign.items():
            new_designs[subkey] = pad_edesign_with_idle_lines(subdesign, line_labels)
        
        return _CombinedDesign(new_designs, qubit_labels=line_labels)

    # SimultaneousDesign with single design + full qubit labels tensors out the circuits with idle lines
    return _SimulDesign([edesign], qubit_labels=line_labels)
