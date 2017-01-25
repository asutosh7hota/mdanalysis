# -*- Mode: python; tab-width: 4; indent-tabs-mode:nil; coding:utf-8 -*-
# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4 fileencoding=utf-8
#
# MDAnalysis --- http://www.mdanalysis.org
# Copyright (c) 2006-2016 The MDAnalysis Development Team and contributors
# (see the file AUTHORS for the full list of names)
#
# Released under the GNU Public Licence, v2 or any higher version
#
# Please cite your use of MDAnalysis in published work:
#
# R. J. Gowers, M. Linke, J. Barnoud, T. J. E. Reddy, M. N. Melo, S. L. Seyler,
# D. L. Dotson, J. Domanski, S. Buchoux, I. M. Kenney, and O. Beckstein.
# MDAnalysis: A Python package for the rapid analysis of molecular dynamics
# simulations. In S. Benthall and S. Rostrup editors, Proceedings of the 15th
# Python in Science Conference, pages 102-109, Austin, TX, 2016. SciPy.
#
# N. Michaud-Agrawal, E. J. Denning, T. B. Woolf, and O. Beckstein.
# MDAnalysis: A Toolkit for the Analysis of Molecular Dynamics Simulations.
# J. Comput. Chem. 32 (2011), 2319--2327, doi:10.1002/jcc.21787
#

"""\
Topology attribute objects --- :mod:`MDAnalysis.core.topologyattrs`
===================================================================

Common :class:`TopologyAttr` instances that are used by most topology
parsers.

TopologyAttrs are used to contain attributes such as atom names or resids.
These are usually read by the TopologyParser.
"""

from six.moves import zip, range
from collections import defaultdict
import itertools
import numpy as np

from . import flags
from ..lib.util import cached, convert_aa_code
from ..lib import transformations, mdamath
from ..exceptions import NoDataError, SelectionError
from .topologyobjects import TopologyGroup
from . import selection
from .groups import (GroupBase, Atom, Residue, Segment,
                     AtomGroup, ResidueGroup, SegmentGroup)

_LENGTH_VALUEERROR = ("Setting {group} with wrong sized array. "
                      "Length {group}: {lengroup}, length values: {lenvalues}")


class TopologyAttr(object):
    """Base class for Topology attributes.

    .. note::   This class is intended to be subclassed, and mostly amounts to
                a skeleton. The methods here should be present in all
                :class:`TopologyAttr` child classes, but by default they raise
                appropriate exceptions.

    Attributes
    ----------
    attrname : str
        the name used for the attribute when attached to a ``Topology`` object
    singular : str
        name for the attribute on a singular object (Atom/Residue/Segment)
    per_object : str
        If there is a strict mapping between Component and Attribute
    top : Topology
        handle for the Topology object TopologyAttr is associated with

    """
    attrname = 'topologyattrs'
    singular = 'topologyattr'
    per_object = None  # ie Resids per_object = 'residue'
    top = None  # pointer to Topology object

    groupdoc = None
    singledoc = None

    def __init__(self, values, guessed=False):
        self.values = values
        self._guessed = guessed

    def __len__(self):
        """Length of the TopologyAttr at its intrinsic level."""
        return len(self.values)

    def __getitem__(self, group):
        """Accepts an AtomGroup, ResidueGroup or SegmentGroup"""
        if isinstance(group, (Atom, AtomGroup)):
            return self.get_atoms(group)
        elif isinstance(group, (Residue, ResidueGroup)):
            return self.get_residues(group)
        elif isinstance(group, (Segment, SegmentGroup)):
            return self.get_segments(group)

    def __setitem__(self, group, values):
        if isinstance(group, (Atom, AtomGroup)):
            return self.set_atoms(group, values)
        elif isinstance(group, (Residue, ResidueGroup)):
            return self.set_residues(group, values)
        elif isinstance(group, (Segment, SegmentGroup)):
            return self.set_segments(group, values)

    @property
    def is_guessed(self):
        """Bool of if the source of this information is a guess"""
        return self._guessed

    def get_atoms(self, ag):
        """Get atom attributes for a given AtomGroup"""
        # aix = ag.indices
        raise NoDataError

    def set_atoms(self, ag, values):
        """Set atom attributes for a given AtomGroup"""
        raise NotImplementedError

    def get_residues(self, rg):
        """Get residue attributes for a given ResidueGroup"""
        raise NoDataError

    def set_residues(self, rg, values):
        """Set residue attributes for a given ResidueGroup"""
        raise NotImplementedError

    def get_segments(self, sg):
        """Get segment attributes for a given SegmentGroup"""
        raise NoDataError

    def set_segments(self, sg, values):
        """Set segmentattributes for a given SegmentGroup"""
        raise NotImplementedError


# core attributes

