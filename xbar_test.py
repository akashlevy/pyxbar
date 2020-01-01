import argparse
import json
import numpy as np

# TODO: refactor checkerboard to be generated pairs of (i,j)

# Parse arguments
parser = argparse.ArgumentParser(description='Test the results of a crossbar array from SPICE.')
parser.add_argument('config', help='configuration JSON file')
parser.add_argument('--visualize', help='display checkerboard visualization', action="store_true")
parser.add_argument('--verbose', help='display breakdown of testcases', action="store_true")
args = parser.parse_args()

# Define parameters
params = json.load(open(args.config))

# Open transient result file
infile = open("sp/%s.tr0" % params['title'])

# Get signal names
nsigs = int(infile.read(4))
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
    verify = test['verify']
    if test['name'] == 'cb' or test['name'] == 'cb5pt':
        # Skip initial wait+read
        t = test['wait'] * 2
        if params['type'] == '1R':
            if test['name'] == 'cb':
                t += params['rows'] * params['cols'] * (test['read']['pw'] + test['wait'])
            elif test['name'] == 'cb5pt':
                t += test['testsize'] ** 2 * 5 * (test['read']['pw'] + test['wait'])
        elif params['type'] == '2R':
            t += test['read']['pw'] + test['wait']

        for flip in range(test['flips']):
            # Skip write pulses
            # TODO: not assume same PW for set/reset
            if test['name'] == 'cb':
                t += params['rows'] * params['cols'] * (test['set']['pw'] + test['wait'])
            elif test['name'] == 'cb5pt':
                t += test['testsize'] ** 2 * 5 * (test['set']['pw'] + test['wait'])
            meas = np.zeros((params['rows'], params['cols']))

            # 1R verification
            if params['type'] == '1R':
                # Check column current
                if verify['method'] == 'current':
                    # Read 5 subsets for scalability
                    if test['name'] == 'cb_5pt':
                        # 4 corners
                        for i in range(test['testsize']) + range(params['rows'] - test['testsize'], params['rows']):
                            for j in range(test['testsize']) + range(params['cols'] - test['testsize'], params['cols']):
                                point = find_point_in_range(infile, t + test['slewtime'], t + test['read']['pw'] + test['wait'] - test['slewtime'])
                                meas[i][j] = point["i(vcol_%s" % j]
                                t += test['read']['pw'] + test['wait']
                        # Middle
                        for i in range(params['rows']/2 - test['testsize']/2, params['rows']/2 + test['testsize']/2):
                            for j in range(params['cols']/2 - test['testsize']/2, params['cols']/2 + test['testsize']/2):
                                point = find_point_in_range(infile, t + test['slewtime'], t + test['read']['pw'] + test['wait'] - test['slewtime'])
                                meas[i][j] = point["i(vcol_%s" % j]
                                t += test['read']['pw'] + test['wait']
                    # Full checkerboard
                    else:
                        # Measure current on read pulse
                        for i in range(params['rows']):
                            for j in range(params['cols']):
                                point = find_point_in_range(infile, t + test['slewtime'], t + test['read']['pw'] + test['wait'] - test['slewtime'])
                                meas[i][j] = point["i(vcol_%s" % j]
                                t += test['read']['pw'] + test['wait']
                # Check RRAM filament gap
                elif verify['method'] == 'gap':
                    # Read 5 subsets for scalability
                    if test['name'] == 'cb_5pt':
                        # 4 corners
                        for i in range(test['testsize']) + range(params['rows'] - test['testsize'], params['rows']):
                            for j in range(test['testsize']) + range(params['cols'] - test['testsize'], params['cols']):
                                point = find_point_in_range(infile, t + test['read']['pw'] + test['slewtime'], t + test['read']['pw'] + test['wait'] - test['slewtime'])
                                meas[i][j] = point["v(gap_%s_%s" % (i,j)]
                                t += test['read']['pw'] + test['wait']
                        # Middle
                        for i in range(params['rows']/2 - test['testsize']/2, params['rows']/2 + test['testsize']/2):
                            for j in range(params['cols']/2 - test['testsize']/2, params['cols']/2 + test['testsize']/2):
                                point = find_point_in_range(infile, t + test['read']['pw'] + test['slewtime'], t + test['read']['pw'] + test['wait'] - test['slewtime'])
                                meas[i][j] = point["v(gap_%s_%s" % (i,j)]
                                t += test['read']['pw'] + test['wait']
                    # Full checkerboard
                    else:
                        # Measure gap after read pulse
                        for i in range(params['rows']):
                            for j in range(params['cols']):
                                point = find_point_in_range(infile, t + test['read']['pw'] + test['slewtime'], t + test['read']['pw'] + test['wait'] - test['slewtime'])
                                meas[i][j] = point["v(gap_%s_%s" % (i,j)]
                                t += test['read']['pw'] + test['wait']
            # 2R verification
            elif params['type'] == '2R':
                # Check 2R midpoint voltage
                if verify['method'] == 'midvoltage':
                    point = find_point_in_range(infile, t + test['slewtime'], t + test['read']['pw'] + test['wait'] - test['slewtime'])
                    # Read 5 subsets for scalability
                    if test['name'] == 'cb_5pt':
                        # 4 corners
                        for i in range(test['testsize']) + range(params['rows'] - test['testsize'], params['rows']):
                            for j in range(test['testsize']) + range(params['cols'] - test['testsize'], params['cols']):
                                meas[i][j] = point["v(mid_%s_%s" % (i,j)]
                        # Middle
                        for i in range(params['rows']/2 - test['testsize']/2, params['rows']/2 + test['testsize']/2):
                            for j in range(params['cols']/2 - test['testsize']/2, params['cols']/2 + test['testsize']/2):
                                meas[i][j] = point["v(mid_%s_%s" % (i,j)]
                    # Full checkerboard
                    else:
                        for i in range(params['rows']):
                            for j in range(params['cols']):
                                meas[i][j] = point["v(mid_%s_%s" % (i,j)]
                    t += test['read']['pw'] + test['wait']
            
            # Display checkerboard if specified
            if args.visualize:
                import matplotlib.pyplot as plt
                print(meas)
                vmin = min(verify['bounds']['lo'][1], verify['bounds']['hi'][1])*0.99999
                vmax = max(verify['bounds']['lo'][0], verify['bounds']['hi'][0])*1.00001
                plt.imshow(meas, 'gray', origin='upper', interpolation='nearest', vmin=vmin, vmax=vmax)
                plt.show()

            # Check if tests passed
            # Read 5 subsets for scalability
            if test['name'] == 'cb_5pt':
                # 4 corners
                for i in range(test['testsize']) + range(params['rows'] - test['testsize'], params['rows']):
                    for j in range(test['testsize']) + range(params['cols'] - test['testsize'], params['cols']):
                        expected = 'hi' if (i+j+flip) % 2 == 0 else 'lo'
                        tpass = meas[i][j] >= verify['bounds'][expected][0] and meas[i][j] <= verify['bounds'][expected][1]
                        if args.verbose:
                            print("(flip, i, j, pass) = (%s, %s, %s, %s)" % (flip, i, j, tpass))
                            if not tpass:
                                print("Measured: %s" % meas[i][j])
                        passed = passed and tpass
                # Middle
                for i in range(params['rows']/2 - test['testsize']/2, params['rows']/2 + test['testsize']/2):
                    for j in range(params['cols']/2 - test['testsize']/2, params['cols']/2 + test['testsize']/2):
                        expected = 'hi' if (i+j+flip) % 2 == 0 else 'lo'
                        tpass = meas[i][j] >= verify['bounds'][expected][0] and meas[i][j] <= verify['bounds'][expected][1]
                        if args.verbose:
                            print("(flip, i, j, pass) = (%s, %s, %s, %s)" % (flip, i, j, tpass))
                            if not tpass:
                                print("Measured: %s" % meas[i][j])
                        passed = passed and tpass
            # Full checkerboard
            else:
                for i in range(params['rows']):
                    for j in range(params['cols']):
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