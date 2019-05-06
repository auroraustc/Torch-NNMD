#!/usr/bin/env python3
# -*- coding:utf-8 -*-

import numpy as np
import math
import torch as tf
import torch.utils.data
import torch.nn as nn
import torch.optim as optim
import os
import gc
import time
from ctypes import *
from class_and_function import *


default_dtype = tf.float64
tf.set_default_dtype(default_dtype)
tf.set_printoptions(precision=10)
device = tf.device('cuda' if torch.cuda.is_available() else 'cpu')
#device = tf.device('cpu')

if (device != tf.device('cpu')):
    print("cuDNN version: ", tf.backends.cudnn.version())
    # tf.backends.cudnn.enabled = False
    #tf.backends.cudnn.benchmark = True
    MULTIPLIER = tf.cuda.device_count()
else:
    MULTIPLIER = 1
#if (hvd.rank() == 0):
if (True):
    f_out = open("./TEST_LOSS.OUT", "w")
    f_out.close()

FREEZE_MODEL = tf.load("./freeze_model.pytorch", map_location=device)

"""Load coordinates, sym_coordinates, energy, force, type, n_atoms and parameters"""
parameters = FREEZE_MODEL['parameters']
print("All parameters:")
print(parameters)

COORD_Reshape_tf, SYM_COORD_Reshape_tf, ENERGY_tf, FORCE_Reshape_tf, N_ATOMS_tf, TYPE_Reshape_tf, NEI_IDX_Reshape_tf, \
NEI_COORD_Reshape_tf, FRAME_IDX_tf, SYM_COORD_DX_Reshape_tf, SYM_COORD_DY_Reshape_tf, SYM_COORD_DZ_Reshape_tf, \
N_ATOMS_ORI_tf= read_and_init_bin_file(parameters, default_dtype=default_dtype)

"""Now all the needed information has been stored in the COORD_Reshape, SYM_COORD_Reshape, 
   ENERGY and FORCE_Reshape array."""

print("-----------------------------------------------")
print("|*******************WARNING*******************|")
print("| YOUR ARE RUNNING TEST ON THE CURRENT SYSTEM |")
print("|     NO OPTIMIZATION WILL BE PERFORMED!      |")
print("-----------------------------------------------")

print("Data pre-processing complete. Building net work and load data.\n")

mean_init=np.zeros(parameters.N_types_all_frame)
A = tf.zeros(parameters.N_types_all_frame, parameters.Nframes_tot)
for type_idx in range(parameters.N_types_all_frame):
    A[type_idx] = tf.sum(TYPE_Reshape_tf == parameters.type_index_all_frame[type_idx], dim=1)
A = A.transpose(0,1).numpy()
B = ENERGY_tf.numpy()
mean_init = np.linalg.lstsq(A,B,rcond=-1)[0]


ONE_BATCH_NET = one_batch_net(parameters, mean_init)
ONE_BATCH_NET.load_state_dict(FREEZE_MODEL['model_state_dict'])
std = FREEZE_MODEL['std'].narrow(0,0,1)
avg = FREEZE_MODEL['avg'].narrow(0,0,1)
###init_weights using xavier with gain = sqrt(0.5) is necessary. Now the damn adam works good with this initialization
#ONE_BATCH_NET.apply(init_weights)
ONE_BATCH_NET = ONE_BATCH_NET.to(device)
TOTAL_NUM_PARAMS = sum(p.numel() for p in ONE_BATCH_NET.parameters() if p.requires_grad)
print(ONE_BATCH_NET)
print("Number of parameters in the net: %d"%TOTAL_NUM_PARAMS)

use_std_avg = True

DATA_SET = tf.utils.data.TensorDataset(COORD_Reshape_tf, SYM_COORD_Reshape_tf, ENERGY_tf, FORCE_Reshape_tf, N_ATOMS_tf, \
                                       TYPE_Reshape_tf, NEI_IDX_Reshape_tf, NEI_COORD_Reshape_tf, FRAME_IDX_tf, \
                                       SYM_COORD_DX_Reshape_tf, SYM_COORD_DY_Reshape_tf, SYM_COORD_DZ_Reshape_tf, \
                                       N_ATOMS_ORI_tf)#0..12
TRAIN_LOADER = tf.utils.data.DataLoader(DATA_SET, batch_size = 1, shuffle = False)

CRITERION = nn.MSELoss(reduction = "mean")
#LR_SCHEDULER = tf.optim.lr_scheduler.ExponentialLR(OPTIMIZER2, parameters.decay_rate)
START_TRAIN_TIMER = time.time()
STEP_CUR = 0

print("Start testing using device: ", device)#, ", count: ", tf.cuda.device_count())
###For test, epoch = 1
parameters.epoch = 1