class Atomindices(TopologyAttr):
    """Globally unique indices for each atom in the group.

    If the group is an AtomGroup, then this gives the index for each atom in
    the group. This is the unambiguous identifier for each atom in the
    topology, and it is not alterable.

    If the group is a ResidueGroup or SegmentGroup, then this gives the indices
    of each atom represented in the group in a 1-D array, in the order of the
    elements in that group.

    """
    attrname = 'indices'
    singular = 'index'
    target_classes = [Atom]

    def __init__(self):
        self._guessed = False

    def set_atoms(self, ag, values):
        raise AttributeError("Atom indices are fixed; they cannot be reset")

    def get_atoms(self, ag):
        return ag.ix

    def get_residues(self, rg):
        return list(self.top.tt.residues2atoms_2d(rg.ix))

    def get_segments(self, sg):
        return list(self.top.tt.segments2atoms_2d(sg.ix))


class Resindices(TopologyAttr):
    """Globally unique resindices for each residue in the group.

    If the group is an AtomGroup, then this gives the resindex for each atom in
    the group. This unambiguously determines each atom's residue membership.
    Resetting these values changes the residue membership of the atoms.

    If the group is a ResidueGroup or SegmentGroup, then this gives the
    resindices of each residue represented in the group in a 1-D array, in the
    order of the elements in that group.

    """
    attrname = 'resindices'
    singular = 'resindex'
    target_classes = [Atom, Residue]

    def __init__(self):
        self._guessed = False

    def get_atoms(self, ag):
        return self.top.tt.atoms2residues(ag.ix)

    def get_residues(self, rg):
        return rg.ix

    def set_residues(self, rg, values):
        raise AttributeError("Residue indices are fixed; they cannot be reset")

    def get_segments(self, sg):
        return list(self.top.tt.segments2residues_2d(sg.ix))


class Segindices(TopologyAttr):
    """Globally unique segindices for each segment in the group.

    If the group is an AtomGroup, then this gives the segindex for each atom in
    the group. This unambiguously determines each atom's segment membership.
    It is not possible to set these, since membership in a segment is an
    attribute of each atom's residue.

    If the group is a ResidueGroup or SegmentGroup, then this gives the
    segindices of each segment represented in the group in a 1-D array, in the
    order of the elements in that group.

    """
    attrname = 'segindices'
    singular = 'segindex'
    target_classes = [Atom, Residue, Segment]

    def __init__(self):
        self._guessed = False

    def get_atoms(self, ag):
        return self.top.tt.atoms2segments(ag.ix)

    def get_residues(self, rg):
        return self.top.tt.residues2segments(rg.ix)

    def get_segments(self, sg):
        return sg.ix

    def set_segments(self, sg, values):
        raise AttributeError("Segment indices are fixed; they cannot be reset")


# atom attributes

class AtomAttr(TopologyAttr):
    """Base class for atom attributes.

    """
    attrname = 'atomattrs'
    singular = 'atomattr'
    target_classes = [Atom]

    def get_atoms(self, ag):
        return self.values[ag.ix]

    def set_atoms(self, ag, values):
        self.values[ag.ix] = values

    def get_residues(self, rg):
        """By default, the values for each atom present in the set of residues
        are returned in a single array. This behavior can be overriden in child
        attributes.

        """
        aixs = self.top.tt.residues2atoms_2d(rg.ix)
        return [self.values[aix] for aix in aixs]

    def get_segments(self, sg):
        """By default, the values for each atom present in the set of residues
        are returned in a single array. This behavior can be overriden in child
        attributes.

        """
        aixs = self.top.tt.segments2atoms_2d(sg.ix)
        return [self.values[aix] for aix in aixs]


# TODO: update docs to property doc
class Atomids(AtomAttr):
    """ID for each atom.
    """
    attrname = 'ids'
    singular = 'id'
    per_object = 'atom'


# TODO: update docs to property doc
class Atomnames(AtomAttr):
    """Name for each atom.
    """
    attrname = 'names'
    singular = 'name'
    per_object = 'atom'
    transplants = defaultdict(list)

    def getattr__(atomgroup, name):
        try:
            return atomgroup._get_named_atom(name)
        except selection.SelectionError:
            raise AttributeError("'{0}' object has no attribute '{1}'".format(
                    atomgroup.__class__.__name__, name))

    def _get_named_atom(group, name):
        """Get all atoms with name *name* in the current AtomGroup.

        For more than one atom it returns a list of :class:`Atom`
        instance. A single :class:`Atom` is returned just as such. If
        no atoms are found, a :exc:`SelectionError` is raised.

        .. versionadded:: 0.9.2
        """
        # There can be more than one atom with the same name
        atomlist = group.atoms.unique[group.atoms.unique.names == name]
        if len(atomlist) == 0:
            raise selection.SelectionError(
                "No atoms with name '{0}'".format(name))
        elif len(atomlist) == 1:
            # XXX: keep this, makes more sense for names
            return atomlist[0]
        else:
            # XXX: but inconsistent (see residues and Issue 47)
            return atomlist

    # AtomGroup already has a getattr
