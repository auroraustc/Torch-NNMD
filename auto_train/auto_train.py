#!/usr/bin/env python3

import os
import json
import numpy as np
import random
import math

DATA_PATH = "./data"
TORCHANN_CPP_EXE = " GENERATE_P "
TORCHANN_TRAIN = " train_noclassify_nompi.py "
TORCHANN_PREDICT = " predict_noclassify_nompi.py "
TORCHANN_PARAMS = " PARAMS.json "
LAMMPS_EXE = " lmp_intel_cpu_intelmpi "
LAMMPS_COMMAND = " -v mode file "
LAMMPS_INPUT = " in.clint.W "
LAMMPS_DATA = " data.W "
LASP_EXE = " lasp "
LASP_INPUT = "lasp.in"
LASP_DATA = "lasp.str"
VASP_EXE = " vasp_gpu_544 "
BACKGROUND_SYMBOL = " & "
LEFT_ARROW = " < "
PYTHON2 = " python2 "
PYTHON3 = " python3 "
TORCHAN_LAMMPS_WRAPER = " TorchANN_wrap.py file "
WAIT = " wait "
DATASET_DIR_PREFIX = "DATASET_"
EXPLORE_DIR_PREFIX = "EXPLORE_"
DFT_DIR_PREFIX = "DFT_"
SCRIPTS_PATH = "../"


class auto_train_parameters():
    def __init__(self):
        total_loop = 1
        explore_method = 1 # 1 for lammps MD, 2 for lasp SSW
        dft_method = 1 # 1 for VASP
        explore_ratio = 0.2 # how many structures will be used to perform explore step
        dft_ratio = 0.2 # How many explored structures will be chosen to perform DFT and add to training set
        t_generate = "GENERATE_P"
        t_train = "train_noclassify_nompi.py"
        t_predict = "predict_noclassify_nompi.py"
        t_input = "PARAMS.json"
        data_path = "./"
        lammps_exe = "lmp_intel_cpu_intelmpi"
        lammps_input = "in.clint.W"
        lammps_data_name = "data.W"
        lasp_exe = "lasp"
        lasp_input = "lasp.in"
        lasp_data_name = "lasp.str"
        vasp_exe = "vasp_std"

    def __str__(self):
        str_ = []
        str_ += (">>> total_loop: %5d\n" % self.total_loop)
        str_ += (">>> explore_method: %5d\n" % self.explore_method)
        str_ += (">>> dft_method: %5d\n" % self.dft_method)
        str_ += (">>> explore_ratio: %5.2f%%\n" % (self.explore_ratio * 100.0))
        str_ += (">>> dft_ratio: %5.2f%%\n" % (self.dft_ratio * 100.0))
        str_ += (">>> t_generate: %s\n" % self.t_generate)
        str_ += (">>> t_train: %s\n" % self.t_train)
        str_ += (">>> t_predict: %s\n" % self.t_predict)
        str_ += (">>> t_input: %s\n" % self.t_input)
        str_ += (">>> t_data_pat: %s\n" % self.data_path)
        if (self.explore_method == 1):
            str_ += (">>> lammps_exe: %s\n" % self.lammps_exe)
            str_ += (">>> lammps_input: %s\n" % self.lammps_input)
            str_ += (">>> lammps_data_name: %s\n" % self.lammps_data_name)
        elif (self.explore_method == 2):
            str_ += (">>> lasp_exe: %s\n" % self.lasp_exe)
            str_ += (">>> lasp_input: %s\n" % self.lasp_input)
            str_ += (">>> lasp_data_name: %s\n" % self.lasp_data_name)
        if (self.dft_method == 1):
            str_ += (">>> vasp_exe: %s\n" % self.vasp_exe)

        str_ = ''.join(str(element) for element in str_)
        return str_

    def read_parameters(self, filename):
        INPUT_FILE = open(filename, "r")
        INPUT_DATA = json.load(INPUT_FILE)
        self.total_loop = INPUT_DATA['total_loop']
        self.explore_method = INPUT_DATA['explore_method']
        self.dft_method = INPUT_DATA['dft_method']
        self.explore_ratio = INPUT_DATA['explore_ratio']
        self.dft_ratio = INPUT_DATA['dft_ratio']
        self.t_generate = INPUT_DATA['t_generate']
        self.t_train = INPUT_DATA['t_train']
        self.t_predict = INPUT_DATA['t_predict']
        self.t_input = INPUT_DATA['t_input']
        self.data_path = INPUT_DATA['data_path']
        if (self.explore_method == 1):
            self.lammps_exe = INPUT_DATA['lammps_exe']
            self.lammps_input = INPUT_DATA['lammps_input']
            self.lammps_data_name = INPUT_DATA['lammps_data_name']
        elif (self.explore_method == 2):
            self.lasp_exe = INPUT_DATA['lasp_exe']
            self.lasp_input = INPUT_DATA['lasp_input']
            self.lasp_data_name = INPUT_DATA['lasp_data_name']
        else:
            print("explore_method not supported!")
            exit()
        if (self.dft_method == 1):
            self.vasp_exe = INPUT_DATA['vasp_exe']
        else:
            print("dft_method not supported!")
            exit()
        INPUT_FILE.close()


