"""Python implementations of common polynomial operations"""
#***************************************************************************************************
# Copyright 2015, 2019 National Technology & Engineering Solutions of Sandia, LLC (NTESS).
# Under the terms of Contract DE-NA0003525 with NTESS, the U.S. Government retains certain rights
# in this software.
# Licensed under the Apache License, Version 2.0 (the "License"); you may not use this file except
# in compliance with the License.  You may obtain a copy of the License at
# http://www.apache.org/licenses/LICENSE-2.0 or in the LICENSE file in the root pyGSTi directory.
#***************************************************************************************************

import numpy as _np
from functools import partial as _partial

# Has an optimized cython implementation
from numpy import prod as float_product


def _typed_bulk_eval_compact_polynomials(vtape, ctape, paramvec, dest_shape, dtype="auto"):
    """
    Evaluate many compact polynomial forms at a given set of variable values.

    Parameters
    ----------
    vtape, ctape : numpy.ndarray
        Specifies "variable" and "coefficient" 1D numpy arrays to evaluate.
        These "tapes" can be generated by concatenating the tapes of individual
        complact-polynomial tuples returned by :method:`Polynomial.compact`.

    paramvec : array-like
        An object that can be indexed so that `paramvec[i]` gives the
        numerical value to substitute for i-th polynomial variable (x_i).

    dest_shape : tuple
        The shape of the final array of evaluated polynomials.  The resulting
        1D array of evaluated polynomials is reshaped accordingly.

    dtype : {"auto", "real", "complex}
        The type of the coefficient array that is returned.

    Returns
    -------
    numpy.ndarray
        An array of the same type as the coefficient tape or with the type
        given by `dtype`, and with shape given by `dest_shape`.
    """
    if dtype == "auto":
        result = _np.empty(dest_shape, ctape.dtype)  # auto-determine type?
    elif dtype == "complex":
        result = _np.empty(dest_shape, complex)
    elif dtype == "real":
        result = _np.empty(dest_shape, 'd')
    else:
        raise ValueError("Invalid dtype: %s" % dtype)

    res = result.flat  # for 1D access

    c = 0; i = 0; r = 0
    while i < vtape.size:
        poly_val = 0
        nTerms = vtape[i]; i += 1
        #print("POLY w/%d terms (i=%d)" % (nTerms,i))
        for m in range(nTerms):
            nVars = vtape[i]; i += 1  # number of variable indices in this term
            a = ctape[c]; c += 1
            #print("  TERM%d: %d vars, coeff=%s" % (m,nVars,str(a)))
            for k in range(nVars):
                a *= paramvec[vtape[i]]; i += 1
            poly_val += a
            #print("  -> added %s to poly_val = %s" % (str(a),str(poly_val))," i=%d, vsize=%d" % (i,vtape.size))
        res[r] = poly_val; r += 1
    assert(c == ctape.size), "Coeff Tape length error: %d != %d !" % (c, ctape.size)
    assert(r == result.size), "Result/Tape size mismatch: only %d result entries filled!" % r
    return result


# These have separate cython implementations but the same python implementation, so we'll simply alias the names
bulk_eval_compact_polynomials_real = _partial(_typed_bulk_eval_compact_polynomials, dtype='real')
bulk_eval_compact_polynomials_complex = _partial(_typed_bulk_eval_compact_polynomials, dtype='complex')