#    transplants[AtomGroup].append(
#        ('__getattr__', getattr__))

    transplants[Residue].append(
        ('__getattr__', getattr__))

    # this is also getitem for a residue
    transplants[Residue].append(
        ('__getitem__', getattr__))

    transplants[AtomGroup].append(
        ('_get_named_atom', _get_named_atom))

    transplants[Residue].append(
        ('_get_named_atom', _get_named_atom))

    def phi_selection(residue):
        """AtomGroup corresponding to the phi protein backbone dihedral
        C'-N-CA-C.

        Returns
        -------
        AtomGroup
            4-atom selection in the correct order. If no C' found in the
            previous residue (by resid) then this method returns ``None``.
        """
        # TODO: maybe this can be reformulated into one selection string without
        # the additions later
        sel_str = "segid {} and resid {} and name C".format(
            residue.segment.segid, residue.resid - 1)
        sel = residue.universe.select_atoms(sel_str) + \
            residue['N'] + residue['CA'] + residue['C']

        # select_atoms doesnt raise errors if nothing found, so check size
        if len(sel) == 4:
            return sel
        else:
            return None

    transplants[Residue].append(('phi_selection', phi_selection))

    def psi_selection(residue):
        """AtomGroup corresponding to the psi protein backbone dihedral
        N-CA-C-N'.

        Returns
        -------
        AtomGroup
            4-atom selection in the correct order. If no N' found in the
            following residue (by resid) then this method returns ``None``.
        """
        sel_str = "segid {} and resid {} and name N".format(
            residue.segment.segid, residue.resid + 1)

        sel = residue['N'] + residue['CA'] + residue['C'] + \
            residue.universe.select_atoms(sel_str)

        if len(sel) == 4:
            return sel
        else:
            return None

    transplants[Residue].append(('psi_selection', psi_selection))

    def omega_selection(residue):
        """AtomGroup corresponding to the omega protein backbone dihedral
        CA-C-N'-CA'.

        omega describes the -C-N- peptide bond. Typically, it is trans (180
        degrees) although cis-bonds (0 degrees) are also occasionally observed
        (especially near Proline).

        Returns
        -------
        AtomGroup
            4-atom selection in the correct order. If no C' found in the
            previous residue (by resid) then this method returns ``None``.

        """
        nextres = residue.resid + 1
        segid = residue.segment.segid
        sel = residue['CA'] + residue['C'] + \
              residue.universe.select_atoms(
                  'segid %s and resid %d and name N' % (segid, nextres),
                  'segid %s and resid %d and name CA' % (segid, nextres))
        if len(sel) == 4:
            return sel
        else:
            return None

    transplants[Residue].append(('omega_selection', omega_selection))

    def chi1_selection(residue):
        """AtomGroup corresponding to the chi1 sidechain dihedral N-CA-CB-CG.

        Returns
        -------
        AtomGroup
            4-atom selection in the correct order. If no CB and/or CG is found
            then this method returns ``None``.

        .. versionadded:: 0.7.5
        """
        try:
            return residue['N'] + residue['CA'] + residue['CB'] + residue['CG']
        except AttributeError:
            return None

    transplants[Residue].append(('chi1_selection', chi1_selection))


# TODO: update docs to property doc
class Atomtypes(AtomAttr):
    """Type for each atom"""
    attrname = 'types'
    singular = 'type'
    per_object = 'atom'


# TODO: update docs to property doc
class Elements(AtomAttr):
    """Element for each atom"""
    attrname = 'elements'
    singular = 'element'


# TODO: update docs to property doc
class Radii(AtomAttr):
    """Radii for each atom"""
    attrname = 'radii'
    singular = 'radius'
    per_object = 'atom'


class ChainIDs(AtomAttr):
    """ChainID per atom

    Note
    ----
    This is an attribute of the Atom, not Residue or Segment
    """
    attrname = 'chainIDs'
    singular = 'chainID'
    per_object = 'atom'


class Tempfactors(AtomAttr):
    """Tempfactor for atoms"""
    attrname = 'tempfactors'
    singular = 'tempfactor'
    per_object = 'atom'


