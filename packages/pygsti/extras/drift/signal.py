from __future__ import division, print_function, absolute_import, unicode_literals
#*****************************************************************
#    pyGSTi 0.9:  Copyright 2015 Sandia Corporation
#    This Software is released under the GPL license detailed
#    in the file "license.txt" in the top-level pyGSTi directory
#*****************************************************************
"""Functions for Fourier analysis of time-series data"""

import numpy as _np
from scipy.fftpack import dct as _dct
from scipy.fftpack import idct as _idct
from scipy.fftpack import fft as _fft
from scipy.fftpack import ifft as _ifft
from scipy import convolve as _convolve
import warnings as _warnings

try:
    from astropy.stats import LombScargle as _LombScargle
except:
    pass

# def spectrum(x, times=None, frequencies='auto', counts=1, null_hypothesis=None, stype='DCT'):

#     x_mean = _np.mean(x)
#     T = len(x)
    
#     # If the null hypothesis is not specified, we take our null hypothesis to be a constant bias
#     # coin, with the bias given by the mean of the data / number of counts.
#     if null_hypothesis is None:    
#         null_hypothesis = x_mean/counts
#         if null_hypothesis <=0 or null_hypothesis >= 1:
#             return _np.zeros(T)

#     normalizer = _np.sqrt(counts*null_hypothesis * (1 - null_hypothesis))
#     rescaled_x = (x -  counts*null_hypothesis)/normalizer
    
#     if stype == 'DCT':
#         return _dct(rescaled_x,norm='ortho')**2

#     elif stype == 'LSP':
#         assert(times is not None)
#         if frequencies == 'auto':
#             freq = frequencies_from_timestep((max(times)-min(times))/T,T)
#         else:
#             freq = frequencies
#         power = _LombScargle(times,rescaled_x).power(freq, normalization='psd')
#         return  freq, power

#     elif stype == 'DFT':
#         return _np.abs(_fft(rescaled_x))**2/T

def DFT(x, times=None, counts=1, null_hypothesis=None):

    x_mean = _np.mean(x)
    T = len(x)

    # If the null hypothesis is not specified, we take our null hypothesis to be a constant bias
    # coin, with the bias given by the mean of the data / number of counts.
    if null_hypothesis is None:    
        null_hypothesis = x_mean/counts
        if null_hypothesis <=0 or null_hypothesis >= 1:
            return _np.zeros(T)

    normalizer = _np.sqrt(counts*null_hypothesis * (1 - null_hypothesis))
    rescaled_x = (x -  counts*null_hypothesis)/normalizer

    return _np.abs(_fft(rescaled_x))**2/T

def LSP(x, times=None, frequencies='auto', counts=1, null_hypothesis=None):

    x_mean = _np.mean(x)
    T = len(x)
    
    # If the null hypothesis is not specified, we take our null hypothesis to be a constant bias
    # coin, with the bias given by the mean of the data / number of counts.
    if null_hypothesis is None:    
        null_hypothesis = x_mean/counts
        if null_hypothesis <=0 or null_hypothesis >= 1:
            return _np.zeros(T)

    normalizer = _np.sqrt(counts*null_hypothesis * (1 - null_hypothesis))
    rescaled_x = (x -  counts*null_hypothesis)/normalizer

    assert(times is not None)
    if isinstance(frequencies,str):
        freq = frequencies_from_timestep((max(times)-min(times))/T,T)
    else:
        freq = frequencies
    power = _LombScargle(times,rescaled_x).power(freq, normalization='psd')
    
    return  freq, power

def DCT(x, counts=1, null_hypothesis=None):
    """
    Returns the Type-II discrete cosine transform of y, with an orthogonal normalization, where
    y is an array with elements related to the x array by
    
    y[k] = (x[k] - null_hypothesis[k])/normalizer;
    normalizer = sqrt(counts*null_hypothesis[k]*(1-null_hypothesis[k])).
    
    If null_hypothesis is None, then null_hypothesis[k] is mean(x)/counts, for all k. This is
    with the exception that when mean(x)/counts = 0 or 1 (when the above y[k] is ill-defined),
    in which case the zero vector is returned.
    
    Parameters
    ----------
    x : array
        Data string, on which the normalization and discrete cosine transformation is performed. If
        counts is not specified, this must be a bit string.
        
    null_hypothesis : array, optional
        If not None, an array to use in the normalization before the DCT. If None, it is
        taken to be an array in which every element is the mean of x.
        
    counts : int, optional
        TODO
                
    Returns
    -------
    array
        The DCT modes described above.

    """
    x_mean = _np.mean(x)
    N = len(x)
    
    #assert(min(counts*_np.ones(N) - x) >= 0), "The number of counts must be >= to the maximum of the data array!"
    #assert(min(x) >= 0), "The elements of the data array must be >= 0"
    
    # If the null hypothesis is not specified, we take our null hypothesis to be a constant bias
    # coin, with the bias given by the mean of the data / number of counts.
    if null_hypothesis is None:    
        null_hypothesis = x_mean/counts
        if null_hypothesis <= 0 or null_hypothesis >= 1:
            out = _np.ones(N)
            out[0] = 0.
            return out
    #else:
    #    assert(min(null_hypothesis)>0 and max(null_hypothesis)<1), "All element of null_hypothesis must be in (0,1)!"
    #    assert(len(null_hypothesis) == N), "The null hypothesis array must be the same length as the data array!"
    
    return _dct((x - counts*null_hypothesis)/_np.sqrt(counts*null_hypothesis * (1 - null_hypothesis)),norm='ortho')

