import json
import os
from os.path import join,exists
from datetime import datetime
import time

from typing import Optional, Dict

from utills import write_int_to_file,read_int_from_file,read_last_line, max_co_occur

s_in_d=60*60*24

class Calander():
    def __init__(self,path,new=False,hour_limit=100,day_limit=1000):
        
        self.history=join(path,'history')
        self.curent=join(path,'curent')
        self.idx_file=join(path,'idx')
        
        if new:
            os.mkdir(path)
            os.mkdir(self.history)
            os.mkdir(self.curent)
            write_int_to_file(self.idx_file,0)

        self.hour_limit=hour_limit 
        self.day_limit=day_limit

    def _get_parent_folder(self, time_key: int) -> str:
        x=time_key//s_in_d
        x=x*s_in_d
        return join(self.curent,f'{x}_{x+s_in_d-1}')

    def _get_folder_path(self, time_key: int) -> str:
        return join(self._get_parent_folder(time_key),str(time_key))


    def get_count(self):
        return read_int_from_file(self.idx_file) 
    def _increment_count(self): 
        count=self.get_count()+1
        write_int_to_file(self.idx_file,count) 
    
    def get_last(self,idx:int):
        cur=read_last_line(join(self.history,f'event_{idx}.jsonl'))
        cur=json.loads(cur)
        return cur
    
    @staticmethod
    def verify_and_unload(d):
        start=d['start']
        end=d['end']
        name=d['name']
        assert type(name)==str
        assert start<end 
        assert end-start<=s_in_d
        return start,end,name
    
    def capacity_check(self,start:int,end:int,interval:int):
        check=self.range_search(start-interval,end+interval)
        if not check:
            return 0
        check=[(x['start'],x['end']) for x in check]
        return max_co_occur(check,interval)

    def add(self,d:dict):
        idx=self.get_count()
        start,end,name=self.verify_and_unload(d)

        hour_capacity=self.capacity_check(start,end,60*60)
        day_capacity=self.capacity_check(start,end,s_in_d) 

        assert day_capacity<self.day_limit
        assert hour_capacity<self.hour_limit

        path=self._get_folder_path(start)
        if not exists(path):
            os.makedirs(path)
        with open(join(path,f'event_{idx}.json'),'w') as f:
            json.dump(d,f)

        self.log_history(idx,d)
        self._increment_count()

        return {'day':day_capacity,'hour':hour_capacity}
      

    def modify(self,idx:int,start_time :int,d:Optional[Dict] = None):
        '''
        modifys or deletes a file, if u dont pass d u will delete if u do u overide
        '''
        folder_path=self._get_folder_path(start_time)
        file_path=join(folder_path,f'event_{idx}.json')
        if d==None:
            os.remove(file_path)
            os.removedirs(folder_path)
        else:
            self.verify_and_unload(d)
            with open(file_path,'w') as f:
                json.dump(d,f)

        self.log_history(idx,d)


        
    def log_history(self,idx:int,d:Optional[Dict] = None):
        '''
        takes in an event index and the curent state of that event and modifys in the change
        if the event is new it will be created
        '''
        with open(join(self.history,f'event_{idx}.jsonl'),'a') as f:
            f.write('\n'+json.dumps(d))

    def search_events_start(self,start:int,end:int):
        assert start<end
        
        ans=[]
        for i in range((start//s_in_d)*s_in_d,end,s_in_d):
            #print(i)
            path=self._get_parent_folder(i)
            if not exists(path):
                continue
            for x in os.listdir(path):
                if start<=int(x)<=end: 
                    ans.extend([join(path,x,s) for s in os.listdir(join(path,x))])
        return ans

    def range_search(self,start:int,end:int):
        
        ans=[]
        for s in self.search_events_start(start-s_in_d,start-1):
            with open(s) as f:
                x=json.load(f)
                if start<x['end']:
                    ans.append(x) 
        for s in self.search_events_start(start,end):
            with open(s) as f:
                    ans.append(json.load(f)) 
        return ans



if __name__=='__main__':
    from shutil import rmtree
    

    if exists('cal_data'):
        rmtree('cal_data')
    c=Calander('cal_data',new=True)
    c=Calander('cal_data')

    t=int(time.time())
    p=c._get_folder_path(t)
    print(p)
    #os.makedirs(p)
    j='\n'+json.dumps(None)
    print(j)
    print(json.loads(j))
    #c.add(None)
    c.add({'start':1,'end':2,'name':'event name'})
    c.add({'start':t,'end':t+5,'name':'next 5 seconds'}) 

    print('found:')
    print(c.search_events_start(0,s_in_d*365*20))
    try: 
        c.add({'start':t,'end':0,'name':'event name'})
        raise ValueError
    except:
        pass
    
    try: 
        c.modify(1,c.get_last(1)['start'],{'yay':'!!'})
        raise ValueError
    except: 
        pass
    
    c.modify(0,1,None)
    print(c.get_last(1))
    print('range test')

    c.add({'start':-10,'end':27,'name':'event name'})
    c.add({'start':1,'end':27,'name':'event name'})
    c.add({'start':20,'end':21,'name':'event name'})
    c.add({'start':1,'end':27,'name':'event name'})
    c.add({'start':28,'end':30,'name':'event name'})

    print(c.range_search(5,10))

    try:
        c=Calander('cal_data',hour_limit=1)
        c.add({'start':1,'end':27,'name':'event name'})
        raise ValueError 
    except:
         c=Calander('cal_data')

    #print('\n'*20)
    print (c.capacity_check(0,100,1))
    print (c.capacity_check(0,100,100))

    print(c.add({'start':1,'end':27,'name':'event name'}))