class Masses(AtomAttr):
    attrname = 'masses'
    singular = 'mass'
    per_object = 'atom'
    target_classes = [Atom, Residue, Segment]
    transplants = defaultdict(list)

    groupdoc = """Mass of each component in the Group.

    If the Group is an AtomGroup, then the masses are for each atom. If the
    Group is a ResidueGroup or SegmentGroup, the masses are for each residue or
    segment, respectively. These are obtained by summation of the member atoms
    for each component.
    """

    singledoc = """Mass of the component."""

    def __init__(self, values, guessed=False):
        self.values = np.asarray(values, dtype=np.float64)
        self._guessed = guessed

    def get_residues(self, rg):
        resatoms = self.top.tt.residues2atoms_2d(rg.ix)

        if isinstance(rg.ix, int):
            # for a single residue
            masses = self.values[resatoms].sum()
        else:
            # for a residuegroup
            masses = np.empty(len(rg))
            for i, row in enumerate(resatoms):
                masses[i] = self.values[row].sum()

        return masses

    def get_segments(self, sg):
        segatoms = self.top.tt.segments2atoms_2d(sg.ix)

        if isinstance(sg.ix, int):
            # for a single segment
            masses = self.values[segatoms].sum()
        else:
            # for a segmentgroup
            masses = np.array([self.values[row].sum() for row in segatoms])

        return masses

    def center_of_mass(group, pbc=None):
        """Center of mass of the Group.

        Parameters
        ----------
        pbc : bool, optional
            If ``True``, move all atoms within the primary unit cell before
            calculation. [``False``]

        Returns
        -------
        center : ndarray
            center of group given masses as weights

        Notes
        -----
            The :class:`MDAnalysis.core.flags` flag *use_pbc* when set to
            ``True`` allows the *pbc* flag to be used by default.

        .. versionchanged:: 0.8 Added `pbc` parameter
        """
        return group.atoms.center(weights=group.atoms.masses,
                                  pbc=pbc)

    transplants[GroupBase].append(
        ('center_of_mass', center_of_mass))

    def total_mass(group):
        """Total mass of the Group.

        """
        return group.masses.sum()

    transplants[GroupBase].append(
        ('total_mass', total_mass))

    def moment_of_inertia(group, **kwargs):
        """Tensor moment of inertia relative to center of mass as 3x3 numpy
        array.

        Parameters
        ----------
        pbc : bool, optional
            If ``True``, move all atoms within the primary unit cell before
            calculation. [``False``]

        .. note::
            The :class:`MDAnalysis.core.flags` flag *use_pbc* when set to
            ``True`` allows the *pbc* flag to be used by default.

        .. versionchanged:: 0.8 Added *pbc* keyword
        """
        atomgroup = group.atoms
        pbc = kwargs.pop('pbc', flags['use_pbc'])

        # Convert to local coordinates
        com = atomgroup.center_of_mass(pbc=pbc)
        if pbc:
            pos = atomgroup.pack_into_box(inplace=False) - com
        else:
            pos = atomgroup.positions - com

        masses = atomgroup.masses
        # Create the inertia tensor
        # m_i = mass of atom i
        # (x_i, y_i, z_i) = pos of atom i
        # Ixx = sum(m_i*(y_i^2+z_i^2));
        # Iyy = sum(m_i*(x_i^2+z_i^2));
        # Izz = sum(m_i*(x_i^2+y_i^2))
        # Ixy = Iyx = -1*sum(m_i*x_i*y_i)
        # Ixz = Izx = -1*sum(m_i*x_i*z_i)
        # Iyz = Izy = -1*sum(m_i*y_i*z_i)
        tens = np.zeros((3, 3), dtype=np.float64)
        # xx
        tens[0][0] = (masses * (pos[:, 1] ** 2 + pos[:, 2] ** 2)).sum()
        # xy & yx
        tens[0][1] = tens[1][0] = - (masses * pos[:, 0] * pos[:, 1]).sum()
        # xz & zx
        tens[0][2] = tens[2][0] = - (masses * pos[:, 0] * pos[:, 2]).sum()
        # yy
        tens[1][1] = (masses * (pos[:, 0] ** 2 + pos[:, 2] ** 2)).sum()
        # yz + zy
        tens[1][2] = tens[2][1] = - (masses * pos[:, 1] * pos[:, 2]).sum()
        # zz
        tens[2][2] = (masses * (pos[:, 0] ** 2 + pos[:, 1] ** 2)).sum()

        return tens

    transplants[GroupBase].append(
        ('moment_of_inertia', moment_of_inertia))

    def radius_of_gyration(group, **kwargs):
        """Radius of gyration.

        Parameters
        ----------
        pbc : bool, optional
            If ``True``, move all atoms within the primary unit cell before
            calculation. [``False``]

        .. note::
            The :class:`MDAnalysis.core.flags` flag *use_pbc* when set to
            ``True`` allows the *pbc* flag to be used by default.

        .. versionchanged:: 0.8 Added *pbc* keyword
        """
        atomgroup = group.atoms
        pbc = kwargs.pop('pbc', flags['use_pbc'])
        masses = atomgroup.masses

        com = atomgroup.center_of_mass(pbc=pbc)
        if pbc:
            recenteredpos = atomgroup.pack_into_box(inplace=False) - com
        else:
            recenteredpos = atomgroup.positions - com

        rog_sq = np.sum(masses * np.sum(recenteredpos**2,
                                        axis=1)) / atomgroup.total_mass()

        return np.sqrt(rog_sq)

    transplants[GroupBase].append(
        ('radius_of_gyration', radius_of_gyration))

    def shape_parameter(group, **kwargs):
        """Shape parameter.

        See [Dima2004]_ for background information.

        Parameters
        ----------
        pbc : bool, optional
            If ``True``, move all atoms within the primary unit cell before
            calculation. [``False``]

        .. note::
            The :class:`MDAnalysis.core.flags` flag *use_pbc* when set to
            ``True`` allows the *pbc* flag to be used by default.

        .. [Dima2004] Dima, R. I., & Thirumalai, D. (2004). Asymmetry in the
                  shapes of folded and denatured states of proteins. *J
                  Phys Chem B*, 108(21),
                  6564-6570. doi:`10.1021/jp037128y`_

        .. versionadded:: 0.7.7
        .. versionchanged:: 0.8 Added *pbc* keyword
        """
        atomgroup = group.atoms
        pbc = kwargs.pop('pbc', flags['use_pbc'])
        masses = atomgroup.masses

        com = atomgroup.center_of_mass(pbc=pbc)
        if pbc:
            recenteredpos = atomgroup.pack_into_box(inplace=False) - com
        else:
            recenteredpos = atomgroup.positions - com
        tensor = np.zeros((3, 3))

        for x in range(recenteredpos.shape[0]):
            tensor += masses[x] * np.outer(recenteredpos[x, :],
                                           recenteredpos[x, :])
        tensor /= atomgroup.total_mass()
        eig_vals = np.linalg.eigvalsh(tensor)
        shape = 27.0 * np.prod(eig_vals - np.mean(eig_vals)) / np.power(np.sum(eig_vals), 3)

        return shape

    transplants[GroupBase].append(
        ('shape_parameter', shape_parameter))

    def asphericity(group, pbc=None):
        """Asphericity.

        See [Dima2004]_ for background information.

        Parameters
        ----------
        pbc : bool, optional
            If ``True``, move all atoms within the primary unit cell before
            calculation. If ``None`` use value defined in
            MDAnalysis.core.flags['use_pbc']

        .. note::
            The :class:`MDAnalysis.core.flags` flag *use_pbc* when set to
            ``True`` allows the *pbc* flag to be used by default.

        .. [Dima2004] Dima, R. I., & Thirumalai, D. (2004). Asymmetry in the
                  shapes of folded and denatured states of proteins. *J
                  Phys Chem B*, 108(21),
                  6564-6570. doi:`10.1021/jp037128y`_

        .. versionadded:: 0.7.7
        .. versionchanged:: 0.8 Added *pbc* keyword
        """
        atomgroup = group.atoms
        if pbc is None:
            pbc = flags['use_pbc']
        masses = atomgroup.masses

        if pbc:
            recenteredpos = (atomgroup.pack_into_box(inplace=False) -
                             atomgroup.center_of_mass(pbc=True))
        else:
            recenteredpos = (atomgroup.positions -
                             atomgroup.center_of_mass(pbc=False))

        tensor = np.zeros((3, 3))
        for x in range(recenteredpos.shape[0]):
            tensor += masses[x] * np.outer(recenteredpos[x],
                                           recenteredpos[x])

        tensor /= atomgroup.total_mass()
        eig_vals = np.linalg.eigvalsh(tensor)
        shape = (3.0 / 2.0) * (np.sum((eig_vals - np.mean(eig_vals))**2) /
                               np.sum(eig_vals)**2)

        return shape

    transplants[GroupBase].append(
        ('asphericity', asphericity))

    def principal_axes(group, pbc=None):
        """Calculate the principal axes from the moment of inertia.

        e1,e2,e3 = AtomGroup.principal_axes()

        The eigenvectors are sorted by eigenvalue, i.e. the first one
        corresponds to the highest eigenvalue and is thus the first principal
        axes.

        Parameters
        ----------
        pbc : bool, optional
            If ``True``, move all atoms within the primary unit cell before
            calculation. If ``None`` use value defined in setup flags.

        .. note::
            The :class:`MDAnalysis.core.flags` flag *use_pbc* when set to
            ``True`` allows the *pbc* flag to be used by default.

        Returns
        -------
        axis_vectors : array
            3 x 3 array with ``v[0]`` as first, ``v[1]`` as second, and
            ``v[2]`` as third eigenvector.

        .. versionchanged:: 0.8 Added *pbc* keyword

        """
        atomgroup = group.atoms
        if pbc is None:
            pbc = flags['use_pbc']
        e_val, e_vec = np.linalg.eig(atomgroup.moment_of_inertia(pbc=pbc))

        # Sort
        indices = np.argsort(e_val)
        # Return transposed in more logical form. See Issue 33.
        return e_vec[:, indices].T

    transplants[GroupBase].append(
        ('principal_axes', principal_axes))

    def align_principal_axis(group, axis, vector):
        """Align principal axis with index `axis` with `vector`.

        Parameters
        ----------
        axis : {0, 1, 2}
            Index of the principal axis (0, 1, or 2), as produced by
            :meth:`~principal_axes`.
        vector : array_like
            Vector to align principal axis with.

        Notes
        -----
        To align the long axis of a channel (the first principal axis, i.e.
        *axis* = 0) with the z-axis::

          u.atoms.align_principal_axis(0, [0,0,1])
          u.atoms.write("aligned.pdb")
        """
        p = group.principal_axes()[axis]
        angle = np.degrees(mdamath.angle(p, vector))
        ax = transformations.rotaxis(p, vector)
        # print "principal[%d] = %r" % (axis, p)
        # print "axis = %r, angle = %f deg" % (ax, angle)
        return group.rotateby(angle, ax)

    transplants[GroupBase].append(
        ('align_principal_axis', align_principal_axis))


