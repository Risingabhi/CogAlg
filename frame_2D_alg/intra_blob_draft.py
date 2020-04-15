import operator as op
from collections import deque, defaultdict
from itertools import groupby, starmap, zip_longest
import numpy as np
import numpy.ma as ma
from intra_comp import *
from utils import pairwise, flatten
from functools import reduce
'''
    2D version of 1st-level algorithm is a combination of frame_blobs, intra_blob, and comp_P: optional raster-to-vector conversion.
    
    intra_blob recursively evaluates each blob for one of three forks of extended internal cross-comparison and sub-clustering:
    angle cross-comp,
    der+: incremental derivation comp in high-variation edge areas of +vg: positive deviation of gradient triggers comp_g, 
    rng+: incremental range comp in low-variation flat areas of +v--vg: positive deviation of negated -vg triggers comp_r.
    Each adds a layer of sub_blobs per blob.  
    Please see diagram: https://github.com/boris-kz/CogAlg/blob/master/frame_2D_alg/Illustrations/intra_blob_forking_scheme.png
    
    Blob structure, for all layers of blob hierarchy:
    
    root_blob,  # reference for feedback of blob Dert params and sub_blob_, up to frame
    Dert = I, G, Dy, Dx, M, comp_a: + [Ga, Dyy, Dxy, Dyx, Dxx], S (area), Ly (vertical dimension)
    # I: input, G: gradient, (Dy, Dx): vertical and lateral Ds, M: match, Ga: angle G, Day, Dax: angle Ds  
    sign, 
    map,  # boolean map of blob, to compute overlap in comp_blob
    box,  # boundary box: y0, yn, x0, xn; selective map, box in lower Layers
    dert__, # comp r | comp_g -> i, g, dy, dx, m; comp_a -> i, g, dy, dx, m, ga, day, dax, da0, da1 
    stack_[ stack_params, Py_ [(P_params, dert_)]]: refs down blob formation tree, in vertical (horizontal) order
    
    # fork structure of next layer:
    fcr, # flag comp rng, also clustering criterion in dert and Dert: g in der+ fork, i+m in rng+ fork? 
    fca, # flag comp angle, clustering by ga: gradient of angle?
    fga, # flag comp angle of ga vs. angle of g
    fig, # flag input is gradient
    rdn, # redundancy to higher layers
    rng, # comp range
    layer_ # [(Dert, sub_blob_)]: list of layers across sub_blob derivation tree
           # deeper layers are nested, multiple forks: no single set of fork params?
'''
# filters, All *= rdn:

ave  = 50  # fixed cost per dert, from average g|m, reflects blob definition cost, may be different for comp_a?
aveB = 10000  # fixed cost per intra_blob comp and clustering

# -----------------------------------------------------------------------------------------------------------------------
# functions, ALL WORK-IN-PROGRESS:

