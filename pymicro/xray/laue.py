import numpy as np
from pymicro.crystal.lattice import HklPlane, Lattice
from pymicro.crystal.microstructure import Orientation
from pymicro.xray.xray_utils import *
from pymicro.xray.dct import add_to_image


def select_lambda(hkl, orientation, Xu=np.array([1., 0., 0.]), verbose=False):
    """
    Compute the wavelength corresponding to the first order reflection
    of a given lattice plane in the specified orientation.

    :param hkl: The given lattice plane.
    :param orientation: The orientation of the crystal lattice.
    :param Xu: The unit vector of the incident X-ray beam (default along the X-axis).
    :param bool verbose: activate verbose mode (default False).
    :returns tuple: A tuple of the wavelength value (keV) and the corresponding Bragg angle (radian).
    """
    (h, k, l) = hkl.miller_indices()
    d_hkl = hkl.interplanar_spacing()
    Gc = hkl.scattering_vector()
    gt = orientation.orientation_matrix().transpose()
    Gs = gt.dot(Gc)
    # compute the theta angle between X and the scattering vector which is theta + pi/2
    theta = np.arccos(np.dot(Xu, Gs / np.linalg.norm(Gs))) - np.pi / 2
    # find the lambda selected by this hkl plane
    the_energy = lambda_nm_to_keV(2 * d_hkl * np.sin(theta))
    if verbose:
        print('\n** Looking at plane %d%d%d **' % (h, k, l))
        print('scattering vector in laboratory CS', Gs)
        print('glancing angle between incident beam and the hkl plane is %.1f deg' % (theta * 180 / np.pi))
        print('corresponding energy is %.1f keV' % the_energy)
    return the_energy, theta


def build_list(lattice=None, max_miller=3, extinction=None):
    hklplanes = []
    indices = range(-max_miller, max_miller + 1)
    for h in indices:
        for k in indices:
            for l in indices:
                if h == k == l == 0:  # skip (0, 0, 0)
                    continue
                if not extinction :
                    hklplanes.append(HklPlane(h, k, l, lattice))
                if extinction == 'FCC':
                    # take plane if only all odd or all even hkl indices
                    if (h % 2 == 0 and k % 2 == 0 and l % 2 == 0) or (h % 2 == 1 and k % 2 == 1 and l % 2 == 1):
                        hklplanes.append(HklPlane(h, k, l, lattice))
                if extinction == 'BCC':
                    # take plane only if the sum indices is even
                    if ((h**2 + k**2 + l**2) % 2 == 0):
                        hklplanes.append(HklPlane(h, k, l, lattice))
    return hklplanes


