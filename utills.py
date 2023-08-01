import os
import json
import io
import numpy as np 

import asyncio

from datetime import datetime
from dateutil.parser import parse

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
    x/=x.max(0)+0.1 #eww I am gona puke
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

def contains_all_fields(dictionary, fields):
    return all(field in dictionary for field in fields)

def openai_format(text,role='system'):
    return {'role':role,'content':text}

def unix_from_ans(dt_input, tz=None):
    if isinstance(dt_input, dict):
        ans = datetime(**dt_input)
    elif isinstance(dt_input, str):
        ans = parse(dt_input)
    else:
        raise ValueError("Input must be a dictionary or a string")

    if tz:
        if isinstance(tz, str):
            tz = pytz.timezone(tz)
        ans = ans.astimezone(tz)

    return int(ans.timestamp())

def search_key(folder,key,field='name'):
    ans=[]
    for s in os.listdir(folder):
        path=os.path.join(folder,s)
        if os.path.isdir(path):
            ans.extend(search_key(path,key,field))
        else:
            with open(path) as f:
                d=json.load(f)
                if key in d[field]:
                    ans.append(d)
    return ans

if __name__=='__main__':
    unix_from_ans({'year': 2023, 'month': 8, 'day': 1, 'hour': 17, 'minute': 11})
    unix_from_ans('2023-08-01 17:11')
    unix_from_ans('2023-08-01T17:11:00Z')
    unix_from_ans('August 1, 2023 17:11:00')
    print(unix_from_ans("2023-08-02 10:00"))
