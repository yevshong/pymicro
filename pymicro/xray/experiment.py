import json
from json import JSONEncoder
import numpy as np
from pymicro.xray.detectors import Detector2d, RegArrayDetector2d
from pymicro.crystal.lattice import Lattice, Symmetry
from pymicro.crystal.microstructure import Microstructure, Grain, Orientation


class ForwardSimulation:
    """Class to represent a Forward Simulation."""

    def __init__(self, sim_type, verbose=False):
        self.sim_type = sim_type
        self.verbose = verbose
        self.exp = Experiment()

    def set_experiment(self, experiment):
        """Attach an X-ray experiment to this simulation."""
        self.exp = experiment


class XraySource:
    """Class to represent a X-ray source."""

    def __init__(self, position=None):
        self.set_position(position)
        self._min_energy = None
        self._max_energy = None

    def set_position(self, position):
        if position is None:
            position = (0., 0., 0.)
        self.position = np.array(position)

    @property
    def min_energy(self):
        return self._min_energy

    @property
    def max_energy(self):
        return self._max_energy

    def set_min_energy(self, min_energy):
        self._min_energy = min_energy

    def set_max_energy(self, max_energy):
        self._max_energy = max_energy

    def set_energy(self, energy):
        """Set the energy (monochromatic case)."""
        self.set_min_energy(energy)
        self.set_max_energy(energy)

    def set_energy_range(self, min_energy, max_energy):
        if min_energy < 0:
            print('specified min energy must be positive, using 0 keV')
            min_energy = 0.
        if max_energy <= min_energy:
            print('specified max energy must be larger than min energy, using %.1f' % min_energy)
        self.set_min_energy(min_energy)
        self.set_max_energy(max_energy)


class SlitsGeometry:
    """Class to represent the geometry of a 4 blades slits."""

    def __init__(self, position=None):
        self.set_position(position)  # central position of the aperture (On Xu direction)
        self.hgap = None  # horizontal opening
        self.vgap = None  # vertical opening

    def set_position(self, position):
        if position is None:
            position = (0., 0., 0.)
        self.position = np.array(position)


class ObjectGeometry:
    """Class to represent any object geometry.
    
    The geometry may have multiple form, including just a point, a regular 3D array or it may be described by a CAD 
    file using the STL format. The array represents the material microstructure using the grain ids and should be set 
    in accordance with an associated  Microstructure instance. In this case, zero represent a non crystalline region.
    """

    def __init__(self, geo_type='point', origin=None):
        self.set_type(geo_type)
        self.set_origin(origin)
        # the positions are initially set at the origin, this is a lazy behaviour as discretizing the volume can be expensive
        self.positions = np.array(self.origin)
        self.array = np.ones((1, 1, 1), dtype=np.uint8)  # unique label set to 1
        self.size = np.array([0., 0., 0.])

    def set_type(self, geo_type):
        assert (geo_type in ['point', 'array', 'cad']) is True
        self.geo_type = geo_type

    def set_origin(self, origin):
        if origin is None:
            origin = (0., 0., 0.)
        self.origin = np.array(origin)

    def get_bounding_box(self):
        if self.geo_type in ['point', 'array']:
            return self.origin - self.size / 2, self.origin + self.size / 2
        elif self.geo_type == 'cad':
            bounds = self.cad.GetBounds()
            return (bounds[0], bounds[2], bounds[4]), (bounds[1], bounds[3], bounds[5])

    def get_positions(self):
        return self.positions

    def discretize_geometry(self):
        if self.geo_type == 'point':
            self.positions = np.array(self.origin)
        elif self.geo_type == 'array':
            vx, vy, vz = self.array.shape  # number of voxels
            x_sample = np.linspace(self.get_bounding_box()[0][0], self.get_bounding_box()[1][0], vx)  # mm
            y_sample = np.linspace(self.get_bounding_box()[0][1], self.get_bounding_box()[1][1], vy)  # mm
            z_sample = np.linspace(self.get_bounding_box()[0][2], self.get_bounding_box()[1][2], vz)  # mm
            xx, yy, zz = np.meshgrid(x_sample, y_sample, z_sample, indexing='ij')
            self.positions = np.empty((vx, vy, vz, 3), dtype=float)
            self.positions[:, :, :, 0] = xx
            self.positions[:, :, :, 1] = yy
            self.positions[:, :, :, 2] = zz
        elif self.geo_type == 'cad':
            print('discretizing CAD geometry is not yet supported')
            self.positions = np.array(self.origin)