def compute_ellipsis(orientation, detector, uvw, Xu=[1., 0., 0.], n=101, verbose=False):
    """
    Compute the ellipsis associated with the given zone axis. 
    
    The detector is supposed to be normal to the X-axis, but the incident wave vector can be specified.
    All lattice planes sharing this zone axis will diffract along that ellipse.

    :param orientation: The crystal orientation.
    :param detector: An instance of the Detector2D class.
    :param uvw: An instance of the HklDirection representing the zone axis.
    :param Xu: The unit vector of the incident X-ray beam (default along the X-axis).
    :param int n: number of poits used to define the ellipse.
    :param bool verbose: activate verbose mode (default False).
    :returns data: the (Y, Z) data (in mm unit) representing the ellipsis.
    """
    gt = orientation.orientation_matrix().transpose()
    za = gt.dot(uvw.direction())  # zone axis unit vector in lab frame
    OA = detector.project_along_direction(za)  # vector from the origin to projection of the zone axis onto the detector
    OC = detector.project_along_direction(Xu)  # C is the intersection of the direct beam with the detector
    ON = detector.project_along_direction(detector.w_dir)  # N is the intersection of the X-axis with the detector plane
    CA = OA - OC
    NA = OA - ON
    from math import cos, sin, tan, atan2, pi
    # psi = np.arccos(np.dot(ZAD/np.linalg.norm(ZAD), Xu))
    psi = atan2(np.linalg.norm(np.cross(za, Xu)), np.dot(za, Xu))  # use cross product instead of arccos
    nu = atan2(np.linalg.norm(np.cross(za, detector.w_dir)), np.dot(za, detector.w_dir))
    e = np.sin(nu) / np.cos(psi)  # ellipis excentricity (general case), e reduces to tan(psi) when the incident beam is normal to the detector (nu = psi)
    '''
    The major axis direction is given by the intersection of the plane defined by ON and OA and by the detector 
    plane. It does not depends on Xu, like the cone angle. If the detector is perpendicular to the X-axis, 
    this direction is given by NA. both N and A are located on the major axis.
    '''
    eta = pi / 2 - atan2(NA[1],
                         NA[2])  # atan2(y, x) compute the arc tangent of y/x considering the sign of both y and x
    (uc, vc) = (detector.ucen - OA[1] / detector.pixel_size, detector.vcen - OA[2] / detector.pixel_size)
    '''
    # wrong formulae from Amoros (The Laue Method)...
    a = ON * np.tan(psi)
    b = ON * np.sin(psi)
    # the proper equation for normal incidence are (Cruickshank 1991):
    a = abs(0.5 * ON * np.tan(2 * psi))
    b = abs(0.5 * ON * np.tan(2 * psi) * np.sqrt(1 - np.tan(psi) ** 2))
    this equation does not hold if the incident beam is not normal with the detector !
    the general equation is:
    2.a / ON = tan(nu) + tan(psi - nu) + sin(psi) / (cos(nu) * cos(psi + nu))
    this reduces when nu = psi to 2.a / ON = np.tan(2.psi)
    '''
    factor = tan(nu) + tan(psi - nu) + sin(psi) / (cos(nu) * cos(psi + nu))
    a = 0.5 * np.linalg.norm(ON) * factor
    #a = abs(0.5 * np.linalg.norm(ON) * np.tan(2 * psi))
    b = a * np.sqrt(1 - e ** 2)
    if verbose:
        print('angle nu (deg) is %.1f' % (nu * 180 / np.pi))
        print('angle psi (deg) is %.1f' % (psi * 180 / np.pi))
        print('angle eta (deg) is %.1f' % (eta * 180 / np.pi))
        print('direct beam crosses the det plane at %s' % OC)
        print('zone axis crosses the det plane at %s' % OA)
        print('zone axis crosses the detector at (%.3f,%.3f) mm or (%d,%d) pixels' % (OA[1], OA[2], uc, vc))
        print('ellipse eccentricity is %f' % e)
        print('ellipsis major and minor half axes are a=%.1f and b=%.1f' % (a, b))
    # use a parametric curve to plot the ellipsis
    t = np.linspace(0., 2 * np.pi, n)
    x = a * np.cos(t)
    y = b * np.sin(t)
    data = np.array([x, y])
    # rotate the ellipse
    R = np.array([[np.cos(eta), -np.sin(eta)], [np.sin(eta), np.cos(eta)]])
    data = np.dot(R, data)  # rotate our ellipse
    # move one end of the great axis to the direct beam position
    '''
    NB: in the general case, point C (intersection of the direct beam and the detector) is on the ellipse 
    but not lying on the great axis. Point A and N still lie on the major axis, so the translation can be determined. 
    '''
    NX = np.linalg.norm(ON) * tan(psi - nu)
    print('****************** NX = %.1f' % NX)
    data[0] += (a - NX) * np.cos(eta)
    data[1] += (a - NX) * np.sin(eta)
    #data[0] += ON[1] + a * np.cos(eta)
    #data[1] += ON[2] + a * np.sin(eta)
    yz_data = np.empty((n, 2), dtype=float)
    for i in range(n):
        yz_data[i, 0] = data[0, i]
        yz_data[i, 1] = data[1, i]
    return yz_data


def diffracted_vector(hkl, orientation, Xu=[1., 0., 0.], min_theta=0.1, verbose=False):
    """Compute the diffraction vector for a given reflection of a crystal.

    This method compute the diffraction vector.
    The incident wave vector is along the X axis by default but can be changed by specifying any unit vector.

    :param hkl: an instance of the `HklPlane` class.
    :param orientation: an instance of the `Orientation` class.
    :param Xu: The unit vector of the incident X-ray beam (default along the X-axis).
    :param float min_theta: the minimum considered Bragg angle (in radian).
    :param bool verbose: a flag to activate verbose mode.
    :return: the diffraction vector as a numpy array.
    """
    gt = orientation.orientation_matrix().transpose()
    (h, k, l) = hkl.miller_indices()
    # this hkl plane will select a particular lambda
    (the_energy, theta) = select_lambda(hkl, orientation, Xu=Xu, verbose=verbose)
    if abs(theta) < min_theta * np.pi / 180:  # skip angles < min_theta deg
        return None
    lambda_nm = 1.2398 / the_energy
    X = np.array(Xu) / lambda_nm
    Gs = gt.dot(hkl.scattering_vector())
    if verbose:
        print('bragg angle for %d%d%d reflection is %.1f' % (h, k, l, hkl.bragg_angle(the_energy) * 180 / np.pi))
    assert (abs(theta - hkl.bragg_angle(the_energy)) < 1e-6)  # verify than theta_bragg is equal to the glancing angle
    # compute diffracted direction
    K = X + Gs
    return K


