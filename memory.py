import json
import os
from os.path import join,exists,getctime
from datetime import datetime
import time

from typing import Optional, Dict ,Union

from utills import write_int_to_file,read_int_from_file,read_last_line ,min_max_scale

class MemoryFolder():
    def __init__(self,path,cap=100,new=False,relevance_time=60*60):
        
        self.history=join(path,'history')
        self.curent=join(path,'curent')
        self.idx_file=join(path,'idx')
        self.cap=cap
        self.relevance_time=relevance_time
        
        if new:
            os.mkdir(path)
            os.mkdir(self.history)
            os.mkdir(self.curent)
            write_int_to_file(self.idx_file,0)
    
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
    def verify_log(d:Optional[Union[Dict,None]] = None):
        if d==None: 
            return 
        for k in ('text','importance','viewed'):
            assert k in d.keys()
    @staticmethod
    def idx_from_path(path):
        return int(path[:-6].split('_')[-1]) #'.jsonl' is 6 charchters and its junk_event_idx.jsonl
    def scores(self,d):
        return [d['viewed']/(d['existed']+self.relevance_time),d['existed'],d['importance']]

    def prune(self):
        entries=self.get_all()
        scores=[self.scores(d) for d in entries]
        scores=min_max_scale(scores)
        bad=entries[scores.argmin()]['path']
        idx=self.idx_from_path(bad) 
        self._modify(idx)

    def log_history(self,idx:int,d:Optional[Union[Dict,None]] = None):
        '''
        takes in an event index and the curent state of that event and modifys in the change
        if the event is new it will be created
        '''
        if d==None:
            d={}
        d['change history time']=time.time()
        with open(join(self.history,f'event_{idx}.jsonl'),'a') as f:
            f.write('\n'+json.dumps(d)) 

    def add(self,text :str,importance : Optional[int]=0):
        if len(os.listdir(self.curent))>=self.cap: 
            self.prune()

        idx=self.get_count()
        d={'text':text,'importance':importance,'viewed':0,'idx':idx}
        with open(join(self.curent,f'event_{idx}.jsonl'),'w') as f:
            json.dump(d,f)
        self.log_history(idx,d)
        self._increment_count()
        return idx

    def _modify(self,idx:int,d:Optional[Union[Dict,None]] = None):
        self.verify_log(d)
        path=join(self.curent,f'event_{idx}.jsonl')
        if d==None:
            os.remove(path)
        else:
            with open(path,'w') as f:
                json.dump(d,f)
        
        self.log_history(idx,d)

    def get(self,idx:int):
        path=join(self.curent,f'event_{idx}.jsonl')
        
        with open(path) as f:
            d=json.load(f)

        return d
    
    def __getitem__(self,idx:int):
        path=join(self.curent,f'event_{idx}.jsonl')
        
        if exists(path): 
            with open(path) as f:
                d=json.load(f)
        else:
            path=join(self.history,f'event_{idx}.jsonl')
            d=json.loads(read_last_line(path)) 

        d['existed']=time.time()-getctime(path)
        #d['path']=path
        return d

    def modify(self,idx:int,text=None,importance=None,view=True):
        '''
        user sides modifacation claw. 
        if the no change is passed this will delete the entry
        '''
        if text==None and importance==None and not view:
            self._modify(idx,None)
            return 
        d=self.get(idx)

        if text!=None:
            d['text']=text
        if importance!=None:
            d['importance']=importance
        if view:
            d['viewed']+=1
        d.update(d)

        self._modify(idx,d)

    #def remove(self,idx:int):
        #self._modify(idx)

    def get_all(self):
        ans=[]
        for j in os.listdir(self.curent):
            path=join(self.curent,j)
            with open(path) as f:
                d=json.load(f)
                d['existed']=time.time()-getctime(path)
                d['path']=path
                ans.append(d)
        return ans

if __name__=='__main__':
    from shutil import rmtree
    if exists('mem_data'):
        rmtree('mem_data')
    
    a=MemoryFolder('mem_data',cap=3,new=True)
    #a.scores=lambda x: [0.]
    a.add('hey')
    a.add('yo')
    a.add('I am me',3)
    a.add('bad',0)
    a.add('bad2',0)
    a=MemoryFolder('mem_data')
    a._modify(1,{'text':'yes','importance':3,'viewed':1})
    a._modify(0,None)
    #print(a.get_all())
    a.prune()
    print(a.get_all())
    a.add('get me',3)
    #a.add('get me',3)
    print(a[5])
    print('\n')
    
    try: 
        a.modify(3,'modified')
        raise ValueError 
    except:
        pass
    print(a[3])
    a.modify(5,'modified')
    print(a[5])
    a.modify(5,view=False)
    print(a[5])
