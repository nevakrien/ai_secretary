import numpy as np
import os
from shutil import rmtree 

from datetime import datetime  
from os.path import join,exists

from typing import Union

#this are just for the test
import hashlib

def get_embedings(input_string, vector_length=7):
    hash_object = hashlib.sha256(input_string.encode())
    hex_dig = hash_object.hexdigest()
    seed = int(hex_dig, 16) % (2**32 - 1)  # Convert to integer first, then apply modulo
    np.random.seed(seed)
    vector = np.random.random(size=vector_length)
    return vector


class memory():
    def __init__(self, path):
        assert exists(path)
        self.path = path 
    
    @staticmethod 
    def make_new(path):    
        os.makedirs(path)
        for f in memory.get_base_folders():
        	os.mkdir(join(path,f))
        return memory(path)
    
    @staticmethod  
    def get_base_folders():
    	return ['notes','goals','history']

    def add_folder(self, heading: str, text: str, place='history'):
        path = join(self.path, place)
        assert exists(path)
        assert len(heading) < 100
        new_folder_path = join(path, heading)

        assert '.' not in new_folder_path #this makes sure the ai dosent access the external file system
        os.makedirs(new_folder_path, exist_ok=True)
        
        self.add_memory('created',text,2,place=join(place,heading))

    def add_memory(self, heading: str, text : str,importance :Union[int,float], place='history'):
        path = join(self.path, place)
        assert exists(path)
        assert len(heading) < 100
        save_path=join(path, heading)
        assert '.' not in save_path #this makes sure the ai dosent access the external file system
        np.save(save_path, {'text': text, 'key': get_embedings(text),'importance': importance,
        	'time':datetime.now().strftime('%Y-%m-%d %H:%M:%S')})


    def change_importance(self, heading: str,importance :Union[int,float], place='history'):
        path = join(self.path, place, heading)
        assert '.' not in path #this makes sure the ai dosent access the external file system
        x=np.load(path+'.npy', allow_pickle=True).item()
        #print(x)
        x['importance']=importance 
        np.save(path+'.npy',x)
        

    def remove_memory(self, heading: str, place='history'):
        path = join(self.path, place, heading)
        assert '.' not in path #this makes sure the ai dosent access the external file system
        os.remove(path+'.npy')
            
    
    def remove_folder(self, folder:  str, place=''):
        path = join(self.path, place, folder)
        assert '.' not in path #this makes sure the ai dosent access the external file system
        assert not path in self.get_base_folders() 
        rmtree(path)
    
    def _search(self, place, depth=-1, date_range=None, importance_threshold=None, keyword=None, only_created=False):
        path = join(self.path, place)
        assert exists(path)
        return self._recursive_search(path, depth, date_range, importance_threshold, keyword, only_created)

    def _recursive_search(self, path, depth, date_range, importance_threshold, keyword, only_created):
        results = []
        if depth == 0:
            return results
        for entry in os.scandir(path):
            if entry.is_file() and entry.name.endswith('.npy'):
                if only_created and entry.name != 'created.npy':
                    continue
                if keyword and keyword not in entry.name:
                    continue
                data = np.load(entry.path, allow_pickle=True).item()  # convert numpy array to Python dict
                mem_date = datetime.strptime(data['time'], '%Y-%m-%d %H:%M:%S')
                mem_importance = data['importance']
                if date_range:
                    start_date = datetime.strptime(date_range[0], '%Y-%m-%d')
                    end_date = datetime.strptime(date_range[1], '%Y-%m-%d')
                    if not start_date <= mem_date <= end_date:
                        continue
                if importance_threshold:
                    if mem_importance < importance_threshold:
                        continue
                results.append((os.path.dirname(entry.path), entry.name, data))
            elif entry.is_dir():
                results.extend(self._recursive_search(entry.path, depth - 1, date_range, importance_threshold, keyword, only_created))
        return results

    def search(self, place, depth=-1, date_range=None, importance_threshold=None, keyword=None, only_created=False, fields=('text',)):
        raw_results = self._search(place, depth, date_range, importance_threshold, keyword, only_created)
        tree = {}
        data = []

        for dirpath, filename, contents in raw_results:
            relative_path = os.path.relpath(dirpath, self.path)
            path_parts = relative_path.split(os.path.sep)
            cursor = tree
            for part in path_parts:
                if part not in cursor:
                    cursor[part] = {}
                cursor = cursor[part]
            info = {field: contents[field] for field in fields}
            cursor[filename] = info
            data.append((dirpath, filename, info))

        def pretty_print_tree(tree_dict, indent=''):
            lines = []
            for key, value in tree_dict.items():
                if isinstance(value, dict):
                    lines.append(f"{indent}{key}:")
                    lines.extend(pretty_print_tree(value, indent=indent + '\t'))
                else:
                    lines.append(f"{indent}{key}: {value}")
            return lines

        lines = pretty_print_tree(tree)
        return '\n'.join(lines), data

     
if __name__ == '__main__':
    if exists('lol'):
    	rmtree('lol')

    x=memory.make_new('lol')
    x.add_folder('dirr','discribing this folder')
    x.add_memory('mem','first',1)
    x.add_memory('mem','i added u',10,place=join('history','dirr'))
    memory('lol').change_importance('mem',2,place=join('history','dirr'))
    print(memory('lol')._search('history',2,importance_threshold=2))

    print('\n\n\n')
    x.add_memory('mem2','first',1)
    x.add_memory('stuff','first',1)
    x.remove_memory('mem', place=join('history','dirr'))
    #x.remove_folder('dirr', 'history')
    x.add_folder('check','discribing this folder',place="")
    print(memory('lol')._search('history', 1,keyword='mem'))

    print('\n\n\n')

    x.add_folder('check 2', 'history')
    x.add_folder('check','discribing this folder',place="")
    tree,data=memory('lol').search('', -1,only_created=True,)
    print(tree)
    print(data)