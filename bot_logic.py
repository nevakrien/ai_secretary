from calander import Calander,s_in_d
from memory import MemoryFolder 
from embedding import Lazy_embed #this one will be the debug version 
#from server import Conversation_Manager

from utills import min_max_scale,unix_from_string,string_from_unix

import asyncio

import os 
from os.path import join,exists

from datetime import datetime
import time
import pytz 

class Bot():
	def __init__(self,path,new=False):
		self.semaphore = asyncio.Semaphore(1)
		self.path=path 
		
		if new:
			os.makedirs(path)
			self.set_timezone('Asia/Jerusalem')

		self.cal=Calander(join(path,'calander'),new=new)
		
		self.goals=MemoryFolder(join(path,'goals'),new=new)
		self.mem=MemoryFolder(join(path,'memories'),new=new)
		self.prof=MemoryFolder(join(path,'user profile'),new=new)
		self.ref=MemoryFolder(join(path,'reflections'),new=new)
    
	async def lock(self):
		await self.semaphore.acquire()

	def free(self):
		self.semaphore.release()

	def set_timezone(self,tz):
		with open(join(self.path,'time_zone.txt'),'w') as f:
				f.write(tz)

	async def get_timezone(self):
		with open(join(self.path,'time_zone.txt')) as f:
				return pytz.timezone(f.read())
	
	@classmethod
	def init_debug_embed(cls,folder):
		cls.embed=Lazy_embed(folder)

	@classmethod
	def init_embed(cls,model):
		#lazy import
		from ai_tools import get_embedding

		func=lambda x: get_embedding(x,model=model)
		cls.embed=Lazy_embed(join('embeddings',model),func=func)

	async def search_folder(self, key, mem, num=10):
	    data = mem.get_all()

	    if len(data) == 0:
	        return []

	    # Start tasks to read data and compute embeddings
	    tasks = [asyncio.create_task(self.embed(d['text'])) for d in data]

	    # Await tasks and assign embeddings to data
	    for d, task in zip(data, tasks):
	        d['embed'] = await task

	    scores = [[d['embed'] @ key, d['importance'], d['existed']] for d in data]
	    scores = min_max_scale(scores)
	    idx = (-scores).argsort()[:num]

	    return [data[i] for i in idx]


	async def range_search(self,start,end):
		return self.cal.range_search(start,end)

	async def get_info(self,message,start,end):
		t = int(time.time())

		# Start the key and events tasks
		key_task = asyncio.create_task(self.embed(message))
		events_task = asyncio.create_task(self.range_search(start, end))

		# Await key to start folder_tasks
		key = await key_task
		folders = [self.prof, self.goals, self.mem, self.ref]
		folder_tasks = [asyncio.create_task(self.search_folder(key, x)) for x in folders]

		# Finally, await events and folder_tasks
		events = await events_task
		folders = await asyncio.gather(*folder_tasks)

		return [message, folders, events]

	def format_info(self,message, folders, events,tz):
		#tz=self.get_timezone()

		ans='recent events:\n'
		for i,e in enumerate(events):
			start=string_from_unix(e['start'],tz=tz)
			end=string_from_unix(e['end'], tz=tz)
			ans+=f"{i}. {e['name']} starts:{start} ends:{end}\n"
		ans+='\n'

		ans+='Format:\nid. text [importance]:\n\n'
		for folder,name in zip(folders,['user profile', 'goals', 'memories', 'reflections']):
			ans+=f"{name}:\n"
			for i,d in enumerate(folder):
				ans+=f"{i}. {d['text']} [{d['importance']}]\n"
			ans+='\n'

		ans+=f'user said: {message}' 

		return ans

	async def respond_to_message(self, message):
	    await self.lock()
	    t = int(time.time())
	    tz=await self.get_timezone()
	    info=await self.get_info(message,t-s_in_d,t+s_in_d)
	    ans=BotAnswer(self,info,tz)
	    info=self.format_info(*info,tz=tz)
	    delay = 10
	    self.free()
	    return ans,info, delay