def diffracted_intensity(hkl, I0=1.0, symbol='Ni', verbose=False):
    '''Compute the diffracted intensity.
    
    This compute a number representing the diffracted intensity within the kinematical approximation. 
    This number includes many correction factors:
    
     * atomic factor
     * structural factor
     * polarisation factor
     * Debye-Waller factor
     * absorption factor
     * ...
    
    :param HklPlane hkl: the hkl Bragg reflection.
    :param float I0: intensity of the incident beam.
    :param str symbol: string representing the considered lattice.
    :param bool verbose: flag to activate verbose mode.
    :return: the diffracted intensity.
    :rtype: float.
    '''
    # TODO find a way to load the atom scattering data from the lattice... and not load it for every reflection!
    path = os.path.dirname(__file__)
    scat_data = np.genfromtxt(os.path.join(path, 'data', '%s_atom_scattering.txt' % symbol))
    # scale the intensity with the atomic scattering factor
    q = 1 / (2 * hkl.interplanar_spacing())
    try:
        index = (scat_data[:, 0] < q).tolist().index(False)
    except ValueError:
        index = -1
    fa = scat_data[index, 1] / scat_data[0, 1]  # should we normalize with respect to Z?

    I = I0 * fa

    if verbose:
        print('q=%f in nm^-1 -> fa=%.3f' % (q, fa))
        print('intensity:', I)
    return I


def compute_Laue_pattern(orientation, detector, hkl_planes=None, Xu=np.array([1., 0., 0.]), spectrum=None, spectrum_thr=0.,
                         r_spot=5, color_field='constant', inverted=False, show_direct_beam=False, verbose=False):
    '''
    Compute a transmission Laue pattern. The data array of the given
    `Detector2d` instance is initialized with the result.
    
    The incident beam is assumed to be along the X axis: (1, 0, 0) but can be changed to any direction. 
    The crystal can have any orientation using an instance of the `Orientation` class. 
    The `Detector2d` instance holds all the geometry (detector size and position).

    A parameter controls the meaning of the values in the diffraction spots in the image. It can be just a constant 
    value, the diffracted beam energy (in keV) or the intensity as computed by the :py:meth:`diffracted_intensity` 
    method.

    :param orientation: The crystal orientation.
    :param detector: An instance of the Detector2d class.
    :param list hkl_planes: A list of the lattice planes to include in the pattern.
    :param Xu: The unit vector of the incident X-ray beam (default along the X-axis).
    :param spectrum: A two columns array of the spectrum to use for the calculation.
    :param float spectrum_thr: The threshold to use to determine if a wave length is contributing or not.
    :param int r_spot: Size of the spots on the detector in pixel (5 by default)
    :param str color_field: a traing describing, must be 'constant', 'energy' or 'intensity'
    :param bool inverted: A flag to control if the pattern needs to be inverted.
    :param bool show_direct_beam: A flag to control if the direct beam is shown.
    :param bool verbose: activate verbose mode (False by default).
    :returns: the computed pattern as a numpy array.
    '''
    detector.data = np.zeros(detector.size, dtype=np.float32)
    # create a small square image for one spot
    spot = np.ones((2 * r_spot + 1, 2 * r_spot + 1), dtype=np.uint8)
    max_val = np.iinfo(np.uint8).max  # 255 here
    if show_direct_beam:
        add_to_image(detector.data, max_val * 3 * spot, (detector.ucen, detector.vcen))

    if spectrum is not None:
        print('using spectrum')
        #indices = np.argwhere(spectrum[:, 1] > spectrum_thr)
        E_min = min(spectrum) #float(spectrum[indices[0], 0])
        E_max = max(spectrum) #float(spectrum[indices[-1], 0])
        lambda_min = lambda_keV_to_nm(E_max)
        lambda_max = lambda_keV_to_nm(E_min)
        #if verbose:
        print('energy bounds: [{0:.1f}, {1:.1f}] keV'.format(E_min, E_max))

    for hkl in hkl_planes:
        (the_energy, theta) = select_lambda(hkl, orientation, Xu=Xu, verbose=False)
        if spectrum is not None:
            if abs(the_energy) < E_min or abs(the_energy) > E_max:
                #print('skipping reflection {0:s} which would diffract at {1:.1f}'.format(hkl.miller_indices(), abs(the_energy)))
                continue
                #print('including reflection {0:s} which will diffract at {1:.1f}'.format(hkl.miller_indices(), abs(the_energy)))
        K = diffracted_vector(hkl, orientation, Xu=Xu)
        if K is None or np.dot([1., 0., 0.], K) == 0:
            continue  # skip diffraction // to the detector

        R = detector.project_along_direction(K, origin=[0., 0., 0.])
        (u, v) = detector.lab_to_pixel(R)
        if verbose and u >= 0 and u < detector.size[0] and v >= 0 and v < detector.size[1]:
            print('* %d%d%d reflexion' % hkl.miller_indices())
            print('diffracted beam will hit the detector at (%.3f, %.3f) mm or (%d, %d) pixels' % (R[1], R[2], u, v))
            print('diffracted beam energy is {0:.1f} keV'.format(abs(the_energy)))
            print('Bragg angle is {0:.2f} deg'.format(abs(theta * 180 / np.pi)))
        # mark corresponding pixels on the image detector
        if color_field == 'constant':
            add_to_image(detector.data, max_val * spot, (u, v))
        elif color_field == 'energy':
            add_to_image(detector.data, abs(the_energy) * spot.astype(float), (u, v))
        elif color_field == 'intensity':
            I = diffracted_intensity(hkl, I0=max_val, verbose=verbose)
            add_to_image(detector.data, I * spot, (u, v))
        else:
            raise ValueError('unsupported color_field: %s' % color_field)
    if inverted:
        # np.invert works only with integer types
        print('casting to uint8 and inverting image')
        # limit maximum to max_val (255) and convert to uint8
        over = detector.data > 255
        detector.data[over] = 255
        detector.data = detector.data.astype(np.uint8)
        detector.data = np.invert(detector.data)
    return detector.data


