from __future__ import division, print_function, absolute_import, unicode_literals
#*****************************************************************
#    pyGSTi 0.9:  Copyright 2015 Sandia Corporation
#    This Software is released under the GPL license detailed
#    in the file "license.txt" in the top-level pyGSTi directory
#*****************************************************************

import itertools    as _itertools
import numbers      as _numbers
import collections  as _collections
import numpy        as _np

from .basis import Basis, basis_constructor, change_basis, basis_transform_matrix
from .basis import build_basis
from .dim   import Dim
'''
Functions for creating the standard sets of matrices in the standard, pauli, gell mann, and qutrit bases
'''
## Pauli basis matrices
sqrt2 = _np.sqrt(2)
id2x2 = _np.array([[1,0],[0,1]])
sigmax = _np.array([[0,1],[1,0]])
sigmay = _np.array([[0,-1.0j],[1.0j,0]])
sigmaz = _np.array([[1,0],[0,-1]])

##Matrix unit basis
def _mut(i,j,N):
    mx = _np.zeros( (N,N), 'd'); mx[i,j] = 1.0
    return mx
mxUnitVec = ( _mut(0,0,2), _mut(0,1,2), _mut(1,0,2), _mut(1,1,2) )
mxUnitVec_2Q = ( _mut(0,0,4), _mut(0,1,4), _mut(0,2,4), _mut(0,3,4),
                 _mut(1,0,4), _mut(1,1,4), _mut(1,2,4), _mut(1,3,4),
                 _mut(2,0,4), _mut(2,1,4), _mut(2,2,4), _mut(2,3,4),
                 _mut(3,0,4), _mut(3,1,4), _mut(3,2,4), _mut(3,3,4)  )

@basis_constructor('std', 'Matrix-unit', real=False)
def std_matrices(dimOrBlockDims):
    """
    Get the elements of the matrix unit, or "standard", basis
    spanning the density-matrix space given by dimOrBlockDims.

    The returned matrices are given in the standard basis of the
    "embedding" density matrix space, that is, the space which
    embeds the block-diagonal matrix structure stipulated in
    dimOrBlockDims. These matrices form an orthonormal basis under
    the trace inner product, i.e. Tr( dot(Mi,Mj) ) == delta_ij.

    Parameters
    ----------
    dimOrBlockDims : int or list of ints
        Structure of the density-matrix space.

    Returns
    -------
    list
        A list of N numpy arrays each of shape (dmDim, dmDim),
        where dmDim is the matrix-dimension of the overall
        "embedding" density matrix (the sum of dimOrBlockDims)
        and N is the dimension of the density-matrix space,
        equal to sum( block_dim_i^2 ).

    Notes
    -----
    Each element is a matrix containing
    a single "1" entry amidst a background of zeros, and there
    are never "1"s in positions outside the block-diagonal structure.
    """
    dmDim, gateDim, blockDims = Dim(dimOrBlockDims)

    mxList = []; start = 0
    for blockDim in blockDims:
        for i in range(start,start+blockDim):
            for j in range(start,start+blockDim):
                mxList.append( _mut( i, j, dmDim ) )
        start += blockDim

    assert(len(mxList) == gateDim and start == dmDim)
    return mxList

def _GetGellMannNonIdentityDiagMxs(dimension):
    d = dimension
    listOfMxs = []
    if d > 2:
        dm1_listOfMxs = _GetGellMannNonIdentityDiagMxs(d-1)
        for dm1_mx in dm1_listOfMxs:
            mx = _np.zeros( (d,d), 'complex' )
            mx[0:d-1,0:d-1] = dm1_mx
            listOfMxs.append(mx)
    if d > 1:
        mx = _np.identity( d, 'complex' )
        mx[d-1,d-1] = 1-d
        mx *= _np.sqrt( 2.0 / (d*(d-1)) )
        listOfMxs.append(mx)

    return listOfMxs