# TODO: update docs to property doc
class Charges(AtomAttr):
    attrname = 'charges'
    singular = 'charge'
    per_object = 'atom'
    target_classes = [Atom, Residue, Segment]
    transplants = defaultdict(list)

    def get_residues(self, rg):
        resatoms = self.top.tt.residues2atoms_2d(rg.ix)

        if isinstance(rg.ix, int):
            charges = self.values[resatoms].sum()
        else:
            charges = np.empty(len(rg))
            for i, row in enumerate(resatoms):
                charges[i] = self.values[row].sum()

        return charges

    def get_segments(self, sg):
        segatoms = self.top.tt.segments2atoms_2d(sg.ix)

        if isinstance(sg.ix, int):
            # for a single segment
            charges = self.values[segatoms].sum()
        else:
            # for a segmentgroup
            charges = np.array([self.values[row].sum() for row in segatoms])

        return charges

    def total_charge(group):
        """Total charge of the Group.

        """
        return group.charges.sum()

    transplants[GroupBase].append(
        ('total_charge', total_charge))


# TODO: update docs to property doc
class Bfactors(AtomAttr):
    """Crystallographic B-factors in A**2 for each atom"""
    attrname = 'bfactors'
    singular = 'bfactor'
    per_object = 'atom'


# TODO: update docs to property doc
class Occupancies(AtomAttr):
    attrname = 'occupancies'
    singular = 'occupancy'
    per_object = 'atom'