def _typed_bulk_eval_compact_polynomials_derivs(vtape, ctape, wrt_params, paramvec, dest_shape, dtype="auto"):
    #Note: assumes wrt_params is SORTED but doesn't assert it like Python version does

    vtape_sz = vtape.size
    wrt_sz = wrt_params.size

    assert(len(dest_shape) == 2)
    assert(len(wrt_params) == dest_shape[1])

    if dtype == "auto":
        result = _np.zeros(dest_shape, ctape.dtype)  # auto-determine type?
    elif dtype == "complex":
        result = _np.zeros(dest_shape, complex)  # indices [iPoly, iParam]
    elif dtype == "real":
        result = _np.zeros(dest_shape, 'd')  # indices [iPoly, iParam]
    else:
        raise ValueError("Invalid dtype: %s" % dtype)

    c = 0; i = 0; iPoly = 0
    while i < vtape_sz:
        j = i # increment j instead of i for this poly
        nTerms = vtape[j]; j+=1
        #print "POLY w/%d terms (i=%d)" % (nTerms,i)

        for m in range(nTerms):
            coeff = ctape[c]; c += 1
            nVars = vtape[j]; j += 1 # number of variable indices in this term

            #print "  TERM%d: %d vars, coeff=%s" % (m,nVars,str(coeff))
            cur_iWrt = 0
            j0 = j # the vtape index where the current term starts
            j1 = j+nVars # the ending index

            #Loop to get counts of each variable index that is also in `wrt`.
            # Once we've passed an element of `wrt` process it, since there can't
            # see it any more (the var indices are sorted).
            while j < j1: #loop over variable indices for this term
                # can't be while True above in case nVars == 0 (then vtape[j] isn't valid)

                #find an iVar that is also in wrt.
                # - increment the cur_iWrt or j as needed
                while cur_iWrt < wrt_sz and vtape[j] > wrt_params[cur_iWrt]: #condition to increment cur_iWrt
                    cur_iWrt += 1 # so wrt_params[cur_iWrt] >= vtape[j]
                if cur_iWrt == wrt_sz: break  # no more possible iVars we're interested in;
                                                # we're done with all wrt elements
                # - at this point we know wrt[cur_iWrt] is valid and wrt[cur_iWrt] >= tape[j]
                cur_wrt = wrt_params[cur_iWrt]
                while j < j1 and vtape[j] < cur_wrt:
                    j += 1 # so vtape[j] >= wrt[cur_iWrt]
                if j == j1: break  # no more iVars - we're done

                #print " check j=%d, val=%d, wrt=%d, cur_iWrt=%d" % (j,vtape[j],cur_wrt,cur_iWrt)
                if vtape[j] == cur_wrt:
                    #Yay! a value we're looking for is present in the vtape.
                    # Figure out how many there are (easy since vtape is sorted
                    # and we'll always stop on the first one)
                    cnt = 0
                    while j < j1 and vtape[j] == cur_wrt:
                        cnt += 1; j += 1
                    #Process cur_iWrt: add a term to evaluated poly for derivative w.r.t. wrt_params[cur_iWrt]
                    a = coeff*cnt
                    for k in range(j0,j1):
                        if k == j-1: continue # remove this index
                        a *= paramvec[ vtape[k] ]
                    result[iPoly, cur_iWrt] += a
                    cur_iWrt += 1 # processed this wrt param - move to next one

            j = j1 # move to next term; j may not have been incremented if we exited b/c of cur_iWrt reaching end

        i = j # update location in vtape after processing poly - actually could just use i instead of j it seems??
        iPoly += 1

    return result


# These have separate cython implementations but the same python implementation, so we'll simply alias the names
bulk_eval_compact_polynomials_derivs_real = _partial(_typed_bulk_eval_compact_polynomials_derivs, dtype='real')
bulk_eval_compact_polynomials_derivs_complex = _partial(_typed_bulk_eval_compact_polynomials_derivs, dtype='complex')


def abs_sum_bulk_eval_compact_polynomials_complex(vtape, ctape, paramvec, dest_size, **kwargs):
    """Equivalent to np.sum(np.abs(bulk_eval_compact_polynomials_complex(.)))"""
    return _np.sum(_np.abs(bulk_eval_compact_polynomials_complex(vtape, ctape, paramvec, (dest_size,), **kwargs)))


