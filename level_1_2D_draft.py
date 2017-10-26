from scipy import misc
from collections import deque
import numpy as np

'''
    Level 1 with patterns defined by the sign of quadrant gradient: modified core algorithm of levels 1 + 2.

    Pixel comparison in 2D forms lateral and vertical derivatives: 2 matches and 2 differences per pixel. 
    They are formed on the same level because average lateral match ~ average vertical match.
    
    Pixels are discrete samples of continuous image, so rightward and downward derivatives per pixel are 
    equally representative samples of 0-90 degree quadrant gradient: minimal unique unit of 2D gradient. 
    Such gradient is computed as average of these two orthogonally diverging derivatives.
   
    2D patterns are blobs of same-sign quadrant gradient, of value for vP or difference for dP.
    Level 1 has 5 steps of encoding, incremental per level defined by vertical coordinate y:

    y:   comp(p_): lateral comp -> tuple t,
    y-1: ycomp(t_): vertical comp -> quadrant t2,
    y-1: form_P(t2_): lateral combination -> 1D pattern P,
    y-2: form_P2(P_): vertical comb and comp -> 2D pattern P2,
    y-3: term_P2(P2_): P2s are evaluated for termination and consolidation
'''

# postfix '_' denotes array vs. element, prefix '_' denotes higher-level variable


def comp(p_):  # comparison of consecutive pixels within level forms tuples: pixel, match, difference

    t_ = []  # complete fuzzy tuples: summation range = rng
    it_ = deque(maxlen=rng)  # incomplete fuzzy tuples: summation range < rng

    for p in p_:
        index = 0

        for it in it_:  # incomplete tuples with summation range from 0 to rng
            pri_p, fd, fm = it

            d = p - pri_p  # difference between pixels
            m = min(p, pri_p)  # match between pixels

            fd += d  # fuzzy d: sum of ds between p and all prior ps within it_
            fm += m  # fuzzy m: sum of ms between p and all prior ps within it_

            it = pri_p, fd, fm
            it_[index] = it
            index += 1

        if len(it_) == rng:

            t = pri_p, fd, fm
            t_.append(t)  # completed tuple is transferred from it_ to t_

        it = p, 0, 0  # fd and fm are directional, initialized each p
        it_.appendleft(it)  # new prior tuple

    t_ += it_  # last number = rng of tuples remain incomplete
    return t_


def ycomp(t_, t2__, _vP_, _dP_):  # vertical comparison between pixels, forms t2: p, d, dy, m, my

    vP_, dP_, valt_, dalt_ = [],[],[],[]  # append by form_P, alt_-> alt2_, packed in scan_P_

    vP = 0,0,0,0,0,0,0,0,[]  # pri_s, I, D, Dy, M, My, G, rdn_olp, e_
    dP = 0,0,0,0,0,0,0,0,[]  # pri_s, I, D, Dy, M, My, G, rdn_olp, e_

    x = 0; olp = 0,0,0  # olp_len, olp_vG, olp_dG: common for current vP and dP
    new_t2__ = []  # buffer 2D template array
    
    for t, t2_ in zip(t_, t2__):  # compares vertically consecutive pixels, forms quadrant gradients

        p, d, m = t
        index = 0
        x += 1

        for t2 in t2_:
            pri_p, _d, fdy, _m, fmy = t2

            dy = p - pri_p  # vertical difference between pixels
            my = min(p, pri_p)  # vertical match between pixels

            fdy += dy  # fuzzy dy: sum of dys between p and all prior ps within t2_
            fmy += my  # fuzzy my: sum of mys between p and all prior ps within t2_

            t2 = pri_p, _d, fdy, _m, fmy
            t2_[index] = t2
            index += 1

        if len(t2_) == rng:

            dg = _d + fdy
            vg = _m + fmy - ave
            t2 = pri_p, _d, fdy, _m, fmy  # completed tuple is moved from t2_ to form_P:

            # form 1D value pattern vP: horizontal span of same-sign vg s with associated vars:

            sv, olp, valt_, dalt_, vP, dP, vP_, _vP_ = \
            form_P(1, t2, vg, dg, olp, valt_, dalt_, vP, dP, vP_, _vP_, x)

            # form 1D difference pattern dP: horizontal span of same-sign dg s, associated vars:

            sd, olp, dalt_, valt_, dP, vP, dP_, _dP_ = \
            form_P(0, t2, dg, vg, olp, dalt_, valt_, dP, vP, dP_, _dP_, x)

        t2 = p, d, 0, m, 0  # fdy and fmy initialized at 0
        t2_.appendleft(t2)  # new prior tuple, displaces completed one
        new_t2__.append(t2_)
        
    # line ends, olp term, vP term, dP term, no init, inclusion per incomplete lateral fd and fm:

    if olp: # or if vP, dP?

        dalt_.append(olp); valt_.append(olp)
        olp_len, olp_vG, olp_dG = olp  # same for vP and dP, incomplete vg - ave / (rng / X-x)?

        if olp_vG > olp_dG:  # comp of olp_vG to olp_dG, == goes to alt_P or to vP: primary?
            vP[7] += olp_len  # olp_len is added to redundant overlap of lesser-oG-  vP or dP
        else:
            dP[7] += olp_len  # no P[8] /= P[7]: rolp = rdn_olp / len(e_): P to alt_Ps rdn ratio

    if y + 1 > rng:
        vP_, _vP_ = scan_P_(0, vP, valt_, vP_, _vP_, x)  # empty _vP_ []
        dP_, _dP_ = scan_P_(1, dP, dalt_, dP_, _dP_, x)  # empty _dP_ []

    return new_t2__, vP_, dP_  # extended in scan_P_, renamed as arguments _vP_, _dP_

    # P_ redefined as np.array ([P, alt_, roots, fork_P2s]): for incrementing without init?
    # P2: 0,0,0,0,0,0,0,[],0,[]: L2, G2, I2, D2, Dy2, M2, My2, alt2_, rdn2, Py_?


