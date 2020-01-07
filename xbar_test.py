'''Tests the crossbar array HSPICE netlist and PWLs based on the output transients'''

import argparse
import json
import numpy as np
from helper import getpat

# Parse arguments
parser = argparse.ArgumentParser(description='Test the results of a crossbar array from SPICE.')
parser.add_argument('config', help='configuration JSON file')
parser.add_argument('--visualize', help='display checkerboard visualization', action="store_true")
parser.add_argument('--verbose', help='display breakdown of testcases', action="store_true")
args = parser.parse_args()

# Define parameters
params = json.load(open(args.config))

# Open transient result file
infile = open("tr0/%s.tr0" % params['title'])

# Get signal names
nsigs = int(infile.read(4)) + int(infile.read(4))
line = infile.readline()
header = ''
while line.strip()[-4:] != '$&%#':
    line = infile.readline()[:-1]
    header += line
signals = filter(lambda x: x != '', header.split(' '))[-nsigs-1:-1]

# Function to search .tr0 file for point in range
def find_point_in_range(infile, tmin, tmax):
    point = {'TIME' : -1}
    while point['TIME'] < tmax:
        sigs = []
        for _ in range(nsigs):
            sigs.append(float(infile.read(11)))
            pos = infile.tell()
            nextchar = infile.read(1)
            if nextchar != '\n':
                infile.seek(pos)
        point = dict(zip(signals,sigs))
        if point['TIME'] >= tmin and point['TIME'] <= tmax:
            return point
    raise Exception("Could not find time point in range (%s, %s)" % (tmin, tmax))

# Process tests
passed = True
for test in params['tests']:
    # Get verify method
    verify = test['verify']
    
    # Get pattern
    pat = getpat(test, params)

    # Skip initial wait+read
    t = test['wait'] * 2
    if params['type'] == '1R':
        t += len(pat) * (test['read']['pw'] + test['wait'])
    elif params['type'] == '2R':
        t += test['read']['pw'] + test['wait']

    for flip in range(test['flips']):
        # Skip write pulses
        # TODO: not assume same PW for set/reset
        t += len(pat) * (test['set']['pw'] + test['wait'])
        meas = np.empty((params['rows'], params['cols']))
        meas[:] = np.nan

        # 1R verification
        if params['type'] == '1R':
            # Check column current
            if verify['method'] == 'current':
                for i, j in pat:
                    point = find_point_in_range(infile, t + test['slewtime'], t + test['read']['pw'] + test['wait'] - test['slewtime'])
                    meas[i][j] = point["i(vcol_%s" % j]
                    t += test['read']['pw'] + test['wait']
            # Check RRAM filament gap
            elif verify['method'] == 'gap':
                for i, j in pat:
                    point = find_point_in_range(infile, t + test['read']['pw'] + test['slewtime'], t + test['read']['pw'] + test['wait'] - test['slewtime'])
                    meas[i][j] = point["v(gap_%s_%s" % (i,j)]
                    t += test['read']['pw'] + test['wait']
        
        # 2R verification
        elif params['type'] == '2R':
            # Check 2R midpoint voltage
            if verify['method'] == 'midvoltage':
                point = find_point_in_range(infile, t + test['slewtime'], t + test['read']['pw'] + test['wait'] - test['slewtime'])
                for i, j in pat:
                    meas[i][j] = point["v(mid_%s_%s" % (i,j)]
                t += test['read']['pw'] + test['wait']
        
        # Display checkerboard if specified
        if args.visualize:
            import matplotlib, matplotlib.pyplot as plt
            if args.verbose:
                print(meas)
            vmin = min(verify['bounds']['lo'][1], verify['bounds']['hi'][1])*0.99999
            vmax = max(verify['bounds']['lo'][0], verify['bounds']['hi'][0])*1.00001
            cmap = matplotlib.cm.get_cmap('gray')
            cmap.set_bad(color='red')
            plt.imshow(meas, cmap, origin='upper', interpolation='nearest', vmin=vmin, vmax=vmax)
            plt.show()

        # Check if tests passed
        for i, j in pat:
            expected = 'hi' if (i+j+flip) % 2 == 0 else 'lo'
            tpass = meas[i][j] >= verify['bounds'][expected][0] and meas[i][j] <= verify['bounds'][expected][1]
            if args.verbose:
                print("(flip, i, j, pass) = (%s, %s, %s, %s)" % (flip, i, j, tpass))
                if not tpass:
                    print("Measured: %s" % meas[i][j])
            passed = passed and tpass

# Close transient result file
infile.close()

# Display if passed
if passed:
    print("PASSED!")
else:
    print("FAILED!")