# TODO: update docs to property doc
class AltLocs(AtomAttr):
    """AltLocs for each atom"""
    attrname = 'altLocs'
    singular = 'altLoc'
    per_object = 'atom'


# residue attributes

class ResidueAttr(TopologyAttr):
    """Base class for Topology attributes.

    .. note::   This class is intended to be subclassed, and mostly amounts to
                a skeleton. The methods here should be present in all
                :class:`TopologyAttr` child classes, but by default they raise
                appropriate exceptions.

    """
    attrname = 'residueattrs'
    singular = 'residueattr'
    target_classes = [Residue]
    per_object = 'residue'

    def get_atoms(self, ag):
        rix = self.top.tt.atoms2residues(ag.ix)
        return self.values[rix]

    def get_residues(self, rg):
        return self.values[rg.ix]

    def set_residues(self, rg, values):
        self.values[rg.ix] = values

    def get_segments(self, sg):
        """By default, the values for each residue present in the set of
        segments are returned in a single array. This behavior can be overriden
        in child attributes.

        """
        rixs = self.top.tt.segments2residues_2d(sg.ix)
        return [self.values[rix] for rix in rixs]


# TODO: update docs to property doc
class Resids(ResidueAttr):
    """Residue ID"""
    attrname = 'resids'
    singular = 'resid'
    target_classes = [Atom, Residue]