def form_P(typ, t2, g, alt_g, olp, alt_, _alt_, P, alt_P, P_, _P_, x):  # forms 1D Ps

    p, d, dy, m, my = t2  # 2D tuple of quadrant per pixel
    pri_s, I, D, Dy, M, My, G, rdn_olp, e_ = P

    if typ:
        olp_len, oG, alt_oG = olp  # overlap between current vP and dP, accumulated in ycomp,
    else:
        olp_len, alt_oG, oG = olp  # -> P2 rdn_olp2, generic 1D ave *= 2: low variation?

    s = 1 if g > 0 else 0
    if s != pri_s and x > rng + 2:  # P (span of same-sign gs) is terminated

        if alt_oG > oG:  # comp of olp_vG to olp_dG, == goes to alt_P or to vP: primary pattern?
            rdn_olp += olp_len  
        else:
            alt_P[7] += olp_len  # redundant overlap in weaker-oG- vP or dP, at either-P term
            # converted to list, else full unpack / repack: no assign to tuple?

        P = pri_s, I, D, Dy, M, My, G, rdn_olp, e_ # -> rdn_olp2, no A = ave * rdn_olp / e_: dA < cost?
        P_, _P_ = scan_P_(typ, P, alt_, P_, _P_, x)  # scan over contiguous higher-level _Ps

        alt = alt_P, olp_len, oG, alt_oG  # or P index len(P_): faster than P?  for P eval in form_blob
        alt_.append(alt)

        _alt = P, olp_len, alt_oG, oG  # redundant olp repr in concurrent alt_P, formed by terminated P
        _alt_.append(_alt)

        I, D, Dy, M, My, G, rdn_olp, e_, alt_ = 0,0,0,0,0,0,0,[],[]
        olp = 0,0,0  # P, alt_, olp are initialized

    # continued or initialized P vars are accumulated:

    olp_len += 1  # alt P overlap: olp_len, oG, alt_oG are accumulated till either P or _P is terminated
    oG += g; alt_oG += alt_g

    I += p    # p s summed within P
    D += d    # lateral D, for P comp and P2 normalization
    Dy += dy  # vertical D, for P2 normalization
    M += m    # lateral D, for P comp and P2 normalization
    My += my  # vertical M, for P2 normalization
    G += g    # d or v gradient summed to define P value, or V = M - 2a * W?

    if typ:
        pri = p, g, alt_g  # g = v gradient
        e_.append(pri)  # pattern element: prior same-level quadrant, for selective incremental range
    else:
        e_.append(g)  # g = d gradient and pattern element, for selective incremental derivation

    P = s, I, D, Dy, M, My, G, rdn_olp, e_  # incomplete P
    olp = olp, oG, alt_oG

    return s, olp, alt_, _alt_, P, alt_P, P_, _P_  # alt_ and _alt_ accumulated in ycomp per level


