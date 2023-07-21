from calander import Calander,WakeupManager,s_in_d
from memory import MemoryFolder 
from embedding import Lazy_embed #this one will be the debug version 
#from server import Conversation_Manager

from ai_tools import gpt_response

from utills import min_max_scale,string_from_unix,openai_format,unix_from_ans

import asyncio
from utills import un_async

import os 
from os.path import join,exists

from datetime import datetime
import time
import pytz 

import numpy as np

class Bot():
	ai_call=None
	def __init__(self,path,new=False):
		self.semaphore = asyncio.Semaphore(1)
		self.path=path 
		
		if new:
			os.makedirs(path)
			self.set_timezone('Asia/Jerusalem')

		self.tz=self.get_timezone()
		#self.ai_call=None

		self.cal=Calander(join(path,'calander'),new=new)
		self.wakeup=WakeupManager(join(path,'wakeups'),new=new)
		self.wakeup.hook=None #this should be overwriten externaly but I am just making sure
		
		self.goals=MemoryFolder(join(path,'goals'),new=new)
		self.mem=MemoryFolder(join(path,'memories'),new=new)
		self.prof=MemoryFolder(join(path,'user profile'),new=new)
		self.ref=MemoryFolder(join(path,'reflections'),new=new)
    
	async def lock(self):
		await self.semaphore.acquire()

	def free(self):
		self.semaphore.release()

	def set_timezone(self,tz):
		self.tz=pytz.timezone(tz)
		with open(join(self.path,'time_zone.txt'),'w') as f:
				f.write(tz)

	def get_timezone(self):
		with open(join(self.path,'time_zone.txt')) as f:
				return pytz.timezone(f.read())
	
	@classmethod
	def init_gpt_func(cls,func):
		cls.ai_call=[func]

	@classmethod
	def init_debug_embed(cls,folder):
		cls.embed=Lazy_embed(folder)

	@classmethod
	def init_embed(cls,model):
		print('you are using the real embedings')
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

	    scores = [[d['embed']@ key, d['importance'], d['existed']] for d in data]
	    scores = min_max_scale(scores)
	    idx = (-scores).argsort()[:num]

	    return [data[i] for i in idx]

	async def key_names(self,arr):
	    if not arr:
	    	return 0

	    tasks = [asyncio.create_task(self.embed(d['name'])) for d in arr]

	    # Await tasks and assign embeddings to data
	    for d, task in zip(arr, tasks):
	        d['embed'] = await task

	    return np.mean([d['embed'] for d in arr],axis=0)


	async def get_info(self,message,start,end,a=0.3,b=0.5,c=0.3,d=0.8):
		t = int(time.time())

		# Start the key and events tasks
		key_task = asyncio.create_task(self.embed(message))
		events = self.cal.range_search(start, end)
		wake = self.wakeup.range_search(start, end)
		
		#wake,events=await asyncio.gather(wake_task,events_task)
		events.sort(key=lambda d: d['start'])
		wake.sort(key=lambda d: d['time'])

		# Await key to start folder_tasks
		time_dep_key=await self.key_names(events+wake)
		#time_dep=self.format_time_dependent(wake,events)
		key = await key_task
		key+=a*time_dep_key

		folders=[]

		folders.append(await self.search_folder(key, self.mem))
		if folders[-1]:
			key+=b*np.mean([d['embed'] for d in folders[-1]],axis=0)

		folders.append(await self.search_folder(key, self.prof))
		if folders[-1]:
			key+=c*np.mean([d['embed'] for d in folders[-1]],axis=0)

		folders.append(await self.search_folder(key, self.goals))
		if folders[-1]: 
			key+=d*np.mean([d['embed'] for d in folders[-1]],axis=0)

		folders.append(await self.search_folder(key, self.ref))

		return [message, folders, events,wake]

	def format_time_dependent(self,events,wakes):
		ans=[openai_format('events: index. name; start; end;')]#'recent events:\n'
		
		for i,e in enumerate(events):
			start=string_from_unix(e['start'],tz=self.tz)
			end=string_from_unix(e['end'], tz=self.tz)
			ans.append(openai_format(f"{i}. {e['name']}; starts:{start}; ends:{end}"))
		#ans+='\n'
		ans.append(openai_format('wakeups: index. name; time\nmessage;'))
		for i,w in enumerate(wakes):
			time=string_from_unix(w['time'],tz=self.tz)
			ans.append(openai_format(f"{i}. {w['name']}; time:{time}\n{w['message']}"))

		return ans

	def format_folder(self,folder,name):
		if not folder:
			return []
		ans=[openai_format(f"{name}:\n")]
		for i,d in enumerate(folder):
				ans.append(openai_format(f"{i}. {d['text']} [{d['importance']}]",role='assistant'))
		return ans

	def format_folders(self,message, folders,source):
		#tz=self.get_timezone()
		#ans=self.format_time_dependent(wakeups,events)

		ans=[openai_format('Format:\nid. text [importance]:')]
		
		for folder,name in zip(folders,['memories','user profile', 'goals',  'reflections']):
			ans+=self.format_folder(folder,name)
			

		ans.append(openai_format(f'{message}',role=source)) 

		return ans

	async def logic_step(self,time_inputs,folder_inputs,info,ans):
		x,text,function_call=await self.ai_call[0](time_inputs+folder_inputs)
		folder_inputs.append(x)
		if function_call:
			try:
				out= ans.funcs[function_call['name']](function_call['arguments'])
				if out:
					if function_call['name']=='search_calander':
						ans.resolve_changes() 
						info[-2:]=out
						time_inputs=self.format_time_dependent(*info[2:4])
						d=openai_format('sucessfuly changed the events at the top',role='function')
						d['name']='search_calander'
						folder_inputs.append(d)
						ans=BotAnswer(self,info)

			except Exception as e:
				d=openai_format(str(e),role='function')
				d['name']=function_call['name']
				folder_inputs.append(d)
		return ans

	async def session(self, message,source):
	    await self.lock()
	    t = int(time.time())
	    #tz=await self.get_timezone()
	    info=await self.get_info(message,t-s_in_d,t+s_in_d)
	    ans=BotAnswer(self,info)
	    folder_inputs=self.format_folders(*info[:2],source)
	    time_inputs=self.format_time_dependent(*info[2:4])
	    
	    if self.ai_call:
	    	ans=await self.logic_step(time_inputs,folder_inputs,info,ans)
	    	self.free()
	    	return ans
	    else:
	    	print('runing without ai calls')
	    	delay = 10
	    self.free()
	    return ans,time_inputs+folder_inputs, delay
	
	async def respond_to_message(self, message):
		return await self.session(message,source='user')