class Sample:
    """Class to describe a material sample.
    
    A sample is made by a given material (that may have multiple phases), has a name and a position in the experimental 
    local frame. A sample also has a geometry (just a point by default), that may be used to discretize the volume 
    in space or display it in 3D.
    
    .. note::

      For the moment, the material is simply a crystal lattice.
    """

    def __init__(self, name=None, position=None, geo=None, material=None, microstructure=None):
        self.name = name
        self.data_dir = '.'
        self.set_position(position)
        self.set_geometry(geo)
        self.set_material(material)
        self.set_microstructure(microstructure)
        self.grain_ids_path = None

    def set_name(self, name):
        """Set the sample name.
        
        :param str name: The sample name.
        """
        self.name = name

    def set_position(self, position):
        """Set the sample reference position.

        :param tuple position: A vector (tuple or array form) describing the sample position.
        """
        if position is None:
            position = (0., 0., 0.)
        self.position = np.array(position)

    def set_geometry(self, geo):
        """Set the geometry of this sample.

        :param ObjectGeometry geo: A vector (tuple or array form) describing the sample position.
        """
        if geo is None:
            geo = ObjectGeometry()
        assert isinstance(geo, ObjectGeometry) is True
        self.geo = geo

    def get_material(self):
        return self.material

    def set_material(self, material):
        if material is None:
            material = Lattice.cubic(1.0)
        self.material = material

    def get_microstructure(self):
        return self.microstructure

    def set_microstructure(self, microstructure):
        if microstructure is None:
            microstructure = Microstructure()
        self.microstructure = microstructure

    def has_grains(self):
        """Method to see if a sample has at least one grain in the microstructure.
        
        :return: True if the sample has at east one grain, False otherwise."""
        return len(self.microstructure.grains) > 0

    def get_grain_ids(self):
        if not hasattr(self, 'grain_ids'):
            # try to load grain map
            #try:
            import h5py
            import os
            full_path = os.path.join(self.data_dir, self.grain_ids_path)
            print('loading grain_ids field from %s' % full_path)
            f = h5py.File(full_path)
            print('successfully loaded grain_ids with shape {}'.format(f['vol'].shape))
            self.grain_ids = f['vol'][()].transpose(2, 1, 0)  # now we have [x, y, z] representation just like matlab
            f.close()
            #except AttributeError:
            #    print('failed to load grain_ids, please set the grain_ids path for this sample')
        return self.grain_ids

