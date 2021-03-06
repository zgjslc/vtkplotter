from __future__ import division, print_function

import numpy as np
import vtk
import vtkplotter.colors as colors
import vtkplotter.docs as docs
import vtkplotter.settings as settings
import vtkplotter.utils as utils
from vtk.util.numpy_support import numpy_to_vtk, vtk_to_numpy

__doc__ = (
    """
Submodule extending the ``vtkActor``, ``vtkVolume``
and ``vtkImageActor`` objects functionality.
"""
    + docs._defs
)

__all__ = ['ActorBase']

####################################################
# classes
class ActorBase(object):
    """Adds functionality to ``Mesh(vtkActor)``, ``Assembly``,
    ``Volume`` and ``Picture`` objects.

    .. warning:: Do not use this class to instance objects, use the above ones.
    """

    def __init__(self):

        self.filename = ""
        self.name = ""
        self.trail = None
        self.trailPoints = []
        self.trailSegmentSize = 0
        self.trailOffset = None
        self.shadow = None
        self.shadowX = None
        self.shadowY = None
        self.shadowZ = None
        self.units = None
        self.top = None
        self.base = None
        self.info = dict()
        self._time = 0
        self._legend = None
        self.scalarbar = None
        self.renderedAt = set()
        self.picked3d = None
        self.cmap = None
        self.flagText = None
        self._mapper = None

    def mapper(self, newMapper=None):
        """Return the ``vtkMapper`` data object, or update it with a new one."""
        if newMapper:
            self.SetMapper(newMapper)
            if self._mapper:
                iptdata = self._mapper.GetInput()
                if iptdata:
                    newMapper.SetInputData(self._mapper.GetInput())
            self._mapper = newMapper
            self._mapper.Modified()
        return self._mapper

    def inputdata(self):
        """Return the VTK input data object."""
        if self._mapper:
            return self._mapper.GetInput()
        return self.GetMapper().GetInput()


    def show(self, **options):
        """
        Create on the fly an instance of class ``Plotter`` or use the last existing one to
        show one single object.

        This is meant as a shortcut. If more than one object needs to be visualised
        please use the syntax `show([mesh1, mesh2, volume, ...], options)`.

        :param bool newPlotter: if set to `True`, a call to ``show`` will instantiate
            a new ``Plotter`` object (a new window) instead of reusing the first created.
            See e.g.: |readVolumeAsIsoSurface.py|_
        :return: the current ``Plotter`` class instance.

        .. note:: E.g.:

            .. code-block:: python

                from vtkplotter import *
                s = Sphere()
                s.show(at=1, N=2)
                c = Cube()
                c.show(at=0, interactive=True)
        """
        from vtkplotter.plotter import show
        return show(self, **options)


    def N(self):
        """Retrieve number of points. Shortcut for `NPoints()`."""
        return self.inputdata().GetNumberOfPoints()

    def NPoints(self):
        """Retrieve number of points. Same as `N()`."""
        return self.inputdata().GetNumberOfPoints()

    def NCells(self):
        """Retrieve number of cells."""
        return self.inputdata().GetNumberOfCells()


    def pickable(self, value=None):
        """Set/get pickable property of mesh."""
        if value is None:
            return self.GetPickable()
        else:
            self.SetPickable(value)
            return self


    def legend(self, txt=None):
        """Set/get ``Mesh`` legend text.

        :param str txt: legend text.

        Size and positions can be modified by setting attributes
        ``Plotter.legendSize``, ``Plotter.legendBC`` and ``Plotter.legendPos``.

        .. hint:: |fillholes.py|_
        """
        if txt:
            self._legend = txt
        else:
            return self._legend
        return self

    def flag(self, text=None):
        """Add a flag label which becomes visible when hovering the object with mouse.
        Can be later disabled by setting `flag(False)`.
        """
        if text is None:
            if self.filename:
                text = self.filename.split('/')[-1]
            elif self.name:
                text = self.name
            else:
                text = ""
        self.flagText = text
        return self


    def time(self, t=None):
        """Set/get object's absolute time."""
        if t is None:
            return self._time
        self._time = t
        return self  # return itself to concatenate methods

    def pos(self, x=None, y=None, z=None):
        """Set/Get object position."""
        if x is None:
            return np.array(self.GetPosition())
        if z is None:  # assume p_x is of the form (x,y,z)
            if y is not None: # assume x and y are given so z=0
                z=0
            else: # assume p_x is of the form (x,y,z)
                x, y, z = x
        self.SetPosition(x, y, z)

        if self.trail:
            self.updateTrail()
        if self.shadow:
            self._updateShadow()
        return self  # return itself to concatenate methods

    def addPos(self, dp_x=None, dy=None, dz=None):
        """Add vector to current object position."""
        p = np.array(self.GetPosition())
        if dz is None:  # assume dp_x is of the form (x,y,z)
            self.SetPosition(p + dp_x)
        else:
            self.SetPosition(p + [dp_x, dy, dz])
        if self.trail:
            self.updateTrail()
        if self.shadow:
            self._updateShadow()
        return self

    def x(self, position=None):
        """Set/Get object position along x axis."""
        p = self.GetPosition()
        if position is None:
            return p[0]
        self.SetPosition(position, p[1], p[2])
        if self.trail:
            self.updateTrail()
        if self.shadow:
            self._updateShadow()
        return self

    def y(self, position=None):
        """Set/Get object position along y axis."""
        p = self.GetPosition()
        if position is None:
            return p[1]
        self.SetPosition(p[0], position, p[2])
        if self.trail:
            self.updateTrail()
        if self.shadow:
            self._updateShadow()
        return self

    def z(self, position=None):
        """Set/Get object position along z axis."""
        p = self.GetPosition()
        if position is None:
            return p[2]
        self.SetPosition(p[0], p[1], position)
        if self.trail:
            self.updateTrail()
        if self.shadow:
            self._updateShadow()
        return self

    def rotate(self, angle, axis=(1, 0, 0), axis_point=(0, 0, 0), rad=False):
        """Rotate around an arbitrary `axis` passing through `axis_point`."""
        if rad:
            anglerad = angle
        else:
            anglerad = np.deg2rad(angle)
        axis = utils.versor(axis)
        a = np.cos(anglerad / 2)
        b, c, d = -axis * np.sin(anglerad / 2)
        aa, bb, cc, dd = a * a, b * b, c * c, d * d
        bc, ad, ac, ab, bd, cd = b * c, a * d, a * c, a * b, b * d, c * d
        R = np.array(
            [
                [aa + bb - cc - dd, 2 * (bc + ad), 2 * (bd - ac)],
                [2 * (bc - ad), aa + cc - bb - dd, 2 * (cd + ab)],
                [2 * (bd + ac), 2 * (cd - ab), aa + dd - bb - cc],
            ]
        )
        rv = np.dot(R, self.GetPosition() - np.array(axis_point)) + axis_point

        if rad:
            angle *= 180.0 / np.pi
        # this vtk method only rotates in the origin of the object:
        self.RotateWXYZ(angle, axis[0], axis[1], axis[2])
        self.SetPosition(rv)
        if self.trail:
            self.updateTrail()
        if self.shadow:
            self.addShadow(self.shadowX, self.shadowY, self.shadowZ,
                           self.shadow.GetProperty().GetColor(),
                           self.shadow.GetProperty().GetOpacity())
        return self

    def rotateX(self, angle, rad=False):
        """Rotate around x-axis. If angle is in radians set ``rad=True``.

        NB: mesh.rotateX(12).rotateY(14) will rotate FIRST around Y THEN around X.
        """
        if rad:
            angle *= 180 / np.pi
        self.RotateX(angle)
        if self.trail:
            self.updateTrail()
        if self.shadow:
            self.addShadow(self.shadowX, self.shadowY, self.shadowZ,
                           self.shadow.GetProperty().GetColor(),
                           self.shadow.GetProperty().GetOpacity())
        return self

    def rotateY(self, angle, rad=False):
        """Rotate around y-axis. If angle is in radians set ``rad=True``.

        NB: mesh.rotateX(12).rotateY(14) will rotate FIRST around Y THEN around X.
        """
        if rad:
            angle *= 180.0 / np.pi
        self.RotateY(angle)
        if self.trail:
            self.updateTrail()
        if self.shadow:
            self.addShadow(self.shadowX, self.shadowY, self.shadowZ,
                           self.shadow.GetProperty().GetColor(),
                           self.shadow.GetProperty().GetOpacity())
        return self

    def rotateZ(self, angle, rad=False):
        """Rotate around z-axis. If angle is in radians set ``rad=True``.

        NB: mesh.rotateX(12).rotateZ(14) will rotate FIRST around Z THEN around X.
        """
        if rad:
            angle *= 180.0 / np.pi
        self.RotateZ(angle)
        if self.trail:
            self.updateTrail()
        if self.shadow:
            self.addShadow(self.shadowX, self.shadowY, self.shadowZ,
                           self.shadow.GetProperty().GetColor(),
                           self.shadow.GetProperty().GetOpacity())
        return self

