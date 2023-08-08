import openai
import os
from os.path import join,exists
import json
import asyncio
from datetime import datetime

from telegram import  Update
from telegram.ext import ContextTypes

from server import tel_main,Conversation_Manager,FolowUpCalls,Responder,send_message,log_update
from bot_logic import Bot 
from ai_tools import gpt_response,RateLimitedAPICall,LogAPICall,extract_message
from calander import WakeupManager,s_in_d
#remember to overwrite the wakeup WakeupHook 

#DEBUG=False
class WakeupHook():
	def __init__(self,user_id,tel_bot):
		self.user_id=user_id
		self.tel_bot=tel_bot

	async def __call__(self,name,message):
		bot=ai_bot_from_id(self.user_id,self.tel_bot)
		notes,delay=await bot.do_wakeup(name,message)
		FolowUpCalls(self.tel_bot,self.user_id,notes,delay)



def ai_bot_from_id(user_id,tel_bot):
	manager=Ai_Conversation_Manager.from_id(user_id,tel_bot)
	path=join('users',str(user_id),'bot_data') 
	bot=Bot(path)
	bot.debug=True
	bot.send_message=manager.send_message
	bot.wakeup.WakeupHook=WakeupHook(user_id,tel_bot)
	return bot

class Ai_Conversation_Manager(Conversation_Manager): 
	async def hook(self,message,path):
		user_id=int(os.path.split(path)[-1])
		bot=ai_bot_from_id(user_id,self.bot)
		notes,delay=await bot.respond_to_message(message)
		FolowUpCalls(self.bot,user_id,notes,delay)

class AIResponder(Responder):#we just want the start method from Responder 
	
	def __init__(self,start,ping):
		self.wrapped_start=start #this is excuted when a new user shows up 
		self.wrapped_reminder=ping #this will wait and get intrupted whenever a new message is send

	async def initialize_tasks(self,application):
		#this is for after a restart so that all the waiting code runs
		print('looking for callbacks')
		bot=application.bot
		user_directories = [d for d in os.listdir('users') if os.path.isdir(join('users', d))]
		for user_dir in user_directories:
		    path = join('users', user_dir)
		    user_id=int(user_dir)


		    bot=ai_bot_from_id(user_id,application.bot)
		    bot.wakeup.recover_from_crash()


		    if exists(join(path, 'scedualed_respond.json')):
		        with open(join(path, 'scedualed_respond.json'), 'r') as f:
		            respond_info = json.load(f)
		        time_sent = datetime.strptime(respond_info['time'], '%Y-%m-%d %H:%M:%S')
		        time_now = datetime.now()
		        delay = (time_sent - time_now).total_seconds()+respond_info['delay']
		            
		        if delay > 0:
		            w = FolowUpCalls( bot,user_id, respond_info['message'], delay)
		        else:
		            #delay,message=await self.wrapped_errored_reminder(bot,user_id,respond_info['message'])
		            message, delay=await ai_bot_from_id(user_id,bot).ping_wakeup(respond_info['message'],error=True)
		            w = FolowUpCalls(bot,user_id,message, delay)

		        #self.user_threads[user_id] = w
		    else: 
		        print(f'error missing response in:\n{path}')
		    
		print('resolved callbacks. runing as usual')

	async def respond(self,update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
		"""main response function"""
		user = update.effective_user
		path=join('users',str(user.id))

		try:
		    FolowUpCalls.user_threads[user.id].cancel()
		except KeyError:
		    pass

		asyncio.create_task(log_update(user.id,update))
		#response_text='got message'#await gpt_logic(update)
		conv=Ai_Conversation_Manager.from_id(user.id,context.bot)
		await conv.add(update.message.text)
        
            


if __name__ == "__main__":

	print('started server')
	with open('secrets') as f:
	    tel,ai=tuple(f.read().split('\n'))[:2]

	openai.api_key=ai

	call=RateLimitedAPICall(lambda t:gpt_response(t,full=True),3,10)
	call=RateLimitedAPICall(call,10,5*60)
	call=RateLimitedAPICall(call,100,s_in_d)
	call=LogAPICall(call,'GPT_Calls')
	async def call2(x):
		x=await call(x)
		return extract_message(x)
	#call=lambda x:extract_message(x)
	#return x,x.get('content'),x.get("function_call")
	Bot.init_gpt_func(call2)
	Bot.init_embed('text-embedding-ada-002') 

	async def start(bot,user_id,user):
		ai_bot=Bot(join('users',str(user_id),'bot_data'),new=True)
		await send_message(bot,user_id,f'hi {user.name} \nthis app is still being devloped thanks for you patiance')
		ai_bot.prof.add(f'the user is named {user.name}',10)
		ai_bot.prof.add(f'user is new they joined at {ai_bot.get_now()}',7)


	async def reminder(tel_bot,user_id,notes:str):
		try:
			FolowUpCalls.user_threads[user.id].cancel()
		except KeyError:
			pass 

		bot=ai_bot_from_id(user_id,tel_bot)
		notes,delay=await bot.ping_wakeup(notes)
		FolowUpCalls(tel_bot,user_id,notes,delay)



	responder=AIResponder(start,reminder)
	tel_main(tel,responder)