class Experiment:
    """Class to represent an actual or a virtual X-ray experiment.
    
    A cartesian coordinate system (X, Y, Z) is associated with the experiment. By default X is the direction of X-rays 
    and the sample is placed at the origin (0, 0, 0).
    """

    def __init__(self):
        self.source = XraySource()
        self.sample = Sample(name='dummy')
        self.slits = SlitsGeometry()
        self.detectors = []
        self.active_detector_id = -1

    def set_sample(self, sample):
        assert isinstance(sample, Sample) is True
        self.sample = sample

    def get_sample(self):
        return self.sample

    def set_source(self, source):
        assert isinstance(source, XraySource) is True
        self.source = source

    def get_source(self):
        return self.source

    def set_slits(self, slits):
        assert isinstance(slits, SlitsGeometry) is True
        self.slits = slits

    def get_slits(self):
        return self.slits

    def add_detector(self, detector, set_as_active=True):
        """Add a detector to this experiment.
        
        If this is the first detector, the active detector id is set accordingly.

        :param Detector2d detector: an instance of the Detector2d class.
        :param bool set_as_active: set this detector as active.
        """
        assert isinstance(detector, Detector2d) is True
        self.detectors.append(detector)
        if set_as_active:
            self.active_detector_id = self.get_number_of_detectors() - 1

    def get_number_of_detectors(self):
        """Return the number of detector for this experiment."""
        return len(self.detectors)

    def get_active_detector(self):
        """Return the active detector for this experiment."""
        return self.detectors[self.active_detector_id]
    
    def forward_simulation(self, fs, set_result_to_detector=True):
        """Perform a forward simulation of the X-ray experiment onto the active detector.
        
        This typically sets the detector.data field with the computed image.

        :param bool set_result_to_detector: if True, the result is assigned to the current detector.
        :param fs: An instance of `ForwardSimulation` or its derived class.
        """
        if fs.sim_type == 'laue':
            fs.set_experiment(self)
            result = fs.fsim()
        elif fs.sim_type == 'dct':
            fs.set_experiment(self)
            result = fs.dct_projection()
        else:
            print('wrong type of simulation: %s' % fs.sim_type)
            return None
        if set_result_to_detector:
            self.get_active_detector().data = result
        return result

    def save(self, file_path='experiment.txt'):
        """Export the parameters to describe the current experiment to a file using json."""
        dict_exp = {}
        dict_exp['Source'] = self.source
        dict_exp['Sample'] = self.sample
        dict_exp['Detectors'] = self.detectors
        dict_exp['Active Detector Id'] = self.active_detector_id
        # save to file using json
        json_txt = json.dumps(dict_exp, indent=4, cls=ExperimentEncoder)
        with open(file_path, 'w') as f:
            f.write(json_txt)

    @staticmethod
    def load(file_path='experiment.txt'):
        with open(file_path, 'r') as f:
            dict_exp = json.load(f)
        sample = Sample()
        sample.set_name(dict_exp['Sample']['Name'])
        sample.data_dir = dict_exp['Sample']['Data Dir']
        sample.set_position(dict_exp['Sample']['Position'])
        if 'Geometry' in dict_exp['Sample']:
            sample_geo = ObjectGeometry()
            sample_geo.set_type(dict_exp['Sample']['Geometry']['Type'])
            sample.set_geometry(sample_geo)
        if 'Material' in dict_exp['Sample']:
            a, b, c = dict_exp['Sample']['Material']['Lengths']
            alpha, beta, gamma = dict_exp['Sample']['Material']['Angles']
            centering = dict_exp['Sample']['Material']['Centering']
            symmetry = Symmetry.from_string(dict_exp['Sample']['Material']['Symmetry'])
            material = Lattice.from_parameters(a, b, c, alpha, beta, gamma, centering=centering, symmetry=symmetry)
            sample.set_material(material)
        if 'Microstructure' in dict_exp['Sample']:
            micro = Microstructure(dict_exp['Sample']['Microstructure']['Name'])
            for i in range(len(dict_exp['Sample']['Microstructure']['Grains'])):
                dict_grain = dict_exp['Sample']['Microstructure']['Grains'][i]
                grain = Grain(dict_grain['Id'], Orientation.from_euler(dict_grain['Orientation']['Euler Angles (degrees)']))
                grain.position = np.array(dict_grain['Position'])
                grain.volume = dict_grain['Volume']
                grain.hkl_planes = dict_grain['hkl_planes']
                micro.grains.append(grain)
            sample.set_microstructure(micro)
        # lazy behaviour, we load only the grain_ids path, the actual array is loaded in memory if needed
        sample.grain_ids_path = dict_exp['Sample']['Grain Ids Path']
        exp = Experiment()
        exp.set_sample(sample)
        source = XraySource()
        source.set_position(dict_exp['Source']['Position'])
        if 'Min Energy (keV)' in dict_exp['Source']:
            source.set_min_energy(dict_exp['Source']['Min Energy (keV)'])
        if 'Max Energy (keV)' in dict_exp['Source']:
            source.set_max_energy(dict_exp['Source']['Max Energy (keV)'])
        exp.set_source(source)
        for i in range(len(dict_exp['Detectors'])):
            dict_det = dict_exp['Detectors'][i]
            if dict_det['Class'] == 'Detector2d':
                det = Detector2d(size=dict_det['Size (pixels)'])
                det.ref_pos = dict_det['Reference Position (mm)']
            if dict_det['Class'] == 'RegArrayDetector2d':
                det = RegArrayDetector2d(size=dict_det['Size (pixels)'])
                det.pixel_size = dict_det['Pixel Size (mm)']
                det.ref_pos = dict_det['Reference Position (mm)']
                if 'Min Energy (keV)' in dict_exp['Detectors']:
                    det.tilt = dict_det['Tilts (deg)']
                if 'Binning' in dict_det:
                    det.set_binning(dict_det['Binning'])
                det.u_dir = np.array(dict_det['u_dir'])
                det.v_dir = np.array(dict_det['v_dir'])
                det.w_dir = np.array(dict_det['w_dir'])
            exp.add_detector(det)
        return exp