class BotAnswer():
	def __init__(self,bot,info):
		self.bot=bot
		self.tz=bot.tz

		self.funcs={'search_calander':self.search_calander, 'modify_note':self.modify_note,
		 'modify_event':self.modify_event, 'modify_wakeup':self.modify_wakeup}
		#warning!!! order matters
		self.folders={'memories':bot.mem,'user profile':bot.prof,'goals':bot.goals,'reflections':bot.ref}
		self.cal=bot.cal
		self.wakeup=bot.wakeup
		self.note_info={k:v for k,v in zip(self.folders.keys(),info[1])}
		self.new_notes={k:[] for k in self.folders.keys()}
		self.event_info=info[2]
		self.new_events=[]
		self.wake_info=info[3]
		self.new_wakeups=[]
	

	def search_calander(self,start:dict,end:dict):
		start=unix_from_ans(start,self.tz)
		end=unix_from_ans(end,self.tz)
		events=self.cal.range_search(start,end) 
		wakes=self.wakeup.range_search(start,end) 
		return events,wakes

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
	
	def modify_wakeup(self,idx,name=None,time=None,message=None):
		'''
        changes wakeup number idx in folder 
        if idx is zero make a new one

        if the no change is passed this will delete the entry

        impotance should be an int 
        and folder should be in ['user profile', 'goals', 'memories', 'reflections']
        '''
		if time==None and name==None and message==None:
			self.wake_info[idx]=[self.wake_info[idx]['idx'],self.wake_info[idx]['time']]
			return

		if idx==None:
			self.new_wakeups.append({'name':name,'message':message,'time':unix_from_ans(time)})
			return
		
		d=self.self.wake_info[idx]
		if name!=None:
			d['name']=name
		if message!=None:
			d['message']=text
		if time!=None:
			d['time']=unix_from_ans(time)

	def modify_event(self,idx,d):
		'''
		expects either a dict with ['start','end','name'] or None
		if None is passed will delete the entry
		'''
		if d!=None:
			d['start']=unix_from_ans(d['start'])
			d['end']=unix_from_ans(d['end'])
			
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
			#print(d)
			self.cal.add(d)

		#this need to be gathered and ran later
		add_tasks=[self.wakeup.add(d) for d in self.new_wakeups]
		#asyncio.run()
		un_async(asyncio.gather(*add_tasks))

		#modify
		for k,v in self.note_info.items():
			folder=self.folders[k]
			for d in v:
				if isinstance(d,int):
					folder._modify(d)
				else:
					#print(d)
					d['viewed']+=1
					d.pop('embed')
					folder._modify(d['idx'],d)

		for d in self.event_info:
			if isinstance(d,list):
				#print('del')
				self.cal.modify(d[0],d[1])
			else:
				d.pop('embed')
				self.cal.modify(d['idx'],d['start'],d)

		for d in self.wake_info:
			if isinstance(d,list):
				#print('del')
				self.wakeup.modify(d[0],d[1])
			else:
				d.pop('embed')
				self.wakeup.modify(d['idx'],d['time'],d)