def gnomonic_projection_point(data):
    """compute the gnomonic projection of a given point or series of points.

    This methods assumes the incident X-ray beam is along (1, 0, 0). This could be extended to any incident direction. 
    The points coordinates are passed along with a single array which must be of size (n, 3) where n is the number of 
    points. If a single point is used, the data can indifferently be of size (1, 3) or (3). 

    :param ndarray data: array of the point(s) coordinates in the laboratory frame.
    :return data_gp: array of the projected point(s) coordinates in the laboratory frame.
    """
    if data.ndim == 1:
        data = data.reshape((1, 3))
    r = np.sqrt(data[:, 1] ** 2 + data[:, 2] ** 2)  # mm
    theta = 0.5 * np.arctan(r / data[:, 0])
    p = data[:, 0] * np.tan(np.pi / 2 - theta)  # distance from the incident beam to the gnomonic projection mm
    data_gp = np.zeros_like(data)  # mm
    data_gp[:, 0] = data[:, 0]
    data_gp[:, 1] = - data[:, 1] * p / r
    data_gp[:, 2] = - data[:, 2] * p / r
    return data_gp


def gnomonic_projection_point2(data, OC=None):
    """compute the gnomonic projection of a given point or series of points in the general case.

    This methods *does not* assumes the incident X-ray beam is along (1, 0, 0).  
    The points coordinates are passed along with a single array which must be of size (n, 3) where n is the number of 
    points. If a single point is used, the data can indifferently be of size (1, 3) or (3). 

    :param ndarray data: array of the point(s) coordinates in the laboratory frame, aka OR components.
    :param ndarray OC: coordinates of the center of the gnomonic projection in the laboratory frame.
    :return data_gp: array of the projected point(s) coordinates in the laboratory frame.
    """
    if OC is None:
        return gnomonic_projection_point(data)
    from math import cos, sin, pi, atan2
    if data.ndim == 1:
        data = data.reshape((1, 3))
    data_gp = np.zeros_like(data)  # mm
    data_gp[:, 0] = data[:, 0]
    for i in range(data.shape[0]):
        R = data[i]  # diffraction spot position in the laboratory frame
        CR = R - OC
        alpha = atan2(
            np.linalg.norm(np.cross(OC / np.linalg.norm(OC), CR / np.linalg.norm(CR))),
            np.dot(OC / np.linalg.norm(OC), CR / np.linalg.norm(CR))) - pi / 2
        # the Bragg angle can be measured using the diffraction spot position
        theta = 0.5 * np.arccos(np.dot(OC / np.linalg.norm(OC), R / np.linalg.norm(R)))
        r = np.sqrt(CR[1] ** 2 + CR[2] ** 2)  # mm
        # distance from the incident beam to the gnomonic projection mm
        p = np.linalg.norm(OC) * cos(theta) / sin(theta - alpha)
        data_gp[:, 1] = OC[1] - CR[1] * p / r
        data_gp[:, 2] = OC[2] - CR[2] * p / r
    return data_gp