class run_lasp():
    def __init__(self):
        CMD1 = " lasp "
        CMD = CMD1

    def execuate(self):
        os.system(self.CMD)

    def printcmd(self):
        print(self.CMD)


"""Copy file to dest. file and dest are strings"""
class cp_file():
    def __init__(self, file, dest):
        CMD1 = "cp -r "
        CMD2 = file + " "
        CMD3 = dest + " "
        CMD = CMD1 + CMD2 + CMD3

    def execuate(self):
        os.system(self.CMD)

    def printcmd(self):
        print(self.CMD)


def int_to_str(INT):
    STR_TMP = []
    STR_TMP += ("%d" % INT)
    STR = ''.join(str(element) for element in STR_TMP)
    return STR


def raw_to_lammps():
    box = np.loadtxt("box.raw", dtype=np.float)
    coord = np.loadtxt("coord.raw", dtype=np.float)
    type = np.loadtxt("type.raw", dtype=np.int)
    type_unique = np.array(list(set(type)))
    type_unique.sort()
    natoms = len(type)
    ntypes = len(type_unique)
    box = box.reshape(3,3)
    coord = coord.reshape(-1, 3)
    p_a = np.sqrt(np.sum(np.square(box[0])))
    p_b = np.sqrt(np.sum(np.square(box[1])))
    p_c = np.sqrt(np.sum(np.square(box[2])))
    lx = p_a
    p_xy = p_b * np.dot(box[0], box[1]) / p_a / p_b
    p_xz = p_c * np.dot(box[0], box[2]) / p_a / p_c
    ly = np.sqrt(p_b**2 - p_xy**2)
    p_yz = (p_b * p_c * np.dot(box[1], box[2]) / p_b / p_c - p_xy * p_xz) / ly
    lz = np.sqrt(p_c**2 - p_xz**2 - p_yz**2)
    lammps_data_f = open(LAMMPS_DATA, "wt")

    lammps_data_f.write("# Converted from POSCAR to lammps format\n")
    lammps_data_f.write("\n")
    lammps_data_f.write("%d atoms\n" % natoms)
    lammps_data_f.write("%d atom types\n" % ntypes)
    lammps_data_f.write("\n")
    lammps_data_f.write("0.000000  %10.6f   xlo xhi\n" % lx)
    lammps_data_f.write("0.000000  %10.6f   ylo yhi\n" % ly)
    lammps_data_f.write("0.000000  %10.6f   zlo zhi\n" % lz)
    lammps_data_f.write("\n")
    lammps_data_f.write("%10.6f  %10.6f  %10.6f   xy xz yz\n" % (p_xy, p_xz, p_yz))
    lammps_data_f.write("\n")
    lammps_data_f.write("Atoms\n")
    lammps_data_f.write("\n")

    for i in range(len(type)):
        lammps_data_f.write("%4i  %-4d   %7f  %7f  %7f\n" % (i + 1, 1 + (type[i] == type_unique).nonzero()[0], \
                                                        coord[i][0], coord[i][1], coord[i][2]))

    lammps_data_f.close()
    return


def get_angle(a, b):
    norma = np.sqrt(np.sum(np.square(a)))
    normb = np.sqrt(np.sum(np.square(b)))
    cosab = np.dot(a,b)/norma/normb
    angleab = np.arccos(cosab) / np.pi * 180
    return angleab


def get_atom_name(num):
    ele_symbol_list = ['H', 'He', 'Li', 'Be', 'B ', 'C ', 'N ', 'O ', 'F ', 'Ne', \
                       'Na', 'Mg', 'Al', 'Si', 'P ', 'S ', 'Cl', 'Ar', 'K ', 'Ca', \
                       'Sc', 'Ti', 'V ', 'Cr', 'Mn', 'Fe', 'Co', 'Ni', 'Cu', 'Zn', \
                       'Ga', 'Ge', 'As', 'Se', 'Br', 'Kr', 'Rb', 'Sr', \
                       'Y ', 'Zr', 'Nb', 'Mo', 'Tc', 'Ru', 'Rh', 'Pd', 'Ag', 'Cd', \
                       'In', 'Sn', 'Sb', 'Te', 'I ', 'Xe', \
                       'Cs', 'Ba', 'La', 'Ce', 'Pr', 'Nd', 'Pm', \
                       'Sm', 'Eu', 'Gd', \
                       'Tb', 'Dy', 'Ho', 'Er', 'Tm', 'Yb', 'Lu', \
                       'Hf', 'Ta', 'W ', 'Re', 'Os', 'Ir', 'Pt', 'Au', 'Hg', \
                       'Tl', 'Pb', 'Bi', 'Po', 'At', 'Rn']
    ele_num_list = [x + 1 for x in range(86)]
    ele_dict = dict(zip(ele_num_list, ele_symbol_list))
    return ele_dict[num]