if __name__=='__main__':
	from shutil import rmtree
	
	
	if exists('bot_sketch'):
	    rmtree('bot_sketch')
	
	Bot.init_debug_embed('lol_hash')
	#Bot.init_embed("text-embedding-ada-002")
	bot=Bot('bot_sketch',new=True)
	bot.wakeup.hook=lambda n,m: asyncio.sleep(0)
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

	print(f'\n{datetime.fromtimestamp(1).astimezone(bot.tz)}')
	
	bot.cal.add({'start':t+5,'end':t+7,'name':'later'})
	bot.cal.add({'start':t,'end':t+1,'name':'now'})
	un_async(bot.wakeup.add({'time':t+4,'name':'god dam it','message':'we really need to do that thing in that place'}))
	un_async(bot.wakeup.add({'time':t+60*6,'name':'mam','message':'naaaa'}))
	response=un_async(bot.respond_to_message('hey'))

	print(response[1])
	ans = response[0].search_calander({'year': 1970, 'month': 1, 'day': 1, 'hour': 2, 'minute': 0},
	                                           {'year': 1970, 'month': 1, 'day': 1, 'hour': 2, 'minute': 1})

	#print(max([int(x['name']) for x in ans]))

	response[0].modify_note('memories', 1)
	response[0].modify_note('user profile', None, 'hey', 2)

	response[0].modify_event(0, None)
	response[0].modify_event(None, {'start': {'year': 2021, 'month': 1, 'day': 1, 'hour': 2, 'minute': 0},
	                                'end': {'year': 2021, 'month': 1, 'day': 2, 'hour': 2, 'minute': 0},
	                                'name': 'mood'})
	response[0].modify_event(None, {'start': {'year': 2023, 'month': 7, 'day': 29, 'hour': 5, 'minute': 31},
	                                'end': {'year': 2023, 'month': 7, 'day': 29, 'hour': 21, 'minute': 47},
	                                'name': 'waking',
	                                'wake': 'do stuff'})
	response[0].modify_event(None, {'start': {'year': 2023, 'month': 7, 'day': 20, 'hour': 21, 'minute': 31},
	                                'end': {'year': 2023, 'month': 7, 'day': 20, 'hour': 22, 'minute': 31},
	                                'name': 'next'})

	response[0].modify_wakeup(None, time={'year': 2023, 'month': 1, 'day': 2, 'hour': 2, 'minute': 0},
	                          message='stuff', name='wakeup')

	response[0].resolve_changes()

	print(bot.prof[0])
	print(bot.cal.get_next())
	print(bot.cal.get_next(days=100))

		