def intra_blob(blob, rdn, rng, fig, fca, fcr, fga):

    # recursive input rng+ | der+ | angle cross-comp within a blob
    # flags: fca: comp angle, fga: comp angle of ga, fig: input is g, fcr: comp over rng+

    if fca:
        dert__ = comp_a(blob['dert__'], fga)  # form ga blobs, evaluate for comp_aga | comp_g:
        cluster_derts(blob, dert__, ave*rdn, fca, fcr, fig=0)  # cluster by sign of crit=ga -> ga_sub_blobs

        for sub_blob in blob['blob_']:  # eval intra_blob: if disoriented g: comp_aga, else comp_g
            if sub_blob['sign']:
                if sub_blob['Dert']['Ga'] > aveB * rdn:
                    # +Ga -> comp_aga -> dert + gaga, ga_day, ga_dax:
                    intra_blob(sub_blob, rdn+1, rng=1, fig=1, fca=1, fcr=0, fga=1)

            elif -sub_blob['Dert']['Ga'] > aveB * rdn:
                # -Ga -> comp_g -> dert = g, gg, gdy, gdx, gm:
                intra_blob(sub_blob, rdn+1, rng=1, fig=1, fca=0, fcr=0, fga=1)  # fga passed to comp_agg
    else:
        if fcr: dert__ = comp_r(blob['dert__'], fig, blob['root']['fcr'])  # 3x3, sparse to avoid center overlap
        else:   dert__ = comp_g(blob['dert__'])

        cluster_derts(blob, dert__, ave*rdn, fca, fcr, fig)  # cluster by sign of crit=g -> g_sub_blobs
        # feedback: root['layer_'] += [[(lL, fig, fcr, rdn, rng, blob['sub_blob_'])]]  # 1st sub_layer

        for sub_blob in blob['blob_']:  # eval intra_blob comp_a | comp_rng if low gradient
            if sub_blob['sign']:
                if sub_blob['Dert']['G'] > aveB * rdn:
                    # +G -> comp_a -> dert + a, ga=0, day=0, dax=0:
                    intra_blob(sub_blob, rdn+1, rng=1, fig=1, fca=1, fcr=0, fga=0)

            elif -sub_blob['Dert']['G'] > aveB * rdn:
                # -G -> comp_r -> dert with accumulated derivatives:
                intra_blob(sub_blob, rdn+1, rng+1, fig=fig, fca=0, fcr=1, fga=0)
                # fga is passed to comp_agr
    '''
    also cluster_derts(crit=gi): abs_gg (no * cos(da)) -> abs_gblobs, no eval by Gi?
    with feedback:
    for sub_blob in blob['blob_']:
        blob['layer_'] += intra_blob(sub_blob, rdn + 1 + 1 / lL, rng, fig, fca)  # redundant to sub_blob
    '''
# constants:

iPARAMS = "I", "G", "Dy", "Dx", "M"  # formed by comp_pixel
aPARAMS = iPARAMS + ("Ga", "Dyy", "Dxy", "Dyx", "Dxx")  # (sin, cos), formed by comp_a, same for comp_g
rPARAMS = iPARAMS  # if fig: + gPARAMS  # formed by comp_r

P_PARAMS = "L", "x0", "dert_", "down_fork_", "up_fork_", "y", "sign"
S_PARAMS = "S", "Ly", "y0", "x0", "xn", "Py_", "down_fork_", "up_fork_", "sign"

P_PARAM_KEYS = iPARAMS + P_PARAMS
aP_PARAM_KEYS = aPARAMS + P_PARAMS
S_PARAM_KEYS = iPARAMS + S_PARAMS
aS_PARAM_KEYS = aPARAMS + S_PARAMS


def cluster_derts(blob, dert__, Ave, fca, fcr, fig):  # clustering crit is always g in dert[1], fder is a sign

    blob['layer_'][0][0] = dict(I=0, G=0, Dy=0, Dx=0, M=0, Ga=0, Dyy=0, Dxy=0, Dyx=0, Dxx=0, S=0, Ly=0,
                                sub_blob_=[])  # to fill with fork params and sub_sub_blobs
                                # initialize first sub_blob in first layer

    P__ = form_P__(dert__, Ave, fca, fcr, fig)  # horizontal clustering
    P_ = scan_P__(P__)
    stack_ = form_stack_(P_)  # vertical clustering
    sub_blob_ = form_blob_(stack_, blob['fork_'])  # with feedback to root_fork at blob['fork_']

    return sub_blob_

# clustering functions, out of date:
#---------------------------------------------------------------------------------------------------------------------------------------

