import json
import os
from os.path import join,exists
from datetime import datetime
import time

from typing import Optional, Dict

from utills import write_int_to_file,read_int_from_file,read_last_line



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

    def _get_folder_path(self, time_key: int, current: bool = False) -> str:
        time_key=datetime.fromtimestamp(time_key)
        return os.path.join(self.curent,time_key.strftime('%Y/%m/%d/%s'))

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
        assert end-start<=60*60*24
        return start,end,name
    
    def add(self,d:dict):
        idx=self.get_count()
        start,end,name=self.verify_and_unload(d)

        
        path=self._get_folder_path(start)
        os.makedirs(path)
        with open(join(path,f'event_{idx}.json'),'w') as f:
            json.dump(d,f)

        self.log_history(idx,d)
        self._increment_count()
      

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
        #this is has weird timezone bugs in edge cases
        assert start<end
        start_date=datetime.fromtimestamp(start)
        end_date=datetime.fromtimestamp(end)

        ans=[] 

        #big chunk of range checks
        for year in range(start_date.year,end_date.year+1):
            if year==start_date.year:
                start_month=start_date.month
            else:
                start_month=1

            if year==end_date.year:
                end_month=end_date.month
            else:
                end_month=12

            for month in range(start_month,end_month+1):
                if year==start_date.year and month==start_date.month:
                    start_day=start_date.day
                else:
                    start_day=1

                if year==end_date.year and month==end_date.month:
                    end_day=end_date.day
                else:
                    end_day=31

                for day in range(start_day,end_day+1):
                    #print(f'{year}-{month}-{day}')
                    m=str(month)
                    if(len(m)==1):
                        m=f'0{m}'
                    d=str(day)
                    if(len(d)==1):
                        d=f'0{d}'
                    path=join(self.curent,str(year),m,d)
                    if not exists(path):
                        continue
                    for unix in os.listdir(path):
                        if start<=int(unix)<=end:
                            ans.extend(os.listdir(join(path,unix)))
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
    print(c.search_events_start(0,50000000))
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
    
    #c.modify(0,1,None)
    print(c.get_last(1))
