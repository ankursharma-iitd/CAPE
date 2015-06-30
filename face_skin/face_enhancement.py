"""
Created on June 18, 2015
@author: shiruilu

Face Enhancement from CAPE, put together
"""
# for search path
import os
import sys

source_dirs = ['cape_util', 'aindane', 'face_detection'
               , 'skin_detection', 'wls_filter']

for d in source_dirs:
    sys.path.insert( 0, os.path.join(os.getcwd(), '../'+d) )

import cape_util
import aindane
import appendixa_skin_detect as apa_skin
import wls_filter
import docs_face_detector as vj_face

from eacp import EACP

import cv2
import numpy as np
from matplotlib import pyplot as plt
from scipy.signal import argrelextrema
import pdb

IMG_DIR = '../resources/images/'
BM_DIR = './benchmarks/'

def detect_bimodal(H):
    """
    H: all the (smoothed) histograms of faces on the image
    RETURN:
    bimodal_Fs: True means detected
                False means undetected (i.e. not bimodal)
                None means not sure, will plot H[i] for analysis
    """
    # argrelextrema return (array([ 54, 132]),) (a tuple), only [0] used for 1d
    maximas_Fs = [ argrelextrema(h, np.greater, order=10)[0] for h in H ]
    # argrelextrema return (array([ 54, 132]),) (a tuple), only [0] used for 1d
    minimas_Fs = [ argrelextrema(h, np.less, order=10)[0] for h in H ]
    # to visualize the bimodal:
    # print "maximas each face(hist): ", maximas_Fs, "minimas each face(hist): ", minimas_Fs
    # plt.plot(H[i]); plt.xlim([1,256]); plt.show()
    bimodal_Fs = np.zeros(len(H) ,dtype=bool)
    D = np.zeros(len(H)); M = np.zeros(len(H)); B = np.zeros(len(H));
    for i in range(len(H)): # each face i
        tot_face_pix = np.sum(H[i])
        # pdb.set_trace()
        if len(maximas_Fs[i]) ==2 and len(minimas_Fs[i]) ==1: #bimodal detected
            d = maximas_Fs[i][0]
            b = maximas_Fs[i][1]
            m = minimas_Fs[i][0]
            print 'd,b,m: ',d,b,m
            B[i] = b; M[i] = m; D[i] = d;
            # NOTICE: Here its 0.003 not 5%(as described in CAPE)!
            # 5% should be cumulated from several cylinders around the peak
            # Here it's ONLY the highest peak
            if H[i][d] >=0.003*tot_face_pix and H[i][b] >=0.003*tot_face_pix \
               and (H[i][m] <=0.8*H[i][d] and H[i][m] <=0.8*H[i][b]):
                bimodal_Fs[i] = True
        elif len(maximas_Fs[i]) >2 or len(minimas_Fs[i]) >1:
            print '?? more than two maximas, or more than one minima, see the plot'
            plt.plot(H[i]); plt.xlim([1,256]); plt.show()
            bimodal_Fs[i] = None
        else:
            None
    return bimodal_Fs, D, M, B

def sidelight_correction(I_out, H, S, faces_xywh):
    bimodal_Fs, D, M, B = detect_bimodal(H)
    A = np.ones(I_out.shape)
    for i in range(len(bimodal_Fs)):
        if bimodal_Fs[i] == True:
            b = B[i]; d = D[i]; m = M[i];
            f = (b-d) / (m-d)
            x,y,w,h = faces_xywh[i]; A_face_view = A[y:y+h, x:x+w]; A_face_view[S[i][:] <m] = f
        else:
            print '? bimodal not detected on', i, 'th face'
    A = EACP(A, I_out)
    I_out_side_crr = (I_out * A).astype('uint8') # pixelwise mul
    cape_util.display( I_out_side_crr, name='sidelight corrected, L' ,mode='gray')
    return I_out_side_crr

def exposure_correction(I_out, I_out_side_crr, skin_masks, faces_xywh):
    A = np.ones(I_out_side_crr.shape)
    for i in range(len(faces_xywh)):
        x,y,w,h = faces_xywh[i]
        face = I_out_side_crr[y:y+h, x:x+w]; # each sidelight corrected face (L channel)
        skin_face = cv2.bitwise_and(face, skin_masks[i][1]) # skin on that face
        cumsum = cv2.calcHist([skin_face],[0],None,[255],[1,256]).T.ravel().cumsum() # hist of the skin
        p = np.searchsorted(cumsum, cumsum[-1]*0.75)
        if p <120:
            f = (120+p)/(2*p)
            A_face_view = A[y:y+h, x:x+w]
            A_face_view[face >0] = f # >0 means every pixel *\in S*
            A = EACP(A, I_out)

    I_out_expo_crr = (I_out_side_crr * A).astype('uint8')
    cape_util.display( I_out_expo_crr, name='exposure corrected L', mode='gray')
    return I_out_expo_crr

def main():
    I_origin = cv2.imread(IMG_DIR+'input_teaser.png')
    _I_LAB = cv2.cvtColor(I_origin, cv2.COLOR_BGR2LAB)
    # WLS filter, only apply to L channel
    I = _I_LAB[...,0]
    Base, Detail = wls_filter.wlsfilter(I)
    I_out = Base
    I_aindane = aindane.aindane(I_origin)
    faces_xywh = vj_face.face_detect(I_aindane)
    faces = [ I_origin[y:y+h, x:x+w] for (x,y,w,h) in faces_xywh ]
    # for face in faces:
        # cv2.imwrite('teaser_face.png', face)
    skin_masks = [ apa_skin.skin_detect(face) for face in faces ]
    # for (skin, mask) in skin_masks:
        # cape_util.display( skin )

    _I_out_faces = [ I_out[y:y+h, x:x+w] for (x,y,w,h) in faces_xywh ]
    S = [ cv2.bitwise_and(_I_out_faces[i], skin_masks[i][1]) \
               for i in range(len(_I_out_faces)) ]
    for s in S:
        cape_util.display( s, name='detected skin of L channel', mode='gray')
        # plot original hist(rectangles form, of S). don't include 0(masked)
        plt.hist(s.ravel(), 255, [1,256]); plt.xlim([1,256]); plt.show()
    # unsmoothed hist (cv2.calcHist return 2d vector)
    _H = [ cv2.calcHist([s],[0],None,[255],[1,256]).T.ravel() for s in S ]
    # smooth hist, correlate only take 1d input
    H = [ np.correlate(_h, cv2.getGaussianKernel(30,10).ravel(), 'same') \
          for _h in _H ]
    # visualize smoothed hist
    for h in H:
        plt.plot(h); plt.xlim([1,256]); plt.show()

    I_out_side_crr = sidelight_correction(I_out, H, S, faces_xywh)
    I_out_expo_crr = exposure_correction(I_out, I_out_side_crr, skin_masks, faces_xywh)

    _I_LAB[...,0] = I_out_expo_crr + Detail
    I_res = cv2.cvtColor(_I_LAB, cv2.COLOR_LAB2BGR)
    cape_util.display(np.hstack([I_origin, I_res]), name='final result', mode='bgr')
    return 0

if __name__ == '__main__':
    main()