class BotAnswer():
	def __init__(self,bot,info,tz):
		self.bot=bot
		self.tz=tz
		#warning!!! order matters
		self.folders={'user profile':bot.prof,'goals':bot.goals,'memories':bot.mem,'reflections':bot.ref}
		self.cal=bot.cal
		self.note_info={k:v for k,v in zip(self.folders.keys(),info[1])}
		self.new_notes={k:[] for k in self.folders.keys()}
		self.event_info=info[2]
		self.new_events=[]
	

	async def search_calander(self,start:str,end:str):
		start=unix_from_string(start,self.tz)
		end=unix_from_string(end,self.tz)
		return await self.bot.range_search(start,end) 

	def modify_note(self,folder,idx,text=None,importance=None):
		'''
        changes note number idx in folder 
        if idx is zero make a new one

        if the no change is passed this will delete the entry

        impotance should be an int 
        and folder should be in ['user profile', 'goals', 'memories', 'reflections']
        '''
		if text==None and importance==None:
			self.note_info[folder][idx]=self.note_info[folder][idx]['idx']
			return

		if idx==None:
			self.new_notes[folder].append({'text':text,'importance':importance})
			return
		
		d=self.note_info[folder][idx]
		if text!=None:
			d['text']=text
		if importance!=None:
			d['importance']=importance


	def modify_event(self,idx,d):
		'''
		expects either a dict with ['start','end','name'] or None
		if None is passed will delete the entry
		'''
		if d!=None:
			d['start']=unix_from_string(d['start'])
			d['end']=unix_from_string(d['end'])
		else: 
			d=self.event_info[idx]
			d=[d['idx'],d['start']]

		if idx==None:
			self.new_events.append(d)
			return 

		self.event_info[idx]=d

	def resolve_changes(self):
		#new
		for k,v in self.new_notes.items():
			folder=self.folders[k]
			for d in v:
				folder.add(text=d['text'],importance=d['importance'])
		
		for d in self.new_events:
			self.cal.add(d)

		#modify
		for k,v in self.note_info.items():
			folder=self.folders[k]
			for d in v:
				if isinstance(d,int):
					folder._modify(d)
				else:
					print(d)
					d['viewed']+=1
					d.pop('embed')
					folder._modify(d['idx'],d)

		for d in self.event_info:
			if isinstance(d,list):
				#print('del')
				self.cal.modify(d[0],d[1])
			else:
				self.cal.modify(d['idx'],d['start'],d)





if __name__=='__main__':
	from shutil import rmtree
	from utills import un_async
	
	if exists('bot_sketch'):
	    rmtree('bot_sketch')
	
	Bot.init_debug_embed('lol_hash')
	#Bot.init_embed("text-embedding-ada-002")
	bot=Bot('bot_sketch',new=True)
	t=int(time.time()) 

	#print(un_async(bot.embed('hi')))
	for i in range(7):
		bot.ref.add(f'yay{i}'+i*'!',i)

	for i in range(7):
		bot.mem.add(f'stuff{i}'+(i%4)*'\n'+'yes',i%3)

	x=un_async(bot.embed('hi'))
	ans=un_async(bot.search_folder(x,bot.mem,num=4))
	#Bot.lol='hi'
	print(ans[0])
	print([x['text'] for x in ans])

	print('\n\n')

	for i in range(100):
		bot.cal.add({'start':i,'end':i+3,'name':str(i)})

	print(bot.cal.range_search(5,7))

	print(f'\n{datetime.fromtimestamp(1).astimezone(un_async(bot.get_timezone()))}')
	
	bot.cal.add({'start':t,'end':t+1,'name':'now'})
	response=un_async(bot.respond_to_message('hey'))

	print(response[1])
	#response=BotAnswer(bot,un_async(bot.get_info('gay',0,100)))
	ans= un_async(response[0].search_calander('1970-01-01 02:00','1970-01-01 02:01'))

	print(max([int(x['name']) for x in ans]))

	

	response[0].modify_note('memories',1)
	response[0].modify_note('user profile',None,'hey',2)
	
	response[0].modify_event(0,None)
	response[0].modify_event(None,{'start':'2021-01-01 02:00','end':'2021-01-02 02:00','name':'mood'})

	response[0].resolve_changes()
	print(bot.prof[0])

	