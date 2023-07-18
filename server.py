'''
dear future me I am so sorry for the mess you are about to see.
I have worked for so long on this very simple idea rewriting it a bunch of times
there is still a few of totaly useless things here I am too afraid to touch 

regardless this seems to work and while I cant test it at scale I think it should work at scale too

for future refrence this is why we dont pretend to know java... you are a python devloper for fuck sake write prosedural code
'''

import json

import os
from os.path import join,exists,getctime
from datetime import datetime

from telegram import ForceReply, Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

import asyncio 

import openai 
import json

import os
from os.path import join,exists
from datetime import datetime
import time

from telegram import ForceReply, Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

import asyncio

from calander import s_in_d


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

class FolowUpCalls:
    user_threads={}
    
    @classmethod
    def set_func(cls,func):
        cls.func=[func]
    #this is here so that scedualed responses work even after a server restart
    
    def __init__(self, bot,user_id, message, delay):
        if message==None:
            return
        try:
            self.user_threads[user_id].cancel()
        except KeyError:
            pass

        self.bot = bot
        self.user_id=user_id
        self.message = message
        self.delay = delay

        self.path=join('users',str(self.user_id),'scedualed_respond.json')
        with open(self.path, 'w') as f:
            json.dump({'message': self.message,'delay': delay,'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')}, f)
        self.task = asyncio.create_task(self.run())
        self.user_threads[user_id]=self

    async def run(self):
        await asyncio.sleep(self.delay)
        delay,notes=await self.func[0](self.bot,self.user_id, self.message)
        
        if notes==None:
            return

        FolowUpCalls(self.bot,self.user_id,notes,delay)
        #os.remove(self.path)
        #return val
        #with open(self.path, 'w') as f:
         #   json.dump({'chat_id': self.chat_id, 'message': self.message, 'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')}, f)
        

    def cancel(self):
        #if not self.task.done():
        self.task.cancel()
        if exists(self.path):
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

        #self.user_threads = {}

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
        delay,notes=await self.wrapped_response(context.bot,user.id,update.message.text)

        w=FolowUpCalls(context.bot,user.id,notes,delay)
        #self.user_threads[user.id]=w

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
            user_id=int(user_dir)
            if exists(join(path, 'scedualed_respond.json')):
                with open(join(path, 'scedualed_respond.json'), 'r') as f:
                    respond_info = json.load(f)
                time_sent = datetime.strptime(respond_info['time'], '%Y-%m-%d %H:%M:%S')
                time_now = datetime.now()
                delay = (time_sent - time_now).total_seconds()
                    
                if time_sent > time_now:
                    w = FolowUpCalls( bot,user_id, respond_info['message'], delay)
                else:
                    delay,message=await self.wrapped_errored_reminder(bot,user_id,respond_info['message'])
                    w = FolowUpCalls(bot,user_id,message, delay)

                #self.user_threads[user_id] = w
            else: 
                print(f'error missing response in:\n{path}')
            
        print('resolved callbacks. runing as usual')


class Conversation_Manager():
    #when using this u can just overide the process message method
    convs={} 

    def __init__(self,path:str,bot,buffer_time=3):
        self.semaphore = asyncio.Semaphore(1)

        with open(join(path,'init.json'),'r') as f:
            user_info = json.load(f)
        self.chat_id=user_info['chat_id']
        self.bot=bot
        
        self.path=path
        self.save_path=join(path,'texting.txt')
        self.last_out=0 #this is unix time
        #self.mem_path=join(path,'scedualed_respond.json')
        #self.lock=0
        self.buffer_time=buffer_time
      
        #self.task=asyncio.create_task(asyncio.sleep(0))
    async def lock(self):
        await self.semaphore.acquire()

    def free(self):
        self.semaphore.release() 
        
    @classmethod  
    def from_id(cls,idx,bot):
        try:
            return cls.convs[idx]
        except KeyError:
            path=join('users',str(idx))
            ans=cls(path,bot)
            cls.convs[idx]=ans 
            return ans
 
    async def hook(self,message,path):
        #await self.lock()
        
        await self.send_message(f'we got:\n{message}')
        #self.free()

    async def _hook(self):
        #await self.lock()
        m=await self.done_gathering()
        if m:
            await self.hook(m,self.path)
        #self.free()

    async def send_message(self,message):
        #assert not self.lock
        
        t=datetime.now().strftime('%Y-%m-%d %H:%M:%S')+'.json'
        await self.bot.send_message(self.chat_id, message)
        with open(join(self.path,'send_messages',t), 'w') as f:
                json.dump({'chat_id': self.chat_id, 'message': message}, f)

    async def add(self,message):
        with open(self.save_path,'a') as f:
            f.write(message+'\n\n')
        #self.task.cancel()
        
        #if time.time()-self.last_out>self.buffer_time:
        asyncio.create_task(self._hook())


    async def done_gathering(self):
        #await self.lock()
        await self.lock()
        #print('locked')
        t=time.time()-self.last_out
        await asyncio.sleep(self.buffer_time-t)
        #print('woke')

        if exists(self.save_path):
            with open(self.save_path) as f:
                message=f.read()
                os.remove(self.save_path)
        else: 
            message= '' 

        self.last_out=time.time()
        
        self.free()
        #print('free')
        return message



def tel_main(tel,response,reminder,errored_reminder,start) -> None:
    """Start the bot."""
    responder=Responder(response,reminder,errored_reminder,start)
    FolowUpCalls.set_func(reminder)

    application = Application.builder().token(tel).post_init(responder.initialize_tasks).build()
    
    application.add_handler(CommandHandler("start", responder.start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, responder.respond))
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":

    thread_count=0
    print('started server')
    with open('secrets') as f:
        tel,ai=tuple(f.read().split('\n'))[:2]

    openai.api_key=ai
    #self.user_threads = {}  # this stores the callback threads 

    async def response(bot,user_id,message):
        #print(bot)
        conv=Conversation_Manager.from_id(user_id,bot)
        
        await conv.add(message)

        return 10,'2'

    async def reminder(bot,user_id,notes:str):
        #print(junk)
        #print(bot)
        conv=Conversation_Manager.from_id(user_id,bot)
        
        
        m= await conv.done_gathering()
        if m:
            await conv.send_message(f'reminder got:\n{m}')
        await conv.send_message(f'reminder:\n{notes}')
        
        secs=int(notes)
        if secs>4:
            ans=None 
        else:
            ans=str(2*secs)
        return secs,ans

    async def errored_reminder(bot,user_id,notes:str):
        conv=Conversation_Manager.from_id(user_id,bot)
        
        #conv.task.cancel()
        m= await conv.done_gathering()
        if m:
            await conv.send_message(f'found:\n{m}\n in memory')
        await conv.send_message(f'server error delayed response:\n{notes}')

        secs=int(notes)
        if secs>4:
            ans=None 
        else:
            ans=str(2*secs)
        return secs,ans
        #await send_message(bot,user_id,'server error delayed response:\n'+notes) 

    async def start(bot,user_id,user):
        await send_message(bot,user_id,f'hi {user.name}')

    tel_main(tel,start=start,response=response,errored_reminder=errored_reminder,reminder=reminder)