class ExperimentEncoder(json.JSONEncoder):

    def default(self, o):
        if isinstance(o, ObjectGeometry):
            dict_geo = {}
            dict_geo['Type'] = o.geo_type
            return dict_geo
        if isinstance(o, Lattice):
            dict_lattice = {}
            dict_lattice['Angles'] = o._angles.tolist()
            dict_lattice['Lengths'] = o._lengths.tolist()
            dict_lattice['Centering'] = o._centering
            dict_lattice['Symmetry'] = o._symmetry.to_string()
            return dict_lattice
        if isinstance(o, Sample):
            dict_sample = {}
            dict_sample['Name'] = o.name
            dict_sample['Data Dir'] = o.data_dir
            dict_sample['Position'] = o.position.tolist()
            dict_sample['Geometry'] = o.geo
            dict_sample['Material'] = o.material
            dict_sample['Microstructure'] = o.microstructure
            dict_sample['Grain Ids Path'] = o.grain_ids_path
            return dict_sample
        if isinstance(o, RegArrayDetector2d):
            dict_det = {}
            dict_det['Class'] = o.__class__.__name__
            dict_det['Size (pixels)'] = o.size
            dict_det['Pixel Size (mm)'] = o.pixel_size
            dict_det['Data Type'] = str(o.data_type)
            dict_det['Reference Position (mm)'] = o.ref_pos.tolist()
            dict_det['Binning'] = o.binning
            dict_det['u_dir'] = o.u_dir.tolist()
            dict_det['v_dir'] = o.v_dir.tolist()
            dict_det['w_dir'] = o.w_dir.tolist()
            return dict_det
        if isinstance(o, Detector2d):
            dict_det = {}
            dict_det['Class'] = o.__class__.__name__
            dict_det['Size (pixels)'] = o.size
            dict_det['Data Type'] = o.data_type
            dict_det['Reference Position (mm)'] = o.ref_pos.tolist()
            return dict_det
        if isinstance(o, XraySource):
            dict_source = {}
            dict_source['Position'] = o.position.tolist()
            if o.min_energy is not None:
                dict_source['Min Energy (keV)'] = o.min_energy
            if o.max_energy is not None:
                dict_source['Max Energy (keV)'] = o.max_energy
            return dict_source
        if isinstance(o, Microstructure):
            dict_micro = {}
            dict_micro['Name'] = o.name
            dict_micro['Grains'] = o.grains
            return dict_micro
        if isinstance(o, Grain):
            dict_grain = {}
            dict_grain['Id'] = o.id
            dict_grain['Position'] = o.position.tolist()
            dict_grain['Orientation'] = o.orientation
            dict_grain['Volume'] = o.volume
            if hasattr(o, 'hkl_planes'):
                dict_grain['hkl_planes'] = o.hkl_planes
            return dict_grain
        if isinstance(o, Orientation):
            dict_orientation = {}
            dict_orientation['Euler Angles (degrees)'] = o.euler.tolist()
            return dict_orientation