def form_P__(dert__, Ave, fca, fcr, fig, x0=0, y0=0):  # cluster dert__ into P__, in horizontal ) vertical order

    # compute value (clustering criterion) per each intra_comp fork, crit__ and dert__ are 2D arrays:
    if fca:
        crit__ = Ave - dert__[5, :, :]  # comp_a output eval by inverted ga deviation, add a coeff to Ave?
        param_keys = aP_PARAM_KEYS  # comp_a output params
    elif fcr:
        if fig: crit__ = dert__[0 + 4, :, :] - Ave  # comp_r output eval by i + m, accumulated over comp range
        else:   crit__ = Ave - dert__[1, :, :]  # comp_r output eval by inverted g, accumulated over comp range
        param_keys = P_PARAM_KEYS
    else:
        crit__ = dert__[1, :, :] - Ave  # comp_g output eval by g
        param_keys = P_PARAM_KEYS

    # Cluster dert__ into Pdert__:
    s_x_L__ = [*map(
        lambda crit_:  # Each line
            [(sign, next(group)[0], len(list(group)) + 1)  # (s, x, L)
             for sign, group in groupby(enumerate(crit_ > 0),
                                        op.itemgetter(1))  # (x, s): return s
             if sign is not ma.masked],  # Ignore gaps.
        crit__,  # blob slices in line
    )]
    Pdert__ = [[dert_[:, x : x+L].T for s, x, L in s_x_L_]
                for dert_, s_x_L_ in zip(dert__.swapaxes(0, 1), s_x_L__)]

    # Accumulate Dert = P param_keys:
    PDert__ = map(lambda Pdert_:
                       map(lambda Pdert_: Pdert_.sum(axis=0),
                           Pdert_),
                   Pdert__)
    P__ = [
        [
            dict(zip( # Key-value pairs:
                param_keys,
                [*PDerts, L, x+x0, Pderts, [], [], y, s]  # why Pderts?
            ))
            for PDerts, Pderts, (s, x, L) in zip(*Pparams_)
        ]
        for y, Pparams_ in enumerate(zip(PDert__, Pdert__, s_x_L__), start=y0)
    ]

    return P__


def scan_P__(P__):
    """Detect up_forks and down_forks per P."""

    for _P_, P_ in pairwise(P__):  # Iterate through pairs of lines.
        _iter_P_, iter_P_ = iter(_P_), iter(P_)  # Convert to iterators.
        try:
            _P, P = next(_iter_P_), next(iter_P_)  # First pair to check.
        except StopIteration:  # No more up_fork-down_fork pair.
            continue  # To next pair of _P_, P_.
        while True:
            isleft, olp = comp_edge(_P, P)  # Check for 4 different cases.
            if olp and _P['sign'] == P['sign']:
                _P['down_fork_'].append(P)
                P['up_fork_'].append(_P)
            try:  # Check for stopping:
                _P, P = (next(_iter_P_), P) if isleft else (_P, next(iter_P_))
            except StopIteration:  # No more up_fork - down_fork pair.
                break  # To next pair of _P_, P_.

    return [*flatten(P__)]  # Flatten P__ before return.


def comp_edge(_P, P):  # Used in scan_P_().
    """
    Check for end-point relative position and overlap.
    Used in scan_P__().
    """
    _x0 = _P['x0']
    _xn = _x0 + _P['L']
    x0 = P['x0']
    xn = x0 + P['L']

    if _xn < xn:  # End-point relative position.
        return True, x0 < _xn  # Overlap.
    else:
        return False, _x0 < xn


def form_stack_(P_, fig):
    """Form segments of vertically contiguous Ps."""
    # Get a list of every segment's first P:
    P0_ = [*filter(lambda P: (len(P['up_fork_']) != 1
                              or len(P['up_fork_'][0]['down_fork_']) != 1),
                   P_)]

    if fig:
        param_keys = gS_PARAM_KEYS
    else:
        param_keys = S_PARAM_KEYS

    # Form segments:
    seg_ = [dict(zip(param_keys,  # segment's params as keys
                     # Accumulated params:
                     [*map(sum,
                           zip(*map(op.itemgetter(*param_keys[:-6]),
                                    Py_))),
                      len(Py_), Py_[0].pop('y'), Py_,  # Ly, y0, Py_ .
                      Py_[-1].pop('down_fork_'), Py_[0].pop('up_fork_'),  # down_fork_, up_fork_ .
                      Py_[0].pop('sign')]))
            # cluster_vertical(P): traverse segment from first P:
            for Py_ in map(cluster_vertical, P0_)]

    for seg in seg_:  # Update segs' refs.
        seg['Py_'][0]['seg'] = seg['Py_'][-1]['seg'] = seg

    for seg in seg_:  # Update down_fork_ and up_fork_ .
        seg.update(down_fork_=[*map(lambda P: P['seg'], seg['down_fork_'])],
                   up_fork_=[*map(lambda P: P['seg'], seg['up_fork_'])])

    for i, seg in enumerate(seg_):  # Remove segs' refs.
        del seg['Py_'][0]['seg']

    return seg_