# TODO: update docs to property doc
class Resnames(ResidueAttr):
    attrname = 'resnames'
    singular = 'resname'
    target_classes = [Atom, Residue]
    transplants = defaultdict(list)

    def getattr__(residuegroup, resname):
        try:
            return residuegroup._get_named_residue(resname)
        except selection.SelectionError:
            raise AttributeError("'{0}' object has no attribute '{1}'".format(
                    residuegroup.__class__.__name__, resname))

    transplants[ResidueGroup].append(('__getattr__', getattr__))
    # This transplant is hardcoded for now to allow for multiple getattr things
    #transplants[Segment].append(('__getattr__', getattr__))

    def _get_named_residue(group, resname):
        """Get all residues with name *resname* in the current ResidueGroup
        or Segment.

        For more than one residue it returns a
        :class:`MDAnalysis.core.groups.ResidueGroup` instance. A single
        :class:`MDAnalysis.core.group.Residue` is returned for a single match.
        If no residues are found, a :exc:`SelectionError` is raised.

        .. versionadded:: 0.9.2

        """
        # There can be more than one residue with the same name
        residues = group.residues.unique[
                group.residues.unique.resnames == resname]
        if len(residues) == 0:
            raise selection.SelectionError(
                "No residues with resname '{0}'".format(resname))
        elif len(residues) == 1:
            # XXX: keep this, makes more sense for names
            return residues[0]
        else:
            # XXX: but inconsistent (see residues and Issue 47)
            return residues

    transplants[ResidueGroup].append(
        ('_get_named_residue', _get_named_residue))

    def sequence(self, **kwargs):
        """Returns the amino acid sequence.

        The format of the sequence is selected with the keyword *format*:

        ============== ============================================
        *format*       description
        ============== ============================================
        'SeqRecord'    :class:`Bio.SeqRecord.SeqRecord` (default)
        'Seq'          :class:`Bio.Seq.Seq`
        'string'       string
        ============== ============================================

        The sequence is returned by default (keyword ``format = 'SeqRecord'``)
        as a :class:`Bio.SeqRecord.SeqRecord` instance, which can then be
        further processed. In this case, all keyword arguments (such as the
        *id* string or the *name* or the *description*) are directly passed to
        :class:`Bio.SeqRecord.SeqRecord`.

        If the keyword *format* is set to ``'Seq'``, all *kwargs* are ignored
        and a :class:`Bio.Seq.Seq` instance is returned. The difference to the
        record is that the record also contains metadata and can be directly
        used as an input for other functions in :mod:`Bio`.

        If the keyword *format* is set to ``'string'``, all *kwargs* are
        ignored and a Python string is returned.

        .. rubric:: Example: Write FASTA file

        Use :func:`Bio.SeqIO.write`, which takes sequence records::

           import Bio.SeqIO

           # get the sequence record of a protein component of a Universe
           protein = u.select_atoms("protein")
           record = protein.sequence(id="myseq1", name="myprotein")

           Bio.SeqIO.write(record, "single.fasta", "fasta")

        A FASTA file with multiple entries can be written with ::

           Bio.SeqIO.write([record1, record2, ...], "multi.fasta", "fasta")

        :Keywords:
            *format*

                - ``"string"``: return sequence as a string of 1-letter codes
                - ``"Seq"``: return a :class:`Bio.Seq.Seq` instance
                - ``"SeqRecord"``: return a :class:`Bio.SeqRecord.SeqRecord`
                  instance

                Default is ``"SeqRecord"``

             *id*
                Sequence ID for SeqRecord (should be different for different
                sequences)
             *name*
                Name of the protein.
             *description*
                Short description of the sequence.
             *kwargs*
                Any other keyword arguments that are understood by
                :class:`Bio.SeqRecord.SeqRecord`.

        :Raises: :exc:`ValueError` if a residue name cannot be converted to a
                 1-letter IUPAC protein amino acid code; make sure to only
                 select protein residues. Raises :exc:`TypeError` if an unknown
                 *format* is selected.

        .. versionadded:: 0.9.0
        """
        import Bio.Seq
        import Bio.SeqRecord
        import Bio.Alphabet
        formats = ('string', 'Seq', 'SeqRecord')

        format = kwargs.pop("format", "SeqRecord")
        if format not in formats:
            raise TypeError("Unknown format='{0}': must be one of: {1}".format(
                    format, ", ".join(formats)))
        try:
            sequence = "".join([convert_aa_code(r) for r in self.residues.resnames])
        except KeyError as err:
            raise ValueError("AtomGroup contains a residue name '{0}' that "
                             "does not have a IUPAC protein 1-letter "
                             "character".format(err.message))
        if format == "string":
            return sequence
        seq = Bio.Seq.Seq(sequence, alphabet=Bio.Alphabet.IUPAC.protein)
        if format == "Seq":
            return seq
        return Bio.SeqRecord.SeqRecord(seq, **kwargs)

    transplants[ResidueGroup].append(
        ('sequence', sequence))


# TODO: update docs to property doc
class Resnums(ResidueAttr):
    attrname = 'resnums'
    singular = 'resnum'
    target_classes = [Atom, Residue]


class ICodes(ResidueAttr):
    """Insertion code for Atoms"""
    attrname = 'icodes'
    singular = 'icode'


# segment attributes

class SegmentAttr(TopologyAttr):
    """Base class for segment attributes.

    """
    attrname = 'segmentattrs'
    singular = 'segmentattr'
    target_classes = [Segment]
    per_object = 'segment'

    def get_atoms(self, ag):
        six = self.top.tt.atoms2segments(ag.ix)
        return self.values[six]

    def get_residues(self, rg):
        six = self.top.tt.residues2segments(rg.ix)
        return self.values[six]

    def get_segments(self, sg):
        return self.values[sg.ix]

    def set_segments(self, sg, values):
        self.values[sg.ix] = values


# TODO: update docs to property doc
class Segids(SegmentAttr):
    attrname = 'segids'
    singular = 'segid'
    target_classes = [Atom, Residue, Segment]
    transplants = defaultdict(list)

    def getattr__(segmentgroup, segid):
        try:
            return segmentgroup._get_named_segment(segid)
        except selection.SelectionError:
            raise AttributeError("'{0}' object has no attribute '{1}'".format(
                    segmentgroup.__class__.__name__, segid))

    transplants[SegmentGroup].append(
        ('__getattr__', getattr__))

    def _get_named_segment(group, segid):
        """Get all segments with name *segid* in the current SegmentGroup.

        For more than one residue it returns a
        :class:`MDAnalysis.core.groups.SegmentGroup` instance. A single
        :class:`MDAnalysis.core.group.Segment` is returned for a single match.
        If no residues are found, a :exc:`SelectionError` is raised.

        .. versionadded:: 0.9.2

        """
        # Undo adding 's' if segid started with digit
        if segid.startswith('s') and len(segid) >= 2 and segid[1].isdigit():
            segid = segid[1:]

        # There can be more than one segment with the same name
        segments = group.segments.unique[
                group.segments.unique.segids == segid]
        if len(segments) == 0:
            raise selection.SelectionError(
                "No segments with segid '{0}'".format(segid))
        elif len(segments) == 1:
            # XXX: keep this, makes more sense for names
            return segments[0]
        else:
            # XXX: but inconsistent (see residues and Issue 47)
            return segments

    transplants[SegmentGroup].append(
        ('_get_named_segment', _get_named_segment))


