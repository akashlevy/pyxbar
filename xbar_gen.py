'''Generates the crossbar array HSPICE netlist and PWLs'''

import argparse
import json
from collections import OrderedDict
from string import Template
from helper import getpat

# Parse arguments
parser = argparse.ArgumentParser(description='Generate a crossbar array in SPICE.')
parser.add_argument('config', help='configuration JSON file')
args = parser.parse_args()

# Define parameters
params = json.load(open(args.config))

# Initialize substitution dictionary
subs = {}

# Copy from params to subs
subs['title'] = params['title']
subs['tstep'] = params['tstep']
subs['includes'] = '\n'.join([".include %s" % incl for incl in params['includes']])
subs['models'] = '\n'.join([".hdl %s" % incl for incl in params['models']])
subs['options'] = '\n'.join([".option %s" % incl for incl in params['options']])
subs['params'] = '\n'.join([".param %s" % incl for incl in params['params']])

# Create subcircuit for cell with parasitic
if params['type'] == '1R' or params['type'] == '2R':
    # Template substitution
    template = Template(open("templates/%s_cell.sp.tmpl" % params['type']).read())
    subs['subckts'] = template.substitute(params)

# Initialize probes
probes = []

# Instantiate crossbar
xbar = ''
if params['type'] == '1R':
    for i in range(params['rows']):
        for j in range(params['cols']):
            # Create cell (i,j) and initialize nodes
            fmt = {'i': i, 'j': j, 'ni': i+1, 'nj': j+1}
            xbar += "Xcell_{i}_{j} row_{i}_{j} row_{i}_{nj} col_{i}_{j} col_{ni}_{j} gap_{i}_{j} CELL\n".format(**fmt)
            xbar += ".ic v(gap_{i}_{j})=0.85\n".format(**fmt)
elif params['type'] == '2R':
    for i in range(params['rows']):
        for j in range(params['cols']):
            # Create cell (i,j) and initialize nodes
            fmt = {'i': i, 'j': j, 'ni': i+1, 'nj': j+1}
            xbar += "Xcell_{i}_{j} row_{i}_{j} row_{i}_{nj} col_{i}_{j} col_{ni}_{j} mid_{i}_{j} gap1_{i}_{j} gap2_{i}_{j} CELL\n".format(**fmt)
            xbar += ".ic v(gap1_{i}_{j})=0.85 v(gap2_{i}_{j})=0.85\n".format(**fmt)
subs['xbar'] = xbar