def form_stack_(P_, fa):
    """Form segments of vertically contiguous Ps."""
    # Determine params type:
    if "M" not in P_[0]:
        seg_param_keys = (*aSEG_PARAM_KEYS[:2], *aSEG_PARAM_KEYS[3:])
        Dert_keys = (*aDERT_PARAMS[:2], *aDERT_PARAMS[3:], "L")
    elif fa:  # segment params: I G M Dy Dx Ga Dyay Dyax Dxay Dxax S Ly y0 Py_ down_fork_ up_fork_ sign
        seg_param_keys = aSEG_PARAM_KEYS
        Dert_keys = aDERT_PARAMS + ("L",)
    else:  # segment params: I G M Dy Dx S Ly y0 Py_ down_fork_ up_fork_ sign
        seg_param_keys = gSEG_PARAM_KEYS
        Dert_keys = gDERT_PARAMS + ("L",)

    # Get a list of every segment's top P:
    P0_ = [*filter(lambda P: (len(P['up_fork_']) != 1
                              or len(P['up_fork_'][0]['down_fork_']) != 1),
                   P_)]

    # Form segments:
    seg_ = [dict(zip(seg_param_keys,  # segment's params as keys
                     # Accumulated params:
                     [*map(sum,
                           zip(*map(op.itemgetter(*Dert_keys),
                                    Py_))),
                      len(Py_), Py_[0].pop('y'),  # Ly, y0
                      min(P['x0'] for P in Py_),
                      max(P['x0'] + P['L'] for P in Py_),
                      Py_,  # Py_ .
                      Py_[-1].pop('down_fork_'), Py_[0].pop('up_fork_'),  # down_fork_, up_fork_ .
                      Py_[0].pop('sign')]))
            # cluster_vertical(P): traverse segment from first P:
            for Py_ in map(cluster_vertical, P0_)]

    for seg in seg_:  # Update segs' refs.
        seg['Py_'][0]['seg'] = seg['Py_'][-1]['seg'] = seg

    for seg in seg_:  # Update down_fork_ and up_fork_ .
        seg.update(down_fork_=[*map(lambda P: P['seg'], seg['down_fork_'])],
                   up_fork_=[*map(lambda P: P['seg'], seg['up_fork_'])])

    for i, seg in enumerate(seg_):  # Remove segs' refs.
        del seg['Py_'][0]['seg']

    return seg_


def cluster_vertical(P):  # Used in form_segment_().
    """
    Cluster P vertically, stop at the end of segment
    """
    if len(P['down_fork_']) == 1 and len(P['down_fork_'][0]['up_fork_']) == 1:
        down_fork = P.pop('down_fork_')[0]  # Only 1 down_fork.
        down_fork.pop('up_fork_')  # Only 1 up_fork.
        down_fork.pop('y')
        down_fork.pop('sign')
        return [P] + cluster_vertical(down_fork)  # Plus next P in segment

    return [P]  # End of segment


