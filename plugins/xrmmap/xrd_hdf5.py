#!/usr/bin/python
"""

"""
import numpy as np
import time
import h5py
import sys
import os

from larch import Group, ValidateLarchPlugin

# Default tau values for xspress3

class XSP3Data(object):
    def __init__(self, npix, ndet, nchan):
        self.firstPixel   = 0
        self.numPixels    = 0
        self.realTime     = np.zeros((npix, ndet), dtype='f8')
        self.liveTime     = np.zeros((npix, ndet), dtype='f8')
        self.outputCounts = np.zeros((npix, ndet), dtype='f8')
        self.inputCounts  = np.zeros((npix, ndet), dtype='f8')
        # self.counts       = np.zeros((npix, ndet, nchan), dtype='f4')

def read_xrd_hdf5(fname, npixels=None, verbose=False,
                   estimate_dtc=False, _larch=None):
    # Reads a HDF5 file created with the DXP xMAP driver
    # with the netCDF plugin buffers
    npixels = None
    clockrate = 12.5e-3   # microseconds per clock tick: 80MHz clock
    t0 = time.time()
    h5file = h5py.File(fname, 'r')

    root  = h5file['entry/instrument']
    counts = root['detector/data']
    #
    # support bother newer and earlier location of NDAttributes
    ndattr = None
    try:
        ndattr = root['NDAttributes']
    except KeyError:
        pass

    if 'CHAN1SCA0' not in ndattr:
        try:
            ndattr = root['detector/NDAttributes']
        except KeyError:
            pass
    if 'CHAN1SCA0' not in ndattr:
        raise ValueError("cannot find NDAttributes for '%s'" % fname)

    # note: sometimes counts has npix-1 pixels, while the time arrays
    # really have npix...  So we take npix from the time array, and
    npix = ndattr['CHAN1SCA0'].shape[0]
    ndpix, ndet, nchan = counts.shape
    if npixels is None:
        npixels = npix
        if npixels < ndpix:
            ndpix = npixels

    out = XSP3Data(npixels, ndet, nchan)
    out.numPixels = npixels
    t1 = time.time()
    if ndpix < npix:
        out.counts = np.zeros((npix, ndet, nchan), dtype='f8')
        out.counts[:ndpix, :, :]  = counts[:]
    else:
        out.counts = counts[:]

    if estimate_dtc:
        dtc_taus = XSPRESS3_TAUS
        if _larch is not None and _larch.symtable.has_symbol('_sys.gsecars.xspress3_taus'):
            dtc_taus = _larch.symtable._sys.gsecars.xspress3_taus

    for i in range(ndet):
        chan = "CHAN%i" %(i+1)
        clock_ticks = ndattr['%sSCA0' % chan].value
        reset_ticks = ndattr["%sSCA1" % chan].value
        all_events  = ndattr["%sSCA3" % chan].value
        if "%sEventWidth" in ndattr:
            event_width = 1.0 + ndattr['%sEventWidth' % chan].value
        else:
            event_width = 6.0

        clock_ticks[np.where(clock_ticks<10)] = 10.0
        rtime = clockrate * clock_ticks
        out.realTime[:, i] = rtime
        out.liveTime[:, i] = rtime
        ocounts = out.counts[:, i, 1:-1].sum(axis=1)
        ocounts[np.where(ocounts<0.1)] = 0.1
        out.outputCounts[:, i] = ocounts

        dtfactor = clock_ticks/(clock_ticks - (all_events*event_width + reset_ticks))
        out.inputCounts[:, i] = dtfactor * ocounts

        if estimate_dtc:
            ocr = ocounts/(rtime*1.e-6)
            icr = ocr
            out.inputCounts[:, i] = icr * (rtime*1.e-6)

    h5file.close()
    t2 = time.time()
    if verbose:
        print('   time to read file    = %5.1f ms' % ((t1-t0)*1000))
        print('   time to extract data = %5.1f ms' % ((t2-t1)*1000))
        print('   read %i pixels ' %  npixels)
        print('   data shape:    ' ,  out.counts.shape)
    return out

def test_read(fname):
    print( fname,  os.stat(fname))
    fd = read_xrd_hdf5(fname, verbose=True)
    print(fd.counts.shape)

def registerLarchPlugin():
    return ('_xrd', {'read_xrd_hdf5': read_xrd_hdf5})
