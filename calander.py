import json
import os
from os.path import join,exists
from datetime import datetime
import time

from typing import Optional, Dict

from utills import write_int_to_file,read_int_from_file,read_last_line, max_co_occur

import asyncio 

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
        assert end-start<=s_in_d+1
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
        d['idx']=idx

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
            if not os.listdir(folder_path):
                os.rmdir(folder_path)
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

    def get_next(self,days=7):
        t=int(time.time())
        for i in range(0,days):
            path=self._get_parent_folder(t+i*s_in_d)
            if exists(path):
                m=min(int(name) for name in os.listdir(path))
                path=join(path,str(m))
                ans=[]
                for j in os.listdir(path):
                    with open(join(path,j)) as f:
                        ans.append(json.load(f))
                return ans

class WakeupManager():
    def __init__(self,path,new=False,spacing=60*5,limit=10):
        
        self.history=join(path,'history')
        self.curent=join(path,'curent')
        self.idx_file=join(path,'idx')
        
        if new:
            os.mkdir(path)
            os.mkdir(self.history)
            os.mkdir(self.curent)
            write_int_to_file(self.idx_file,0)

        self.spacing=spacing
        self.limit=limit

        self.tasks={}

    @classmethod 
    async def hook(cls,name,message):
        print(name)
        print(message) 

    async def _hook(self,d,flag):
        #print('started hook')
        await asyncio.sleep(d['time'] - time.time())  # Wait until the time of the wakeup
        flag[0]=False
        await self.hook(d['name'],d['message'])
        d['happened'] = True  # Set happened flag to True
        self.modify(d['idx'], d['time'], d)  # Update the wakeup 
        #print('done hook')
        
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
        cur=read_last_line(join(self.history,f'wakeup_{idx}.jsonl'))
        cur=json.loads(cur)
        return cur
    
    @staticmethod
    def verify_and_unload(d):
        time=d['time']
        name=d['name']
        message=d['message']
        assert type(name)==str
        assert type(message)==str
        assert type(time)==int
        return time,name,message


    def make_task(self,idx,wake):   
        flag=[True]
        self.tasks[idx]=[asyncio.create_task(self._hook(wake,flag)),flag]

    async def add(self,d:dict):
        idx=self.get_count()
        time,name,message=self.verify_and_unload(d)

        d['idx']=idx
        d['happened']=False
        
        #if exists(path):
            #raise Exception("A wakeup already exists for this timestamp")

        my_time=len(self.range_search(time-self.spacing,time+self.spacing))
        capacity=len(self.search_wakeups(time-s_in_d,time+s_in_d)) 

        assert my_time==0 
        assert capacity<self.limit

        path=self._get_folder_path(time)
        os.makedirs(path)

        with open(join(path,f'wakeup_{idx}.json'),'w') as f:
            json.dump(d,f)

        self.log_history(idx,d)
        self._increment_count() 

        self.make_task(idx,d)#asyncio.create_task(self._hook(d))

        return capacity



    def modify(self,idx:int,time :int,d:Optional[Dict] = None):
        '''
        modifies or deletes a file, if you don't pass d it will delete if you do you override
        '''
        folder_path=self._get_folder_path(time)
        file_path=join(folder_path,f'wakeup_{idx}.json')
        if d==None:
            os.remove(file_path)
            if not os.listdir(folder_path):
                os.rmdir(folder_path)
            try:
                task=self.tasks[idx]
                if task[1]:
                    task[0].cancel()
            except KeyError:
                pass
        else:
            self.verify_and_unload(d)
            with open(file_path,'w') as f:
                json.dump(d,f)

        self.log_history(idx,d)

    def log_history(self,idx:int,d:Optional[Dict] = None):
        '''
        takes in an event index and the current state of that event and modifies in the change
        if the event is new it will be created
        '''
        with open(join(self.history,f'wakeup_{idx}.jsonl'),'a') as f:
            f.write('\n'+json.dumps(d))

    
    def check_wakeup_exists(self, time):
        path=self._get_folder_path(time)
        return os.path.exists(path)

    def range_search(self,start:int,end:int):
        ans=[]
        for s in self.search_wakeups(start,end):
            with open(s) as f:
                ans.append(json.load(f)) 
        return ans

    def search_wakeups(self,start:int,end:int):
        assert start<end

        ans=[]
        for i in range((start//s_in_d)*s_in_d,end,s_in_d):
            path=self._get_parent_folder(i)
            if not exists(path):
                continue
            for x in os.listdir(path):
                if start<=int(x)<=end: 
                    ans.extend([join(path,x,s) for s in os.listdir(join(path,x))])
        return ans


    def recover_from_crash(self):
        # Get all wakeups
        wakeups = self.range_search(0, int(time.time()) + s_in_d*365*20)

        for wakeup in wakeups:
            if not wakeup['happened']:  # If a wakeup didn't occur
                asyncio.create_task(self._hook(wakeup))

if __name__=='__main__':
    from shutil import rmtree
    from utills import un_async
    

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
    #c.add({'start':t,'end':t+5,'name':'next 5 seconds'}) 
    #c.add({'start':t,'end':t+10,'name':'next 10 seconds'}) 
    #c.add({'start':t+5,'end':t+10,'name':'next 5 seconds'}) 
    c.add({'start':t+s_in_d*3,'end':t+s_in_d*3+1,'name':'3 days'})
    c.add({'start':t+s_in_d*5,'end':t+s_in_d*5+1,'name':'3 days'})

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
    print('next')
    print(c.get_next())

#wakeupmanager
    print(10*'\n'+'wakeup')
    if exists('wakeup_lol'):
        rmtree('wakeup_lol')

    # Prepare
    manager = WakeupManager('wakeup_lol', new=True, spacing=2, limit=2)  # replace with a valid path

    t=int(time.time()) 
    wakeup1 = {
        'time': t+ 1,  # 1 seconds from now
        'name': 'test1',
        'message': 'this is a test message1'
    }

    wakeup2 = {
        'time': t+ 2,  #  seconds from now
        'name': 'test2',
        'message': 'this is a test message2'
    }

    wakeup3 = {
        'time': t + 3,  #  seconds from now
        'name': 'test2',
        'message': 'this is a test message3'
    }

    print(wakeup1)
    # Add wakeups
    un_async(manager.add(wakeup1))
    try:
        un_async(manager.add(wakeup2.copy()))
        raise ValueError
    except:
        pass

    #loop=asyncio.get_event_loop()
    #for x in loop:
     #   print(x)

    #.run_until_complete()
    print(manager.tasks)
    un_async(manager.tasks[0][0])

    # Check if the wakeups have happened
    wakeup1_result = manager.get_last(0)
    assert wakeup1_result['happened'] == True, "Wakeup 1 did not occur"

    manager=WakeupManager('wakeup_lol',spacing=1,limit=10)
    
    manager.modify(0, wakeup1['time'])
    print(manager.range_search(wakeup1['time'],wakeup1['time']+5))
    
    un_async(manager.add(wakeup1))
    
    try:
        un_async(manager.add(wakeup2))
        raise ValueError 
    except:
        pass

    un_async(manager.add(wakeup3))
    print(manager.tasks)
    manager.modify(wakeup3['idx'], wakeup3['time'])

    #print(manager.tasks)
    tasks=[task[0] for task  in manager.tasks.values()]
    try:
        un_async(asyncio.gather(*tasks))
    except asyncio.exceptions.CancelledError:
        print('we canceled properly')
    #wakeup2_result = manager.get_last(1)
    #assert wakeup2_result['happened'] == True, "Wakeup 2 did not occur"
    from utills import search_key
    print(search_key(manager.curent,'test'))
    print(search_key(manager.curent,'not apearing'))
    
    print("All tests passed successfully!")

    # Clean up
    #manager.modify(0, wakeup1['time'])
    #manager.modify(1, wakeup2['time'])

    #loop.run_forever()
    #print("Clean up successful!")