# PWL class
class PWL(object):
    # Initialize class and generate test waveforms
    def __init__(self, params):
        self.params = params

        # Initialize time and row/column waveforms
        if params['type'] == '1R' or params['type'] == '2R':
            self.t = 0
            self.rowpwls = []
            self.colpwls = []
            for _ in range(params['rows']):
                self.rowpwls.append([])
            for _ in range(params['cols']):
                self.colpwls.append([])

        # For each test, generate the corresponding waveform
        for test in params['tests']:
            pat = getpat(test, params)
            self.add_standby_pwl(test)
            self.add_read_pwl(test, pat)
            for flip in range(test['flips']):
                self.add_cb_flip_pwl(test, pat, flip)
                self.add_read_pwl(test, pat)

    # Add on to row PWL based on mode and pulse height
    def add_row_pulse(self, test, i, mode, height):
        self.rowpwls[i].append((self.t, height))
        self.rowpwls[i].append((self.t + test[mode]['pw'] - test['slewtime'], height))
        self.rowpwls[i].append((self.t + test[mode]['pw'], 0))
        self.rowpwls[i].append((self.t + test[mode]['pw'] + test['wait'] - test['slewtime'], 0))

    # Add on to column PWL based on mode and pulse height
    def add_col_pulse(self, test, j, mode, height):
        self.colpwls[j].append((self.t, height))
        self.colpwls[j].append((self.t + test[mode]['pw'] - test['slewtime'], height))
        self.colpwls[j].append((self.t + test[mode]['pw'], 0))
        self.colpwls[j].append((self.t + test[mode]['pw'] + test['wait'] - test['slewtime'], 0))

    # Get unselected row/col voltages based on scheme
    def get_usels(self, test, mode):
        if test['scheme'] == 'V/2':
            uselV1 = abs(test[mode]['rowV'] - test[mode]['colV']) / 2.0
            uselV2 = abs(test[mode]['rowV'] - test[mode]['colV']) / 2.0
        if test['scheme'] == 'V/3':
            uselV1 = abs(test[mode]['rowV'] - test[mode]['colV']) / 3.0
            uselV2 = abs(test[mode]['rowV'] - test[mode]['colV']) * 2 / 3.0
        if test['scheme'] == 'float':
            uselV1 = None
            uselV2 = None
        if mode == 'reset':
            uselV1, uselV2 = uselV2, uselV1
        return uselV1, uselV2

    # Add pulse to all PWLs based on mode and (i,j)
    def add_pwl(self, test, mode, i, j):
        test[None] = {'rowV': 0, 'colV': 0, 'pw': test['wait']}
        uselV1, uselV2 = self.get_usels(test, mode)
        for i2 in range(params['rows']):
            if i == i2:
                self.add_row_pulse(test, i2, mode, test[mode]['rowV'])
            else:
                self.add_row_pulse(test, i2, mode, uselV1)
        for j2 in range(params['cols']):
            if j == j2:
                self.add_col_pulse(test, j2, mode, test[mode]['colV'])
            else:
                self.add_col_pulse(test, j2, mode, uselV2)
        self.t += test[mode]['pw'] + test['wait']

    # Add waveform to standby
    def add_standby_pwl(self, test):
        self.add_pwl(test, None, i, j)

    # Add waveform to read all cells
    def add_read_pwl(self, test, pat):
        if params['type'] == '1R':
            for i, j in pat:
                self.add_pwl(test, 'read', i, j)
        elif params['type'] == '2R':
            for i in range(params['rows']):
                self.add_row_pulse(test, i, 'read', test['read']['rowV'])
            for j in range(params['cols']):
                self.add_col_pulse(test, j, 'read', test['read']['colV'])
            self.t += test['read']['pw'] + test['wait']

    # Add waveform to write a binary checkerboard (alternating 0's and 1's)
    def add_cb_flip_pwl(self, test, pat, flip):
        # Parameter 'flip' determines whether a SET or RESET occurs first
        # Iterate through pattern points (i,j)
        for i, j in pat:
            if (i+j+flip) % 2 == 0:
                self.add_pwl(test, 'set', i, j)
            else:
                self.add_pwl(test, 'reset', i, j)
            # Add probes
            if 'probegroups' in params:
                if 'gaps' in params['probegroups']:
                    if params['type'] == '1R':
                        probes.append('V(gap_%s_%s, col_%s_%s)' % (i,j,i,j))
                    elif params['type'] == '2R':
                        probes.append('V(gap1_%s_%s, mid_%s_%s)' % (i,j,i,j))
                        probes.append('V(gap2_%s_%s, col_%s_%s)' % (i,j,i,j))
                if 'mids' in params['probegroups']:
                    if params['type'] == '1R':
                        raise Exception('Cannot probe midpoint for 1R structure')
                    elif params['type'] == '2R':
                        probes.append('V(mid_%s_%s)' % (i,j))

    def to_spice(self):
        spiceout = ''
        # Generate PWL for rows
        for i, rowpwl in enumerate(self.rowpwls):
            wf = ' '.join([("%s %s" % entry).ljust(20) for entry in rowpwl])
            wf = wf.replace('None', 'Z')
            spiceout += "Vrow_{i} row_{i}_0 0 PWLZ({wf})\n".format(i=i, wf=wf)
        # Generate PWL for cols
        for j, colpwl in enumerate(self.colpwls):
            wf = ' '.join([("%s %s" % entry).ljust(20) for entry in colpwl])
            wf = wf.replace('None', 'Z')
            spiceout += "Vcol_{j} col_0_{j} 0 PWLZ({wf})\n".format(j=j, wf=wf)
        return spiceout

# Instantiate PWLs
pwl = PWL(params)
subs['pwls'] = pwl.to_spice()

# Transient analysis
subs['tstop'] = pwl.t

# Probe statements
if 'probegroups' in params:
    if 'vins' in params['probegroups']:
        for i in range(params['rows']):
            probes.append('V(row_%s_0)' % i)
        for j in range(params['cols']):
            probes.append('V(col_0_%s)' % j)
    if 'currents' in params['probegroups']:
        for i in range(params['rows']):
            probes.append('I(Vrow_%s)' % i)
        for j in range(params['cols']):
            probes.append('I(Vcol_%s)' % j)
subs['probes'] = '\n'.join([".probe %s" % incl for incl in params['probes'] + list(OrderedDict.fromkeys(probes))])

# Template substitution
template = Template(open('templates/script.sp.tmpl').read())
output = template.substitute(subs)
open("sp/%s.sp" % params['title'], 'w').write(output)