def IDCT(modes,null_hypothesis,counts=1):
    """
    Inverts the DCT function.
    
    Parameters
    ----------
    modes : array
        The fourier modes to be transformed to time-domain.
        
    null_hypothesis : array
        The null_hypothesis vector. For the IDCT it is not optional, and all
        elements of this array must be in (0,1).
        
    counts : int, optional
        TODO
        
    Returns
    -------
    array
        Inverse of the DCT function
        
    """
    #assert(min(null_hypothesis)>0 and max(null_hypothesis)<1), "All element of null_hypothesis must be in (0,1)!"
    #assert(len(null_hypothesis) == len(modes)), "The null hypothesis array must be the same length as the data array!"
    
    return  _idct(modes,norm='ortho')*_np.sqrt(counts*null_hypothesis * (1 - null_hypothesis)) + counts*null_hypothesis


def bartlett_spectrum(x,num_spectra,counts=1,null_hypothesis=None):
    """
    If N/num_spectra is not an integer, then 
    not all of the data points are used.
    
    TODO: docstring
    TODO: Make this work with multicount data.
    """
    
    N = len(x)
    length = int(_np.floor(N/num_spectra))
    
    if null_hypothesis is None:
        null_hypothesis = _np.mean(x)*_np.ones(N)/counts
    
    spectra = _np.zeros((num_spectra,length))
    bartlett_spectrum = _np.zeros(length)
    
    for i in range(0,num_spectra):
        spectra[i,:] = DCT(x[i*length:((i+1)*length)],counts=counts,
                           null_hypothesis=null_hypothesis[i*length:((i+1)*length)])**2
        
    bartlett_spectrum = _np.mean(spectra,axis=0)
                
    return bartlett_spectrum

def bartlett_spectrum_averaging(spectrum, num_spectra):
    """
    If N/num_spectra is not an integer, then 
    not all of the data points are used.
    
    TODO: docstring
    TODO: Make this work with multicount data.
    """ 
    length = int(_np.floor(len(spectrum)/num_spectra))  
    spectra = _np.zeros((num_spectra,length))
    for i in range(0,num_spectra):
        spectra[i,:] = spectrum[i*length:((i+1)*length)]
        
    bartlett_spectrum = _np.mean(spectra,axis=0)
                
    return bartlett_spectrum

def frequencies_from_timestep(timestep,T):
    
    return _np.arange(0,T)/(2*timestep*T)

# Todo : make a method of a transform object.
def amplitudes_at_frequencies(freqInds, timeseries, transform='DCT'):
    """
    todo
    """
    amplitudes = {}
    for o in timeseries.keys():
        if transform == 'DCT':
            amplitudes[o] = list(_dct(timeseries[o],norm='ortho')[freqInds]/_np.sqrt(len(timeseries[o])))
        elif transform == 'DFT':
            # todo : check this normalization (this bit of function has never been used)
            amplitudes[o] = list(_fft(timeseries[o])[freqInds]/len(timeseries[o]))
    
    return  amplitudes

def DCT_basis_function(omega, T, t):
    """
    Todo

    These are the *unnormalized* DCT amplitudes.
    """
    return _np.cos(omega*_np.pi*(t+0.5)/T)

#def create_DCT_basis_function(omega, T):
#
#    def DCT_basis_function(t): return _np.cos(omega*_np.pi*(t+0.5)/T)
#
#    return DCT_basis_function

# def probability_from_DCT_amplitudes(alphas, omegas, T, t):
#     """
#     Todo

#     This uses the *unnormalized* DCT amplitudes.
#     """
#     return _np.sum(_np.array([alphas[i]*DCT_basis_function(omegas[i], T, t) for i in range(len(omegas))]))

def sparsity(p):
    """
    Returns the Hoyer index of the input vector.
    TODO: docstring
    """
    n = len(p)
    return (_np.sqrt(n) - _np.linalg.norm(p,1)/_np.linalg.norm(p,2))/(_np.sqrt(n)-1)

