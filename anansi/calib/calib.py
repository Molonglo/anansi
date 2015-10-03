import numpy as np
from scipy.signal import medfilt

ANTENNA_FILE_DTPYE = [("a","|S6"),("position","float32")]
BASELINE_FILE_DTYPE = [("a","|S6"),("b","|S6")]
BASELINE_DTYPE = [("idx","int32"),("a","|S6"),("b","|S6"),("dist","float32"),
                  ("sn","float32"),("coarse_delay","float32"),
                  ("fine_delay","float32"),("phase","float32")]

def random_complex(amp,size):
    a = 1+np.tan(np.random.uniform(-np.pi,np.pi,size))*1j
    return a/abs(a)

class DelayFinder(object):
    def __init__(self,baselines,cp_spectra):
        self.baselines = baselines
        self.cp_spec = cp_spectra
        self.phases = np.angle(self.cp_spec)
        npairs,nchans = self.cp_spec.shape
        self.npairs = npairs
        self.nchans = nchans
        self.chans = np.arange(self.nchans)
        self.chan_mask = np.ones(self.nchans).astype("bool")
        self.pair_mask = np.ones(self.npairs).astype("bool")
        self.lags = self.find_coarse_delay()

    def threshold_snr(self,snr):
        self.pair_mask[self.baselines['sn'] < snr] = False
        
    def threshold_delay(self,delay):
        self.pair_mask[self.baselines['coarse_delay'] > delay] = False
        
    def make_edge_mask(self,fine_nchans,width=8):
        self.chan_mask[np.roll(self.chans,-width/2)%fine_nchans < width] = False
        
    def find_coarse_delay(self):
        lags = abs(np.fft.fftshift(np.fft.ifft(self.cp_spec),axes=(1,)))
        lags -= np.median(lags,axis=1).reshape(self.npairs,1)
        lags /= 1.4826 * np.median(abs(lags),axis=1).reshape(self.npairs,1)
        self.baselines['sn'] = lags.max(axis=1)
        self.baselines['coarse_delay'] = lags.argmax(axis=1)-self.nchans/2
        return lags
        
    def apply_coarse_delay(self):
        pass


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

    def get_coarse_delays(self):
        lags = generate_lags(self)
        self.info['sn'] = lags.max(axis=1)
        self.info['coarse_delay'] = lags.argmax(axis=1)-self.nchans/2

    def remove_coarse_delays(self):
        ramps = np.vstack([ramp(self.nchans,i)] for i in self.info['coarse_delay'])
        self.cp *= ramps

def ramp(size,shift):
    return np.e**(np.pi*2*1j*np.arange(size)/float(size) * shift)

def generate_lags(b):
    lags = abs(np.fft.fftshift(np.fft.ifft(b.cp),axes=(1,)))
    lags -= np.median(lags,axis=1).reshape(b.npairs,1)
    lags /= 1.4826 * np.median(abs(lags),axis=1).reshape(b.npairs,1)
    return lags

def replace_channel_edges(b,width=8):
    b = b.copy()
    w = width/2
    z = b.cp.reshape(b.npairs,b.ncoarse,b.nfine)
    means = np.median(abs(z[:,:,w:-w:]),axis=2).reshape(b.npairs,b.ncoarse,1)
    pool = random_complex(1,[b.npairs,b.ncoarse,width]) * means
    z[:,:,:w]  = pool[:,:,:w]
    z[:,:,-w:] = pool[:,:,w:]
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
        baselines_update[ii] = (ii,b['a'],b['b'],dist,0.0,0,0.0,0.0)
    return baselines_update,cp_specs
    

    

    
    
    