if (True):
#with tf.autograd.profiler.profile(enabled = True, use_cuda=True) as prof:
    START_BATCH_USER_TIMER = time.time()
    for epoch in range(parameters.epoch):
        #TRAIN_SAMPLER.set_epoch(epoch)
        START_EPOCH_TIMER = time.time()
        if (parameters.epoch != 1 ):
            pref_e = (parameters.limit_pref_e - parameters.start_pref_e) * 1.0 / (parameters.epoch - 1.0) * epoch + parameters.start_pref_e
            pref_f = (parameters.limit_pref_f - parameters.start_pref_f) * 1.0 / (parameters.epoch - 1.0) * epoch + parameters.start_pref_f
        else:
            pref_e = parameters.start_pref_e
            pref_f = parameters.start_pref_f

        for batch_idx, data_cur in enumerate(TRAIN_LOADER):
            for i in range(len(data_cur)):
                data_cur[i] = data_cur[i].to(device)
            START_BATCH_TIMER = time.time()

            PROF_FLAG = (STEP_CUR == -1)
            with tf.autograd.profiler.profile(enabled=PROF_FLAG, use_cuda=True) as prof:
                NEI_IDX_Reshape_tf_cur = data_cur[6]
                NEI_IDX_Reshape_tf_cur = tf.reshape(NEI_IDX_Reshape_tf_cur,
                                                    (len(NEI_IDX_Reshape_tf_cur), data_cur[4][0], parameters.SEL_A_max))
                FORCE_Reshape_tf_cur = data_cur[3]
                NEI_COORD_Reshape_tf_cur = data_cur[7]

                ###Adam
                # correct
                E_cur_batch, F_cur_batch, std, avg = ONE_BATCH_NET(data_cur, parameters, std, avg, use_std_avg, device)
                shape_tmp = std.shape
                std = std[0].reshape(1, shape_tmp[1] * shape_tmp[2]).expand(MULTIPLIER, shape_tmp[1] * shape_tmp[2]).reshape(shape_tmp)
                avg = avg[0].reshape(1, shape_tmp[1] * shape_tmp[2]).expand(MULTIPLIER, shape_tmp[1] * shape_tmp[2]).reshape(shape_tmp)
                use_std_avg = True
                # Energy loss part
                loss_E_cur_batch = CRITERION(E_cur_batch, data_cur[2])
                # Force
                F_cur_batch = tf.reshape(F_cur_batch, (len(data_cur[6]), data_cur[4][0] * 3))
                loss_F_cur_batch = tf.zeros(1, device = device)

                """if ((STEP_CUR % (parameters.check_step // MULTIPLIER) == 0)):
                    print("Force check:\n", F_cur_batch[0].data)
                    print("Additional parameters check:\n", "std:\n",  std, "\navg:\n", avg, "\nuse_std_avg", use_std_avg)
                    f_out = open("./LOSS.OUT", "a")
                    print("Force check:\n", F_cur_batch.data[0], file=f_out)
                    print("Additional parameters check:\n", "std:\n",  std, "\navg:\n", avg, "\nuse_std_avg", use_std_avg, file=f_out)
                    f_out.close()
                """
                loss_F_cur_batch = CRITERION(F_cur_batch, data_cur[3])

                loss_cur_batch = pref_e * loss_E_cur_batch + pref_f * loss_F_cur_batch
                #OPTIMIZER2.zero_grad()
                #loss_cur_batch.backward()
                #OPTIMIZER2.step()
                # correct end
                ###Adam end

                END_BATCH_TIMER = time.time()

                ###Adam print
                if (True):
                    END_BATCH_USER_TIMER = time.time()
                    print("Epoch: %-10d, Frame: %-10d, lossE: %10.6f eV/atom, lossF: %10.6f eV/A, time: %10.3f s" % (
                        epoch, batch_idx, tf.sqrt(loss_E_cur_batch) / data_cur[4][0].double(), tf.sqrt(loss_F_cur_batch),
                    END_BATCH_USER_TIMER - START_BATCH_USER_TIMER))
                    if (True):
                        f_out = open("./TEST_LOSS.OUT", "a")
                        print("Epoch: %-10d, Frame: %-10d, lossE: %10.6f eV/atom, lossF: %10.6f eV/A, time: %10.3f s" % ( \
                           epoch, batch_idx, tf.sqrt(loss_E_cur_batch) / data_cur[4][0].double(), tf.sqrt(loss_F_cur_batch),
                        END_BATCH_USER_TIMER - START_BATCH_USER_TIMER), \
                        file = f_out)
                        f_out.close()
                    START_BATCH_USER_TIMER = time.time()
                ###Adam end

                STEP_CUR += 1

                """if (STEP_CUR >= 2):
                    break"""
            if (PROF_FLAG):
                f_prof = open("./PROF.OUT", "w")
                print("profiling info saved in ./PROF.OUT")
                print(prof.table(sort_by="cpu_time"), file = f_prof)
                f_prof.close()
        END_EPOCH_TIMER = time.time()


        if (False):
            break


END_TRAIN_TIMER = time.time()
ELAPSED_TRAIN = END_TRAIN_TIMER - START_TRAIN_TIMER
print("Training complete. Time elapsed: %10.3f s\n"%ELAPSED_TRAIN)