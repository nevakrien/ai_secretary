import os
import io
import numpy as np 

import asyncio

from datetime import datetime

def write_int_to_file(filename, number):
    with open(filename, "wb") as f:
        f.write(number.to_bytes((number.bit_length() + 7) // 8, 'big'))

def read_int_from_file(filename):
    with open(filename, "rb") as f:
        return int.from_bytes(f.read(), 'big')
        
def read_last_line(filename):
    with open(filename, 'rb') as f:
        if f.readline():  # Check file is not empty
            f.seek(-2, os.SEEK_END)
            while f.read(1) != b'\n':
                f.seek(-2, io.SEEK_CUR)
            last_line = f.readline().decode()
        else:
            last_line = ''
    return last_line

def max_co_occur(events,interval:int):
    assert interval>0 
    events=np.array(events)
    events=events[np.argsort(events[:,0])]
    ans=0
    cur=[events[0]]
    
    for e in events[1:]:
        #right=e[0]
        cur=[x for x in cur if e[0]-x[1]<interval]
        cur.append(e)
        ans=max(ans,len(cur))
    return ans

def min_max_scale(x):
    x=np.array(x)
    x-=x.min(0)
    x/=x.max(0)
    return x.mean(1) 

def un_async(func):
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(func)

def unix_from_string(m,tz=None):
    m=datetime.strptime(m,"%Y-%m-%d %H:%M")
    if(tz):
        m=tz.localize(m)
    return int(m.timestamp())


def string_from_unix(timestamp, tz=None):
    m = datetime.fromtimestamp(timestamp)
    if tz:
        m = m.astimezone(tz)
    return m.strftime("%Y-%m-%d %H:%M")

