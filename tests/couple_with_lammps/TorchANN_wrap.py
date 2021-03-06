#!/usr/bin/env python

# ----------------------------------------------------------------------
# LAMMPS - Large-scale Atomic/Molecular Massively Parallel Simulator
# http://lammps.sandia.gov, Sandia National Laboratories
# Steve Plimpton, sjplimp@sandia.gov
# ----------------------------------------------------------------------

# Syntax: vasp_wrap.py file/zmq POSCARfile

# wrapper on VASP to act as server program using CSlib
#   receives message with list of coords from client
#   creates VASP inputs
#   invokes VASP to calculate self-consistent energy of that config
#   reads VASP outputs
#   sends message with energy, forces, pressure to client

# NOTES:
# check to insure basic VASP input files are in place?
# could archive VASP input/output in special filenames or dirs?
# need to check that POTCAR file is consistent with atom ordering?
# could make syntax for launching VASP more flexible
#   e.g. command-line arg for # of procs
# detect if VASP had an error and return ERROR field, e.g. non-convergence ??

from __future__ import print_function
import sys

version = sys.version_info[0]
if version == 3:
  sys.exit("The CSlib python wrapper does not yet support python 3")
  
import subprocess
import xml.etree.ElementTree as ET
from cslib import CSlib
import numpy as np
import os

# comment out 2nd line once 1st line is correct for your system

#torchanncmd  = "srun -N 1 --ntasks-per-node=4 " + \
#          "-n 4 /projects/vasp/2017-build/cts1/vasp5.4.4/vasp_tfermi/bin/vasp_std"
torchanncmd  = "/home/aurora/Documents/Study/Machine_Learning/DeePMD_torch/single_prec_for_coord/c_single/GENERATE_P;" + \
          "/home/aurora/Documents/Study/Machine_Learning/DeePMD_torch/single_prec_for_coord/python_single_train/" + \
          "no_mpi/predict_noclassify_nompi.py"
#torchanncmd  = "touch tmp"

# enums matching FixClientMD class in LAMMPS

SETUP,STEP = range(1,2+1)
DIM,PERIODICITY,ORIGIN,BOX,NATOMS,NTYPES,TYPES,COORDS,UNITS,CHARGE = range(1,10+1)
FORCES,ENERGY,VIRIAL,ERROR = range(1,4+1)

# -------------------------------------
# functions

# error message and exit

def error(txt):
  print("ERROR:",txt)
  sys.exit(1)

# -------------------------------------
# read initial VASP POSCAR file to setup problem
# return natoms,ntypes,box

def vasp_setup(poscar):

  ps = open(poscar,'r').readlines()

  # box size

  words = ps[2].split()
  xbox = float(words[0])
  words = ps[3].split()
  ybox = float(words[1])
  words = ps[4].split()
  zbox = float(words[2])
  box = [xbox,ybox,zbox]

  ntypes = 0
  natoms = 0
  words = ps[6].split()
  for word in words:
    if word == '#': break
    ntypes += 1
    natoms += int(word)
  
  return natoms,ntypes,box
  
# -------------------------------------
# write a new POSCAR file for VASP

def poscar_write(poscar,natoms,ntypes,types,coords,box):

  psold = open(poscar,'r').readlines()
  psnew = open("POSCAR",'w')

  # header, including box size
  
  psnew.write(psold[0])
  psnew.write(psold[1])
  psnew.write("%g %g %g\n" % (box[0],box[1],box[2]))
  psnew.write("%g %g %g\n" % (box[3],box[4],box[5]))
  psnew.write("%g %g %g\n" % (box[6],box[7],box[8]))
  psnew.write(psold[5])
  psnew.write(psold[6])

  # per-atom coords
  # grouped by types

  psnew.write("Cartesian\n")

  for itype in range(1,ntypes+1):
    for i in range(natoms):
      if types[i] != itype: continue
      x = coords[3*i+0]
      y = coords[3*i+1]
      z = coords[3*i+2]
      aline = "  %g %g %g\n" % (x,y,z)
      psnew.write(aline)

  psnew.close()


