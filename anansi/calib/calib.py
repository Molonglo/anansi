import numpy as np
from scipy.signal import medfilt
from scipy.optimize import minimize

ANTENNA_FILE_DTPYE = [("a","|S6"),("position","float32")]
BASELINE_FILE_DTYPE = [("a","|S6"),("b","|S6")]
BASELINE_DTYPE = [("idx","int32"),("a","|S6"),("b","|S6"),("dist","float32"),
                  ("sn","float32"),("coarse_delay","float32"),
                  ("fine_delay","float32"),("phase","float32"),
                  ("total_delay","float32"),("weight","float32"),
                  ("fsn","float32")]


#IDEAS:
# 1. use best baselines to identify regions of rfi
# 2. iterate over RFI solutions to find weak correlation
# 3. Problem is that it is unclear if strong correlation is RFI or not
# 4. Phone calls rarely phase in difference portions of the band

class Baselines(object):
    def __init__(self,baselines,cp_spectra,nfine):
        self.info = baselines
        self.cp = np.ma.masked_array(cp_spectra,np.tile(False,cp_spectra.shape))
        self.cp.set_fill_value(0j)
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

    def set_weights(self,min_dist=50.0,min_sn=30.0,min_fsn=1.0,func=lambda x:x):
        i = self.info
        idxs = (i['dist']>min_dist) & (i['sn']>min_sn) & (i['fsn']>min_fsn)
        i['weight'][idxs] = func(i['fsn'][idxs])
        i['weight'][~idxs] = 0.0
        
    def mask_short_baselines(self,min_dist=50.0):
        self.cp.mask[self.info['dist']<min_dist] = True
        
    def mask_police_frequencies(self):
        self.cp.mask[:,1161:1163] = True
        self.cp.mask[:,1239:1241] = True

    def mask_channel_edges(self,width=8):
        mask = self.cp.reshape(self.npairs,self.ncoarse,self.nfine).mask
        mask[:,:,:width/2]  = True
        mask[:,:,-width/2:] = True

    def mask_rfi(self,thresh=3.0):
        a = abs(self.cp)
        a-=np.ma.extras.median(a,axis=1).reshape(self.npairs,1)
        a/=1.4826*np.ma.extras.median(abs(a),axis=1).reshape(self.npairs,1)
        self.cp.mask[a>thresh] = True

    def _remove_delays(self,delays):
        ramps = np.vstack([ramp(self.nchans,i)] for i in delays)
        self.cp*=ramps

    def _generate_lags(self):
        lags = abs(np.fft.fftshift(np.fft.ifft(self.cp.filled()),axes=(1,)))
        lags -= np.median(lags,axis=1).reshape(self.npairs,1)
        lags /= 1.4826 * np.median(abs(lags),axis=1).reshape(self.npairs,1)
        self.lags = lags

    def _zero_phase(self):
        self.info['phase'] = np.angle(self.cp.sum(axis=1))
        self.cp *= np.e**(-1j*self.info['phase']).reshape(self.npairs,1)

    def _estimate_sn(self):
        self.info['fsn'] = (self.cp.real.mean(axis=1)/self.cp.imag.std(axis=1))
    
    def fit_delays(self,normed=False):
        # find and remove coarse and fine delay
        def minfunc(delay,spec):
            # This function returns the reciprocal of the coherence
            # of a visibility after delay application
            return 1./abs((ramp(self.nchans,delay)*spec).sum())
        self._generate_lags()
        self.info['sn'] = self.lags.max(axis=1)
        self.info['coarse_delay'] = self.lags.argmax(axis=1)-self.nchans/2
        self._remove_delays(self.info['coarse_delay'])
        for ii,spec in enumerate(self.cp):
            result = minimize(minfunc,[0.0],args=(spec,),bounds=[(-1.0,1.0)])
            self.info['fine_delay'][ii] = result['x'][0]
        self.info['total_delay'] = self.info['coarse_delay']+self.info['fine_delay']
        self._remove_delays(self.info['fine_delay'])
        self._zero_phase()
        self._estimate_sn()
        #Derotate the phase

## need a perfect bandpass for normalisation... Can we get this from the PFB response???


        


def replace_channel_edges(b,width=8,random=True):
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

def remove_narrow_band_rfi(b,window=125,thresh=40):
    b = b.copy()
    spec = abs(b.cp).sum(axis=0)
    spec -= medfilt(spec,window)
    spec/=(1.4826*np.median(abs(spec)))
    b.cp[:,abs(spec)>thresh] = 0.0
    return b,spec

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
    ncp = b.cp*ramps
    #b.info['sn'] = abs(ncp.mean(axis=1))
    z = ncp.reshape(b.npairs,b.ncoarse,b.nfine)
    b.info['fsn'] = (z.real.mean(axis=2)/z.imag.std(axis=2)).max(axis=1)

    return Baselines(b.info,ncp,b.nfine)

def random_complex(amp,size):
    a = 1+np.tan(np.random.uniform(-np.pi,np.pi,size))*1j
    return a/abs(a)

def ramp(size,shift):
    return np.e**(np.pi*2*1j*np.arange(size)/float(size) * shift)

def generate_lags(b,nchans):
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
        baselines_update[ii] = (ii,b['a'],b['b'],dist,0.0,0,0.0,0.0,0.0,0.0,0.0)
    return baselines_update,cp_specs
    
def load_all_baselines(cc_file,antenna_file,baselines_file,nchans):
    antennas = dict(np.genfromtxt(antenna_file,dtype=ANTENNA_FILE_DTPYE))
    for key,pos in antennas.items():
        if key.startswith("E"):
            antennas[key] = -1*pos
    baselines = np.genfromtxt(baselines_file, usecols=(0,1), dtype=BASELINE_FILE_DTYPE)
    nbaselines = baselines.size
    cp_specs = np.fromfile(cc_file,dtype="complex64").reshape(nbaselines,nchans)
    baselines_update = np.recarray(baselines.size,dtype=BASELINE_DTYPE)
    for ii,b in enumerate(baselines):
        dist =  abs(antennas[b['a']] - antennas[b['b']])
        baselines_update[ii] = (ii,b['a'],b['b'],dist,0.0,0,0.0,0.0,0.0,0.0,0.0)
    return baselines_update,cp_specs
    

    
    
    
