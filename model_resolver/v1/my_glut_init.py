# fmt: off
from OpenGL.GLUT import special



INITIALIZED = False
def glutInit( *args ):
    """Initialise the GLUT library"""
    if args:
        arg,args = args[0],args[1:]
        count = None
        if isinstance(arg, special.integer_types):
            # raw API style, (count, values)
            count = arg
            if count != len(args):
                raise ValueError( """Specified count of %s does not match length (%s) of argument list %s"""%(
                    count, len(args), args,
                ))
        elif isinstance( arg, (bytes,special.unicode)):
            # passing in a sequence of strings as individual arguments
            args = (arg,)+args 
            count = len(args)
        else:
            args = arg 
            count = len(args)
    else:
        count=0
        args = []
    args = [special.as_8_bit(x) for x in args]
    if not count:
        count, args = 1, [special.as_8_bit('foo')]
    holder = (special.ctypes.c_char_p * len(args))()
    for i,arg in enumerate(args):
        holder[i] = arg
    count = special.ctypes.c_int( count )
    import os 
    currentDirectory = os.getcwd()
    try:
        # XXX need to check for error condition here...
        special._base_glutInit( special.ctypes.byref(count), holder )
    finally:
        os.chdir( currentDirectory )
    return [
        holder[i] for i in range( count.value )
    ]
glutInit.wrappedOperation = special._simple.glutInit
