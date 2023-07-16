import json

import os
from os.path import join,exists
from datetime import datetime

from telegram import ForceReply, Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

import asyncio 

import openai 
import json

import os
from os.path import join,exists
from datetime import datetime

from telegram import ForceReply, Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

import asyncio


async def send_message(bot,user_id,message):
    #sends and logs a message
    path=join('users',str(user_id))
    with open(join(path,'init.json'),'r') as f:
        user_info = json.load(f)
    chat_id=user_info['chat_id']
    
    t=datetime.now().strftime('%Y-%m-%d %H:%M:%S')+'.json'

    await bot.send_message(chat_id, message)
    with open(join(path,'send_messages',t), 'w') as f:
            json.dump({'chat_id': chat_id, 'message': message}, f)
    


async def log_update(user_id,update):
    path=join('users',str(user_id))
    with open(join(path,'init.json'),'r') as f:
        user_info = json.load(f)
    chat_id=user_info['chat_id']
    
    t=datetime.now().strftime('%Y-%m-%d %H:%M:%S')+'.json'

    with open(join(path,'recived_messages',t), 'w') as f:
            json.dump({'chat_id': chat_id, 'message': update.message.text}, f) 

class WaitingFunctionCall:
    #this is here so that scedualed responses work even after a server restart
    def __init__(self,func, bot,user_id, message, delay):
        self.func=func
        self.bot = bot
        self.user_id=user_id
        self.message = message
        self.delay = delay

        self.path=join('users',str(self.user_id),'scedualed_respond.json')
        with open(self.path, 'w') as f:
            json.dump({'message': self.message,'delay': delay,'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')}, f)
        self.task = asyncio.create_task(self.run())

    async def run(self):
        await asyncio.sleep(self.delay)
        await self.func(self.bot,self.user_id, self.message)
        os.remove(self.path)
        #with open(self.path, 'w') as f:
         #   json.dump({'chat_id': self.chat_id, 'message': self.message, 'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')}, f)
        

    def cancel(self):
        if not self.task.done():
            self.task.cancel()
            os.remove(self.path)

class Responder():
    '''
    this class handles the severs reaction to a single message. 
    it should handle all the ids and basic loging for us 
    
    note that we still need to use async and manage our own usage cap 
    sending messages is also not in the scope of this class
    '''
	def __init__(self,response,reminder,errored_reminder,start):
		self.wrapped_response=response #this will allways excute to complesion before new messages are considered 
		self.wrapped_reminder=reminder #this will wait and get intrupted whenever a new message is send
		self.wrapped_errored_reminder=errored_reminder #this will excute if a reminder was server errored
		self.wrapped_start=start #this is excuted when a new user shows up
	
	async def respond(self,update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
	    """main response function"""
	    user = update.effective_user
	    path=join('users',str(user.id))

	    try:
	        user_threads[user.id].cancel()
	    except KeyError:
	        pass

	    asyncio.create_task(log_update(user.id,update))
	    #response_text='got message'#await gpt_logic(update)
	    delay,notes=await self.wrapped_response(context.bot,user.id,update.message.text)

	    w=WaitingFunctionCall(self.wrapped_reminder,context.bot,user.id,notes,delay)
	    user_threads[user.id]=w

    #await w.task


	async def start(self,update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
	    """Send a message when the command /start is issued."""
	    user = update.effective_user
	    path=join('users',str(user.id))
	    os.makedirs(path,exist_ok=True)
	    
	    if(not exists(join(path,'init.json'))):
	        print('new user joined!')
	        with open(join(path,'init.json'),'w') as f:
	            json.dump({'name':user.name,'time':datetime.now().strftime('%Y-%m-%d %H:%M:%S')}, f)
	        
	        os.makedirs(join(path,'send_messages'))
	        os.makedirs(join(path,'recived_messages'))

	      
	    # Update chat_id
	    with open(join(path,'init.json'),'r') as f:
	        user_info = json.load(f)
	    user_info['chat_id'] = update.message.chat_id
	    with open(join(path,'init.json'),'w') as f:
	        json.dump(user_info, f)
	    
	    #await update.message.reply_html(rf"Hi {user.mention_html()}!", reply_markup=ForceReply(selective=True))
	    await self.wrapped_start(context.bot,user.id,user)#send_message(context.bot,user.id,rf"Hi {user.name}!")


	async def initialize_tasks(self,application):
        #this is for after a restart so that all the waiting code runs
	    print('looking for callbacks')
	    bot=application.bot
	    user_directories = [d for d in os.listdir('users') if os.path.isdir(join('users', d))]
	    for user_dir in user_directories:
	        path = join('users', user_dir)
	        if exists(join(path, 'scedualed_respond.json')):
	            with open(join(path, 'scedualed_respond.json'), 'r') as f:
	                respond_info = json.load(f)
	            time_sent = datetime.strptime(respond_info['time'], '%Y-%m-%d %H:%M:%S')
	            time_now = datetime.now()
	            if time_sent > time_now:
	                delay = (time_sent - time_now).total_seconds()
	                w = WaitingFunctionCall(self.wrapped_reminder,bot, user_dir, respond_info['message'], delay)
	                user_threads[int(user_dir)] = w
	            else:
	                asyncio.create_task(self.wrapped_errored_reminder(bot, user_dir, respond_info['message']))
	        
	    print('resolved callbacks. runing as usual')


def tel_main(tel,response,reminder,errored_reminder,start) -> None:
    """Start the bot."""
    responder=Responder(response,reminder,errored_reminder,start)

    application = Application.builder().token(tel).post_init(responder.initialize_tasks).build()
    
    application.add_handler(CommandHandler("start", responder.start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, responder.respond))
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
	print('started server')
	with open('secrets') as f:
	    tel,ai=tuple(f.read().split('\n'))[:2]

	openai.api_key=ai
	user_threads = {}  # this stores the callback threads 

	async def response(bot,user_id,message):
		await send_message(bot,user_id,f'got message: {message}')
		return 10,'wait event trihggered'

	async def reminder(bot,user_id,notes:str):
		await send_message(bot,user_id,message)


	async def errored_reminder(bot,user_id,notes:str):
		await send_message(bot,user_id,'server error delayed response:\n'+message) 

	async def start(bot,user_id,user):
		await send_message(bot,user_id,f'hi {user.name}')

	tel_main(tel,start=start,response=response,errored_reminder=errored_reminder,reminder=reminder)