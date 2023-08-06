from calander import Calander,WakeupManager,s_in_d
from memory import MemoryFolder 
from embedding import Lazy_embed #this one will be the debug version 
#from server import Conversation_Manager

from openai.error import RateLimitError

from ai_tools import gpt_response,Input_validation

from utills import min_max_scale,string_from_unix,openai_format,unix_from_ans,search_key

import asyncio
from utills import un_async

import os 
from os.path import join,exists

from datetime import datetime
import time
import pytz 

import numpy as np
import json

from pytimeparse.timeparse import timeparse

from typing import Optional


'''
TO DO:

1.fix how bot_answer internaly calls search
2.manage the input length with nice try catch logic
3.prompt engnier your way into getting good time managment and people skills 
'''

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

		self.debug=False
	def get_now(self):
		return datetime.now(self.tz).strftime("%Y-%m-%d %H:%M")
	
	def get_start_prompt(self):
	    return [openai_format(f'''
the current time is {self.get_now()}.
You're an assistant designed to provide valuable help to users who may struggle with planning, decision-making, and remembering tasks. Your goal is to alleviate these burdens while maintaining a human-like interaction.

Your functionality relies on three key internal systems:
- A Wake-Up Manager: Schedules specific times for you to execute actions autonomously. 
- A Calendar: Helps you manage tasks and events on the user's behalf.
- A Note System: Four categorized folders - 'memories', 'user profile', 'goals', and 'reflections', aiding in personalization and providing long-term memory. the memories folder automatically saves the messaging history between us and the user.

Remember, the calendar won't alert the user of upcoming events; you need to schedule a wake-up for reminders. The Note System, especially 'user profile', 'goals', and 'reflections', is critical for tailoring your assistance to the user's needs and preferences. Using these notes, you can customize your responses over time.

Keep your interactions user-centric, grounded in known information, and refrain from speculation. Prioritize clear, concise responses and avoid unnecessary complexity. This efficiency will result in effective assistance. 
''')]



	def get_end_prompt(self):
	    return [openai_format(f'''
When managing datetimes and durations in function calls, adhere to these formats:
- DateTime: "YYYY-MM-DD HH:MM"
- Duration: '1h 30m' or '90m'.

For modifications:
- Event times: Use "start" and "end".
- Wakeup times: Use "time".

To delete an event, wakeup, or note, pass JUST ITS INDEX (and folder for notes). E.g., modify_note(idx=5, folder="memories") deletes the note with index 5 in the "memories" folder.

Finally, consider affirming your actions to the user with a text response. This not only confirms successful communication but also enhances user experience. Always anticipate user needs and adapt to their context.

With these guidelines, your interactions will be effective, efficient, and user-friendly.

''')]




	async def send_message(self,message):
		print('sending message')
		print(message)

	async def _send_message(self,message):
		t=datetime.now(self.tz).strftime('%Y-%m-%d %H:%M')
		self.mem.add(f'at: {t} I said: "{message}"')
		await self.send_message(message)
		
	
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

	def format_wakeup(self,d,i):
		time=string_from_unix(d['time'],tz=self.tz)
		return f"{i}. {d['name']}; time:{time}\n{d['message']}"
	
	def format_event(self,d,i):
		start=string_from_unix(d['start'],tz=self.tz)
		end=string_from_unix(d['end'], tz=self.tz)
		return f"{i}. {d['name']}; starts:{start}; ends:{end}"
	
	def format_time_dependent(self,events,wakes):
		ans=[openai_format('events: index. name; start; end;')]#'recent events:\n'
		
		for i,e in enumerate(events):
			ans.append(openai_format(self.format_event(e,i)))
			#start=string_from_unix(e['start'],tz=self.tz)
			#end=string_from_unix(e['end'], tz=self.tz)
			#ans.append(openai_format(f"{i}. {e['name']}; starts:{start}; ends:{end}"))
		#ans+='\n'
		ans.append(openai_format('wakeups: index. name; time\nmessage;'))
		for i,w in enumerate(wakes):
			ans.append(openai_format(self.format_wakeup(w,i)))
			#time=string_from_unix(w['time'],tz=self.tz)
			#ans.append(openai_format(f"{i}. {w['name']}; time:{time}\n{w['message']}"))

		return ans

	def format_note(self,d,i):
		return f"{i}. {d['text']} [{d['importance']}]"

	def format_folder(self,folder,name):
		if not folder:
			return []
		ans=[openai_format(f"{name}:\n")]
		for i,d in enumerate(folder):
				ans.append(openai_format(self.format_note(d,i),role='system'))
		return ans

	def format_folders(self, folders):
		#tz=self.get_timezone()
		#ans=self.format_time_dependent(wakeups,events)

		ans=[openai_format('Format:\nid. text [importance]:')]
		
		for folder,name in zip(folders,['memories','user profile', 'goals',  'reflections']):
			ans+=self.format_folder(folder,name)
			

		#ans.append(openai_format(f'{message}',role=source)) 

		return ans

	async def logic_step(self,message_input,time_inputs,folder_inputs,ans):
		#can raise RateLimitError
		x,text,function_call=await self.ai_call[0](self.get_start_prompt()+time_inputs+folder_inputs+message_input+self.get_end_prompt())
		message_input.append(x)
		if text:
			await self._send_message(text)

		if function_call:
			try:
				args=json.loads(function_call['arguments'])
				if self.debug:
					print(f"calling: {function_call['name']} with {args}")
				out= ans.funcs[function_call['name']](**args)	
				for d in out:
					if d['role']=='function':
						d['name']=function_call['name']
				message_input+=out
				#print(f"good function call: {function_call['name']}")

			except Exception as e:
				if isinstance(e,Change_Time):
					raise e
				d=openai_format(f'error of type:{str(type(e))} error text: {str(e)}',role='function')
				d['name']=function_call['name']
				message_input.append(d)
				message_input.append(openai_format('IMPORTANT: your last function call errored, please validate that your inputs are in the corect format'))
				#print('bad function call raising error')
				if self.debug:
					raise e

			#await ans.resolve_changes() #for debuging only so when it gets caught in an error loop I can abord and see the state
			return await self.logic_step(message_input,time_inputs,folder_inputs,ans)
			
		await ans.resolve_changes()
		#await ans.resolve_changes()
		#return text
		

		#delay = s_in_d 
		#prompt = 'its been a day'
		return ans.prompt,ans.delay

	async def session(self, message,source):
		await self.lock()
		t = int(time.time())
		#tz=await self.get_timezone()
		info=await self.get_info(message,t-s_in_d,t+s_in_d)
		ans=BotAnswer(self,info)
		message_input=[openai_format(message,role=source)]
		folder_inputs=self.format_folders(info[1])
		time_inputs=self.format_time_dependent(*info[2:4])
		
		while True:
			try:
				ans,delay=await self.logic_step(message_input,time_inputs,folder_inputs,ans)
				break
			
			except RateLimitError:
				raise NotImplementedError
			
			except Change_Time as e:
				
				#I am SO sorry 
				await ans.resolve_time_changes()
				ans.new_events=[]
				ans.new_wakeups=[]

				time_inputs = ans.time_inputs
				mmm=openai_format(f'NOTICE: The previous top message was replaced due to a function call for the {e.count} time(s). Please note that older function calls modifying or deleting events and wakeups no longer refer to the items currently at the top.')
				
				#add note messages
				if e.count==1:
					time_inputs.insert(0, message_input.pop(-1))
					time_inputs.insert(0, mmm)
					
				#modify note messages
				else:
					time_inputs[1]= message_input.pop(-1)
					time_inputs[0]=mmm
					
				
				message_input.append(openai_format(f'NOTICE: A search function was invoked for the {e.count} time(s). The result now appears at the top of the messages.'))
	 
		if source=='user':
			self.mem.add(f'at {self.get_now()} user said:{message}')
		self.free()

		return ans,delay


	async def respond_to_message(self, message):
		return await self.session(message,source='user')


	async def do_wakeup(self,name, message):
		text=f'wakeup "{name}":\n{message}'
		return await self.session(text,source='assistant')

	async def ping_wakeup(self, message,error=False):
		text=f'auto wakeup :\n{message}'
		if error: 
			text=f'Server error delayed auto wakeup :\n{message}'
		return await self.session(text,source='assistant')

