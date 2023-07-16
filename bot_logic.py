from calander import Calander 
from memory import MemoryFolder 
from embedding import Lazy_embed #this one will be the debug version 
#from server import Conversation_Manager

from utills import min_max_scale

import os 
from os.path import join,exists

class Bot():
	def __init__(self,path,new=False):
		self.path=path 
		
		if new:
			os.makedirs(path)
		self.cal=Calander(join(path,'calander'),new=new)
		
		self.goals=MemoryFolder(join(path,'goals'),new=new)
		self.mem=MemoryFolder(join(path,'memorys'),new=new)
		self.prof=MemoryFolder(join(path,'user profile'),new=new)
		self.ref=MemoryFolder(join(path,'reflections'),new=new)

	
	@classmethod
	def init_debug_embed(cls,folder):
		cls.embed=Lazy_embed(folder)

	@classmethod
	def init_embed(cls,model):
		#lazy import
		from ai_tools import get_embedding

		func=lambda x: get_embedding(x,model=model)
		cls.embed=Lazy_embed(join('embeddings',model),func=func)

	async def search_folder(self,key,mem,num=10):
		data=mem.get_all()
		#scores=[[self.embed(d['text'])@key,d['importance'],d['existed']] for d in data]
		#scores=[]
		for d in data:
			d['embed']=self.embed(d['text'])
		for d in data:
			d['embed']=await self.embed(d['text'])
		
		scores=[[d['embed']@key,d['importance'],d['existed']] for d in data]

		scores=min_max_scale(scores)
		idx=(-scores).argsort()[:num]
		return [data[i] for i in idx]


if __name__=='__main__':
	from shutil import rmtree
	from utills import un_async
	
	if exists('bot_sketch'):
	    rmtree('bot_sketch')
	
	Bot.init_debug_embed('lol_hash')
	#Bot.init_embed("text-embedding-ada-002")
	bot=Bot('bot_sketch',new=True)

	#print(un_async(bot.embed('hi')))
	for i in range(7):
		bot.mem.add(f'yay{i}')

	x=un_async(bot.embed('hi'))
	ans=un_async(bot.search_folder(x,bot.mem,num=4))
	#Bot.lol='hi'
	print([x['text'] for x in ans])

	print('\n\n')

	for i in range(10):
		bot.cal.add({'start':i,'end':i+3,'name':str(i)})

	print(bot.cal.range_search(5,7))