def renormalizer(p, method='logistic'):
    """
    Takes an arbitrary input vector and maps it to a vector
    bounded within [0,1].

    Parameters
    ----------
    p : array of floats
        The vector with values to be mapped to [0,1]

    method : {'logistic', 'sharp'}


    Returns
    -------
    numpy.array
        If method is 'sharp' then...
        If method is 'logistic' then..
    """
    if method == 'logistic':
    
        mean = _np.mean(p)
        nu = min([1-mean ,mean ]) 
        out = mean - nu + (2*nu)/(1 + _np.exp(-2*(p - mean)/nu))
     
    elif method == 'sharp':
        out = p.copy()
        out[p>1] = 1.
        out[p<0] = 0.
    
    else:
        raise ValueError("method should be 'logistic' or 'sharp'")
        
    return out

def logistic_transform(p, mean):
    """
    Todo
    """
    nu = min([1-mean ,mean ]) 
    out = mean - nu + (2*nu)/(1 + _np.exp(-2*(p - mean)/nu))
    return out

def constrain_model_via_uniform_amplitude_compression(model, times, epsilon=0.001, stepsize=0.005,
                                                       verbosity=1):
    """
    Todo. This only works given that parameter 0 is the DC-mode and the probablities sum to
    1 at each time.

    Returns
    -------

    """
    newmodel = model.copy()
    if len(newmodel.basisfunctionInds) <= 1:
        return model, False

    pt = newmodel.get_probabilities(times)

    maxpt = max([max(pt[o]) for o in model.parameters.keys()])
    minpt = min([min(pt[o]) for o in model.parameters.keys()])

    iteration = 1
    modelchanged = False
    while maxpt >= 1-epsilon or minpt <= epsilon:
        
        modelchanged = True
        newparameters = model.parameters.copy()
        for i in model.parameters.keys():
            newparameters[i][1:] = [decrease_magnitude(p,stepsize) for p in newparameters[i][1:]]
        
        # Input the new parameters to the model
        newmodel.set_parameters(newparameters)
        # Get the new probabilities trajectory
        pt = model.get_probabilities(times)
        # Find out it's max and min value
        maxpt = max([max(pt[o]) for o in model.parameters.keys()])
        minpt = min([min(pt[o]) for o in model.parameters.keys()])

        if iteration >= 10000:
            _warnings.warning("10,000 iterations implemented trying to make model physical! Quiting and returning unphysical model.")
            return model 

        iteration += 1

    return newmodel, modelchanged

def decrease_magnitude(p, epsilon):
    """
    todo.
    """
    if p > 0:
        p = p - epsilon
        if p > 0:
            return p
        else:
            return 0
    elif p < 0:
        p = p + epsilon
        if p < 0:
            return p
        else:
            return 0
    else:
        return 0.

# def reduce_DCT_amplitudes_until_probability_is_physical(alphas, omegas, T, epsilon=0.001, step_size=0.005,
#                                                         verbosity=1):
#     """
#     """
#     assert(0 in omegas)
#     assert(0 == omegas[0]), "This function assume that the 0 mode is first in the list!"
#     pt = [probability_from_DCT_amplitudes(alphas, omegas, T, t) for t in range(T)]
#     newalphas = alphas.copy()

#     if alphas[0] > (1 - epsilon) or alphas[0] < epsilon:
#         newalphas[1:] = _np.zeros(len(newalphas)-1)
#         print("Constraint can't be satisfied using this function, because the zero-mode contribution is outside the requested bounds!")
#         return newalphas

#     iteration = 0
#     while max(pt) >= 1-epsilon or min(pt) <= epsilon:
#         iteration += 1
#         if verbosity > 0:
#             print("Interation {} of amplitude reduction.".format(iteration))
#         # We don't change the amplitude of the DC component.
#         for i in range(1,len(newalphas)):
#             if newalphas[i] > 0.:
#                 newalphas[i] = newalphas[i] - step_size
#                 # If it changes sign we set it to zero.
#                 if newalphas[i] < 0.:
#                     newalphas[i] = 0
#             if newalphas[i] < 0.:
#                 newalphas[i] = newalphas[i] + step_size
#                 # If it changes sign we set it to zero.
#                 if newalphas[i] > 0.:
#                     newalphas[i] = 0
#         pt = [probability_from_DCT_amplitudes(newalphas, omegas, T, t) for t in range(T)]

#     if verbosity > 0:
#         print("Estimate within bounds.")
#     return newalphas 

def low_pass_filter(data, max_freq=None):
    """
    TODO: docstring
    """
    n = len(data) 
    
    if max_freq is None:
        max_freq = min(int(np.ceil(n/10)),50)
        
    modes = _dct(data,norm='ortho')
    
    if max_freq < n - 1:
        modes[max_freq + 1:] = _np.zeros(len(data)-max_freq-1)

    return _idct(modes,norm='ortho')

def moving_average(sequence, width=100):
    """
    TODO: docstring
    """
    seq_length = len(sequence)
    base = _convolve(_np.ones(seq_length), _np.ones((int(width),))/float(width), mode='same')
    signal = _convolve(sequence, _np.ones((int(width),))/float(width), mode='same')
    return signal/base 