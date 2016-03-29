import numpy as np
import ephem as e

skew = 2.3755870374367263e-05
slope = 0.0034494653328734047
lat = -0.617342348978

def rotation_matrix(angle, d):
    directions = {
        "x":[1.,0.,0.],
        "y":[0.,1.,0.],
        "z":[0.,0.,1.]
        }
    direction = np.array(directions[d])
    sina = np.sin(angle)
    cosa = np.cos(angle)
    # rotation matrix around unit vector 
    R = np.diag([cosa, cosa, cosa])
    R += np.outer(direction, direction) * (1.0 - cosa)
    direction *= sina
    R += np.array([[ 0.0,         -direction[2],  direction[1]],
                   [ direction[2], 0.0,          -direction[0]],
                   [-direction[1], direction[0],  0.0]])
    return R

def reflection_matrix(d):
    m = {
    "x":[[-1.,0.,0.],[0., 1.,0.],[0.,0., 1.]],
    "y":[[1., 0.,0.],[0.,-1.,0.],[0.,0., 1.]],
    "z":[[1., 0.,0.],[0., 1.,0.],[1.,0.,-1.]]
    }
    return np.array(m[d])

def pos_vector(a,b):
    return np.array([[np.cos(b)*np.cos(a)],
                     [np.cos(b)*np.sin(a)],
                     [np.sin(b)]])

def pos_from_vector(vec):
    a,b,c = vec
    a_ = np.arctan2(b,a)
    c_ = np.arcsin(c)   
    return a_,c_

def transform(a,b,R,inverse=True):
    P = pos_vector(a,b)
    if inverse:
        R = R.T
    V = np.dot(R,P).ravel()
    a,b = pos_from_vector(V)
    a = 0 if np.isnan(a) else a
    b = 0 if np.isnan(a) else b
    return a,b

def telescope_to_nsew_matrix(skew,slope):
    R = rotation_matrix(-skew,"x")
    R = np.dot(R,rotation_matrix(slope,"y"))
    return R

def nsew_to_azel_matrix(skew,slope):
    pre_R = telescope_to_nsew_matrix(skew,slope)
    x_rot = rotation_matrix(-np.pi/2,"x")
    y_rot = rotation_matrix(np.pi/2,"y")
    R = np.dot(x_rot,y_rot)
    R = np.dot(pre_R,R)
    R_bar = reflection_matrix("x")
    R = np.dot(R,R_bar)
    return R

def azel_to_hadec_matrix(lat):
    rot_y = rotation_matrix(np.pi/2-lat,"y")
    rot_z = rotation_matrix(np.pi,"z")
    R = np.dot(rot_y,rot_z)
    return R

def nsew_to_azel(ns, ew):    
    az,el = transform(ns,ew,nsew_to_azel_matrix(skew,slope))
    return az,el

def azel_to_nsew(az, el):  
    ns,ew = transform(az,el,nsew_to_azel_matrix(skew,slope).T)
    return ns,ew

def nsew_to_hadec(ns,ew,lat=lat,skew=skew,slope=slope):
    R = np.dot(nsew_to_azel_matrix(skew,slope),azel_to_hadec_matrix(lat))
    ha,dec = transform(ns,ew,R)
    return ha,dec

def hadec_to_nsew(ha,dec,lat=lat,skew=skew,slope=slope):
    R = np.dot(nsew_to_azel_matrix(skew,slope),azel_to_hadec_matrix(lat))
    ns,ew = transform(ha,dec,R.T)
    return ns,ew

def _catch_discontinuitues(ns,ew,tol=0.4):
    idxs = np.where(np.sqrt((ns[:-1] - ns[1:])**2 + (ew[:-1] - ew[1:])**2)>tol)
    for idx in idxs:
        ew = np.insert(ew,idx+1,np.nan)
        ns = np.insert(ns,idx+1,np.nan)
    return ns,ew

def nsew_of_constant_dec(ha,dec):
    R = np.dot(nsew_to_azel_matrix(skew,slope),azel_to_hadec_matrix(lat))
    P = pos_vector(ha,np.ones_like(ha)*dec)
    ns,ew = pos_from_vector(np.dot(R,np.transpose(P,(2,0,1))).transpose((1,2,0)).squeeze().transpose())
    ns,ew = _catch_discontinuitues(ns,ew)
    return np.array((ns,ew))

def nsew_of_constant_ha(ha,dec):
    R = np.dot(nsew_to_azel_matrix(skew,slope),azel_to_hadec_matrix(lat))
    P = pos_vector(ha,dec)
    ns,ew = pos_from_vector(np.dot(R,np.transpose(P,(2,0,1))).transpose((1,2,0)).squeeze().transpose())
    ns,ew = _catch_discontinuitues(ns,ew)
    return np.array((ns,ew))

