#!/usr/bin/env python
import numpy as np
from pymicro.crystal.lattice import Lattice
from pymicro.crystal.microstructure import Orientation, Grain, Microstructure
from matplotlib import pyplot as plt, colors, cm

class PoleFigure:
  '''A class to handle pole figures.
  
  A pole figure is a popular tool to plot multiple crystal orientations, 
  either in the sample coordinate system (direct pole figure) or 
  alternatively plotting a particular direction in the crystal 
  coordinate system (inverse pole figure).
  '''

  def __init__(self, microstructure=None, lattice=None, axis = 'Z', hkl='111', 
    proj='stereo', verbose=False):
    '''
    Create an empty PoleFigure object associated with an empty Microstructure.
    
    :param str axis: the pole figure axis ('Z' by default), vertical axis in the direct pole figure and direction plotted on the inverse pole figure.
    :param microstructure: the :py:class:`~pymicro.crystal.microstructure.Microstructure` containing the collection of orientations to plot (None by default).
    :param lattice: the crystal :py:class:`~pymicro.crystal.lattice.Lattice`.

    .. warning::

       Any crystal structure is now supported (you have to set the proper 
       crystal lattice) but it has oly really be tested for cubic.

    :param str hkl: slip plane family ('111' by default)    
    :param str proj: projection type, can be either 'stereo' (default) or 'flat'
    :param int mksize: marker size in pts unit as displayed on the plots (12 by default)    
    :param bool verbose: verbose mode (False by default)
    :param bool color_by_grain_id: color the spot on the pole figure with grain color (False by default)
    :param bool pflegend: show the legend (only if color_by_grain_id is active, False by default)
    '''
    self.proj = proj
    self.axis = axis
    if microstructure:
      self.microstructure = microstructure
    else:
      self.microstructure = Microstructure()
    if lattice:
      self.lattice = lattice
    else:
      self.lattice = Lattice.cubic(1.0)
    self.set_hkl_poles(hkl)
    self.verbose = verbose
    self.mksize = 12
    self.color_by_grain_id = False
    self.pflegend = False
    self.x = np.array([1,0,0])
    self.y = np.array([0,1,0])
    self.z = np.array([0,0,1])
    
    # list all crystal directions
    self.c001s = np.array([[0,0,1],[0,1,0],[1,0,0]], dtype=np.float)
    self.c011s = np.array([[0,1,1],[1,0,1],[1,1,0],[0,-1,1],[-1,0,1],[-1,1,0]], dtype=np.float) / np.sqrt(2)
    self.c111s = np.array([[1,1,1],[-1,-1,1],[1,-1,1],[-1,1,1]], dtype=np.float) / np.sqrt(3)

  def set_hkl_poles(self, hkl):
    '''Set the pole list to plot.

    :params str hkl: slip plane family ('111' by default)
    '''
    self.family = hkl # keep a record of this
    planes = self.lattice.get_hkl_family(self.family)
    poles = []
    for p in planes:
      poles.append(p.normal())
    self.poles = poles
    
  def plot_pole_figures(self, plot_sst=True, display=True, save_as='pdf'):
    '''Plot and save a picture with both direct and inverse pole figures.
    
    :param bool plot_sst: controls wether to plot the full inverse pole \
    figure or only the standard stereographic triangle (True by default).
    :param bool display: display the plot if True, else save a picture \
    of the pole figures (True by default)
    :param str save_as: File format used to save the image such as pdf \
    or png ('pdf' by default)
    
    ::
    
      micro = Microstructure(name = 'AlLi_sam8')
      micro.grains.append(Grain(11, Orientation.from_euler(np.array([262.364, 16.836, 104.691]))))
      Al_fcc = Lattice.face_centered_cubic(0.405) # not really necessary since default lattice is cubic
      pf = PoleFigure(microstructure=micro, proj='stereo', lattice=Al_fcc, hkl='111')
      pf.mksize = 12
      pf.color_by_grain_id = True
      pf.pflegend = True # this works well for a few grains
      pf.plot_pole_figures()
    
    .. figure:: _static/AlLi_sam8_pole_figure.png
        :width: 750 px
        :height: 375 px
        :alt: AlLi_sam8_pole_figure
        :align: center

        A 111 pole figure plotted for a single crystal orientation.
    '''
    fig = plt.figure(figsize=(10,5))
    # direct PF
    ax1 = fig.add_subplot(121, aspect='equal')
    self.plot_pf(ax = ax1, mk='o', col='k', ann=False)
    # inverse PF
    ax2 = fig.add_subplot(122, aspect='equal')
    if plot_sst:
      self.plot_sst(ax = ax2)
    else:
      self.plot_ipf(ax = ax2)
    if display:
      plt.show()
    else:
      plt.savefig('%s_pole_figure.%s' % (self.microstructure.name, save_as) , format=save_as)

  def plot_crystal_dir(self, c_dir, mk='o', col='k', ax=None, ann=False, lab=''):
    '''Function to plot a crystal direction on a pole figure.
    
    :param c_dir: A vector describing the crystal direction.    
    :param mk: marker used to plot the pole (disc by default).
    :param col: color used to plot the pole (black by default).
    :param ax: a reference to a pyplot ax to draw the pole.
    :param bool ann: Annotate the pole with the coordinates of the vector if True (False by default).    
    :param str lab: Label to use in the legend of the plot ('' by default).
    :raise ValueError: if the projection type is not supported
    '''
    if c_dir[2] < 0: c_dir *= -1 # make unit vector have z>0
    if self.proj == 'flat':
      cp = c_dir
    elif self.proj == 'stereo':
      c = c_dir + self.z
      c /= c[2] # SP'/SP = r/z with r=1
      cp = c
      #cp = np.cross(c, self.z)
    else:
      raise ValueError('Error, unsupported projection type', proj)
    ax.plot(cp[0], cp[1], linewidth=0, markerfacecolor=col, marker=mk, \
      markersize=self.mksize, label=lab)
    # Next 3 lines are necessary in case c_dir[2]=0, as for Euler angles [45, 45, 0]
    if c_dir[2] < 0.000001:
      ax.plot(-cp[0], -cp[1], linewidth=0, markerfacecolor=col, marker=mk, \
        markersize=self.mksize, label=lab)
    if ann:
      ax.annotate(c_dir.view(), (cp[0], cp[1]-0.1), xycoords='data',
      fontsize=8, horizontalalignment='center', verticalalignment='center')

  def plot_line_between_crystal_dir(self, c1, c2, ax=None, steps=11, col='k'):
    '''Plot a curve between two crystal directions.

    The curve is actually composed of several straight lines segments to 
    draw from direction 1 to direction 2.

    :param c1: vector describing crystal direction 1
    :param c2: vector describing crystal direction 2
    :param ax: a reference to a pyplot ax to draw the line
    :param int: steps: number of straight lines composing the curve (11 by default)
    :param col: line color (black by default)
    '''
    path = np.zeros((steps, 2), dtype=float)
    for j, i in enumerate(np.linspace(0., 1., steps)):
      ci = i*c1 + (1-i)*c2
      ci /= np.linalg.norm(ci)
      if self.proj == 'stereo':
        ci += self.z
        ci /= ci[2]
      path[j, 0] = ci[0]
      path[j, 1] = ci[1]
    ax.plot(path[:, 0], path[:, 1], color=col, markersize=self.mksize, linewidth=2)

  def plot_pf_background(self, ax):
    '''Function to plot the background of the pole figure.
    
    :param ax: a reference to a pyplot ax to draw the backgroud.
    '''
    an = np.linspace(0,2*np.pi,100)
    plt.hold('on')
    ax.plot(np.cos(an), np.sin(an), 'k-')
    ax.plot([-1,1], [0,0], 'k-')
    ax.plot([0,0], [-1,1], 'k-')

  def plot_pf_dir(self, c_dir, ax=None, mk='o', col='k', ann=False, lab=''):
    '''Plot a crystal direction in a direct pole figure.'''
    if self.axis == 'Z':
      h = 0; v = 1; u = 2
    elif self.axis == 'Y':
      h = 0; v = 2; u = 1
    else:
      h = 1; v = 2; u = 0
	# the direction to plot is given by c_dir[h,v,u]
    if self.verbose: print 'corrected for pf axis:',c_dir[[h,v,u]]
    self.plot_crystal_dir(c_dir[[h,v,u]], mk=mk, col=col, ax=ax, ann=ann, lab=lab)
	  
  def plot_pf(self, ax=None, mk='o', col='k', ann=False):
    '''Create the direct pole figure. 
    
    :param ax: a reference to a pyplot ax to draw the poles.
    :param mk: marker used to plot the poles (disc by default).
    :param col: symbol color (black by default)
    :param bool ann: Annotate the pole with the coordinates of the vector if True (False by default).    
    '''
    axe_labels = ['X', 'Y', 'Z']
    if self.axis == 'Z':
      h = 0; v = 1; u = 2
    elif self.axis == 'Y':
      h = 0; v = 2; u = 1
    else:
      h = 1; v = 2; u = 0
    self.plot_pf_background(ax)
    ax.annotate(axe_labels[h], (1.01, 0.0), xycoords='data',
      fontsize=16, horizontalalignment='left', verticalalignment='center')
    ax.annotate(axe_labels[v], (0.0, 1.01), xycoords='data',
      fontsize=16, horizontalalignment='center', verticalalignment='bottom')
    for grain in self.microstructure.grains:
      B = grain.orientation_matrix()
      Bt = B.transpose()
      for i, c in enumerate(self.poles):
        label = ''
        c_rot = Bt.dot(c)
        if self.verbose: print 'plotting ',c,' in sample CS (corrected for pf axis):',c_rot
        if self.color_by_grain_id:
          col = Microstructure.rand_cmap().colors[grain.id]
          if self.pflegend and i == 0:
            # only add grain legend for its first pole
            label = 'grain ' + str(grain.id)
	self.plot_pf_dir(c_rot, mk=mk, col=col, ax=ax, ann=ann, lab=label)
    ax.axis([-1.1,1.1,-1.1,1.1])
    if self.pflegend and self.color_by_grain_id:
      ax.legend(bbox_to_anchor=(0.05, 1), loc=1, numpoints=1, \
        prop={'size':10})
    ax.axis('off')
    ax.set_title('{%s} direct %s projection' % (self.family, self.proj))

  def plot_pf_hot(self, strain_levels, ax=None, mk='o', col='k', ann=False, min_level = 0.015, max_level = 0.025):
    '''Create the direct pole figure, the poles are colored using a hot 
    colormap to display the strain level of each orientation. 

    :param dict strain_level: a dictionnary containing each strain level \
    for each grain id in the :py:class:`~pymicro.crystal.microstructure.Microstructure` associated with this pole figure.
    :param ax: a reference to a pyplot ax to draw the poles.
    :param mk: marker used to plot the poles (disc by default).
    :param col: symbol color (black by default)
    :param bool ann: Annotate the pole with the coordinates of the vector if True (False by default).    
    :param float min_level: minimum strain level to use in the colormap.
    :param float max_level: maximum strain level to use in the colormap.
    '''
    axe_labels = ['X', 'Y', 'Z']
    if self.axis == 'Z':
      h = 0; v = 1; u = 2
    elif self.axis == 'Y':
      h = 0; v = 2; u = 1
    else:
      h = 1; v = 2; u = 0
    self.plot_pf_background(ax)
    ax.annotate(axe_labels[h], (1.01, 0.0), xycoords='data',
      fontsize=16, horizontalalignment='left', verticalalignment='center')
    ax.annotate(axe_labels[v], (0.0, 1.01), xycoords='data',
      fontsize=16, horizontalalignment='center', verticalalignment='bottom')
    for grain in self.microstructure.grains:
      B = grain.orientation_matrix()
      Bt = B.transpose()
      for i, c in enumerate(self.poles):
        label = ''
        c_rot = Bt.dot(c)
        if self.verbose: print 'plotting ',c,' in sample CS (corrected for pf axis):',c_rot
        if self.color_by_strain_level:
          strain_level = strain_levels[grain.id]
          color = int(256*(strain_level-min_level)/float(max_level-min_level))
          col = self.lut[color][1:4]
        self.plot_pf_dir(c_rot, mk=mk, col=col, ax=ax, ann=ann, lab=label)
    ax.axis([-1.1,1.1,-1.1,1.1])
    if self.pflegend and self.color_by_grain_id:
      ax.legend(bbox_to_anchor=(0.05, 1), loc=1, numpoints=1, \
        prop={'size':10})
    ax.axis('off')
    ax.set_title('{%s} direct %s projection' % (self.family, self.proj))

  def sst_symmetry_cubic(self, z_rot):
    '''Perform cubic symmetry according to the unit SST triangle.
    '''
    if z_rot[0] < 0: z_rot[0] = -z_rot[0]
    if z_rot[1] < 0: z_rot[1] = -z_rot[1]
    if z_rot[2] < 0: z_rot[2] = -z_rot[2]

    if (z_rot[2] > z_rot[1]):
      z_rot[1], z_rot[2] = z_rot[2], z_rot[1]
    
    if (z_rot[1] > z_rot[0]):
      z_rot[0], z_rot[1] = z_rot[1], z_rot[0]
      
    if (z_rot[2] > z_rot[1]):
	  z_rot[1], z_rot[2] = z_rot[2], z_rot[1]
      
    return [z_rot[1], z_rot[2], z_rot[0]]
    
  def plot_sst(self, ax=None, mk='s', col='k', ann=False):
    ''' Create the inverse pole figure in the unit standard triangle. 
    '''
    c001 = np.array([0,0,1])
    c101 = np.array([1,0,1])
    c111 = np.array([1,1,1])
    self.plot_line_between_crystal_dir(c001, c101, ax=ax)
    self.plot_line_between_crystal_dir(c001, c111, ax=ax)
    self.plot_line_between_crystal_dir(c101, c111, ax=ax)
    # now plot the sample axis
    for grain in self.microstructure.grains:
      B = grain.orientation_matrix()
      # compute axis and apply SST symmetry
      if self.axis == 'Z':
        axis = self.z
      elif self.axis == 'Y':
        axis = self.y
      else:
        axis = self.x
      axis_rot = self.sst_symmetry_cubic(B.dot(axis))
      self.plot_crystal_dir(axis_rot, mk=mk, col=col, ax=ax, ann=ann)
      if self.verbose: print 'plotting ',self.axis,' in crystal CS:',axis_rot
    ax.axis('off')
    ax.axis([-0.05,0.45,-0.05,0.40])
    ax.set_title('%s-axis SST inverse %s projection' % (self.axis, self.proj))
    
  def plot_ipf(self, ax=None, mk='s', col='k', ann=False):
    ''' Create the inverse pole figure for direction Z. 
    
    Parameters:
    
    **ax**: a reference to a pyplot ax to draw the figure
    
    **mk**: marker type (square by default)
    
    **col**: marker color (red by default)
    
    **ann**: draw annotation near the crystal direction (False by default)
    '''
    self.plot_pf_background(ax)
    for c in self.c111s:
      for i in range(3):
        d = c.copy(); d[i] = 0
        e = np.zeros_like(c); e[i] = c[i]
        self.plot_line_between_crystal_dir(c, d, ax=ax)
        self.plot_line_between_crystal_dir(c, e, ax=ax)
    markers = ['s', 'o', '^']
    for i, dirs in enumerate([self.c001s, self.c011s, self.c111s]):
      [self.plot_crystal_dir(c, mk=markers[i], col='k', ax=ax, ann=False) for c in dirs]
      # also plot the negative direction of those lying in the plane z==0
      for c in dirs:
        if np.dot(c,self.z) == 0.0:
          self.plot_crystal_dir(-c, mk=markers[i], col='k', ax=ax, ann=False)
    # now plot the sample axis
    for grain in self.microstructure.grains:
      B = grain.orientation_matrix()
      if self.axis == 'Z':
        axis = self.z
      elif self.axis == 'Y':
        axis = self.y
      else:
        axis = self.x
      axis_rot = B.dot(axis)
      if self.color_by_grain_id:
        col = Microstructure.rand_cmap().colors[grain.id]
      self.plot_crystal_dir(axis_rot, mk=mk, col=col, ax=ax, ann=ann)
      if self.verbose: print 'plotting ',self.axis,' in crystal CS:',axis_rot
    ax.axis([-1.1,1.1,-1.1,1.1])
    ax.axis('off')
    ax.set_title('%s-axis inverse %s projection' % (self.axis, self.proj))

  @staticmethod
  def plot(orientation):
    '''Plot a pole figure (both direct and inverse) for a single orientation.

    Parameters:
    
    **orientation**: the crystalline `Orientation` to plot.
    '''
    micro = Microstructure()
    micro.grains.append(Grain(1, orientation))
    pf = PoleFigure(microstructure=micro)
    pf.plot_pole_figures(display=True)

  @staticmethod
  def plot_euler(phi1, Phi, phi2):
    '''Directly plot a pole figure for a single orientation given its 
    three Euler angles.

    ::
    
      PoleFigure.plot_euler(10, 20, 30)

    Parameters:
    
    **phi1**: first Euler angle.
    
    **Phi**: second Euler angle.
    
    **phi2**: third Euler angle.
    '''
    PoleFigure.plot(Orientation.from_euler(np.array([phi1, Phi, phi2])))
    