def raw_write(natoms, ntypes, types, coords, box):

  np.savetxt("box.raw", np.array(box).reshape(1, -1), fmt="%10.6f")
  np.savetxt("coord.raw", np.array(coords).reshape(1, -1), fmt="%10.6f")
  typess=np.array(types)
  typess= -64 * typess + (79 + 64)#convert 1 to 79 and 2 to 15
  np.savetxt("type.raw", typess.reshape(1, -1), fmt="%5d")

  np.savetxt("force.raw", np.array(coords).reshape(1, -1), fmt="%10.6f")
  np.savetxt("energy.raw", np.ndarray(1), fmt="%10.6f")

# -------------------------------------
# read a VASP output vasprun.xml file
# uses ElementTree module
# see https://docs.python.org/2/library/xml.etree.elementtree.html

def vasprun_read():
  tree = ET.parse('vasprun.xml')
  root = tree.getroot()
  
  #fp = open("vasprun.xml","r")
  #root = ET.parse(fp)
  
  scsteps = root.findall('calculation/scstep')
  energy = scsteps[-1].find('energy')
  for child in energy:
    if child.attrib["name"] == "e_0_energy":
      eout = float(child.text)

  fout = []
  sout = []
  
  varrays = root.findall('calculation/varray')
  for varray in varrays:
    if varray.attrib["name"] == "forces":
      forces = varray.findall("v")
      for line in forces:
        fxyz = line.text.split()
        fxyz = [float(value) for value in fxyz]
        fout += fxyz
    if varray.attrib["name"] == "stress":
      tensor = varray.findall("v")
      stensor = []
      for line in tensor:
        sxyz = line.text.split()
        sxyz = [float(value) for value in sxyz]
        stensor.append(sxyz)
      sxx = stensor[0][0]
      syy = stensor[1][1]
      szz = stensor[2][2]
      # symmetrize off-diagonal components
      sxy = 0.5 * (stensor[0][1] + stensor[1][0])
      sxz = 0.5 * (stensor[0][2] + stensor[2][0])
      syz = 0.5 * (stensor[1][2] + stensor[2][1])
      sout = [sxx,syy,szz,sxy,sxz,syz]

  #fp.close()
  
  return eout,fout,sout

def torchannrun_read():
  os.system("head -n 1 PREDICT.OUT | awk '{print $8}' > E_tmp")
  eout_np = np.loadtxt("E_tmp")
  eout = eout_np.tolist()
  os.system("sed -n '/For/,/Str/p' PREDICT.OUT | sed '/For/d' | sed '/Str/d' > F_tmp")
  fout_np = np.loadtxt("F_tmp")
  fout_np = fout_np.reshape(-1,)
  fout = fout_np.tolist()
  os.system("grep Stress -A3 PREDICT.OUT | sed '/Str/d' > S_tmp")
  stensor = np.loadtxt("S_tmp").tolist()
  sxx = stensor[0][0]
  syy = stensor[1][1]
  szz = stensor[2][2]
  # symmetrize off-diagonal components
  sxy = 0.5 * (stensor[0][1] + stensor[1][0])
  sxz = 0.5 * (stensor[0][2] + stensor[2][0])
  syz = 0.5 * (stensor[1][2] + stensor[2][1])
  sout = [sxx, syy, szz, sxy, sxz, syz]


  return eout, fout, sout

# -------------------------------------
# main program

# command-line args

if len(sys.argv) != 2:
  print("Syntax: python TorchANN_wrap.py file/zmq")
  sys.exit(1)

mode = sys.argv[1]
#poscar_template = sys.argv[2]

if mode == "file": cs = CSlib(1,mode,"tmp.couple",None)
elif mode == "zmq": cs = CSlib(1,mode,"*:5555",None)
else:
  print("Syntax: python vasp_wrap.py file/zmq POSCARfile")
  sys.exit(1)

#natoms,ntypes,box = vasp_setup(poscar_template)

# initial message for MD protocol

msgID,nfield,fieldID,fieldtype,fieldlen = cs.recv()
if msgID != 0: error("Bad initial client/server handshake")
protocol = cs.unpack_string(1)
if protocol != "md": error("Mismatch in client/server protocol")
cs.send(0,0)

# endless server loop