def raw_to_lasp():
    box = np.loadtxt("box.raw", dtype=np.float)
    coord = np.loadtxt("coord.raw", dtype=np.float)
    type = np.loadtxt("type.raw", dtype=np.int)
    type_unique = np.array(list(set(type)))
    type_unique.sort()
    natoms = len(type)
    ntypes = len(type_unique)
    box = box.reshape(3, 3)
    coord = coord.reshape(-1, 3)

    lx = np.sqrt(np.sum(np.square(box[0])))
    ly = np.sqrt(np.sum(np.square(box[1])))
    lz = np.sqrt(np.sum(np.square(box[2])))
    alpha = get_angle(box[1], box[2])
    beta = get_angle(box[0], box[1])
    gamma = get_angle(box[0], box[1])

    lasp_data_f = open(LASP_DATA, "wt")

    lasp_data_f.write("!BIOSYM archive 3\n")
    lasp_data_f.write("PBC=ON\n")
    lasp_data_f.write("Material Studio CAR format file\n")
    lasp_data_f.write("!DATE     Sep 08 10:57:38 2019\n")
    lasp_data_f.write("PBC%10.4f%10.4f%10.4f%10.4f%10.4f%10.4f\n" % (lx, ly, lz, alpha, beta, gamma))
    for i in range(natoms):
        lasp_data_f.write("%2s%16.9f%16.9f%16.9f%5s%2d%8s%8s%7.3f\n" % \
                          (get_atom_name(type[i]), coord[i][0], coord[i][1], coord[i][2], "XXXX", 1, "xx", \
                           get_atom_name(type[i]), 0.0))

    lasp_data_f.write("end\nend\n")

    lasp_data_f.close()

    return


"""Convert raw to POSCAR. The elements will arange in ascending order, so make sure the element sequence in POTCAR
   is also aranged in ascending order according to their element numbers."""
def raw_to_poscar():

    POSCAR_F = open("POSCAR", "wt")
    box = np.loadtxt("box.raw")
    POSCAR_HEADER = "Converted from raw\n"
    POSCAR_F.write(POSCAR_HEADER)
    POSCAR_F.write(" %f\n" % 1.0)
    POSCAR_F.write(" %10.6f %10.6f %10.6f\n %10.6f %10.6f %10.6f\n %10.6f %10.6f %10.6f\n" % (box[0], box[1], box[2], box[3], box[4], box[5], \
                                                                   box[6], box[7], box[8]))
    type = np.loadtxt("type.raw", dtype=np.int)
    type_unique = np.array(list(set(type)))
    type_unique.sort()

    for i in range(len(type_unique)):
        POSCAR_F.write(" %d " % len((type == type_unique[i]).nonzero()[0]))
    POSCAR_F.write("\n")
    POSCAR_F.write("Cart\n")

    coord = np.loadtxt("coord.raw", dtype=np.float)
    coord = coord.reshape((-1, 3))
    for i in range(len(type_unique)):
        coord_tmp = coord[(type == type_unique[i]).nonzero()[0]]
        for j in range(len(coord_tmp)):
            POSCAR_F.write(" %10.6f %10.6f %10.6f \n" % (coord_tmp[j][0], coord_tmp[j][1], coord_tmp[j][2]))

    POSCAR_F.close()
    return


"""
Command to copy checkpoint file of TorchANN.
When calling this function, make sure your current working directory is the directory which PARAMS_AUTO.json exists.
"""
def copy_checkpoint_TorchANN(loop_idx, DATASET_DIR_PREFIX):
    CMD = "cp " + DATASET_DIR_PREFIX + int_to_str(loop_idx - 1) + "/" + "freeze_model.pytorch" + " " + \
          DATASET_DIR_PREFIX + int_to_str(loop_idx) + "/freeze_model.pytorch.ckpt.cont"
    os.system(CMD)
    return


"""
Command to copy input parameters of TorchANN
When calling this function, make sure your current working directory is the directory which PARAMS_AUTO.json exists.
"""
def copy_input_TorchANN(auto_train_parameters, DATASET_DIR):
    CMD = "cp " + auto_train_parameters.data_path + "/" + auto_train_parameters.t_input + " " + DATASET_DIR
    os.system(CMD)
    return