class Change_Time(Exception):
	def __init__(self,count):
		self.count=count

class BotAnswer():
	def __init__(self,bot,info):
		self.bot=bot
		self.tz=bot.tz

		self.funcs={'word_search_calander':self.word_search_calander,'range_search_calander':self.range_search_calander, 'modify_note':self.modify_note,
		 'modify_event':self.modify_event, 'modify_wakeup':self.modify_wakeup,'set_ping':self.set_ping}
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
		
		self.delay = s_in_d 
		self.prompt = 'its been a day'

		self.time_rewrite_count=0
	
	def word_search_calander(self,key:str):
		#self.resolve_changes()

		self.event_info=search_key(self.cal.curent,key)
		self.wake_info=search_key(self.wakeup.curent,key)
		ans= self.bot.format_time_dependent(self.event_info,self.wake_info)
		
		m=openai_format('searched wakeups and events',role='function')
		m['name']='word_search_calander'
		self.time_inputs= [m]+ans 
		self.time_rewrite_count+=1
		raise Change_Time(self.time_rewrite_count)
	
	def range_search_calander(self,start:dict,end:dict):
		self.resolve_changes()
		start=unix_from_ans(start,self.tz)
		end=unix_from_ans(end,self.tz)
		self.event_info=self.cal.range_search(start,end) 
		self.wake_info=self.wakeup.range_search(start,end) 
		ans= self.bot.format_time_dependent(self.event_info,self.wake_info)
		
		m=openai_format('searched wakeups and events',role='function')
		m['name']='range_search_calander'
		self.time_inputs= [m]+ans 
		self.time_rewrite_count+=1
		raise Change_Time(self.time_rewrite_count)


	def set_ping(self,message:str,duration:str):
		if type(duration) ==str:
			self.delay=timeparse(duration)
		elif type(duration)==int:
			self.delay=duration
			duration=f'{duration}s'
		else: 
			[openai_format(f'you have passed an invalid type for duration',role='function')]
		
		self.prompt=message
		return [openai_format(f'you will be woken up in {duration}',role='function')]
	
	def modify_note(self,folder,idx:Optional[int]=None,text:Optional[str]=None,importance:Optional[int]=None):
		'''
        changes note number idx in folder 
        if idx is zero make a new one

        if the no change is passed this will delete the entry

        impotance should be an int 
        and folder should be in ['user profile', 'goals', 'memories', 'reflections']
        '''
		if text==None and importance==None:
			self.note_info[folder][idx]=self.note_info[folder][idx]['idx']
			return [openai_format(f'removed note {idx} from folder "{folder}"',role='function')]

		if idx==None:
			self.new_notes[folder].append({'text':text,'importance':importance})
			return [openai_format(f'added a new note to folder "{folder}"',role='function')]
		
		d=self.note_info[folder][idx]
		#s=''
		if text!=None:
			d['text']=text
			#s+=f"text: {text}"
		if importance!=None:
			d['importance']=importance
			#s+=f"importance: {importance}"

		return [openai_format(f'modified note {idx} in folder "{folder}"',role='function')]
	
	def modify_wakeup(self,idx:Optional[int]=None,name:Optional[str]=None,time=None,message:Optional[str]=None):
		'''
        changes wakeup number idx in folder 
        if idx is zero make a new one

        if the no change is passed this will delete the entry
        '''
		if time==None and name==None and message==None:
			self.wake_info[idx]=[self.wake_info[idx]['idx'],self.wake_info[idx]['time']]
			return [openai_format(f'canceled wakeup {idx}',role='function')]

		if idx==None:
			new={'name':name,'message':message,'time':unix_from_ans(time)}
			try:
				WakeupManager.verify_and_unload(new)
			except:
				[openai_format('ERROR: Failed to execute. the given wakeup format was wrong', role='function')]

			self.new_wakeups.append(new)
			return [openai_format(f'scedualed wakeup at"{time}"',role='function')]
		
		d=self.wake_info[idx]

		if name!=None:
			d['name']=name
		if message!=None:
			d['message']=message
		if time!=None:
			d['time']=unix_from_ans(time)

		try:
			WakeupManager.verify_and_unload(d)
		except:
			[openai_format('ERROR: Failed to execute. the given wakeup format was wrong', role='function')]

		return [openai_format(f'modified wakeup {idx} name: "{d["name"]}"',role='function')]

	def modify_event(self, idx:Optional[int]=None, start=None, end=None, name:Optional[str]=None):
		print(self.event_info)
		'''
		Expects start, end, and name as separate arguments.
		If all are None, it will delete the entry.
		If there is a mix of defined and undefined among start, end, and name, it will return an error.
		'''
		# Check for a mix of defined and undefined among start, end, and name
		params = [start, end, name]
		if params.count(None) not in [0, 3]:  # either all or none should be None
		    return [openai_format('IMPORTANT: Failed to execute. Either all of start, end, and name should be defined, or all should be None.', role='function')]

		if start is not None and end is not None and name is not None:
		    start = unix_from_ans(start, self.tz)
		    end = unix_from_ans(end, self.tz)
		    event_data = {'start': start, 'end': end, 'name': name}
		    try:
		    	Calander.verify_and_unload(event_data)
		    except:
		    	[openai_format('ERROR: Failed to execute. the given event format was wrong', role='function')]

		    if idx is None:
		        self.new_events.append(event_data)
		        return [openai_format('Added new event.', role='function')]

		    event_data['idx']=self.event_info[idx]['idx']
		    self.event_info[idx] = event_data
		    return [openai_format(f'Modified event {idx}.', role='function')]

		else:
		    if idx is not None:
		        d = self.event_info[idx]
		        self.event_info[idx] = [d['idx'], d['start']]
		        return [openai_format(f'Removed event {idx}.', role='function')]



	def resolve_folders(self):
	    for k, v in self.new_notes.items():
	        folder = self.folders[k]
	        for d in v:
	            folder.add(text=d['text'], importance=d['importance'])

	    for k, v in self.note_info.items():
	        folder = self.folders[k]
	        for d in v:
	            if isinstance(d, int):
	                folder._modify(d)
	            else:
	                d['viewed'] += 1
	                try:
	                    d.pop('embed')
	                except KeyError:
	                    pass
	                folder._modify(d['idx'], d)

	def resolve_events(self):
	    for d in self.new_events:
	        self.cal.add(d)

	    for d in self.event_info:
	        if isinstance(d, list):
	            self.cal.modify(d[0], d[1])
	        else:
	            try:
	                d.pop('embed')
	            except KeyError:
	                pass
	            self.cal.modify(d['idx'], d['start'], d)

	async def resolve_wakeups(self):
	    add_tasks = [self.wakeup.add(d) for d in self.new_wakeups]
	    await asyncio.gather(*add_tasks)

	    for d in self.wake_info:
	        if isinstance(d, list):
	            self.wakeup.modify(d[0], d[1])
	        else:
	            try:
	                d.pop('embed')
	            except KeyError:
	                pass
	            self.wakeup.modify(d['idx'], d['time'], d)

	async def resolve_changes(self):
	    if self.bot.debug:
	    	print('resolving')
	    self.resolve_folders()
	    self.resolve_events()
	    await self.resolve_wakeups()

	async def resolve_time_changes(self):
	    #self.resolve_folders()
	    self.resolve_events()
	    await self.resolve_wakeups()

	
		