while 1:

  # recv message from client
  # msgID = 0 = all-done message

  msgID,nfield,fieldID,fieldtype,fieldlen = cs.recv()
  if msgID < 0: break

  # SETUP receive at beginning of each run
  # required fields: DIM, PERIODICTY, ORIGIN, BOX, 
  #                  NATOMS, NTYPES, TYPES, COORDS
  # optional fields: others in enum above, but VASP ignores them

  if msgID == SETUP:
    
    origin = []
    box = []
    natoms_recv = ntypes_recv = 0
    types = []
    coords = []
    
    for field in fieldID:
      if field == DIM:
        dim = cs.unpack_int(DIM)
        if dim != 3: error("VASP only performs 3d simulations")
      elif field == PERIODICITY:
        periodicity = cs.unpack(PERIODICITY,1)
        if not periodicity[0] or not periodicity[1] or not periodicity[2]:
          error("VASP wrapper only currently supports fully periodic systems")
      elif field == ORIGIN:
        origin = cs.unpack(ORIGIN,1)
      elif field == BOX:
        box = cs.unpack(BOX,1)
      elif field == NATOMS:
        natoms_recv = cs.unpack_int(NATOMS)
        #if natoms != natoms_recv:
        #  error("VASP wrapper mis-match in number of atoms")
      elif field == NTYPES:
        ntypes_recv = cs.unpack_int(NTYPES)
        #if ntypes != ntypes_recv:
        #  error("VASP wrapper mis-match in number of atom types")
      elif field == TYPES:
        types = cs.unpack(TYPES,1)
      elif field == COORDS:
        coords = cs.unpack(COORDS,1)

    # if not origin or not box or not natoms or not ntypes or \
    #    not types or not coords:
    #   error("Required VASP wrapper setup field not received");

  # STEP receive at each timestep of run or minimization
  # required fields: COORDS
  # optional fields: ORIGIN, BOX

  elif msgID == STEP:

    coords = []
    
    for field in fieldID:
      if field == COORDS:
        coords = cs.unpack(COORDS,1)
      elif field == ORIGIN:
        origin = cs.unpack(ORIGIN,1)
      elif field == BOX:
        box = cs.unpack(BOX,1)
    
    if not coords: error("Required VASP wrapper step field not received");

  else: error("VASP wrapper received unrecognized message")
  
  # create POSCAR file
  
  #poscar_write(poscar_template,natoms_recv,ntypes_recv,types,coords,box)
  raw_write(natoms_recv, ntypes_recv, types, coords, box)

  # invoke VASP
  
  print("\nLaunching TorchANN ...")
  print(torchanncmd )
  subprocess.check_output(torchanncmd ,stderr=subprocess.STDOUT,shell=True)
  
  # process VASP output
    
  #energy,forces,virial = vasprun_read()
  energy, forces, virial = torchannrun_read()
  os.system("cat coord.raw >> coord_all.raw")
  os.system("cat box.raw >> box_all.raw")
  os.system("cat type.raw >> type_all.raw")
  energy_np = np.ndarray(1)
  energy_np[0] = energy
  f_energy_all = open("energy_all.raw", "a")
  np.savetxt(f_energy_all, energy_np, fmt="%10.6f")
  f_energy_all.close()
  forces_np = np.array(forces).reshape(1, -1)
  print(forces_np.shape)
  f_force_all = open("force_all.raw", "a")
  np.savetxt(f_force_all, forces_np, fmt="%10.6f")
  f_force_all.close()
  virial_np = np.array(virial).reshape(1, -1)
  f_virial_all = open("virial_all.raw", "a")
  print(virial_np.reshape(-1,))
  np.savetxt(f_virial_all, virial_np, fmt="%10.6f")
  f_virial_all.close()
  
  # convert VASP kilobars to bars

  for i,value in enumerate(virial): virial[i] *= 1000.0
    
  # return forces, energy, pressure to client
  
  cs.send(msgID,3);
  cs.pack(FORCES,4,3*natoms_recv,forces)
  cs.pack_double(ENERGY,energy)
  cs.pack(VIRIAL,4,6,virial)
  
# final reply to client
  
cs.send(0,0)

# clean-up

del cs
