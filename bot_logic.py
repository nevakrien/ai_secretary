from calander import Calander 
from memory import MemoryFolder 
from embedding import Lazy_embed #this one will be the debug version 

import os 
from os.path import join,exists

class Bot():
	def __init__(self,path,new=False):
		self.path=path 
		if new:
			os.makedirs(path)
		self.cal=Calander(join(path,'calander'),new=new)
		
		self.goals=Calander(join(path,'goals'),new=new)
		self.mem=Calander(join(path,'memorys'),new=new)
		self.prof=Calander(join(path,'user profile'),new=new)
		self.ref=Calander(join(path,'reflections'),new=new)

	
	@classmethod
	def init_debug_embed(cls,folder):
		cls.embed=Lazy_embed(folder)

	@classmethod
	def init_embed(cls,model):
		#lazy import
		from ai_tools import get_embedding

		func=lambda x: get_embedding(x,model=model)
		cls.embed=Lazy_embed(join('embeddings',model),func=func)

if __name__=='__main__':
	from shutil import rmtree
	from utills import un_async
	
	if exists('bot_sketch'):
	    rmtree('bot_sketch')
	
	Bot.init_debug_embed('lol_hash')
	bot=Bot('bot_sketch',new=True)

	print(un_async(bot.embed('hi')))
	#Bot.lol='hi'
	#print(bot.lol)