def scan_P_(typ, P, alt_, P_, _P_, x):  # P scans overlapping _Ps in _P_ for inclusion, _P termination

    A = ave  # initialization before accumulation per rdn fork
    buff_ = [] # _P_ buffer for next P; alt_-> rolp, alt2_-> rolp2

    fork_, f_vP_, f_dP_ = deque(),deque(),deque()  # refs per P to compute rdn and transfer forks
    s, I, D, Dy, M, My, G, rdn_alt, e_ = P

    ix = x - len(e_)  # initial x of P
    _ix = 0  # initialized ix of _P displaced from _P_ by last scan_P_

    while x >= _ix:  # P to _P match eval, while horizontal overlap between P and _P_:

        fork_oG = 0  # fork overlap gradient: oG += g
        ex = x  # ex is coordinate of current P element

        _P = _P_.popleft() # _P = _P, _alt_, roots, forks
        # _P = _s, _ix, _x, _I, _D, _Dy, _M, _My, _G, _rdn_alt, _e_ # or rdn_alt is folded in rdn?

        if P[0] == _P[0][0]:  # if s == _s: vg or dg sign match

            while ex > _P[0][1]: # _ix = _P[0][1]
        
                for e in e_:  # oG accumulation per P (PM, PD from comp_P only)

                    if typ: fork_oG += e[1]  # if vP: e = p, g, alt_g
                    else: fork_oG += e  # if dP: e = g
                    ex += 1

            fork = fork_oG, _P  # or PM, PD in comp_P, vs. re-packing _P, rdn = sort order
            fork_.append(fork)  # _P inclusion in P

            _P[2][0].append(P)  # root_.append(P), to track continuing roots in form_PP

        if _P[0][2] > ix:  # if _x > ix:
            buff_.append(_P)  # _P is buffered for next-P comp

        else:  # no horizontal overlap between _P and next P, _P is removed from _P_

            if (_P[2][0] == 0 and y > rng + 3) or y == Y - 1:  # P2 term if root_== 0

                blob_ = _P[2][2]
                for blob in blob_:

                    blob, _vPP, _dPP = blob  # <= one _vPP and _dPP per higher-level blob
                    term_P2(blob, A)  # eval for 2D P re-orient and re-scan, then recursion

                    if _vPP: term_P2(_vPP, A)  # if comp_P in fork_eval(blob)
                    if _dPP: term_P2(_dPP, A)  # not for _dPP in _dPP_: only to eval for rdn?

    P = s, ix, x, I, D, Dy, M, My, G, rdn_alt, e_, alt_  # no horizontal overlap between P and _P_

    if fork_: # P is evaluated for inclusion into its fork _Ps

        bA = A  # P eval for _P blob inclusion and comp_P
        fork_, bA = fork_eval(2, P, P_, _P_, fork_, bA, x)  # bA *= blob rdn

        if f_vP_:  # = lateral len(dPP_): from comp_P over same forks, during fork_eval of blob_

            vA = bA  # eval for inclusion in vPPs (2D value patterns), rdn alt_ = blobs:
            f_vP_, vA = fork_eval(0, P, P_, _P_, f_vP_, vA, x)

            dA = vA  # eval for inclusion in dPPs (2D difference patterns), rdn alt_ = vPPs:
            f_dP_, dA = fork_eval(1, P, P_, _P_, f_dP_, dA, x)

            # individual vPPs and dPPs are also modified in their fork

    roots = [],[],[]  # init root_, r_vP_, r_dP_: for term eval and P2 init for displaced _Ps
    forks = fork_, f_vP_, f_dP_  # current values, each has corr blob, init unless passed down?

    P = P, alt_, roots, forks  # bA, vA, dA per fork rdn, not per root: single inclusion
    P_.append(P)  # for conversion to _P_ in next-line ycomp

    buff_ += _P_  # minus displaced _Ps
    return P_, buff_  # _P_ = buff_, for scan_P_(next P)

    # y-1 P: P, fork_Ps, -> _P at _P_ scan end
    # y-2 _P: P, roots, fork_P2s, -> old | ini P2 at P_ scan end
    # y-3 __P: P2, roots, fork_seg_P2s, -> seg_P2 if root_>1 | term_P2 if root_=0:
    # y-4+: layers of segmented P2s, terminated if full root_-> term_, full term at last cont_P