def gnomonic_projection(detector, pixel_size=None):
    '''This function carries out the gnomonic projection of the detector image.
    
    The data must be of uint8 type (between 0 and 255) with diffraction spots equals to 255.
    The function create a new detector instance (think of it as a virtual detector) located at the same position 
    as the given detector and with an inverse pixel size. The gnomonic projection is stored into this new detector data.
    
    :param RegArrayDetector2d detector: the detector instance with the data from which to compute the projection.
    :returns RegArrayDetector2d gnom: A virtual detector with the gnomonic projection as its data.
    '''
    assert detector.data.dtype == np.uint8
    dif = detector.data == 255
    u = np.linspace(0, detector.size[0] - 1, detector.size[0])
    v = np.linspace(0, detector.size[1] - 1, detector.size[1])
    vv, uu = np.meshgrid(v, u)
    r_pxl = np.sqrt((uu - detector.ucen) ** 2 + (vv - detector.vcen) ** 2)  # pixel
    r = r_pxl * detector.pixel_size  # distance from the incident beam to the pxl in mm
    theta = 0.5 * np.arctan(r / detector.ref_pos[0])  # bragg angle rad
    p = detector.ref_pos[0] * np.tan(np.pi / 2 - theta)  # distance from the incident beam to the gnomonic projection mm

    # compute gnomonic projection coordinates in mm
    u_dif = (uu[dif] - detector.ucen) * detector.pixel_size  # mm, wrt detector center
    v_dif = (vv[dif] - detector.vcen) * detector.pixel_size  # mm, wrt detector center
    ug_mm = - u_dif * p[dif] / r[dif]  # mm, wrt detector center
    vg_mm = - v_dif * p[dif] / r[dif]  # mm, wrt detector center
    print('first projected spot in uv (mm):', (ug_mm[0], vg_mm[0]))
    print('last projected spot in uv (mm):', (ug_mm[-1], vg_mm[-1]))
    print('first projected vector in XYZ (mm):', (detector.ref_pos[0], -ug_mm[0], -vg_mm[0]))
    print('last projected vector in XYZ (mm):', (detector.ref_pos[0], -ug_mm[-1], -vg_mm[-1]))

    # create 2d image of the gnomonic projection because the gnomonic projection is bigger than the pattern
    from pymicro.xray.detectors import RegArrayDetector2d
    gnom = RegArrayDetector2d(size=np.array(detector.size))
    gnom.ref_pos = detector.ref_pos  # same ref position as the actual detector
    if not pixel_size:
        gnom.pixel_size = 1. / detector.pixel_size  # mm
    else:
        gnom.pixel_size = pixel_size  # mm
    gnom.ucen = gnom.size[0] / 2 - gnom.ref_pos[1] / gnom.pixel_size  # should include u_dir
    gnom.vcen = gnom.size[1] / 2 - gnom.ref_pos[2] / gnom.pixel_size  # should include v_dir

    gnom.data = np.zeros(gnom.size, dtype=np.uint8)
    u_gnom = np.linspace(0, gnom.size[0] - 1, gnom.size[0])
    v_gnom = np.linspace(0, gnom.size[1] - 1, gnom.size[1])

    # TODO use a function to go from mm to pixel coordinates
    ug_px = gnom.ucen + ug_mm / gnom.pixel_size  # pixel, wrt (top left corner of gnom detector)
    vg_px = gnom.vcen + vg_mm / gnom.pixel_size  # pixel, wrt (top left corner of gnom detector)

    # remove pixel outside of the ROI (TODO use masked numpy array)
    vg_px[ug_px > gnom.size[0] - 1] = gnom.vcen  # change vg_px first when testing on ug_px
    ug_px[ug_px > gnom.size[0] - 1] = gnom.ucen
    vg_px[ug_px < 0] = gnom.vcen
    ug_px[ug_px < 0] = gnom.ucen

    ug_px[vg_px > gnom.size[1] - 1] = gnom.ucen  # change ug_px first when testing on vg_px
    vg_px[vg_px > gnom.size[1] - 1] = gnom.vcen
    ug_px[vg_px < 0] = gnom.ucen
    vg_px[vg_px < 0] = gnom.vcen

    print(ug_px.min())
    assert (ug_px.min() >= 0)
    assert (ug_px.max() < gnom.size[0])
    assert (vg_px.min() >= 0)
    assert (vg_px.max() < gnom.size[1])

    # convert pixel coordinates to integer
    ug_px = ug_px.astype(np.uint16)
    vg_px = vg_px.astype(np.uint16)
    print('after conversion to uint16:')
    print(ug_px)
    print(vg_px)

    gnom.data[ug_px, vg_px] = 1
    return gnom


def identify_hkl_from_list(hkl_list):
    if hkl_list[1] == hkl_list[2]:
        ids = [1, 3, 0]
    elif hkl_list[1] == hkl_list[3]:
        ids = [1, 2, 0]
    elif hkl_list[0] == hkl_list[2]:
        ids = [0, 3, 1]
    elif hkl_list[0] == hkl_list[3]:
        ids = [0, 2, 1]
    '''
    if hkl_list[1] == hkl_list[2]:
        if hkl_list[3] == hkl_list[4] and hkl_list[0] == hkl_list[5] or \
                                hkl_list[3] == hkl_list[5] and hkl_list[0] == hkl_list[4]:
            identified_list = [hkl_list[1], hkl_list[3], hkl_list[0]]

    elif hkl_list[1] == hkl_list[3]:
        if hkl_list[2] == hkl_list[4]:
            if hkl_list[0] == hkl_list[5]:
                identified_list = [hkl_list[1], hkl_list[2], hkl_list[0]]

        elif hkl_list[2] == hkl_list[5]:
            if hkl_list[0] == hkl_list[4]:
                identified_list = [hkl_list[1], hkl_list[2], hkl_list[0]]

    elif hkl_list[0] == hkl_list[2]:
        if hkl_list[3] == hkl_list[4]:
            if hkl_list[1] == hkl_list[5]:
                identified_list = [hkl_list[0], hkl_list[3], hkl_list[1]]

        elif hkl_list[3] == hkl_list[5]:
            if hkl_list[1] == hkl_list[4]:
                identified_list = [hkl_list[0], hkl_list[3], hkl_list[1]]

    elif hkl_list[0] == hkl_list[3]:
        if hkl_list[2] == hkl_list[4]:
            if hkl_list[1] == hkl_list[5]:
                identified_list = [hkl_list[0], hkl_list[2], hkl_list[1]]

        elif hkl_list[2] == hkl_list[5]:
            if hkl_list[1] == hkl_list[4]:
                identified_list = [hkl_list[0], hkl_list[2], hkl_list[1]]
    '''
    return [hkl_list[i] for i in ids]


