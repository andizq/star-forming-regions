"""
Disc models collection
======================
Classes: Rosenfeld2d
"""

from ..utils.constants import G
from ..utils import units as u
import numpy as np
import numbers

class Rosenfeld2d(object):
    """
    Host class for Rosenfeld+2013 toy model to describe the velocity field of a flared disc in 2D. 
    This model assumes a (Keplerian) double cone to account for the near and far sides of a flared disc 
    and projects their line-of-sight velocity v_obs on the sky-plane. 
    
    Parameters
    ----------
    grid : array_like, shape (nrows, ncols)
       (x', y') map of the sky-plane onto which the disc velocity field will be projected.
       
    Mstar : scalar
       Mass of the star to compute keplerian rotation.
    
    incl : scalar
       Inclination of the disc midplane with respect to the x'y' plane; pi/2 radians is edge-on.
    
    psi : scalar
       Opening angle of the cone describing the velocity field of the gas emitting layer in the disc; 
       0 radians returns the projected velocity field of the disc midplane (i.e no conic emission). 

    get2d : bool
       If True returns the velocity field regrided in a 2D map.
       
    velocity : str from ['keplerian', 'keplerian_vertical']
       Orbital velocity function to compute the velocity field. 

    """

    def __init__(self, grid, Mstar, incl, psi, get2d = True, velocity='keplerian', z_func=False, PA=0.0):
        self.flags = {'disc': True, 'env': False}
        self.grid = grid
        self.n = self.grid.NPoints
        self.Mstar = Mstar
        self.incl = incl
        if not z_func: self.psi = psi
        else: 
            self.psi = np.arctan(z_func(self.grid.rRTP[1]) / self.grid.rRTP[1])
            print (self.psi[self.psi != psi], psi)
        self.z_func = z_func
        self.PA = PA
        self.grid_true = self.cone_to_2d() #(x,y,z) grid as a function of the x'y' plane coordinates.
        velocity_func = {'keplerian': self.velocity_keplerian, 'keplerian_vertical': self.velocity_keplerian_vertical}
        self.velocity = velocity_func[velocity]()
        if get2d: 
            self.velocity2d = {}
            for side in ['near', 'far']:
                self.velocity2d[side] = self.convert_array_to_matrix(self.velocity[side])
        
    def convert_array_to_matrix(self, vec):
        matrix = np.zeros(self.grid.Nodes[self.grid.Nodes>1])
        k = 0
        for j in range(self.grid.Nodes[1]):
            for i in range(self.grid.Nodes[0]):
                matrix[j,i] = vec[k]
                k+=1
        return matrix
        
    def _get_t(self, A, B, C):
        t = []
        if isinstance(self.psi, numbers.Number): 
            for i in range(self.n):
                p = [A, B[i], C[i]]
                t.append(np.sort(np.roots(p)))
        else: 
            for i in range(self.n):
                p = [A[i], B[i], C[i]]
                t.append(np.sort(np.roots(p)))
        return np.array(t)
            
    def solve_quadratic(self, x, y):
        fac = -2*np.sin(self.psi)**2
        A = np.cos(2*self.incl) + np.cos(2*self.psi)
        B = fac * 2*np.tan(self.incl) * y
        C = fac * (x**2 + (y / np.cos(self.incl))**2)
        return self._get_t(A,B,C)

    def velocity_keplerian(self):
        vel = {}
        for side in ['near', 'far']:
            x, y, z, R = self.grid_true[side]
            phi = np.arctan2(y, x)
            ang_fac = np.sin(self.incl) * np.cos(phi)
            vel[side] = -np.sqrt(G * self.Mstar/R) * ang_fac #Positive vel means positive along z, which means approaching to the observer, for that reason imposed a (-) factor.
        return vel

    def velocity_keplerian_vertical(self):
        vel = {}
        for side in ['near', 'far']:
            x, y, z, R = self.grid_true[side]
            r = np.linalg.norm([R,z], axis=0)
            phi = np.arctan2(y, x) 
            ang_fac = np.sin(self.incl) * np.cos(phi)
            vel[side] = -np.sqrt(G * self.Mstar/r**3) * R * ang_fac #Positive vel means positive along z, which means approaching to the observer, for that reason imposed a (-) factor.

        #z_near = self.grid_true['near'][2]
        #z_far = self.grid_true['far'][2]
        
        #vel['near'] = np.ma.masked_where(z_near>1800*u.au, vel['near'])
        #vel['far'] = np.ma.masked_where(np.logical_or(z_far>1800*u.au, ~vel['near'].mask), vel['far'])
        
        return vel
            
    def rotate_sky_plane(self, x, y, ang):
        xy = np.array([x,y])
        cos_ang = np.cos(ang)
        sin_ang = np.sin(ang)
        rot = np.array([[cos_ang, -sin_ang],
                        [sin_ang, cos_ang]])
        return np.dot(rot, xy)

    def cone_to_2d(self):
        if self.PA != 0.0: 
            x_plane, y_plane = self.rotate_sky_plane(self.grid.XYZ[0], self.grid.XYZ[1], -self.PA)
        else:
            x_plane, y_plane = self.grid.XYZ[:2]

        """
        if self.z_func:
            z_true_near = self.z_func(R_true_near)
            z_true_far = self.z_func(R_true_far)
            
        """ 
            
        t = self.solve_quadratic(x_plane,y_plane).T        

        x_true_near = x_plane
        y_true_near = y_plane / np.cos(self.incl) + t[1]*np.sin(self.incl)
            
        x_true_far = x_plane
        y_true_far = y_plane / np.cos(self.incl) + t[0]*np.sin(self.incl)

        R_true_near = np.linalg.norm([x_true_near, y_true_near], axis=0)
        R_true_far = np.linalg.norm([x_true_far, y_true_far], axis=0)
        
        if not self.z_func: 
            z_true_near = t[1] * np.cos(self.incl) 
            z_true_far = t[0] * np.cos(self.incl) 
        else: 
            z_true_near = self.z_func(R_true_near)
            z_true_far = self.z_func(R_true_far) 
            #z_true_near = self.z_func(self.grid.rRTP[1])
            #z_true_far = -z_true_near
            
        return {'near': [x_true_near, y_true_near, z_true_near, R_true_near], 
                'far': [x_true_far, y_true_far, z_true_far, R_true_far]}
        
        
