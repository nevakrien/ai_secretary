
import hashlib
import os
from os.path import exists,join

import numpy as np

#this is a tester function that would be an api call
def get_embedings(input_string, vector_length=7):
    hash_object = hashlib.sha256(input_string.encode())
    hex_dig = hash_object.hexdigest()
    seed = int(hex_dig, 16) % (2**32 - 1)  # Convert to integer first, then apply modulo
    np.random.seed(seed)
    vector = np.random.random(size=vector_length)
    return vector 

class DiskHash():
    def __init__(self,file):
        self.file=file
        if not exists(file):
            os.makedirs(file)
        self.d={}
    
    def hash(self,key:str):
        return hashlib.sha256('a'.encode()).hexdigest()

    def __setitem__(self,key:str,val :np.array):
        self.d.update({key:val})
        h=self.hash(key)
        path=join(self.file,h+'.npy')

        
        if exists(path):
            x=np.load(path,allow_pickle=True).item()
            x.update({key:val})
        else:
            x={key:val}
        np.save(path,x)

    def __getitem__(self,key):
        try:
            return self.d[key]
        except KeyError:
            pass
        h=self.hash(key)
        path=join(self.file,h+'.npy')
        if not exists(path):
            raise KeyError
        self.d.update(np.load(path,allow_pickle=True).item())
        return self.d[key]

class Lazy_embed():
    def __init__(self,folder='embeddings'):
        self.d=DiskHash(folder)

    def __call__(self,x):
        try:
            return self.d[x]
        except KeyError:
            y=get_embedings(x)
            self.d[x]=y
            return y

if __name__ == '__main__':
    print(DiskHash('lol_hash').hash('yass'))
    d=DiskHash('lol_hash')
    d['yes']=get_embedings('yes')
    print(d['yes'])
    print(DiskHash('lol_hash')['yes'])

    emb=Lazy_embed('lol_hash')
    print(emb('five'))