def compact_deriv(vtape, ctape, wrt_params):
    """
    Take the derivative of one or more compact Polynomials with respect
    to one or more variables/parameters.

    Parameters
    ----------
    vtape, ctape : numpy.ndarray
        Specifies "variable" and "coefficient" 1D numpy arrays to differentiate.
        These "tapes" can be generated by concatenating the tapes of individual
        complact-polynomial tuples returned by :method:`Polynomial.compact`.

    wrt_params : list
        The variable indices to differentiate with respect to.  They
        must be sorted in ascending order. E.g. "[0,3]" means separatey
        differentiate w.r.t x_0 and x_3 (concatenated first by wrt_param
        then by poly).

    Returns
    -------
    vtape, ctape : numpy.ndarray
    """
    result_vtape = []
    result_ctape = []
    wrt = sorted(wrt_params)
    assert(wrt == list(wrt_params)), "`wrt_params` (%s) must be in ascending order!" % wrt_params
    #print("TAPE SIZE = ",vtape.size)

    c = 0; i = 0
    while i < vtape.size:
        j = i  # increment j instead of i for this poly
        nTerms = vtape[j]; j += 1
        dctapes = [list() for x in range(len(wrt))]
        dvtapes = [list() for x in range(len(wrt))]
        dnterms = [0] * len(wrt)
        #print("POLY w/%d terms (i=%d)" % (nTerms,i))
        for m in range(nTerms):
            coeff = ctape[c]; c += 1
            nVars = vtape[j]; j += 1  # number of variable indices in this term

            #print("  TERM%d: %d vars, coeff=%s" % (m,nVars,str(coeff)))
            cur_iWrt = 0
            j0 = j  # the vtape index where the current term starts

            #Loop to get counts of each variable index that is also in `wrt`.
            # Once we've passed an element of `wrt` process it, since there can't
            # see it any more (the var indices are sorted).
            while j < j0 + nVars:  # loop over variable indices for this term
                # can't be while True above in case nVars == 0 (then vtape[j] isn't valid)

                #find an iVar that is also in wrt.
                # - increment the cur_iWrt or j as needed
                while cur_iWrt < len(wrt) and vtape[j] > wrt[cur_iWrt]:  # condition to increment cur_iWrt
                    cur_iWrt += 1  # so wrt[cur_iWrt] >= vtape[j]
                if cur_iWrt == len(wrt): break  # no more possible iVars we're interested in;
                # we're done with all wrt elements
                # - at this point we know wrt[cur_iWrt] is valid and wrt[cur_iWrt] >= tape[j]
                while j < j0 + nVars and vtape[j] < wrt[cur_iWrt]:
                    j += 1  # so vtape[j] >= wrt[cur_iWrt]
                if j == j0 + nVars: break  # no more iVars - we're done

                #print(" check j=%d, val=%d, wrt=%d, cur_iWrt=%d" % (j,vtape[j],wrt[cur_iWrt],cur_iWrt))
                if vtape[j] == wrt[cur_iWrt]:
                    #Yay! a value we're looking for is present in the vtape.
                    # Figure out how many there are (easy since vtape is sorted
                    # and we'll always stop on the first one)
                    cnt = 0
                    while j < j0 + nVars and vtape[j] == wrt[cur_iWrt]:
                        cnt += 1; j += 1
                    #Process cur_iWrt: add a term to tape for cur_iWrt
                    dvars = list(vtape[j0:j - 1]) + list(vtape[j:j0 + nVars])  # removes last wrt[cur_iWrt] var
                    dctapes[cur_iWrt].append(coeff * cnt)
                    dvtapes[cur_iWrt].extend([nVars - 1] + dvars)
                    dnterms[cur_iWrt] += 1
                    # print(" wrt=%d found cnt=%d: adding deriv term coeff=%f vars=%s" \
                    #       % (wrt[cur_iWrt], cnt, coeff*cnt, [nVars-1] + dvars))

                    cur_iWrt += 1  # processed this wrt param - move to next one

            #Now term has been processed, adding derivative terms to the dctapes and dvtapes "tape-lists"
            # We continue processing terms, adding to these tape lists, until all the terms of the
            # current poly are processed.  Then we can concatenate the tapes for each wrt_params element.
            # Move to next term; j may not have been incremented if we exited b/c of cur_iWrt reaching end
            j = j0 + nVars

        #Now all terms are processed - concatenate tapes for wrt_params and add to resulting tape.
        for nTerms, dvtape, dctape in zip(dnterms, dvtapes, dctapes):
            result_vtape.extend([nTerms] + dvtape)
            result_ctape.extend(dctape)
        i = j  # update location in vtape after processing poly - actually could just use i instead of j it seems??

    return _np.array(result_vtape, _np.int64), _np.array(result_ctape, complex)