def fork_eval(typ, P, P_, _P_, fork_, A, x):  # A is accumulated, _Ps eval for form_blob, comp_P, form_PP

    # from scan_P_(): fork = crit, _P; _P = _P, roots, fork_P2s
    # _P = _s, _ix, _x, _I, _D, _Dy, _M, _My, _G, _rdn_alt, _e_, _alt_; same as P?

    ini = 1; select_ = deque()
    fork_.sort(key = lambda fork: fork[0])  # max-to-min crit, or sort and select at once:

    while fork_ and (crit > A or ini == 1):  # _P -> P2 inclusion if contiguous sign match

        ini = 0
        fork = fork_.pop()
        crit, fork = fork  # criterion: oG if fork, PM if vPP, PD if dPP

        fA = A * (1 + P[9] / P[10])  # rolp: 1 + rdn_alt / len(e_), not alone: adjust < cost?
        fork = fA, fork

        select_.appendleft(fork)
        A += A  # base filter accum per selected fork

    init = 0 if select_ == 1 else 0
    for fork in select_:

        if typ == 2:  # fork = blob, comp_P if form_blob?

            fork = form_blob(P, fork, init)  # crit is summed in _G, rdn_alt in fA?
            vPP, dPP = comp_P(P, fork, P_, _P_, x)  # adding crit PM | PD?
            fork = fork, vPP, dPP

        else:
            fork = form_PP(typ, P, fork, init)  # fork = vPP or dPP

        fork_.appendleft(fork)  # not-selected forks are out of fork_, don't increment root_

    return fork_, A  # A is accumulated for higher P2 types?


def form_blob(P, fork, init):  # P inclusion into blob (initialized or continuing) of selected fork

    _P, roots, fork_P2s = fork
    blob_ = fork_P2s[0]  # P2: blob | vPP | dPP
    s, ix, x, I, D, Dy, M, My, G, rdn, e_, alt_ = _P  # alt_ is packed

    if init:  # fork_P2s are neither extended nor terminated

        I2 = I
        D2 = D; Dy2 = Dy
        M2 = M; My2 = My
        G2 = G  # oG: vertical contiguity for fork_eval, also for comp_P?
        L2 = len(e_)  # no separate e2_: Py_( P( e_?
        alt2_ = alt_  # or replaced by alt_blob_?
        rdn2 = rdn    # rdn_alt, not fA or rdn_fork?

        Py_ = _P,  # vertical array of patterns within a blob

        blob = L2, G2, I2, D2, Dy2, M2, My2, alt2_, rdn2, Py_
        blob_ = blob,  # single fork blob?

    else:  # single fork continues, max fork if multi-A select?

        L2, G2, I2, D2, Dy2, M2, My2, alt2_, Py_ = blob_[0]

        I2 += I
        D2 += D; Dy2 += Dy
        M2 += M; My2 += My
        G2 += G
        L2 += len(e_)
        alt2_ += alt_
        rdn2 =+ rdn
        Py_.append(_P)

        blob_[0] = L2, G2, I2, D2, Dy2, M2, My2, alt2_, rdn2, Py_ # tuple assignment?

    fork_P2s[0] = blob_
    fork = P, roots, fork_P2s  # P is replacing _P, which was summed into P2

    return fork