class _Connection(AtomAttr):
    """Base class for connectivity between atoms"""
    def __init__(self, values, types=None, guessed=False, order=None):
        self.values = list(values)
        if types is None:
            types = [None] * len(values)
        self.types = types
        if guessed in (True, False):
            # if single value passed, multiply this across
            # all bonds
            guessed = [guessed] * len(values)
        self._guessed = guessed
        if order is None:
            order = [None] * len(values)
        self.order = order
        self._cache = dict()

    def __len__(self):
        return len(self._bondDict)

    @property
    @cached('bd')
    def _bondDict(self):
        """Lazily built mapping of atoms:bonds"""
        bd = defaultdict(list)

        for b, t, g, o in zip(self.values, self.types,
                              self._guessed, self.order):
            # We always want the first index
            # to be less than the last
            # eg (0, 1) not (1, 0)
            # and (4, 10, 8) not (8, 10, 4)
            if b[0] > b[-1]:
                b = b[::-1]
            for a in b:
                bd[a].append((b, t, g, o))
        return bd

    def get_atoms(self, ag):
        try:
            unique_bonds = set(itertools.chain(
                *[self._bondDict[a] for a in ag.ix]))
        except TypeError:
            # maybe we got passed an Atom
            unique_bonds = self._bondDict[ag.ix]
        bond_idx, types, guessed, order = np.hsplit(
            np.array(sorted(unique_bonds)), 4)
        bond_idx = np.array(bond_idx.ravel().tolist(), dtype=np.int32)
        types = types.ravel()
        guessed = guessed.ravel()
        order = order.ravel()
        return TopologyGroup(bond_idx, ag._u,
                             self.singular[:-1],
                             types,
                             guessed,
                             order)

    def add_bonds(self, values, types=None, guessed=True, order=None):
        if types is None:
            types = itertools.cycle((None,))
        if guessed in (True, False):
            guessed = itertools.cycle((guessed,))
        if order is None:
            order = itertools.cycle((None,))

        existing = set(self.values)
        for v, t, g, o in zip(values, types, guessed, order):
            if v not in existing:
                self.values.append(v)
                self.types.append(t)
                self._guessed.append(g)
                self.order.append(o)
        # kill the old cache of bond Dict
        try:
            del self._cache['bd']
        except KeyError:
            pass


class Bonds(_Connection):
    """Bonds between two atoms

    Must be initialised by a list of zero based tuples.
    These indices refer to the atom indices.
        Eg:  [(0, 1), (1, 2), (2, 3)]

    Also adds the `bonded_atoms`, `fragment` and `fragments`
    attributes.
    """
    attrname = 'bonds'
    # Singular is the same because one Atom might have
    # many bonds, so still asks for "bonds" in the plural
    singular = 'bonds'
    transplants = defaultdict(list)

    def bonded_atoms(self):
        """An AtomGroup of all atoms bonded to this Atom"""
        idx = [b.partner(self).index for b in self.bonds]
        return self._u.atoms[idx]

    transplants[Atom].append(
        ('bonded_atoms', property(bonded_atoms, None, None,
                                  bonded_atoms.__doc__)))

    def fragment(self):
        """The fragment that this Atom is part of

        .. versionadded:: 0.9.0
        """
        return self.universe._fragdict[self]

    def fragments(self):
        """Read-only list of fragments.

        Contains all fragments that any Atom in this AtomGroup is
        part of, the contents of the fragments may extend beyond the
        contents of this AtomGroup.

        .. versionadded 0.9.0
        """
        return tuple(sorted(
            set(a.fragment for a in self),
            key=lambda x: x[0].index
        ))

    transplants[Atom].append(
        ('fragment', property(fragment, None, None,
                              fragment.__doc__)))

    transplants[AtomGroup].append(
        ('fragments', property(fragments, None, None,
                               fragments.__doc__)))


class Angles(_Connection):
    """Angles between three atoms

    Initialise with a list of 3 long tuples
    Eg:
      [(0, 1, 2), (1, 2, 3), (2, 3, 4)]

    These indices refer to the atom indices.
    """
    attrname = 'angles'
    singular = 'angles'
    transplants = defaultdict(list)


class Dihedrals(_Connection):
    """A connection between four sequential atoms"""
    attrname = 'dihedrals'
    singular = 'dihedrals'
    transplants = defaultdict(list)


class Impropers(_Connection):
    """An imaginary dihedral between four atoms"""
    attrname = 'impropers'
    singular = 'impropers'
    transplants = defaultdict(list)