#    def rotateX(self, angle, rad=False):
#        """Rotate around x-axis. If angle is in radians set ``rad=True``."""
#        if rad:
#            angle *= 180 / np.pi
#        ipos = np.array(self.GetPosition())
#        self.SetPosition(0,0,0)
#        T = vtk.vtkTransform()
#        T.SetMatrix(self.GetMatrix())
#        T.PostMultiply()
#        T.RotateX(angle)
#        T.Translate(ipos)
#        self.SetUserTransform(T)
#        if self.trail:
#            self.updateTrail()
#        if self.shadow:
#            self.addShadow(self.shadowX, self.shadowY, self.shadowZ,
#                           self.shadow.GetProperty().GetColor(),
#                           self.shadow.GetProperty().GetOpacity())
#        return self
#    def origin(self, o=None):
#        """Set/get mesh's origin coordinates. Default is (0,0,0).
#        Can be used to define an offset."""
#        if o is None:
#            return np.array(self.GetOrigin())
#        self.SetOrigin(o)
#        return self  # return itself to concatenate methods


    def orientation(self, newaxis=None, rotation=0, rad=False):
        """
        Set/Get object orientation.

        :param rotation: If != 0 rotate object around newaxis.
        :param rad: set to True if angle is in radians.

        |gyroscope2| |gyroscope2.py|_
        """
        if rad:
            rotation *= 180.0 / np.pi
        if self.top is None or self.base is None:
            initaxis = (0,0,1)
        else:
            initaxis = utils.versor(self.top - self.base)
        if newaxis is None:
            return initaxis
        newaxis = utils.versor(newaxis)
        pos = np.array(self.GetPosition())
        crossvec = np.cross(initaxis, newaxis)
        angle = np.arccos(np.dot(initaxis, newaxis))
        T = vtk.vtkTransform()
        T.PostMultiply()
        T.Translate(-pos)
        if rotation:
            T.RotateWXYZ(rotation, initaxis)
        T.RotateWXYZ(np.rad2deg(angle), crossvec)
        T.Translate(pos)
        self.SetUserTransform(T)
        if self.trail:
            self.updateTrail()
        if self.shadow:
            self.addShadow(self.shadowX, self.shadowY, self.shadowZ,
                           self.shadow.GetProperty().GetColor(),
                           self.shadow.GetProperty().GetOpacity())
        return self


    def scale(self, s=None):
        """Set/get object's scaling factor.

        :param s: scaling factor(s).
        :type s: float, list

        .. note:: if `s==(sx,sy,sz)` scale differently in the three coordinates."""
        if s is None:
            return np.array(self.GetScale())
        self.SetScale(s)
        return self

    def print(self):
        """Print  ``Mesh``, ``Assembly``, ``Volume`` or ``Image`` infos."""
        utils.printInfo(self)
        return self

    def on(self):
        """Switch on object visibility. Object is not removed."""
        self.VisibilityOn()
        return self

    def off(self):
        """Switch off object visibility. Object is not removed."""
        self.VisibilityOff()
        return self

    def lighting(self, style='', ambient=None, diffuse=None,
                 specular=None, specularPower=None, specularColor=None,
                 enabled=True):
        """
        Set the ambient, diffuse, specular and specularPower lighting constants.

        :param str,int style: preset style, can be `[metallic, plastic, shiny, glossy, ambient]`
        :param float ambient: ambient fraction of emission [0-1]
        :param float diffuse: emission of diffused light in fraction [0-1]
        :param float specular: fraction of reflected light [0-1]
        :param float specularPower: precision of reflection [1-100]
        :param color specularColor: color that is being reflected by the surface
        :param bool enabled: enable/disable all surface light emission

        |wikiphong|

        |specular| |specular.py|_
        """
        pr = self.GetProperty()

        if style:
            if hasattr(pr, "GetColor"):  # could be Volume
                c = pr.GetColor()
            else:
                c = (1,1,0.99)
            mpr = self._mapper
            if hasattr(mpr, 'GetScalarVisibility') and mpr.GetScalarVisibility():
                c = (1,1,0.99)
            if   style=='metallic': pars = [0.1, 0.3, 1.0, 10, c]
            elif style=='plastic' : pars = [0.3, 0.4, 0.3,  5, c]
            elif style=='shiny'   : pars = [0.2, 0.6, 0.8, 50, c]
            elif style=='glossy'  : pars = [0.1, 0.7, 0.9, 90, (1,1,0.99)]
            elif style=='ambient' : pars = [1.0, 0.0, 0.0,  0, (1,1,1)]
            elif style=='default' : pars = [0.1, 1.0, 0.05, 5, c]
            else:
                colors.printc("Error in lighting(): Available styles are", c=1)
                colors.printc(" [default, metallic, plastic, shiny, glossy, ambient]", c=1)
                raise RuntimeError()
            pr.SetAmbient(pars[0])
            pr.SetDiffuse(pars[1])
            pr.SetSpecular(pars[2])
            pr.SetSpecularPower(pars[3])
            if hasattr(pr, "GetColor"): pr.SetSpecularColor(pars[4])

        if ambient is not None: pr.SetAmbient(ambient)
        if diffuse is not None: pr.SetDiffuse(diffuse)
        if specular is not None: pr.SetSpecular(specular)
        if specularPower is not None: pr.SetSpecularPower(specularPower)
        if specularColor is not None: pr.SetSpecularColor(colors.getColor(specularColor))
        if not enabled: pr.LightingOff()
        return self

    def box(self, scale=1):
        """Return the bounding box as a new ``Mesh``.

        :param float scale: box size can be scaled by a factor

        .. hint:: |latex.py|_
        """
        b = self.GetBounds()
        from vtkplotter.shapes import Box
        pos = (b[0]+b[1])/2, (b[3]+b[2])/2, (b[5]+b[4])/2
        length, width, height = b[1]-b[0], b[3]-b[2], b[5]-b[4]
        oa = Box(pos, length*scale, width*scale, height*scale, c='gray')
        if isinstance(self.GetProperty(), vtk.vtkProperty):
            pr = vtk.vtkProperty()
            pr.DeepCopy(self.GetProperty())
            oa.SetProperty(pr)
            oa.wireframe()
        return oa

    def bounds(self):
        """Get the bounds of the data object."""
        return self.GetMapper().GetInput().GetBounds()

    def printHistogram(self, bins=10, height=10, logscale=False, minbin=0,
                       horizontal=False, char=u"\U00002589",
                       c=None, bold=True, title='Histogram'):
        """
        Ascii histogram printing.
        Input can also be ``Volume`` or ``Mesh``.
        Returns the raw data before binning (useful when passing vtk objects).

        :param int bins: number of histogram bins
        :param int height: height of the histogram in character units
        :param bool logscale: use logscale for frequencies
        :param int minbin: ignore bins before minbin
        :param bool horizontal: show histogram horizontally
        :param str char: character to be used
        :param str,int c: ascii color
        :param bool char: use boldface
        :param str title: histogram title

        :Example:
            .. code-block:: python

                from vtkplotter import printHistogram
                import numpy as np
                d = np.random.normal(size=1000)
                data = printHistogram(d, c='blue', logscale=True, title='my scalars')
                data = printHistogram(d, c=1, horizontal=1)
                print(np.mean(data)) # data here is same as d

            |printhisto|
        """
        utils.printHistogram(self, bins, height, logscale, minbin,
                             horizontal, char, c, bold, title)
        return self

    def printInfo(self):
        """Print information about a vtk object."""
        utils.printInfo(self)
        return self


    def c(self, color=False):
        """
        Shortcut for `color()`.
        If None is passed as input, will use colors from current active scalars.
        """
        return self.color(color)


    def getTransform(self):
        """
        Check if ``info['transform']`` exists and returns it.
        Otherwise return current user transformation
        (where the object is currently placed).
        """
        if "transform" in self.info.keys():
            T = self.info["transform"]
            return T
        else:
            T = self.GetMatrix()
            tr = vtk.vtkTransform()
            tr.SetMatrix(T)
            return tr

    def setTransform(self, T):
        """
        Transform object position and orientation.
        """
        if isinstance(T, vtk.vtkMatrix4x4):
            self.SetUserMatrix(T)
        else:
            try:
                self.SetUserTransform(T)
            except TypeError:
                colors.printc('~times Error in setTransform():',
                              'consider transformPolydata() instead.', c=1)
        return self


    def getArrayNames(self):
        from vtk.numpy_interface import dataset_adapter
        wrapped = dataset_adapter.WrapDataObject(self.GetMapper().GetInput())
        return {"PointData":wrapped.PointData.keys(), "CellData":wrapped.CellData.keys()}

    def getPointArray(self, name=0):
        """Return point array content as a ``numpy.array``.
        This can be identified either as a string or by an integer number."""

        data = None
        if hasattr(self, '_polydata') and self._polydata:
            data = self._polydata
            self.mapper().ScalarVisibilityOn()
            arr = data.GetPointData().GetArray(name)
            if not arr:
                return None

            if isinstance(name, int):
                name = data.GetPointData().GetArrayName(name)
            data.GetPointData().SetActiveScalars(name)
            self.mapper().SetScalarModeToUsePointData()
            if settings.autoResetScalarRange:
                self.mapper().SetScalarRange(arr.GetRange())

        elif hasattr(self, '_imagedata') and self._imagedata:
            data = self._imagedata
            arr = data.GetPointData().GetArray(name)
            if not arr:
                return None

        return vtk_to_numpy(arr)

    def getCellArray(self, name=0):
        """Return cell array content as a ``numpy.array``."""
        data = None
        if hasattr(self, '_polydata') and self._polydata:
            data = self._polydata
            self.mapper().ScalarVisibilityOn()
            arr = data.GetCellData().GetArray(name)
            if not arr:
                return None

            if isinstance(name, int):
                name = data.GetCellData().GetArrayName(name)
            data.GetCellData().SetActiveScalars(name)
            self.mapper().SetScalarModeToUseCellData()
            if settings.autoResetScalarRange:
                self.mapper().SetScalarRange(arr.GetRange())

        elif hasattr(self, '_imagedata') and self._imagedata:
            data = self._imagedata
            arr = data.GetCellData().GetArray(name)
            if not arr:
                return None

        return vtk_to_numpy(arr)


    def addPointScalars(self, scalars, name):
        """
        Add point scalars and assign it a name.

        |mesh_coloring| |mesh_coloring.py|_
        """
        data = self.inputdata()
        if len(scalars) != data.GetNumberOfPoints():
            colors.printc('~times addPointScalars(): Number of scalars != nr. of points',
                          len(scalars), data.GetNumberOfPoints(), c=1)
            raise RuntimeError()

        arr = numpy_to_vtk(np.ascontiguousarray(scalars), deep=True)
        arr.SetName(name)
        data.GetPointData().AddArray(arr)
        data.GetPointData().SetActiveScalars(name)
        self._mapper.SetArrayName(name)
        if settings.autoResetScalarRange:
            self._mapper.SetScalarRange(np.min(scalars), np.max(scalars))
        self._mapper.SetScalarModeToUsePointData()
        self._mapper.ScalarVisibilityOn()
        return self

    def addCellScalars(self, scalars, name):
        """
        Add cell scalars and assign it a name.
        """
        data = self.inputdata()
        if isinstance(scalars, str):
            scalars = vtk_to_numpy(data.GetPointData().GetArray(scalars))

        if len(scalars) != data.GetNumberOfCells():
            colors.printc("addCellScalars() Error: Number of scalars != nr. of cells",
                          len(scalars), data.GetNumberOfCells(), c=1)
            raise RuntimeError()

        arr = numpy_to_vtk(np.ascontiguousarray(scalars), deep=True)
        arr.SetName(name)
        data.GetCellData().AddArray(arr)
        data.GetCellData().SetActiveScalars(name)
        self._mapper.SetArrayName(name)
        if settings.autoResetScalarRange:
            self._mapper.SetScalarRange(np.min(scalars), np.max(scalars))
        self._mapper.SetScalarModeToUseCellData()
        self._mapper.ScalarVisibilityOn()
        return self

    def addPointVectors(self, vectors, name):
        """
        Add a point vector field to the object and assign it a name.
        """
        data = self.inputdata()
        if len(vectors) != data.GetNumberOfPoints():
            colors.printc('addPointVectors Error: Number of vectors != nr. of points',
                          len(vectors), data.GetNumberOfPoints(), c=1)
            raise RuntimeError()
        arr = vtk.vtkFloatArray()
        arr.SetNumberOfComponents(3)
        arr.SetName(name)
        for v in vectors:
            arr.InsertNextTuple(v)
        data.GetPointData().AddArray(arr)
        data.GetPointData().SetActiveVectors(name)
        return self

    def addCellVectors(self, vectors, name):
        """
        Add a vector field to each object cell and assign it a name.
        """
        data = self.inputdata()
        if len(vectors) != data.GetNumberOfCells():
            colors.printc('addPointVectors Error: Number of vectors != nr. of cells',
                          len(vectors), data.GetNumberOfCells(), c=1)
            raise RuntimeError()
        arr = vtk.vtkFloatArray()
        arr.SetNumberOfComponents(3)
        arr.SetName(name)
        for v in vectors:
            arr.InsertNextTuple(v)
        data.GetCellData().AddArray(arr)
        data.GetCellData().SetActiveVectors(name)
        return self


    def mapCellsToPoints(self):
        """
        Transform cell data (i.e., data specified per cell)
        into point data (i.e., data specified at each vertex).
        The method of transformation is based on averaging the data values
        of all cells using a particular point.
        """
        c2p = vtk.vtkCellDataToPointData()
        c2p.SetInputData(self.inputdata())
        c2p.Update()
        self._mapper.SetScalarModeToUsePointData()
        return self._update(c2p.GetOutput())

    def mapPointsToCells(self):
        """
        Transform point data (i.e., data specified per point)
        into cell data (i.e., data specified per cell).
        The method of transformation is based on averaging the data values
        of all points defining a particular cell.

        |mesh_map2cell| |mesh_map2cell.py|_
        """
        p2c = vtk.vtkPointDataToCellData()
        p2c.SetInputData(self.polydata(False))
        p2c.Update()
        self._mapper.SetScalarModeToUseCellData()
        return self._update(p2c.GetOutput())

