"""Separate read-only arithmetic implementation for re-scoring saved candidate programs."""
MODULUS=17

def independent_primitive(p, data):
    a,b,c,d,side=[int(t) for t in p]
    n=len(data)
    out=[]
    for index in range(n):
        neighbor=(index+side)%n
        value=(a*data[index]+b*data[neighbor]+c*(index%2)+d)%MODULUS
        out.append(value)
    return tuple(out)

def independent_program(p, wrapper, data):
    o=list(independent_primitive(p,data))
    if wrapper=='id':pass
    elif wrapper=='inc':o=[(z+1)%MODULUS for z in o]
    elif wrapper=='dec':o=[(z-1)%MODULUS for z in o]
    elif wrapper=='rol':o=o[1:]+o[:1]
    elif wrapper=='ror':o=o[-1:]+o[:-1]
    elif wrapper=='rev':o=list(reversed(o))
    else:raise ValueError('unknown wrapper')
    return tuple(o)
