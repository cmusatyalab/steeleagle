import argparse

# Table containing all symbols in the MCPL script.
SYMBOL_TABLE = {'defs' : []}

# Directives.
START_DEF = "<--"
END_DEF = "-->"
COMM = "&>"
DEFS = "defs\n"

# Execute a thread using a code block.
def exec_raw_thread(symbol):
    pass

# Execute a thread using a program counter.
def exec_thread(symbol):
    pass

def get_block(lines, start, end):
    idx = start + 1
    block = ""
    while idx != end:
        block += lines[idx]
        idx += 1
    return block

def add_symbol(info, line_idx):
    name = info[0]
    typ = info[1]

    if name in SYMBOL_TABLE:
        raise SyntaxError('Line {0}: Redefinition of symbol {1}'.format(line_idx, name))
    else:
        SYMBOL_TABLE[name] = {'type' : typ, 'start' : line_idx, 'end' : None, 'block' : None}

def close_symbol(info, line_idx, lines):
    name = info[0]
    typ = info[1]

    if name not in SYMBOL_TABLE:
        raise SyntaxError('Line {0}: Closed symbol does not exist!'.format(line_idx, name))
    else:
        SYMBOL_TABLE[name]['end'] = line_idx
        SYMBOL_TABLE[name]['block'] = get_block(lines, SYMBOL_TABLE[name]['start'], line_idx)

def add_defs(line_idx):
    SYMBOL_TABLE['defs'].append({'start' : line_idx, 'end' : None, 'block' : None})

def close_defs(line_idx, lines):
    last = len(SYMBOL_TABLE['defs']) - 1
    SYMBOL_TABLE['defs'][last]['end'] = line_idx
    SYMBOL_TABLE['defs'][last]['block'] = get_block(lines, SYMBOL_TABLE['defs'][last]['start'], line_idx)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog='hermes',
        description='Runs .mcpl files on device.')
    parser.add_argument('input', help='MCPL flight script to run')

    args = parser.parse_args()
    f = open(args.input, 'r')

    # Parse in file.
    open_symbol = None
    lines = f.readlines()
    for i in range(len(lines)):
        line = lines[i]
        split = line.split(' ')
        if len(split) == 0:
            continue
        elif split[0] == START_DEF:
            if len(split) == 1:
                raise SyntaxError('Line {0}: Define start directive \'<--\' requires name'.format(i)) 
            info = split[1:]
            if open_symbol:
                raise SyntaxError('Line {0}: Illegal overlapping symbol definitions'.format(i))
            elif info[0] != DEFS:
                add_symbol(info, i)
            else:
                add_defs(i)
            open_symbol = info[0]
        elif split[0] == END_DEF:
            if len(split) == 1:
                raise SyntaxError('Line {0}: Define end directive \'-->\' requires name'.format(i))
            info = split[1:]
            if open_symbol != info[0]:
                raise SyntaxError('Line {0}: Illegal overlapping symbol definitions'.format(i))
            elif info[0] != DEFS:
                close_symbol(info, i, lines)
            else:
                close_defs(i, lines)
            open_symbol = None
        else:
            continue

    for k in SYMBOL_TABLE:
        print(k)
        print(SYMBOL_TABLE[k])
        print("\n\n\n")
    # Begin executing main routine.