"""
Command to run TorchANN
When calling this function, make sure your current working directory is DATASET_DIR.
This function should save all the training set in the DATASET_DIR/*.raw
"""
def run_TorchANN_dataset(auto_train_parameters):
    CMD1 = TORCHANN_CPP_EXE + " 2>&1 > runlog_g "
    CMD2 = TORCHANN_TRAIN + " 2>&1 > runlog_t "
    CMD = CMD1 + ";" + CMD2
    os.system(CMD)
    return


"""
Command to run lammps
When calling this function, make sure your current working directory is EXPLORE_DIR/i/, i=1,2,3,...
This function should save all the explored structures in the EXPLORE_DIR/*_all_exp.raw
"""
# class run_lammps():
#     def __init__(self):
#         CMD1 = LAMMPS_EXE + LAMMPS_COMMAND + LEFT_ARROW + LAMMPS_INPUT + BACKGROUND_SYMBOL
#         CMD2 = PYTHON2 + TORCHAN_LAMMPS_WRAPER
#         CMD3 = WAIT
#         CMD = CMD1 + ";" + CMD2 + ";" + CMD3
#
#     def execuate(self):
#         os.system(self.CMD)
#
#     def printcmd(self):
#         print(self.CMD)
def run_lammps_explore(auto_train_parameters):
    CMD = "cp ../../data/" + auto_train_parameters.lammps_input + "  ./"
    os.system(CMD)
    raw_to_lammps()
    CMD = "cp " + SCRIPTS_PATH + "/TorchANN_wrap_python2.py " + " ./"
    os.system(CMD)
    CMD1 = TORCHANN_CPP_EXE
    CMD2 = TORCHANN_PREDICT
    CMD3 = CMD1 + ";" + CMD2
    with open("torchanncmd.txt", "wt") as f:
        f.write(CMD3)
        f.close()

    """Run lammps"""
    CMD1 = LAMMPS_EXE + " -v mode file < " + auto_train_parameters.lammps_input + " " + BACKGROUND_SYMBOL
    CMD2 = PYTHON2 + " TorchANN_wrap_python2.py file"
    CMD3 = WAIT
    CMD = CMD1 + " \n " + CMD2 + " \n " + CMD3
    with open("run.sh", "wt") as f:
        f.write(CMD)
    os.system("bash run.sh")

    """cat all frames together"""
    os.system("cat ./coord_all.raw >> ../coord_all_exp.raw")
    os.system("cat ./force_all.raw >> ../force_all_exp.raw")
    os.system("cat ./box_all.raw >> ../box_all_exp.raw")
    os.system("cat ./type_all.raw >> ../type_all_exp.raw")
    os.system("cat ./energy_all.raw >> ../energy_all_exp.raw")

    return


"""
Command to run LASP
When calling this function, make sure your current working directory is EXPLORE_DIR/i/, i=1,2,3,...
This function should save all the explored structures in the EXPLORE_DIR/*_all_exp.raw
"""
def run_lasp_explore(auto_train_parameters):
    CMD = "cp ../../data/" + auto_train_parameters.lasp_input + "  ./lasp.in"
    os.system(CMD)
    raw_to_lasp()
    CMD = "cp " + SCRIPTS_PATH + "/lasp.external.sh " + " ./"
    os.system(CMD)
    CMD1 = TORCHANN_CPP_EXE
    CMD2 = TORCHANN_PREDICT
    CMD3 = CMD1 + ";" + CMD2
    with open("torchanncmd.txt", "wt") as f:
        f.write(CMD3)
        f.close()

    """Run lammps"""
    CMD1 = LASP_EXE
    CMD = CMD1
    with open("run.sh", "wt") as f:
        f.write(CMD)
    os.system("bash run.sh")

    """cat all frames together"""
    os.system("cat ./coord_all.raw >> ../coord_all_exp.raw")
    os.system("cat ./force_all.raw >> ../force_all_exp.raw")
    os.system("cat ./box_all.raw >> ../box_all_exp.raw")
    os.system("cat ./type_all.raw >> ../type_all_exp.raw")
    os.system("cat ./energy_all.raw >> ../energy_all_exp.raw")

    return


"""
Command to run VASP
When calling this function, make sure your current working directory is DFT_DIR/i/, i=1,2,3,...
This function should save calculated energy, force in the DFT_DIR/*_sel_dft.raw
"""
def run_vasp_dft(auto_train_parameters):
    raw_to_poscar()
    os.system(VASP_EXE)
    """Extract energy and force"""
    os.system("grep free\ \ energy\ \ \ T OUTCAR | awk '{print $5}' > energy.raw")
    type = np.loadtxt("type.raw", dtype=np.int)
    natoms = len(type) + 2
    natoms_str = str(natoms)
    CMD1 = "grep TOTAL-FORCE OUTCAR -A" + natoms_str + " "
    CMD2 = " | sed '/^\ -/d' | sed '/POS/d' | awk '{print $4,$5,$6}' >force.raw "
    CMD = CMD1 + CMD2
    os.system(CMD)
    CMD = "sed -i ':a;N;s/\\n/\ /g;ta' force.raw"
    os.system(CMD)
    os.system("cat energy.raw >> ../energy_sel_dft.raw")
    os.system("cat force.raw >> ../force_sel_dft.raw")
    return