def triplet_indexing(OP, angles_exp, angles_th, tol=1.0):
    '''
    evaluate each triplet composed by 3 diffracted points.
    the total number of triplet is given by the binomial coefficient (n, 3) = n*(n-1)*(n-2)/6
    '''
    nombre_triplet = 0
    OP_indexed = []
    for ti in range(len(OP) - 2):

        for tj in range(ti + 1, len(OP) - 1):

            triplet = np.zeros(3)
            for tk in range(tj + 1, len(OP)):
                nombre_triplet = nombre_triplet + 1
                print('\n\ntriplet number = {0:d}'.format(nombre_triplet))
                # look for possible matches for a given triplet
                triplet = [(ti, tj), (tj, tk), (ti, tk)]
                print('** testing triplet %s' % triplet)
                candidates = []  # will contain the 3 lists of candidates for a given triplet
                for (i, j) in triplet:
                    angle_to_match = angles_exp[i, j]
                    # find the index by looking to matching angles within the tolerance
                    cand = np.argwhere(
                        abs(angles_th['angle'] - angle_to_match) < tol).flatten()  # flatten since shape is (n, 1)
                    print('* couple (OP%d, OP%d) has angle %.2f -> %d couple candidate(s) in the angle_th list: %s' % (
                        i, j, angle_to_match, len(cand), cand))
                    candidates.append(cand)
                print('looking for real triplet in all %d candidates pairs:' % (
                    len(candidates[0]) * len(candidates[1]) * len(candidates[2])))
                for ci in candidates[0]:
                    for cj in candidates[1]:
                        for ck in candidates[2]:
                            # make a list of the candidate hkl plane indices, based on the angle match
                            hkl_list = [angles_th['hkl1'][ci], angles_th['hkl2'][ci],
                                        angles_th['hkl1'][cj], angles_th['hkl2'][cj],
                                        angles_th['hkl1'][ck], angles_th['hkl2'][ck]]
                            # look how many unique planes are in the list (should be 3 for a triplet)
                            print('- candidates with indices %s correspond to %s' % ([ci, cj, ck], hkl_list))
                            unique_indices = np.unique(hkl_list)
                            if len(unique_indices) != 3:
                                print('not a real triplet, skipping this one')
                                continue
                            print('this is a triplet: %s' % unique_indices)
                            # the points can now be identified from the hkl_list ordering
                            identified_list = identify_hkl_from_list(hkl_list)
                            full_list = [tj, tk, ti]
                            full_list.extend(identified_list)
                            print(full_list)
                            OP_indexed.append(full_list)
                            print('*  (OP%d) -> %d ' % (tj, identified_list[0]))
                            print('*  (OP%d) -> %d ' % (tk, identified_list[1]))
                            print('*  (OP%d) -> %d ' % (ti, identified_list[2]))
    print('indexed list length is %d' % len(OP_indexed))
    print(OP_indexed)
    return OP_indexed


def transformation_matrix(hkl_plane_1, hkl_plane_2, xyz_normal_1, xyz_normal_2):
    # create the vectors representing this frame in the crystal coordinate system
    e1_hat_c = hkl_plane_1.normal()
    e2_hat_c = np.cross(hkl_plane_1.normal(), hkl_plane_2.normal()) / np.linalg.norm(
        np.cross(hkl_plane_1.normal(), hkl_plane_2.normal()))
    e3_hat_c = np.cross(e1_hat_c, e2_hat_c)
    e_hat_c = np.array([e1_hat_c, e2_hat_c, e3_hat_c])
    # create local frame attached to the indexed crystallographic features in XYZ
    e1_hat_star = xyz_normal_1
    e2_hat_star = np.cross(xyz_normal_1, xyz_normal_2) / np.linalg.norm(
        np.cross(xyz_normal_1, xyz_normal_2))
    e3_hat_star = np.cross(e1_hat_star, e2_hat_star)
    e_hat_star = np.array([e1_hat_star, e2_hat_star, e3_hat_star])
    # now build the orientation matrix
    orientation_matrix = np.dot(e_hat_c.T, e_hat_star)
    return orientation_matrix


def confidence_index(votes):
    n = np.sum(votes)  # total number of votes
    v1 = max(votes)
    votes[votes.index(v1)] = 0.
    v2 = max(votes)
    ci = (1. * (v1 - v2)) / n
    return ci


