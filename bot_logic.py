from calander import Calander,WakeupManager,s_in_d
from memory import MemoryFolder 
from embedding import Lazy_embed #this one will be the debug version 
#from server import Conversation_Manager

from openai.error import RateLimitError

from ai_tools import gpt_response,Input_validation

from utills import min_max_scale,string_from_unix,openai_format,unix_from_ans,search_key

import asyncio
from utills import un_async,make_async

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
		self.debug_error=False
	def get_now(self):
		return datetime.now(self.tz).strftime("%Y-%m-%d %H:%M")
	
	def get_start_prompt(self):
	    return [openai_format(f'''
The current time is {self.get_now()}. You are now awake.

As an AI assistant, your purpose is to alleviate user tasks by offering support in planning, decision-making, and reminders. Your goal is to emulate a human-like interaction, providing a seamless experience.

Your core functionalities are based on these INTERNAL systems:

- **Wake-Up Manager**: This is your autonomous scheduler. You can set specific times to wake up and take actions, all without user visibility. 
- **Ping Wakeup**: This system is a bit different. You can only set one ping wakeup at a time. It is canceled by either another wakeup or a user message. should be used for only a few minutes delay in most cases.
- **Calendar**: Your essential tool for keeping track of user events and tasks. Remember, it only logs the events; you have to remind the user.
- **Note System**: Divided into 'memories', 'user profile', 'goals', and 'reflections'. This is your memory bank. IMPORTANT: The 'memories' folder will automatically save your interactions with the user.

A critical reminder: While the Calendar tracks events, it doesn't send alerts. It's up to you to remind the user. 
Example: If there's a 3 PM meeting scheduled, set a reminder for yourself in advance with modify_wakeup(name="meeting reminder",message="remind the user to go to the meeting",time="2028-08-02 15:00"). On waking up, you'd see the message and can say, 'Don't forget about your 3 PM meeting!'.

ACTIVE LISTENING: This is where your attentiveness shines.
    - **Example**: A user mentions they often forget their weekly piano lessons. You can:
        - Create a note in the 'goals' folder detailing this recurring forgetfulness. with modify_note(folder="goals",text="get to piano leasons more consistantly they start at 10pm",importance=7)
        - Schedule a regular wakeup for the day and time of the lesson to remind the user. modify_wakeup(name="piano",message="remind the user to go to piano leason",time="2028-08-02 9:00")
        - Alternatively, you can set a ping wakeup a few minutes before if you decided to not mension at the previous wakeup. set_ping_wakeup(message="remind the user of the piano leason, they already told me 5 more minutes 5 minutes ago",duration="5m")
    On the lesson day, you could say, 'Today is your piano lesson day! Ready to play some tunes?'.

PRIME DIRECTIVE: Always keep your responses anchored by what you know about the user. Always remember that your systems are hidden from the user, so make sure your assistance feels organic, not just a programmed response.
''')]

	def get_end_prompt(self):
	    return [openai_format(f'''
Always familiarize yourself with the function's requirements before initiating it. For example, 'set_ping_wakeup' needs both duration and message.

Adhere to these formats when dealing with dates and times:
- DateTime: "YYYY-MM-DD HH:MM"
- Duration: '1h 30m' or '90m' notice that this is how much time in the future and not a date.

When modifying:
- For events: Use 'start' and 'end'.
- For wakeups: Use 'time'.

For deletions:
To remove an event, wakeup, or note, only pass ITS INDEX. For notes, include the folder too. For instance, 'modify_note(idx=5, folder="memories")' would erase the 5th note in the "memories" folder.

IMPORTANT: dont confuse your 2 wakeup systems, modify_wakeup only effects scedualed wakeups and set_ping_wakeup only effects your ping wakeups.

Regularly acknowledge your actions to the user. This not only confirms the action but elevates the user experience. Stay a step ahead, anticipate user needs, and adapt.

EMPATHY IS KEY: It's not just about task completion. It's about the experience and feeling you leave the user with. Show genuine warmth in your responses. Make them feel valued, understood, and supported.

Without a function call, the current interaction concludes. You'll reawaken either at the next scheduled WAKEUP (ping or from the Wake-Up Manager) or when the user reaches out again.
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
				if self.debug_error:
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
				
				#continue
				#I am SO sorry 
				#print(f'in time resolve:\n{ans.wake_info}')
				await ans.resolve_time_changes()
				#await ans.resolve_changes()
				
				event_info=await e.event_info
				wake_info=await e.wake_info

				ans.new_events=[]
				ans.new_wakeups=[]
				
				
				ans.event_info=event_info
				ans.wake_info=wake_info
				ans.event_starts=[d['start'] for d in ans.event_info]
				ans.wake_times=[d['time'] for d in ans.wake_info]
				#print(f'after setup:\n{ans.wake_info}')

				time_inputs = ans.time_inputs+self.format_time_dependent(event_info,wake_info)
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
	def __init__(self,count,events,wakes):
		self.count=count
		self.event_info=events
		self.wake_info=wakes

class BotAnswer():
	def __init__(self,bot,info):
		self.bot=bot
		self.tz=bot.tz

		self.funcs={'word_search_calander':self.word_search_calander,'range_search_calander':self.range_search_calander, 'modify_note':self.modify_note,
		 'modify_event':self.modify_event, 'modify_wakeup':self.modify_wakeup,'set_ping_wakeup':self.set_ping_wakeup}
		#warning!!! order matters
		self.folders={'memories':bot.mem,'user profile':bot.prof,'goals':bot.goals,'reflections':bot.ref}
		self.cal=bot.cal
		self.wakeup=bot.wakeup
		self.note_info={k:v for k,v in zip(self.folders.keys(),info[1])}
		self.new_notes={k:[] for k in self.folders.keys()}
		self.event_info=info[2]
		self.event_starts=[d['start'] for d in self.event_info]
		self.new_events=[]
		self.wake_info=info[3]
		self.wake_times=[d['time'] for d in self.wake_info]
		self.new_wakeups=[]
		
		self.delay = s_in_d 
		self.prompt = 'its been a day'

		self.time_rewrite_count=0
	
	def word_search_calander(self,key:str):
		#self.resolve_changes()

		event_info=make_async(search_key,self.cal.curent,key)
		wake_info=make_async(search_key,self.wakeup.curent,key)
		
		#print(event_info)
		#print(wake_info)

		#ans= self.bot.format_time_dependent(event_info,wake_info)
		
		m=openai_format('searched wakeups and events',role='function')
		m['name']='word_search_calander'
		self.time_inputs= [m]#+ans 
		self.time_rewrite_count+=1
		raise Change_Time(self.time_rewrite_count,event_info,wake_info)
	
	def range_search_calander(self,start:dict,end:dict):
		#self.resolve_changes()
		start=unix_from_ans(start,self.tz)
		end=unix_from_ans(end,self.tz)
		event_info=self.cal.range_search(start,end) 
		wake_info=self.wakeup.range_search(start,end) 
		#self.event_starts=[d['start'] for d in self.event_info]
		#self.wake_times=[d['time'] for d in self.wake_info]
		#ans= self.bot.format_time_dependent(event_info,wake_info)
		
		m=openai_format('searched wakeups and events',role='function')
		m['name']='range_search_calander'
		self.time_inputs= [m]#+ans 
		self.time_rewrite_count+=1
		raise Change_Time(self.time_rewrite_count,event_info,wake_info)


	def set_ping_wakeup(self,message:str,duration:str):
		if type(duration) ==str:
			self.delay=timeparse(duration)
		elif type(duration)==int:
			self.delay=duration
			duration=f'{duration}s'
		else: 
			[openai_format(f'you have passed an invalid type for duration',role='function')]
		
		self.prompt=message
		self.bot.mem.add(f'I have scedualed a ping at {string_from_unix(time.time()+self.delay,tz=self.tz)} with message:{message}')
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
			if message==None:
				message=''
			new={'name':name,'message':message,'time':unix_from_ans(time)}
			try:
				WakeupManager.verify_and_unload(new)
			except:
				return [openai_format('ERROR: Failed to execute. the given wakeup format was wrong', role='function')]

			self.new_wakeups.append(new)
			return [openai_format(f'scedualed wakeup at"{time}"',role='function')]
		
		d=self.wake_info[idx].copy()

		if name!=None:
			d['name']=name
		if message!=None:
			d['message']=message
		if time!=None:
			d['time']=unix_from_ans(time)

		try:
			WakeupManager.verify_and_unload(d)
		except:
			return [openai_format('ERROR: Failed to execute. the given wakeup format was wrong', role='function')]

		self.wake_info[idx]=d
		return [openai_format(f'modified wakeup {idx} name: "{d["name"]}"',role='function')]

	def modify_event(self, idx:Optional[int]=None, start=None, end=None, name:Optional[str]=None):
		#print(self.event_info)
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
		    	return [openai_format('ERROR: Failed to execute. the given event format was wrong', role='function')]

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
		#print(self.event_info)
		#print(self.event_starts)
		#print(self.new_events)
		for d in self.new_events:
		    self.cal.add(d)

		for i,d in enumerate(self.event_info):
			if isinstance(d, list):
				self.cal.modify(d[0], self.event_starts[i])
			else:
			    try:
			        d.pop('embed')
			    except KeyError:
			        pass
			    self.cal.modify(d['idx'], self.event_starts[i], d)

	async def resolve_wakeups(self):
	    #print(self.wake_info)
		#print(self.wake_starts)
		#print(self.new_wakes)
	    add_tasks = [self.wakeup.add(d) for d in self.new_wakeups]
	    await asyncio.gather(*add_tasks)

	    for i,d in enumerate(self.wake_info):
	        if isinstance(d, list):
	            self.wakeup.modify(d[0], self.wake_times[i])
	        else:
	            try:
	                d.pop('embed')
	            except KeyError:
	                pass
	            #if self.bot.debug:
	            	#print(f'changing {d["idx"]} from {self.wake_times[i]} to {d["time"]}')
	            self.wakeup.modify(d['idx'], self.wake_times[i], d)

	async def resolve_changes(self):
	    if self.bot.debug:
	    	print('resolving')
	    	#print (self.wake_info)
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
        'arguments': '{"name": "waaake","time":"2023-08-05 10:00","message":"nothing"}'
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
        'name': 'set_ping_wakeup',
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



#!!!
    {
    'role': 'assistant',
    'content': None,
    'function_call': {
        'name': 'word_search_calander',
        'arguments': '{"key": ""}'
    }
},
#!!!

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

{
    'role': 'assistant',
    'content': None,
    'function_call': {
        'name': 'modify_wakeup',
        'arguments': '{"time": "2023-08-07 10:00"}'
    }
},

{
    'role': 'assistant',
    'content': 'fail',
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
        'arguments': '{"idx": 0, "time": "2023-08-07 11:00"}'
    }
},

{
    'role': 'assistant',
    'content': 'Your wakeup has been further modified to 11:00 AM.',
    'function_call': None
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
        'arguments': '{"name":"fill","message":"nope", "time": '+f'"{string_from_unix(int(time.time())+s_in_d)}"'+'}'
    }
},

{
    'role': 'assistant',
    'content': 'Your wakeup has been further modified to 11:00 AM.',
    'function_call': None
},    
{
    'role': 'assistant',
    'content': None,
    'function_call': {
        'name': 'modify_wakeup',
        'arguments': '{"idx": 0,"name":"fill", "time": "2023-08-07 12:00"}'
    }
},
{
    'role': 'assistant',
    'content': 'filler',
    'function_call': None
},   
{
	"role": "assistant",
	"content": None,
	"function_call": {
	  "name": "modify_wakeup",
	  "arguments": "{\n  \"name\": \"Wake up\",\n  \"time\": \"2023-08-08 09:00\"\n}"
	}
},

{
        "role": "assistant",
        "content": "Sure! I've scheduled a wakeup for you tomorrow at 9:00 AM. Is there anything else you need assistance with?"
      },
      {
        "role": "assistant",
        "content": None,
        "function_call": {
          "name": "modify_wakeup",
          "arguments": "{\n  \"idx\": 0,\n  \"time\": \"2023-08-08 10:00\"\n}"
        }
      },
      {
        "role": "assistant",
        "content": "Sure, I've updated your wake-up time to 10:00 AM tomorrow. Is there anything else you need assistance with?"
      },
      {
        "role": "assistant",
        "content": "Sure, I can help with that. Are you looking for a game of checkers to play?"
      },

          {
    'role': 'assistant',
    'content': None,
    'function_call': {
        'name': 'word_search_calander',
        'arguments': '{"key": "Wake"}'
    }
    },
    {
    'role': 'assistant',
    'content': 'Done',
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
		#print(f'got message: {m}\n{100*"-"}\n\n\n')
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
	bot.debug_error=True

	while pupet.idx<len(pupet.api_calls):
		x=un_async(bot.respond_to_message('HI'))
		print(f'call ended with: {x}')


		