@basis_constructor('gm_unnormalized', 'Gell-Mann unnormalized', real=True)
def gm_matrices_unnormalized(dimOrBlockDims):
    """
    Get the elements of the generalized Gell-Mann
    basis spanning the density-matrix space given by dimOrBlockDims.

    The returned matrices are given in the standard basis of the
    "embedding" density matrix space, that is, the space which
    embeds the block-diagonal matrix structure stipulated in
    dimOrBlockDims. These matrices form an orthogonal but not
    orthonormal basis under the trace inner product.

    Parameters
    ----------
    dimOrBlockDims : int or list of ints
        Structure of the density-matrix space.

    Returns
    -------
    list
        A list of N numpy arrays each of shape (dmDim, dmDim),
        where dmDim is the matrix-dimension of the overall
        "embedding" density matrix (the sum of dimOrBlockDims)
        and N is the dimension of the density-matrix space,
        equal to sum( block_dim_i^2 ).
    """
    if isinstance(dimOrBlockDims, _numbers.Integral):
        d = dimOrBlockDims

        #Identity Mx
        listOfMxs = [ _np.identity(d, 'complex') ]

        #Non-diagonal matrices -- only take those whose non-zero elements are not "frozen" in cssb case
        for k in range(d):
            for j in range(k+1,d):
                mx = _np.zeros( (d,d), 'complex' )
                mx[k,j] = mx[j,k] = 1.0
                listOfMxs.append( mx )

        for k in range(d):
            for j in range(k+1,d):
                mx = _np.zeros( (d,d), 'complex' )
                mx[k,j] = -1.0j; mx[j,k] = 1.0j
                listOfMxs.append( mx )

        #Non-Id Diagonal matrices
        listOfMxs.extend( _GetGellMannNonIdentityDiagMxs(d) )

        assert(len(listOfMxs) == d**2)
        return listOfMxs

    elif isinstance(dimOrBlockDims, _collections.Container) or isinstance(dimOrBlockDims, Dim):
        dmDim, gateDim, blockDims = Dim(dimOrBlockDims)

        listOfMxs = []; start = 0
        for blockDim in blockDims:
            for blockMx in gm_matrices_unnormalized(blockDim):
                mx = _np.zeros( (dmDim, dmDim), 'complex' )
                mx[start:start+blockDim, start:start+blockDim] = blockMx
                listOfMxs.append( mx )
            start += blockDim
        assert(len(listOfMxs) == gateDim)
        return listOfMxs

    else:
        raise ValueError("Invalid dimOrBlockDims = %s" % str(dimOrBlockDims))


@basis_constructor('gm', 'Gell-Mann', real=True)
def gm_matrices(dimOrBlockDims):
    """
    Get the normalized elements of the generalized Gell-Mann
    basis spanning the density-matrix space given by dimOrBlockDims.

    The returned matrices are given in the standard basis of the
    "embedding" density matrix space, that is, the space which
    embeds the block-diagonal matrix structure stipulated in
    dimOrBlockDims. These matrices form an orthonormal basis
    under the trace inner product, i.e. Tr( dot(Mi,Mj) ) == delta_ij.

    Parameters
    ----------
    dimOrBlockDims : int or list of ints
        Structure of the density-matrix space.

    Returns
    -------
    list
        A list of N numpy arrays each of shape (dmDim, dmDim),
        where dmDim is the matrix-dimension of the overall
        "embedding" density matrix (the sum of dimOrBlockDims)
        and N is the dimension of the density-matrix space,
        equal to sum( block_dim_i^2 ).
    """
    mxs = gm_matrices_unnormalized(dimOrBlockDims)
    mxs[0] *= 1/_np.sqrt( mxs[0].shape[0] ) #identity mx
    for mx in mxs[1:]:
        mx *= 1/sqrt2
    return mxs