def poll_system(g_list, dis_tol=1.0, verbose=False):
    """
    Poll system to sort a series of orientation matrices determined by the indexation procedure.

    For each orientation matrix, check if it corresponds to an existing solution, if so: vote for it,
    if not add a new solution to the list
    :param list g_list: the list of orientation matrices (should be in the fz)
    :param float dis_tol: angular tolerance (degrees)
    :param bool verbose: activate verbose mode (False by default)
    :return: a tuple composed by the most popular orientation matrix, the corresponding vote number and the confidence index
    """
    solution_indices = [0]
    votes = [0]
    vote_index = np.zeros(len(g_list), dtype=int)
    dis_tol_rad = dis_tol * np.pi / 180
    from pymicro.crystal.microstructure import Orientation
    for i in range(len(g_list)):
        g = g_list[i]
        # rotations are already in the fundamental zone
        for j in range(len(solution_indices)):
            index = solution_indices[j]
            delta = np.dot(g, g_list[index].T)
            # compute misorientation angle in radians
            angle = Orientation.misorientation_angle_from_delta(delta)
            if verbose:
                print('j=%d -- angle=%f' % (j, angle))
            if angle <= dis_tol_rad:
                votes[j] += 1
                vote_index[i] = j
                if verbose:
                    print('angle (deg) is %.2f' % (180 / np.pi * angle))
                    print('vote list is now %s' % votes)
                    print('solution_indices list is now %s' % solution_indices)
                break
            elif j == len(solution_indices) - 1:
                solution_indices.append(i)
                votes.append(1)
                vote_index[i] = len(votes) - 1
                if verbose:
                    print('vote list is now %s' % votes)
                    print('solution_indices list is now %s' % solution_indices)
                break
    index_result = np.argwhere(votes == np.amax(votes)).flatten()
    if verbose:
        print('Max vote =', np.amax(votes))
        print('index result:', index_result)
        print('Number of equivalent solutions :', len(index_result))
        print(type(index_result))
        print(index_result.shape)
    final_orientation_matrix = []
    for n in range(len(index_result)):
        solutions = g_list[solution_indices[index_result[n]]]
        if verbose:
            print('Solution number {0:d} is'.format(n+1), solutions)
        final_orientation_matrix.append(solutions)
    result_vote = max(votes)
    ci = confidence_index(votes)
    vote_field = [votes[i] for i in vote_index]
    return final_orientation_matrix, result_vote, ci, vote_field


def index(hkl_normals, hkl_planes, tol_angle=0.5, tol_disorientation=1.0, crystal_structure='cubic', display=False):
    # angles between normal from the gnomonic projection
    angles_exp = np.zeros((len(hkl_normals), len(hkl_normals)), dtype=float)
    print('\nlist of angles between points on the detector')
    for i in range(len(hkl_normals)):
        for j in range(i + 1, len(hkl_normals)):
            angle = 180 / np.pi * np.arccos(np.dot(hkl_normals[i], hkl_normals[j]))
            angles_exp[i, j] = angle
            print('%.2f, OP%d, OP%d' % (angles_exp[i, j], i, j))
    # keep a list of the hkl values as string
    hkl_str = []
    for p in hkl_planes:
        (h, k, l) = p.miller_indices()
        hkl_str.append('(%d%d%d)' % (h, k, l))
    # compute theoretical angle between each plane normal, store the results using a structured array
    angles_th = np.empty(len(hkl_planes) * (len(hkl_planes) - 1) / 2,
                         dtype=[('angle', 'f4'), ('hkl1', 'i4'), ('hkl2', 'i4')])
    index = 0
    for i in range(len(hkl_planes)):
        for j in range(i + 1, len(hkl_planes)):
            angle = 180 / np.pi * np.arccos(np.dot(hkl_planes[i].normal(), hkl_planes[j].normal()))
            angles_th[index] = (angle, i, j)
            index += 1

    # sort the array by increasing angle
    angles_th.sort(order='angle')
    print('\nsorted list of angles between hkl plane normals')
    for i in range(len(angles_th)):
        print('%.3f, (%d, %d) -> %s, %s' % (
            angles_th['angle'][i], angles_th['hkl1'][i], angles_th['hkl2'][i], hkl_str[angles_th['hkl1'][i]],
            hkl_str[angles_th['hkl2'][i]]))

    # index by triplets
    normal_indexed = triplet_indexing(hkl_normals, angles_exp, angles_th, tol=tol_angle)
    print('indexed list length is %d' % len(normal_indexed))
    print(normal_indexed)

    # Compute the orientation matrix g for all different triplets
    g_indexation = []
    for i in range(len(normal_indexed)):
        # a given indexed triplet allow to construct 3 orientation matrices (which should be identical)
        pos = [[0, 1, 3, 4], [1, 2, 4, 5], [2, 0, 5, 3]]
        for j in range(3):
            orientation_matrix = transformation_matrix(
                hkl_planes[normal_indexed[i][pos[j][2]]], hkl_planes[normal_indexed[i][pos[j][3]]],
                hkl_normals[normal_indexed[i][pos[j][0]]], hkl_normals[normal_indexed[i][pos[j][1]]])
        # move to the fundamental zone
        om_fz = Lattice.move_rotation_to_FZ(orientation_matrix, crystal_structure=crystal_structure)  # we only add the third one
        g_indexation.append(om_fz)
    final_orientation_matrix, vote, ci, vote_field = poll_system(g_indexation, dis_tol=tol_disorientation)
    if final_orientation_matrix == 0:
        print('Troubles in the data set !')
    else:
        print('\n\n\n### FINAL SOLUTION(S) ###\n')
        for n in range(len(final_orientation_matrix)):
            print('- SOLUTION %d -' % (n + 1))
            final_orientation = Orientation(final_orientation_matrix[n])
            print(final_orientation.inFZ())
            print ('- Cristal orientation in Fundamental Zone \n {0:s} \n'.format(final_orientation.euler))
            print('- Rodrigues vector in the fundamental Zone \n {0:s} \n'.format(final_orientation.rod))
            if display:
                from pymicro.crystal.texture import PoleFigure
                PoleFigure.plot(final_orientation, axis='Z')
        return final_orientation_matrix, ci