def form_blob_old(seg_, root_blob, dert___, rng, fork_type):
    encountered = []
    blob_ = []
    for seg in seg_:
        if seg in encountered:
            continue

        q = deque([seg])
        encountered.append(seg)

        s = seg['Py_'][0]['sign']
        G, M, Dy, Dx, L, Ly, blob_seg_ = 0, 0, 0, 0, 0, 0, []
        x0, xn = 9999999, 0
        while q:
            blob_seg = q.popleft()
            for ext_seg in blob_seg['up_fork_'] + blob_seg['down_fork_']:
                if ext_seg not in encountered:
                    encountered.append(ext_seg)
            G += blob_seg['G']
            M += blob_seg['M']
            Dy += blob_seg['Dy']
            Dx += blob_seg['Dx']
            L += blob_seg['L']
            Ly += blob_seg['Ly']
            blob_seg_.append(blob_seg)

            x0 = min(x0, min(map(op.itemgetter('x0'), blob_seg['Py_'])))
            xn = max(xn, max(map(lambda P: P['x0'] + P['L'], blob_seg['Py_'])))

        y0 = min(map(op.itemgetter('y0'), blob_seg_))
        yn = max(map(lambda segment: segment['y0'] + segment['Ly'], blob_seg_))

        mask = np.ones((yn - y0, xn - x0), dtype=bool)
        for blob_seg in blob_seg_:
            for y, P in enumerate(blob_seg['Py_'], start=blob_seg['y0']):
                x_start = P['x0'] - x0
                x_stop = x_start + P['L']
                mask[y - y0, x_start:x_stop] = False

        # Form blob:
        blob = dict(
            Dert=dict(G=G, M=M, Dy=Dy, Dx=Dx, L=L, Ly=Ly),
            sign=s,
            box=(y0, yn, x0, xn),  # boundary box
            slices=(Ellipsis, slice(y0, yn), slice(x0, xn)),
            seg_=blob_seg_,
            rng=rng,
            dert___=dert___,
            mask=mask,
            root_blob=root_blob,
            hDerts=np.concatenate(
                (
                    [[*root_blob['Dert'].values()]],
                    root_blob['hDerts'],
                ),
                axis=0
            ),
            forks=defaultdict(list),
            fork_type=fork_type,
        )

        feedback(blob)

        blob_.append(blob)

    return blob_


def form_blob_(seg_, root_fork):
    """
    Form blobs from given list of segments.
    Each blob is formed from a number of connected segments.
    """

    # Determine params type:
    if 'M' not in seg_[0]:  # No M.
        Dert_keys = (*aDERT_PARAMS[:2], *aDERT_PARAMS[3:], "S", "Ly")
    else:
        Dert_keys = (*aDERT_PARAMS, "S", "Ly") if nI != 1 \
            else (*gDERT_PARAMS, "S", "Ly")

    # Form blob:
    blob_ = []
    for blob_seg_ in cluster_segments(seg_):
        # Compute boundary box in batch:
        y0, yn, x0, xn = starmap(
            lambda func, x_: func(x_),
            zip(
                (min, max, min, max),
                zip(*[(
                    seg['y0'],  # y0_ .
                    seg['y0'] + seg['Ly'],  # yn_ .
                    seg['x0'],  # x0_ .
                    seg['xn'],  # xn_ .
                ) for seg in blob_seg_]),
            ),
        )

        # Compute mask:
        mask = np.ones((yn - y0, xn - x0), dtype=bool)
        for blob_seg in blob_seg_:
            for y, P in enumerate(blob_seg['Py_'], start=blob_seg['y0']):
                x_start = P['x0'] - x0
                x_stop = x_start + P['L']
                mask[y - y0, x_start:x_stop] = False

        dert__ = root_fork['dert__'][:, y0:yn, x0:xn]
        dert__.mask[:] = mask

        blob = dict(
            Dert=dict(
                zip(
                    Dert_keys,
                    [*map(sum,
                          zip(*map(op.itemgetter(*Dert_keys),
                                   blob_seg_)))],
                )
            ),
            box=(y0, yn, x0, xn),
            seg_=blob_seg_,
            sign=blob_seg_[0].pop('sign'),  # Pop the remaining segment's sign.
            dert__=dert__,
            root_fork=root_fork,
            fork_=defaultdict(list),
        )
        blob_.append(blob)

        # feedback(blob)

    return blob_


