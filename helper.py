'''Helper functions for crossbar generator and tester'''

def getpat(test, params):
    if test['name'] == 'cb':
        # Pattern is full array
        pat = [(i, j) for i in range(params['rows']) for j in range(params['cols'])]
    elif test['name'] == 'cb_5pt':
        # Top-left corner
        pat = [(i, j) for i in range(test['testsize']) for j in range(test['testsize'])]
        # Top-right corner
        pat += [(i, j) for i in range(test['testsize']) for j in range(params['cols'] - test['testsize'], params['cols'])]
        # Middle
        pat += [(i, j) for i in range(params['rows']/2 - test['testsize']/2, params['rows']/2 + test['testsize']/2) for j in range(params['cols']/2 - test['testsize']/2, params['cols']/2 + test['testsize']/2)]
        # Bottom-left corner
        pat += [(i, j) for i in range(params['rows'] - test['testsize'], params['rows']) for j in range(test['testsize'])]
        # Bottom-right corner
        pat += [(i, j) for i in range(params['rows'] - test['testsize'], params['rows']) for j in range(params['cols'] - test['testsize'], params['cols'])]
    else:
        # Undefined test
        raise Exception("The specified test does not exist: %s" % test['name'])
    return pat