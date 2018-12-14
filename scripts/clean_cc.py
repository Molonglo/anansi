import glob
import os
import numpy as np
from anansi.calib import calib

antenna_file,priant_file,baselines_file,nchans = "obs.antenna","obs.priant","obs.baselines",40

try:
    os.mkdir("masked")
except OSError:
    pass

for cc_file in sorted(glob.glob("*.cc")):
    print "Working on %s"%cc_file
    b,cp = calib.load_all_baselines(cc_file,antenna_file,baselines_file,nchans)
    valid_idxs = abs(cp).sum(axis=1) != 0
    b_valid = b[valid_idxs]
    cp_valid = cp[valid_idxs]
    print "found %d valid baselines..."%valid_idxs.sum()
    print "loading..."
    x = calib.Baselines(b_valid,cp_valid,1)
    print "masking..."
    x.mask_channel_edges(width=8);
    x.mask_police_frequencies();
    #x.mask_short_baselines(min_dist=300.0)
    print "finding rfi..."
    x.mask_rfi(3.0)
    cp[valid_idxs,:] = x.cp.filled()[:,:]
    print "writing mask..."
    cp.tofile(os.path.join("masked",cc_file))