def cluster_segments(seg_):
    blob_seg__ = []  # list of blob's segment lists.
    owned_seg_ = []  # list blob-owned segments.

    # Iterate through list of all segments:
    for seg in seg_:
        # Check whether seg has already been owned:
        if seg in owned_seg_:
            continue  # Skip.

        blob_seg_ = [seg]  # Initialize list of blob segments.
        q_ = deque([seg])  # Initialize queue of filling segments.

        while len(q_) > 0:
            blob_seg = q_.pop()
            for ext_seg in blob_seg['up_fork_'] + blob_seg['down_fork_']:
                if ext_seg not in blob_seg_:
                    blob_seg_.append(ext_seg)
                    q_.append(ext_seg)
                    ext_seg.pop("sign")  # Remove all blob_seg's signs except for the first one.

        owned_seg_ += blob_seg_
        blob_seg__.append(blob_seg_)

    return blob_seg__


def feedback_old(blob, sub_fork_type=None):  # Add each Dert param to corresponding param of recursively higher root_blob.

    root_blob = blob['root_blob']
    if root_blob is None:  # Stop recursion.
        return
    fork_type = blob['fork_type']

    # blob Layers is deeper than root_blob Layers:
    len_sub_layers = max(0, 0, *map(len, blob['forks'].values()))
    while len(root_blob['forks'][fork_type]) <= len_sub_layers:
        root_blob['forks'][fork_type].append((0, 0, 0, 0, 0, 0, []))

    # First layer accumulation:
    G, M, Dy, Dx, L, Ly = blob['Dert'].values()
    Gr, Mr, Dyr, Dxr, Lr, Lyr, sub_blob_ = root_blob['forks'][fork_type][0]
    root_blob['forks'][fork_type][0] = (
        Gr + G, Mr + M, Dyr + Dy, Dxr + Dx, Lr + L, Lyr + Ly,
        sub_blob_ + [blob],
    )

    # Accumulate deeper layers:
    root_blob['forks'][fork_type][1:] = \
        [*starmap(  # Like map() except for taking multiple arguments.
            # Function (with multiple arguments):
            lambda Dert, sDert:
            (*starmap(op.add, zip(Dert, sDert)),),  # Dert and sub_blob_ accum
            # Mapped iterables:
            zip(
                root_blob['forks'][fork_type][1:],
                blob['forks'][sub_fork_type][:],
            ),
        )]
    # Dert-only numpy.ndarray equivalent: (no sub_blob_ accumulation)
    # root_blob['forks'][fork_type][1:] += blob['forks'][fork_type]

    feedback(root_blob, fork_type)


def feedback(blob, fork=None):  # Add each Dert param to corresponding param of recursively higher root_blob.

    root_fork = blob['root_fork']

    # fork layers is deeper than root_fork Layers:
    if fork is not None:
        if len(root_fork['layer_']) <= len(fork['layer_']):
            root_fork['layer_'].append((
                dict(zip(  # Dert
                    root_fork['layer_'][0][0],  # keys
                    repeat(0),  # values
                )),
                [],  # blob_
            ))
    """
    # First layer accumulation:
    G, M, Dy, Dx, L, Ly = blob['Dert'].values()
    Gr, Mr, Dyr, Dxr, Lr, Lyr, sub_blob_ = root_blob['forks'][fork_type][0]
    root_blob['forks'][fork_type][0] = (
        Gr + G, Mr + M, Dyr + Dy, Dxr + Dx, Lr + L, Lyr + Ly,
        sub_blob_ + [blob],
    )
    # Accumulate deeper layers:
    root_blob['forks'][fork_type][1:] = \
        [*starmap( # Like map() except for taking multiple arguments.
            # Function (with multiple arguments):
            lambda Dert, sDert:
                (*starmap(op.add, zip(Dert, sDert)),), # Dert and sub_blob_ accum
            # Mapped iterables:
            zip(
                root_blob['forks'][fork_type][1:],
                blob['forks'][sub_fork_type][:],
            ),
        )]
    # Dert-only numpy.ndarray equivalent: (no sub_blob_ accumulation)
    # root_blob['forks'][fork_type][1:] += blob['forks'][fork_type]
    """
    if root_fork['root_blob'] is not None:  # Stop recursion if false.
        feedback(root_fork['root_blob'])