def comp_P(P, _P, P_, _P_, x):  # forms 2D derivatives of 1D P vars to define vPP and dPP:

    ddx = 0  # optional spec

    s, I, D, Dy, M, My, G, e_, rdn, alt_ = P  # select alt_ per fork, no olp: = mx?
    _s, _ix, _x, _I, _D, _Dy, _M, _My, _G, _e_, _rdn, _alt_, blob_ = _P  # no oG: fork sel only?

    ix = x - len(e_)  # len(e_) or w: P width, initial coordinate of P, for output only?

    dx = x - len(e_)/2 - _x - len(_e_)/2  # Dx? comp(dx), ddx = Ddx / h? dS *= cos(ddx), mS /= cos(ddx)?
    mx = x - _ix
    if ix > _ix: mx -= ix - _ix  # x overlap, mx - a_mx, form_P(vxP), vs. distant Ps: mx = -(a_dx - dx)?

    dL = len(e_) - len(_e_)  # -> dwP: higher dim? Ddx + DL triggers adjustment of derivatives or _vars?
    mL = min(len(e_), len(_e_))  # L: P width = len(e_), relative overlap: mx / L, similarity: mL?

    # or G > aG? rL = len(e_) / len(_e_), distant-P or not?
    # summed vars comp by sub if low ratio, or incr div while sign match?

    # ddx and dL signs correlate, dx (position) and dL (dimension) signs don't correlate?
    # full input CLIDV comp, or comp(S| aS(L rdn norm) in positive eM = mx+mL, more predictive than eD?

    dI = I - _I; mI = min(I, _I)  # eval of MI vs. Mh rdn at term PP | var_P, not per slice?
    dD = D - _D; mD = min(D, _D)
    dM = M - _M; mM = min(M, _M)  # no G comp: y-derivatives are incomplete, no alt_ comp: rdn only?

    PD = ddx + dL + dI + dD + dM  # defines dPP; var_P form if PP form, term if var_P or PP term;
    PM = mx + mL + mI + mD + mM   # defines vPP; comb rep value = PM * 2 + PD?  group by y_ders?

    # vPP and dPP included in selected forks, rdn assign and form_PP eval after fork_ term in form_blob?

    blob= 0,0,0,0,0,0,0,0,0,0,[],[]  # crit, rdn, W, I2, D2, Dy2, M2, My2, G2, rdn2, alt2_, Py_
    vPP = 0,0,0,0,0,0,0,0,0,0,[],[] 
    dPP = 0,0,0,0,0,0,0,0,0,0,[],[]  # P2s are initialized at non-matching P transfer to _P_?

    ''' np.array for direct accumulation, or simply iterator of initialization?

    P2_ = np.array([blob, vPP, dPP],
        dtype=[('crit', 'i4'), ('rdn', 'i4'), ('W', 'i4'), ('I2', 'i4'), ('D2', 'i4'), ('Dy2', 'i4'),
        ('M2', 'i4'), ('My2', 'i4'), ('G2', 'i4'), ('rdn2', 'i4'), ('alt2_', list), ('Py_', list)])
    '''

    P = s, I, D, Dy, M, My, G, e_, alt_, blob_  # _fork_ is empty, similar to tuple declaration?
    # returned Ps also include current derivatives per var?

    P_.append(P)  # _P_ = P_ for next-level comp, if no horizontal overlap between P and next _P

    return P_, _P_


def form_PP(PP, fork, root_, blob_, _P_, _P2_, _x, A):  # forms vPPs, dPPs, and their var Ps

    if fork[1] > 0:  # rdn > 0: new PP initialization?

    else:  # increments PP of max fork, cached by fork_eval(), also sums all terminated PPs?

        crit, rdn, L2, I2, D2, Dy2, M2, My2, G2, rdn2, alt2_, Py_ = PP  # initialized at P re-input in comp_P

        L2 += len(alt_); I2 += I; D2 += D; Dy2 += Dy; M2 += M; My2 += My; G2 += G; alt2_ += alt_
        Py_.append(P)

    # _P = _P, blob, _alt_, root_, blob_, _vPP_, _dPP_
    # _P = _s, _ix, _x, _I, _D, _Dy, _M, _My, _G, _e_

    # dimensionally reduced axis: vP'PP or contour: dP'PP; dxP is direction pattern

    a_mx = 2; a_mw = 2; a_mI = 256; a_mD = 128; a_mM = 128  # feedback to define var_vPs (variable value patterns)
    # a_PM = a_mx + a_mw + a_mI + a_mD + a_mM  or A * n_vars, rdn accum per var_P, alt eval per vertical overlap?


    mx, dx, mL, dL, mI, dI, mD, dD, mM, dM, P, _P = fork  # current derivatives, to be included if match
    s, ix, x, I, D, Dy, M, My, G, r, e_, alt_ = P  # input P or _P: no inclusion of last input?

    # criterion eval, P inclusion in PP, then all connected PPs in CP, unique tracing of max_crit PPs:

    if crit > A * 5 * rdn:  # PP vars increment, else empty fork ref?

        L2 += len(alt_); I2 = I; D2 = D; Dy2 = Dy; M2 = M; My2 = My; G2 = G; alt2_ = alt_; Py_ = P
        # also var_P form: LIDV per dx, w, I, D, M? select per term?

        PP = L2, I2, D2, Dy2, M2, My2, G2, alt2_, Py_  # alt2_: fork_ alt_ concat, to re-compute redundancy per PP

        fork = len(_P_), PP
        blob_.append(fork)  # _P index and PP per fork, possibly multiple forks per P

        root_.append(P)  # connected Ps in future blob_ and _P2_

    return PP


