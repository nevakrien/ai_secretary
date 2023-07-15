import json
import os
from os.path import join,exists,getctime
from datetime import datetime
import time

from typing import Optional, Dict ,Union

from utills import write_int_to_file,read_int_from_file,read_last_line 

class MemoryFolder():
    def __init__(self,path,cap=100,new=False):
        
        self.history=join(path,'history')
        self.curent=join(path,'curent')
        self.idx_file=join(path,'idx')
        self.cap=cap
        
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


    def scores(self):
        
        relevance={}
        importance={} 
        fresh={}
        entries=tuple(join(self.curent,j) for j in os.listdir(self.curent))

        for path in entries:
            t=time.time()-getctime(path)
            with open(path) as f:
                d=json.load(f)
                #print(d)
            fresh[path]=t
            relevance[path]=d['viewed']/t
            importance[path]=d['importance'] 

        relevance=sorted(entries,key=lambda k:relevance[k])
        importance=sorted(entries,key=lambda k:importance[k])
        fresh=sorted(entries,key=lambda k:fresh[k],reverse=True) 

        scores={k:[None,None,None] for k in entries}

        for i,x in enumerate(relevance):
            scores[x][0]=i
        for i,x in enumerate(importance):
            scores[x][1]=i 
        for i,x in enumerate(fresh):
            scores[x][2]=i 

        return scores

    def prune(self):
        scores=self.scores()
        bad=min(scores.keys(),key=lambda k:scores[k])
        idx=int(bad[:-6].split('_')[-1])
        self._modify(idx)

    def log_history(self,idx:int,d:Optional[Union[Dict,None]] = None):
        '''
        takes in an event index and the curent state of that event and modifys in the change
        if the event is new it will be created
        '''
        
        with open(join(self.history,f'event_{idx}.jsonl'),'a') as f:
            f.write('\n'+json.dumps(d)) 

    def add(self,text :str,importance : Optional[int]=0):
        if len(os.listdir(self.curent))>=self.cap: 
            self.prune()

        idx=self.get_count()
        d={'text':text,'importance':importance,'viewed':0}
        with open(join(self.curent,f'event_{idx}.jsonl'),'w') as f:
            json.dump(d,f)
        self.log_history(idx,d)
        self._increment_count()

    def _modify(self,idx:int,d:Optional[Union[Dict,None]] = None):
        self.verify_log(d)
        path=join(self.curent,f'event_{idx}.jsonl')
        if d==None:
            os.remove(path)
        else:
            with open(path,'w') as f:
                json.dump(d,f)
        
        self.log_history(idx,d)

    def get_all(self):
        ans=[]
        for j in os.listdir(self.curent):
            with open(join(self.curent,j)) as f:
                ans.append(json.load(f))
        return ans

if __name__=='__main__':
    from shutil import rmtree
    if exists('mem_data'):
        rmtree('mem_data')
    
    a=MemoryFolder('mem_data',cap=3,new=True)
    a.add('hey')
    a.add('yo')
    a.add('I am me',3)
    a.add('bad',0)
    a.add('bad2',0)
    a._modify(1,{'text':'yes','importance':3,'viewed':1})
    a._modify(0,None)
    a.prune()
    print(a.get_all())