@basis_constructor('pp', 'Pauli-Product', real=True)
def pp_matrices(dim, maxWeight=None):
    """
    Get the elements of the Pauil-product basis
    spanning the space of dim x dim density matrices
    (matrix-dimension dim, space dimension dim^2).

    The returned matrices are given in the standard basis of the
    density matrix space, and are thus kronecker products of
    the standard representation of the Pauli matrices, (i.e. where
    sigma_y == [[ 0, -i ], [i, 0]] ) normalized so that the
    resulting basis is orthonormal under the trace inner product,
    i.e. Tr( dot(Mi,Mj) ) == delta_ij.  In the returned list,
    the right-most factor of the kronecker product varies the
    fastsest, so, for example, when dim == 4 the returned list
    is [ II,IX,IY,IZ,XI,XX,XY,XY,YI,YX,YY,YZ,ZI,ZX,ZY,ZZ ].

    Parameters
    ----------
    dim : int
        Matrix-dimension of the density-matrix space.  Must be
        a power of 2.

    maxWeight : int, optional
        Restrict the elements returned to those having weight <= `maxWeight`. An
        element's "weight" is defined as the number of non-identity single-qubit
        factors of which it is comprised.  For example, if `dim == 4` and 
        `maxWeight == 1` then the returned list is [II, IX, IY, IZ, XI, YI, ZI].


    Returns
    -------
    list
        A list of N numpy arrays each of shape (dim, dim), where N == dim^2,
        the dimension of the density-matrix space. (Exception: when maxWeight
        is not None, the returned list may have fewer than N elements.)

    Notes
    -----
    Matrices are ordered with first qubit being most significant,
    e.g., for 2 qubits: II, IX, IY, IZ, XI, XX, XY, XZ, YI, ... ZZ
    """

    sigmaVec = (id2x2/sqrt2, sigmax/sqrt2, sigmay/sqrt2, sigmaz/sqrt2)

    def is_integer(x):
        return bool( abs(x - round(x)) < 1e-6 )

    if not isinstance(dim, _numbers.Integral) and not isinstance(dim, Dim):
        if isinstance(dim, _collections.Container) and len(dim) == 1:
            dim = dim[0]
        else:
            raise ValueError("Dimension for Pauli tensor product matrices must be an *integer* power of 2")

    if isinstance(dim, Dim):
        nQubits = _np.log2(dim.dmDim)
    else:
        nQubits = _np.log2(dim)
    if not is_integer(nQubits):
        raise ValueError("Dimension for Pauli tensor product matrices must be an integer *power of 2*")

    if nQubits == 0: #special case: return single 1x1 identity mx
        return [ _np.identity(1,'complex') ]

    matrices = []
    nQubits = int(round(nQubits))
    basisIndList = [ [0,1,2,3] ]*nQubits
    for sigmaInds in _itertools.product(*basisIndList):
        if maxWeight is not None:
            if sigmaInds.count(0) < nQubits-maxWeight: continue
            
        M = _np.identity(1,'complex')
        for i in sigmaInds:
            M = _np.kron(M,sigmaVec[i])
        matrices.append(M)

    return matrices

@basis_constructor('qt', 'Qutrit', real=True)
def qt_matrices(dim, selected_pp_indices=[0,5,10,11,1,2,3,6,7]):
    """
    Get the elements of a special basis spanning the density-matrix space of
    a qutrit.

    The returned matrices are given in the standard basis of the
    density matrix space. These matrices form an orthonormal basis
    under the trace inner product, i.e. Tr( dot(Mi,Mj) ) == delta_ij.

    Parameters
    ----------
    dim : int
        Matrix-dimension of the density-matrix space.  Must equal 3
        (present just to maintain consistency which other routines)

    Returns
    -------
    list
        A list of 9 numpy arrays each of shape (3, 3).
    """
    assert(dim == 3)
    A = _np.array( [[1,0,0,0],
                   [0,1./_np.sqrt(2),1./_np.sqrt(2),0],
                   [0,0,0,1]], 'd') #projector onto symmetric space
    
    def toQutritSpace(inputMat):
        return _np.dot(A,_np.dot(inputMat,A.transpose()))

    qt_mxs = []
    pp_mxs = pp_matrices(4)
    #selected_pp_indices = [0,5,10,11,1,2,3,6,7] #which pp mxs to project
    # labels = ['II', 'XX', 'YY', 'YZ', 'IX', 'IY', 'IZ', 'XY', 'XZ']
    qt_mxs = [toQutritSpace(pp_mxs[i]) for i in selected_pp_indices]

    # Normalize so Tr(BiBj) = delta_ij (done by hand, since only 3x3 mxs)
    qt_mxs[0] *= 1/_np.sqrt(0.75)
    
    #TAKE 2 (more symmetric = better?)
    q1 = qt_mxs[1] - qt_mxs[0]*_np.sqrt(0.75)/3
    q2 = qt_mxs[2] - qt_mxs[0]*_np.sqrt(0.75)/3
    qt_mxs[1] = (q1 + q2)/_np.sqrt(2./3.)
    qt_mxs[2] = (q1 - q2)/_np.sqrt(2)

    #TAKE 1 (XX-II and YY-XX-II terms... not symmetric):
    #qt_mxs[1] = (qt_mxs[1] - qt_mxs[0]*_np.sqrt(0.75)/3) / _np.sqrt(2.0/3.0)
    #qt_mxs[2] = (qt_mxs[2] - qt_mxs[0]*_np.sqrt(0.75)/3 + qt_mxs[1]*_np.sqrt(2.0/3.0)/2) / _np.sqrt(0.5)

    for i in range(3,9): qt_mxs[i] *= 1/ _np.sqrt(0.5)
    
    return qt_mxs