class AIPupet():
	api_calls = [

    {
        'role': 'assistant',
        'content': 'filler',
        'function_call': None
    },
    {
    'role': 'assistant',
    'content': None,
    'function_call': {
        'name': 'modify_event',
        'arguments': '{"name": "Laundry", "start": {"year": 2023, "month": 8, "day": 1, "hour": 10, "minute": 0}, "end": {"year": 2023, "month": 8, "day": 1, "hour": 11, "minute": 0}}'
    }
},

    {
        'role': 'assistant',
        'content': 'filler',
        'function_call': None
    },
 
        {
    'role': 'assistant',
    'content': None,
    'function_call': {
        'name': 'modify_wakeup',
        'arguments': '{"name": "waaake","time":"2023-08-02 10:00","message":"nothing"}'
    }
},

    {
        'role': 'assistant',
        'content': 'filler',
        'function_call': None
    },

        {
    'role': 'assistant',
    'content': None,
    'function_call': {
        'name': 'set_ping',
        'arguments': '{"message": "changed","duration":"1h"}'
    }
},

    {
        'role': 'assistant',
        'content': 'filler',
        'function_call': None
    },

{
    'role': 'assistant',
    'content': None,
    'function_call': {
        'name': 'word_search_calander',
        'arguments': '{"key": ""}'
    }
}, 
{
    'role': 'assistant',
    'content': None,
    'function_call': {
        'name': 'modify_event',
        'arguments': '{"idx":0}'
    }
},

    {
        'role': 'assistant',
        'content': 'filler',
        'function_call': None
    },
            {
    'role': 'assistant',
    'content': None,
    'function_call': {
        'name': 'word_search_calander',
        'arguments': '{"key": ""}'
    }
}, 
        {
    'role': 'assistant',
    'content': None,
    'function_call': {
        'name': 'modify_wakeup',
        'arguments': '{"name": "waaake","time":"2026-08-02 10:00","message":"nothing"}'
    }
},

        {
    'role': 'assistant',
    'content': None,
    'function_call': {
        'name': 'modify_wakeup',
        'arguments': '{"idx":0,"name": "waaake","time":"2028-08-02 10:00"}'
    }
},


    {
    'role': 'assistant',
    'content': None,
    'function_call': {
        'name': 'word_search_calander',
        'arguments': '{"key": ""}'
    }
},

        {
    'role': 'assistant',
    'content': None,
    'function_call': {
        'name': 'modify_wakeup',
        'arguments': '{"name": "waaake","time":"2024-08-02 10:00","message":"nothing"}'
    }
},



    {
        'role': 'assistant',
        'content': 'filler',
        'function_call': None
    },

       


]

	def __init__(self):
		self.idx=0#len(self.api_calls)-2
		#print(self.idx)
	async def __call__(self,m):
		for m1 in m:
			#print(type(m1))
			if type(m1)!=dict:
				print(m1)
				print(len(m))
		try:
			Input_validation(m)
		except Exception as e:
			for m1 in m:
				print(f"{m1.keys()} {m1['role']}")
			raise e

		x=self.api_calls[self.idx]
		self.idx+=1
		print(f'got message: {m}\n{100*"-"}\n\n\n')
		return x,x.get('content'),x.get("function_call")



if __name__=='__main__':
	from shutil import rmtree
		
	if exists('bot_sketch'):
	    rmtree('bot_sketch')
	
	pupet=AIPupet()
	bot=Bot('bot_sketch',new=True)
	
	bot.wakeup.hook=lambda n,m: asyncio.sleep(0)
	Bot.init_debug_embed('lol_hash') 
	bot.init_gpt_func(pupet)
	bot.debug=True 

	while pupet.idx<len(pupet.api_calls):
		x=un_async(bot.respond_to_message('HI'))
		print(f'call ended with: {x}')


		