if __name__ == '__main__':
    from matplotlib import pyplot as plt, cm, rcParams

    rcParams.update({'font.size': 12})
    rcParams['text.latex.preamble'] = [r"\usepackage{amsmath}"]

    from pymicro.xray.detectors import Varian2520

    det_distance = 100
    detector = Varian2520()
    detector.pixel_size = 0.127  # mm
    det_size_pixel = np.array((1950, 1456))
    det_size_mm = det_size_pixel * detector.pixel_size  # mm

    # orientation of our single crystal
    from pymicro.crystal.lattice import *

    ni = Lattice.from_symbol('Ni')
    from pymicro.crystal.microstructure import *

    phi1 = 10  # deg
    phi = 20  # deg
    phi2 = 10  # deg
    orientation = Orientation.from_euler([phi1, phi, phi2])

    # '''
    # uvw = HklDirection(1, 1, 0, ni)
    uvw = HklDirection(5, 1, 0, ni)
    ellipsis_data = compute_ellipsis(orientation, detector, det_distance, uvw)
    # '''
    hklplanes = build_list(lattice=ni, max_miller=8)

    # compute image for the cube orientation
    det_distance = 300
    orientation = Orientation.cube()

    '''
    # euler angles from EBSD
    euler1 = [286.3, 2.1, 70.5]
    euler2 = [223.7, 2.8, 122.2]
    eulers = [euler1, euler2]
    o_ebsd = Orientation.from_euler(eulers[0])
    # apply the transformation matrix corresponding to putting the sample with X being along the X-ray direction
    Tr = np.array([[0., 0., -1.], [0., 1., 0.], [1., 0., 0.]])
    orientation = Orientation(np.dot(o_ebsd.orientation_matrix(), Tr.T))

    # compute the list of zone axes having a glancing angle < 45 deg
    max_miller = 5
    # max glancing angle in the vertical direction
    max_glangle = np.arctan(0.5*det_size_pixel[1]*detector.pixel_size/det_distance)*180./np.pi
    zoneaxes = []
    indices = range(-max_miller, max_miller+1)
    Bt = orientation.orientation_matrix().transpose()
    for u in indices:
      for v in indices:
        for w in indices:
          if u == v == w == 0: # skip (0, 0, 0)
            continue
          uvw = HklDirection(u, v, w, ni)
          ZA = Bt.dot(uvw.direction())
          psi = np.arccos(np.dot(ZA, np.array([1., 0., 0.])))*180./np.pi
          print('angle between incident beam and zone axis is %.1f' % psi)
          if psi < max_glangle:
            zoneaxes.append(HklDirection(u, v, w, ni))
    for ZA in zoneaxes:
      print(ZA.miller_indices())
    print(len(zoneaxes))
    '''
    image = compute_Laue_pattern(orientation, detector, det_distance, hklplanes)
    plt.imshow(image.T, cmap=cm.gray)
    plt.plot(ellipsis_data[0], ellipsis_data[1], 'b-')
    plt.title(r'Simulated Laue pattern, cube orientation, $d={0}$ mm'.format(det_distance))
    # plt.savefig('Laue_plot_cube_distance_%02d.pdf' % det_distance)
    plt.show()

    '''
    # simple loop to vary the detector distance
    for i in range(6):
      det_distance = 50 + 10*i # mm
      # compute image
      image = compute_Laue_pattern(orientation, detector, det_distance, hklplanes)
      plt.imshow(image.T, cmap=cm.gray)
      plt.title(r'Simulated Laue pattern, $d={0}$ mm, ($\varphi_1={1}^\circ$, $\phi={2}^\circ$, $\varphi_2={3}^\circ$)'.format(det_distance, phi1, phi, phi2))
      plt.savefig('Laue_plot_distance_%02d' % i)

    # another loop to vary the crystal orientation
    for i in range(20):
      phi2 = 2*i # mm
      orientation = Orientation.from_euler([phi1, phi, phi2])
      # compute image
      image = compute_Laue_pattern(orientation, detector, det_distance, hklplanes)
      plt.imshow(image.T, cmap=cm.gray)
      plt.title(r'Simulated Laue pattern, $d={0}$ mm, ($\varphi_1={1}^\circ$, $\phi={2}^\circ$, $\varphi_2={3}^\circ$)'.format(det_distance, phi1, phi, phi2))
      plt.savefig('Laue_plot_phi2_%02d' % i)
    '''
