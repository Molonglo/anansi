import numpy as np
from scipy.signal import medfilt
from scipy.optimize import minimize

ANTENNA_FILE_DTPYE = [("a","|S6"),("position","float32")]
BASELINE_FILE_DTYPE = [("a","|S6"),("b","|S6")]
BASELINE_DTYPE = [("idx","int32"),("a","|S6"),("b","|S6"),("dist","float32"),
                  ("sn","float32"),("coarse_delay","float32"),
                  ("fine_delay","float32"),("phase","float32"),
                  ("total_delay","float32")]


class Baselines(object):
    def __init__(self,baselines,cp_spectra,nfine):
        self.info = baselines
        self.cp = cp_spectra
        npairs,nchans = self.cp.shape
        self.npairs = npairs
        self.nchans = nchans
        self.ncoarse = self.nchans/nfine
        self.nfine = nfine
        
    def sort_by(self,key,desc=False):
        idxs = np.argsort(self.info[key])
        if desc:
            idxs = idxs[::-1]
        self.info = self.info[idxs]
        self.cp = self.cp[idxs]

    def copy(self):
        return Baselines(np.copy(self.info),np.copy(self.cp),self.nfine)

    def threshold(self,condition):
        idxs = np.where(condition)
        self.info['sn'][idxs] = 0.0
       
        
def remove_coarse_delay(b):
    b = b.copy()
    lags = generate_lags(b)
    b.info['sn'] = lags.max(axis=1)
    b.info['coarse_delay'] = lags.argmax(axis=1)-b.nchans/2
    ramps = np.vstack([ramp(b.nchans,i)] for i in b.info['coarse_delay'])
    return Baselines(b.info,b.cp*ramps,b.nfine)

def remove_fine_delay(b):
    b = b.copy()
    def minfunc(delay,spec):
        return 1./abs((ramp(b.nchans,delay)*spec).sum())
    for ii,spec in enumerate(b.cp):
        result = minimize(minfunc,[0.0],args=(spec,),bounds=[(-1.0,1.0)])
        b.info['fine_delay'][ii] = result['x'][0]
    b.info['total_delay'] = b.info['coarse_delay']+b.info['fine_delay']
    ramps = np.vstack([ramp(b.nchans,i)] for i in b.info['fine_delay'])
    return Baselines(b.info,b.cp*ramps,b.nfine)

def random_complex(amp,size):
    a = 1+np.tan(np.random.uniform(-np.pi,np.pi,size))*1j
    return a/abs(a)

def ramp(size,shift):
    return np.e**(np.pi*2*1j*np.arange(size)/float(size) * shift)

def generate_lags(b):
    lags = abs(np.fft.fftshift(np.fft.ifft(b.cp),axes=(1,)))
    lags -= np.median(lags,axis=1).reshape(b.npairs,1)
    lags /= 1.4826 * np.median(abs(lags),axis=1).reshape(b.npairs,1)
    return lags

def replace_channel_edges(b,width=8,random=True):
    b = b.copy()
    w = width/2
    z = b.cp.reshape(b.npairs,b.ncoarse,b.nfine)
    means = np.median(abs(z[:,:,w:-w:]),axis=2).reshape(b.npairs,b.ncoarse,1)
    pool = random_complex(1,[b.npairs,b.ncoarse,width]) * means
    if random:
        z[:,:,:w]  = pool[:,:,:w]
        z[:,:,-w:] = pool[:,:,w:]
    else:
        z[:,:,:w]  = 0j
        z[:,:,-w:] = 0j
    b.cp = z.reshape(b.npairs,b.nchans)
    return b

def load_valid_baselines(cc_file,antenna_file,priant_file,baselines_file,nchans):
    antennas = dict(np.genfromtxt(antenna_file,dtype=ANTENNA_FILE_DTPYE))
    for key,pos in antennas.items():
        if key.startswith("E"):
            antennas[key] = -1*pos
    baselines = np.genfromtxt(baselines_file, usecols=(0,1), dtype=BASELINE_FILE_DTYPE)
    nbaselines = baselines.size
    priants = np.genfromtxt(priant_file,dtype="|S6")
    cp_specs = np.fromfile(cc_file,dtype="complex64").reshape(nbaselines,nchans)
    baseline_mask = np.vstack([(baselines['a']==ant)|(baselines['b']==ant) for ant in priants]).any(axis=0)
    baselines = baselines[baseline_mask]
    cp_specs = cp_specs[baseline_mask]
    baselines_update = np.recarray(baselines.size,dtype=BASELINE_DTYPE)
    for ii,b in enumerate(baselines):
        dist =  abs(antennas[b['a']] - antennas[b['b']])
        baselines_update[ii] = (ii,b['a'],b['b'],dist,0.0,0,0.0,0.0,0.0)
    return baselines_update,cp_specs
    

    

    
    
    