"""
Selected data will be saved as *_sel_exp.raw
Make sure the working dir has been changed to EXPLORE_DIR before call this function
"""
def select_data_for_explore(auto_train_parameters):

    tmp_frame = np.loadtxt("energy_all_dataset.raw")
    tot_frame = len(tmp_frame)
    sel_frame = math.ceil(tot_frame * auto_train_parameters.explore_ratio)
    explore_systems_idx = random.sample(range(tot_frame), sel_frame)

    box_raw_from_data_f = open("box_all_dataset.raw", "rt")
    coord_raw_from_data_f = open("coord_all_dataset.raw", "rt")
    force_raw_from_data_f = open("force_all_dataset.raw", "rt")
    energy_raw_from_data_f = open("energy_all_dataset.raw", "rt")
    type_raw_from_data_f = open("type_all_dataset.raw", "rt")

    box_raw_from_data = box_raw_from_data_f.readlines()
    coord_raw_from_data = coord_raw_from_data_f.readlines()
    force_raw_from_data = force_raw_from_data_f.readlines()
    energy_raw_from_data = energy_raw_from_data_f.readlines()
    type_raw_from_data = type_raw_from_data_f.readlines()

    box_raw_from_data_f.close()
    coord_raw_from_data_f.close()
    force_raw_from_data_f.close()
    energy_raw_from_data_f.close()
    type_raw_from_data_f.close()

    box = open("box_sel_exp.raw", "wt")
    coord = open("coord_sel_exp.raw", "wt")
    force = open("force_sel_exp.raw", "wt")
    energy = open("energy_sel_exp.raw", "wt")
    type = open("type_sel_exp.raw", "wt")

    for i in range(sel_frame):
        # CMD = "mkdir " + int_to_str(i)
        # os.system(CMD)
        # os.system("cp freeze_model.pytorch" + " " + int_to_str(i))
        # os.system("cp PARAMS.json" + " " + int_to_str(i))
        # os.chdir(int_to_str(i))

        box.write(box_raw_from_data[explore_systems_idx[i]])
        coord.write(coord_raw_from_data[explore_systems_idx[i]])
        force.write(force_raw_from_data[explore_systems_idx[i]])
        energy.write(energy_raw_from_data[explore_systems_idx[i]])
        type.write(type_raw_from_data[explore_systems_idx[i]])

        #os.chdir("../")

    box.close()
    coord.close()
    force.close()
    energy.close()
    type.close()

    return sel_frame


"""
Selected data will be saved as *_sel_dft.raw
Make sure the working dir has been changed to DFT_DIR before call this function
"""
def select_data_for_dft(auto_train_parameters):
    tmp_frame_DFT = np.loadtxt("energy_all_exp.raw")
    tot_frame_DFT = len(tmp_frame_DFT)
    sel_frame_DFT = math.ceil(tot_frame_DFT * auto_train_parameters.dft_ratio)
    dft_systems_idx = random.sample(range(tot_frame_DFT), sel_frame_DFT)

    box_raw_from_data_f = open("box_all_exp.raw")
    coord_raw_from_data_f = open("coord_all_exp.raw")
    type_raw_from_data_f = open("type_all_exp.raw")

    box_raw_from_data = box_raw_from_data_f.readlines()
    coord_raw_from_data = coord_raw_from_data_f.readlines()
    type_raw_from_data = type_raw_from_data_f.readlines()

    box_raw_from_data_f.close()
    coord_raw_from_data_f.close()
    type_raw_from_data_f.close()

    box = open("box_sel_dft.raw", "wt")
    coord = open("coord_sel_dft.raw", "wt")
    type = open("type_sel_dft.raw", "wt")

    for i in range(sel_frame_DFT):
        box.write(box_raw_from_data[dft_systems_idx[i]])
        coord.write(coord_raw_from_data[dft_systems_idx[i]])
        type.write(type_raw_from_data[dft_systems_idx[i]])
    box.close()
    coord.close()
    type.close()

    return sel_frame_DFT


