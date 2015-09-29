import numpy as np

def repeat(a,n):
    return np.repeat(a,n).reshape(a.size,n).transpose().ravel()

def multi_radon(data,steps=8):
    ndata = np.copy(data)
    out = []
    for _ in range(steps):
        out.append(radon(ndata)[0])
        for ii,row in enumerate(ndata):
            ndata[ii] = np.roll(ndata[ii],-ii)
    return np.vstack(out)

def radon(data,twiddles=None,nrows=None):
    rows,cols = data.shape
    if nrows:
        ndata = np.zeros([nrows,cols])
        if nrows >= rows:
            ndata[:rows,:] = data
        else:
            ndata[:nrows,:] = data[:nrows,:]
    else:
        nrows = int(2**np.ceil(np.log2(rows)))
        ndata = np.zeros([nrows,cols])
        ndata[:rows,:] = data
    data = ndata
    rows = nrows

    layers = int(np.log2(rows))
    if twiddles is None:
        twiddles = []
        for i in range(1,int(np.log2(rows)+1)):
            twiddles.append(repeat(-1*(np.arange(2**(i)))/2,2**layers/(2**i)))
    twiddles = np.array(twiddles)
    input_ = np.copy(data)
    out = np.zeros_like(data)
    p = [data]
    for layer in range(layers):
        k = int(2**(layer+1))
        for node in range(0,rows,k):
            for jj in range(k/2):
                for ii in range(2):
                    out[node+2*jj+ii] = data[node+jj] + np.roll(data[node+k/2+jj],
                                                                twiddles[layer][node+2*jj+ii])
        data = np.copy(out)
    final_out = out/np.sqrt(rows)
    return final_out,twiddles


def radon_convolve(ar_in,widths):
    widths = np.asarray(widths)
    orig_nrows,nphase = ar_in.shape
    nwidths = widths.size
    profiles = np.zeros([nwidths,nphase])
    for ii,width in enumerate(widths):
        profiles[ii][0:width] = 1
    a,t = radon(ar_in)
    b,t = radon(ar_in,twiddles=-1*t)
    ar = np.vstack((np.flipud(b),a))
    ar-=np.median(ar)
    ar/=1.4826*np.median(abs(ar))
    nrows,nphase = ar.shape
    ar_f = np.fft.fft(ar).repeat(nwidths,axis=0).reshape(nrows,nwidths,nphase)
    pr_f = np.fft.fft(profiles)
    convd = abs(np.fft.ifft(ar_f * pr_f))
    convd/=np.sqrt(widths.reshape(1,nwidths,1))
    peaks = convd.max(axis=2)
    phase = convd.argmax()%convd.shape[-1]
    shift = float(peaks.argmax())/nwidths - (nrows-1)
    shift = shift/orig_nrows
    width = widths[peaks.argmax()%nwidths]
    tp = np.copy(ar_in)
    for ii,row in enumerate(tp):
        tp[ii] = np.roll(tp[ii],int(np.round(shift*ii)))
    return peaks.max(),phase/nphase,shift,width,tp



if __name__ == "__main__":
    x = np.zeros([231,111])
    for ii,row in enumerate(x):
        x[ii][int(ii*0.5):int(ii*0.5)+4] = 1
    p = radon_convolve(x,[1,2,3,4,5,6,7])
    print p
    
    