def term_P2(P2, A):  # blob | vPP | dPP eval for rotation, re-scan, re-comp, recursion, accumulation

    P2_ = []
    ''' 
    conversion of root to term, sum into wider fork, also sum per frame?
    
    mean_dx = 1  # fractional?
    dx = Dx / H
    if dx > a: comp(abs(dx))  # or if dxP Dx: fixed ddx cost?  comp of same-sign dx only

    vx = mean_dx - dx  # normalized compression of distance: min. cost decrease, not min. benefit?
    
    
    eval of d,m adjust | _var adjust | x,y adjust if projected dS-, mS+ for min.1D Ps over max.2D

        if dw sign == ddx sign and min(dw, ddx) > a: _S /= cos (ddx)  # to angle-normalize S vars for comp

    if dw > a: div_comp (w): rw = w / _w, to width-normalize S vars for comp: 

        if rw > a: pn = I/w; dn = D/w; vn = V/w; 

            comp (_n) # or default norm for redun assign, but comp (S) if low rw?

            if d_n > a: div_comp (_n) -> r_n # or if d_n * rw > a: combined div_comp eval: ext, int co-variance?

        comp Dy and My, /=cos at PP term?  default div and overlap eval per PP? not per CP: sparse coverage?
        
    rrdn = 1 + rdn_w / len(e_)  # redundancy rate / w, -> P Sum value, orthogonal but predictive
    
    S = 1 if abs(D) + V + a * len(e_) > rrdn * aS else 0  # rep M = a*w, bi v!V, rdn I?
    '''


def root_2D(f):

    # postfix '_' denotes array vs. element, prefix '_' denotes higher-level variable

    global rng; rng = 1
    global ave; ave = 127  # filters, ultimately set by separate feedback, then ave *= rng

    global Y; global X
    Y, X = f.shape  # Y: frame height, X: frame width

    global _vP2_; _vP2_ = []
    global _dP2_; _dP2_ = []  # 2D Ps terminated on level y-3

    _vP_, _dP_, frame_ = [], [], []

    global y; y = 0

    t2_ = deque(maxlen=rng)  # vertical buffer of incomplete pixel tuples, for fuzzy ycomp
    t2__ = []  # 2D (vertical buffer + horizontal line) array of tuples, also deque for speed?
    p_ = f[0, :]  # first line of pixels
    t_ = comp(p_)

    for t in t_:
        p, d, m = t
        t2 = p, d, 0, m, 0  # fdy and fmy initialized at 0
        t2_.append(t2)  # only one tuple per first-line t2_
        t2__.append(t2_)  # in same order as t_

    for y in range(1, Y):  # vertical coordinate y is index of new level p_

        p_ = f[y, :]
        t_ = comp(p_)  # lateral pixel comparison
        t2__, _vP_, _dP_ = ycomp(t_, t2__, _vP_, _dP_) # vertical pixel comp, P and P2 form

        P2_ = _vP2_, _dP2_  # arrays of blobs terminated per level, adjusted by term_P2
        frame_.append(P2_)  # level of patterns is added to frame of patterns
        _vP2_, _dP2_ = [],[]

    return frame_  # frame of 2D patterns is output to level 2

f = misc.face(gray=True)  # input frame of pixels
f = f.astype(int)
root_2D(f)