"""One loop: train->explore->dft"""
def one_loop(loop_idx, auto_train_parameters):

    LOG_f = open("auto_train.log", "at")
    LOG_f.write("Auto training loop %4d\n" % loop_idx)
    # LOG_f.close()

    DIR_SUFFIX = int_to_str(loop_idx)
    DATASET_DIR = DATASET_DIR_PREFIX + DIR_SUFFIX
    EXPLORE_DIR = EXPLORE_DIR_PREFIX + DIR_SUFFIX
    DFT_DIR = DFT_DIR_PREFIX + DIR_SUFFIX
    os.system("mkdir " + DATASET_DIR)
    os.system("mkdir " + EXPLORE_DIR)
    os.system("mkdir " + DFT_DIR)

    """Move necessary files into DATASET_DIR"""
    """The initial input for training should be provided as five .raws: """
    """coord.raw, type.raw, energy.raw, box.raw and force.raw"""
    if (loop_idx == 0):
        CMD = "cp " + auto_train_parameters.data_path + "/*.raw " + DATASET_DIR
        os.system(CMD)
    else:
        for i in ["coord", "type", "energy", "box", "force"]:
            CMD = "cp " + DATASET_DIR_PREFIX + int_to_str(loop_idx - 1) + "/" + i + ".raw " + " " + DATASET_DIR
            os.system(CMD)
            CMD1 = "cat " + DFT_DIR_PREFIX + int_to_str(loop_idx - 1) + "/" + i + "_sel_dft.raw " + " >> "
            CMD2= DATASET_DIR + "/" + i + ".raw"
            CMD = CMD1 + CMD2
            os.system(CMD)
        # CMD = "cp " + DATASET_DIR_PREFIX + int_to_str(loop_idx - 1) + "/" + "freeze_model.pytorch" + " " + DATASET_DIR +\
        #     "/freeze_model.pytorch.ckpt.cont"
        # os.system(CMD)
        copy_checkpoint_TorchANN(loop_idx, DATASET_DIR_PREFIX)
    # tmp_frame = np.loadtxt(DATASET_DIR + "/energy.raw")
    # tot_frame = len(tmp_frame)
    # sel_frame = math.ceil(tot_frame * auto_train_parameters.explore_ratio)
    # explore_systems_idx = random.sample(range(tot_frame), sel_frame)
    # CMD = "cp " + auto_train_parameters.data_path + "/" + auto_train_parameters.t_input + " " + DATASET_DIR
    # os.system(CMD)
    copy_input_TorchANN(auto_train_parameters, DATASET_DIR)
    """Start train"""

    # LOG_f = open("auto_train.log", "at")
    LOG_f.write("1/3 of %4d: Training...\n" % loop_idx)
    # LOG_f.close()

    os.chdir(DATASET_DIR)
    # CMD1 = TORCHANN_CPP_EXE + " 2>&1 > runlog_g "
    # CMD2 = TORCHANN_TRAIN + " 2>&1 > runlog_t "
    # CMD = CMD1 + ";" + CMD2
    # os.system(CMD)
    run_TorchANN_dataset(auto_train_parameters)

    os.chdir("../")#DATASET_DIR
    os.system("cp " + DATASET_DIR + "/freeze_model.pytorch" + "  " + EXPLORE_DIR)
    os.system("cp " + DATASET_DIR + "/PARAMS.json" + "  " + EXPLORE_DIR)

    """Select data"""
    for i in ["coord", "type", "energy", "box", "force"]:
        CMD = "cp " + DATASET_DIR + "/" + i + ".raw" + " " + EXPLORE_DIR + "/" + i + "_all_dataset.raw"
        os.system(CMD)

    # box_raw_from_data_f = open(DATASET_DIR + "/box.raw", "rt")
    # coord_raw_from_data_f = open(DATASET_DIR + "/coord.raw", "rt")
    # force_raw_from_data_f = open(DATASET_DIR + "/force.raw", "rt")
    # energy_raw_from_data_f = open(DATASET_DIR + "/energy.raw", "rt")
    # type_raw_from_data_f = open(DATASET_DIR + "/type.raw", "rt")
    #
    # box_raw_from_data = box_raw_from_data_f.readlines()
    # coord_raw_from_data = coord_raw_from_data_f.readlines()
    # force_raw_from_data = force_raw_from_data_f.readlines()
    # energy_raw_from_data = energy_raw_from_data_f.readlines()
    # type_raw_from_data = type_raw_from_data_f.readlines()
    #
    # box_raw_from_data_f.close()
    # coord_raw_from_data_f.close()
    # force_raw_from_data_f.close()
    # energy_raw_from_data_f.close()
    # type_raw_from_data_f.close()

    os.chdir(EXPLORE_DIR)
    """Selected frames will be saved to *_sel_exp.raw"""
    sel_frame = select_data_for_explore(auto_train_parameters)

    box_sel_f = open("box_sel_exp.raw", "rt")
    coord_sel_f = open("coord_sel_exp.raw", "rt")
    force_sel_f = open("force_sel_exp.raw", "rt")
    energy_sel_f = open("energy_sel_exp.raw", "rt")
    type_sel_f = open("type_sel_exp.raw", "rt")

    box_from_sel = box_sel_f.readlines()
    coord_from_sel = coord_sel_f.readlines()
    force_from_sel = force_sel_f.readlines()
    energy_from_sel = energy_sel_f.readlines()
    type_from_sel = type_sel_f.readlines()


    for i in range(sel_frame):
        CMD = "mkdir " + int_to_str(i)
        os.system(CMD)
        os.system("cp freeze_model.pytorch" + " " + int_to_str(i))
        os.system("cp PARAMS.json" + " " + int_to_str(i))

        os.chdir(int_to_str(i)) # Now in directory EXPLORE_DIR/i

        box = open("box.raw", "wt")
        box.write(box_from_sel[i])
        box.close()
        coord = open("coord.raw", "wt")
        coord.write(coord_from_sel[i])
        coord.close()
        force = open("force.raw", "wt")
        force.write(force_from_sel[i])
        force.close()
        energy = open("energy.raw", "wt")
        energy.write(energy_from_sel[i])
        energy.close()
        type = open("type.raw", "wt")
        type.write(type_from_sel[i])
        type.close()

        os.chdir("../") # Now in directory EXPLORE_DIR

    """Run explore in dir 0..sel_frame - 1"""

    # LOG_f = open("auto_train.log", "at")
    LOG_f.write("2/3 of %4d: Exploring...\n" % loop_idx)
    # LOG_f.close()

    for i in range(sel_frame):
        os.chdir(int_to_str(i)) # Now in directory EXPLORE_DIR/i

        if (auto_train_parameters.explore_method == 1): #LAMMPS
            # CMD = "cp ../../data/" + auto_train_parameters.lammps_input + "  ./"
            # os.system(CMD)
            # """Convert data to lammps type"""
            # raw_to_lammps()
            # CMD = "cp " + SCRIPTS_PATH + "/TorchANN_wrap_python2.py " + " ./"
            # os.system(CMD)
            # CMD1 = TORCHANN_CPP_EXE
            # CMD2 = TORCHANN_PREDICT
            # CMD3 = CMD1 + ";" + CMD2
            # with open("torchanncmd.txt","wt") as f:
            #     f.write(CMD3)
            #     f.close()
            #
            # """Run lammps"""
            # CMD1 = LAMMPS_EXE + " -v mode file < " + auto_train_parameters.lammps_input + " " + BACKGROUND_SYMBOL
            # CMD2 = PYTHON2 + " TorchANN_wrap_python2.py file"
            # CMD3 = WAIT
            # CMD = CMD1 + " \n " + CMD2 + " \n " + CMD3
            # with open("run.sh", "wt") as f:
            #     f.write(CMD)
            # os.system("bash run.sh")
            run_lammps_explore(auto_train_parameters)
        else:
            run_lasp_explore(auto_train_parameters)

        os.chdir("../") # Now in directory EXPLORE_DIR

    #"""cat all frames together"""
    # for i in range(sel_frame):
    #     os.chdir(int_to_str(i))
    #
    #     os.system("cat ./coord_all.raw >> ../coord_all_exp.raw")
    #     os.system("cat ./force_all.raw >> ../force_all_exp.raw")
    #     os.system("cat ./box_all.raw >> ../box_all_exp.raw")
    #     os.system("cat ./type_all.raw >> ../type_all_exp.raw")
    #     os.system("cat ./energy_all.raw >> ../energy_all_exp.raw")
    #
    #     os.chdir("../")

    os.chdir("../") # Now in directory ./

    os.chdir(DFT_DIR)

    """Copy frames to DFT_dir"""
    for i in ["coord", "box", "type", "energy"]:
        CMD1 = "cp " + "../" + EXPLORE_DIR + "/" + i + "_all_exp.raw" + " ./"
        CMD = CMD1
        os.system(CMD)



    """Select data for DFT"""
    # tmp_frame_DFT = np.loadtxt("energy_all_exp.raw")
    # tot_frame_DFT = len(tmp_frame_DFT)
    # sel_frame_DFT = math.ceil(tot_frame_DFT * auto_train_parameters.dft_ratio)
    # dft_systems_idx = random.sample(range(tot_frame_DFT), sel_frame_DFT)
    #
    # box_raw_from_data_f = open("box_all_exp.raw")
    # coord_raw_from_data_f = open("coord_all_exp.raw")
    # type_raw_from_data_f = open("type_all_exp.raw")
    #
    # box_raw_from_data = box_raw_from_data_f.readlines()
    # coord_raw_from_data = coord_raw_from_data_f.readlines()
    # type_raw_from_data = type_raw_from_data_f.readlines()
    #
    # box_raw_from_data_f.close()
    # coord_raw_from_data_f.close()
    # type_raw_from_data_f.close()
    #
    # box = open("box.raw", "wt")
    # coord = open("coord.raw", "wt")
    # type = open("type.raw", "wt")
    # for i in range(sel_frame_DFT):
    #     box.write(box_raw_from_data[dft_systems_idx[i]])
    #     coord.write(coord_raw_from_data[dft_systems_idx[i]])
    #     type.write(type_raw_from_data[dft_systems_idx[i]])
    # box.close()
    # coord.close()
    # type.close()

    sel_frame_DFT = select_data_for_dft(auto_train_parameters)

    os.chdir("../") # Now in directory ./
    for i in range(sel_frame_DFT):
        CMD = "mkdir " + DFT_DIR + "/" + int_to_str(i)
        os.system(CMD)
        CMD = "cp " + auto_train_parameters.data_path + "/INCAR " + " " + DFT_DIR + "/" + int_to_str(i)
        os.system(CMD)
        CMD = ("cp " + auto_train_parameters.data_path + "/KPOINTS " + " " + DFT_DIR + "/" +int_to_str(i))
        os.system(CMD)
        CMD = ("cp " + auto_train_parameters.data_path + "/POTCAR " + " " + DFT_DIR + "/" +int_to_str(i))
        os.system(CMD)
    os.chdir(DFT_DIR)

    box_sel_f = open("box_sel_dft.raw", "rt")
    coord_sel_f = open("coord_sel_dft.raw", "rt")
    type_sel_f = open("type_sel_dft.raw", "rt")

    box_from_sel = box_sel_f.readlines()
    coord_from_sel = coord_sel_f.readlines()
    type_from_sel = type_sel_f.readlines()

    for i in range(sel_frame_DFT):

        os.chdir(int_to_str(i)) # Now in directory DFT_DIR/i

        box = open("box.raw", "wt")
        box.write(box_from_sel[i])
        box.close()
        coord = open("coord.raw", "wt")
        coord.write(coord_from_sel[i])
        coord.close()
        type = open("type.raw", "wt")
        type.write(type_from_sel[i])
        type.close()

        os.chdir("../") # Now in directory DFT_DIR





    """Perform DFT calculation"""

    # LOG_f = open("auto_train.log", "at")
    LOG_f.write("3/3 of %4d: DFT...\n" % loop_idx)
    LOG_f.close()

    for i in range(sel_frame_DFT):

        os.chdir(int_to_str(i)) # Now in directory DFT_DIR/i

        if (auto_train_parameters.dft_method == 1):
            run_vasp_dft(auto_train_parameters)

        os.chdir("../") # Now in directory DFT_DIR





    os.chdir("../")  # Now in directory ./

    return

def main():

    global TORCHANN_CPP_EXE
    global TORCHANN_TRAIN
    global TORCHANN_PREDICT
    global LAMMPS_EXE
    global LAMMPS_INPUT
    global LAMMPS_DATA
    global LASP_EXE
    global LASP_INPUT
    global LASP_DATA
    global SCRIPTS_PATH
    global VASP_EXE

    SCRIPTS_PATH = os.path.dirname(os.path.realpath(__file__))
    SCRIPTS_PATH += "/scripts"

    auto_train_parameters_in = auto_train_parameters()
    auto_train_parameters_in.read_parameters("PARAMS_AUTO.json")
    print("Check input parameters:\n")
    print(auto_train_parameters_in)
    if (auto_train_parameters_in.explore_method == 1):
        EXP_TYPE = "LAMMPS"
        LAMMPS_EXE = auto_train_parameters_in.lammps_exe
        LAMMPS_INPUT = "" + auto_train_parameters_in.data_path + "/" + auto_train_parameters_in.lammps_input + " "
        LAMMPS_DATA = auto_train_parameters_in.lammps_data_name
    elif (auto_train_parameters_in.explore_method == 2):
        EXP_TYPE = "LASP-SSW"
        LASP_EXE = auto_train_parameters_in.lasp_exe
        LASP_INPUT = "" + auto_train_parameters_in.data_path + "/" + auto_train_parameters_in.lasp_input + " "
        LASP_DATA = auto_train_parameters_in.lasp_data_name
    if (auto_train_parameters_in.dft_method == 1):
        DFT_TYPE = "VASP"
    print("Selected exploration type: %s\n" % EXP_TYPE)
    print("Selected DFT code: %s\n" % DFT_TYPE)

    TORCHANN_CPP_EXE = auto_train_parameters_in.t_generate
    TORCHANN_TRAIN = auto_train_parameters_in.t_train
    TORCHANN_PREDICT = auto_train_parameters_in.t_predict
    VASP_EXE = auto_train_parameters_in.vasp_exe

    for i in range(auto_train_parameters_in.total_loop):
        one_loop(i, auto_train_parameters_in)

    return

if __name__ == '__main__':
    main()






