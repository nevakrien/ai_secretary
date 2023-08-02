import openai 
import numpy as np
import json
import os
from os.path import join,exists
from datetime import datetime

from utills import openai_format,write_int_to_file,read_int_from_file

import asyncio

#not sure I need it but its there for testing mostly
import time

class RateLimitedAPICall:
    def __init__(self, api_function, max_calls, time_window=1):
        self.api_function = api_function
        self.max_calls = max_calls
        self.time_window = time_window  # limiting time window in seconds
        self.call_timestamps = []  # stores the timestamps of the calls

    async def __call__(self, *args, **kwargs):
        # If we've reached max number of calls within the time window,
        # sleep until we're allowed to call again
        if len(self.call_timestamps) >= self.max_calls:
            oldest_call = self.call_timestamps[0]
            time_passed = time.time() - oldest_call

            if time_passed < self.time_window:
                sleep_time = self.time_window - time_passed
                await asyncio.sleep(sleep_time)

        # Make sure our list of timestamps doesn't grow infinitely.
        # Only keep timestamps within our time window.
        current_time = time.time()
        self.call_timestamps = [ts for ts in self.call_timestamps if current_time - ts <= self.time_window]

        # Execute the API function call
        result = await self.api_function(*args, **kwargs)

        # Add the timestamp of this call to the list
        self.call_timestamps.append(time.time())
        
        return result

class LogAPICall: 
    def __init__(self,api_function,folder='Logs'):
        self.path=folder 
        if not exists(self.path):
            os.makedirs(self.path)
            write_int_to_file(join(self.path,'idx'),0)
        self.idx=read_int_from_file(join(self.path,'idx'))
        self.api_function=api_function

    async def __call__(self,messages):
        result =await self.api_function(messages)
        p=join(self.path,str(self.idx))
        os.mkdir(p)
        with open(join(p,'input.txt'),'w') as f:
            f.write(str(messages))
        with open(join(p,'output.txt'),'w') as f:
            f.write(str(result))
        self.idx+=1
        write_int_to_file(join(self.path,'idx'),self.idx)
        return result




async def get_embedding(text, model="text-embedding-ada-002"):
   text = text.replace("\n", " ")
   x= await openai.Embedding.acreate(input = [text], model=model)
   return np.array(x['data'][0]['embedding'])

def Input_validation(messages):
    #try:
    for m in messages:
        assert m['role'] in alowed_roles
        if m['role'] == 'function':
            assert 'name' in m.keys()
        assert 'content' in m.keys()
    #except Exception as e:
        #print(messages)
        #raise e

async def gpt_response(messages, model='gpt-3.5-turbo', full=False):
    Input_validation(messages)

    x = await openai.ChatCompletion.acreate(model=model, messages=messages, functions=functions)
    if full:
        return x
    # print(x)
    return extract_message(x)


def extract_message(x):
    x=x["choices"][0]["message"]
    return x,x.get('content'),x.get("function_call")

alowed_roles=('system','user','assistant','function')


#deafualt_messages=[openai_format('you are a robo asistent'),
#                   openai_format('''at your disposal you have 3 diffrent system: 
#                   calander that keeps events wakeup manager that alows you to scedual runing sessions for yourself and a note system with 4 folders'''),
#          openai_format('when passing in datetimes to functions make sure to only use the alowed keywords and integers inside of a dict clearly stating their purpose {year:2000,month:3,day:5,hour:23,minute:3}'),
#          openai_format('modify event only takes "start" and "end" as its time arguments and modify wakeup takes only "time" as its time argument'),
#                   #openai_format('if you want to delete an event/wakeup/note make sure to pass JUST ITS INDEX (and folder for notes) so modify_event(idx=5) will remove: "5. wedding; start: 2023-07-20 21:06; end:2023-07-20 23:06"'),
#                  openai_format('if you want to delete an event/wakeup/note make sure to pass JUST ITS INDEX (and folder for notes) so modify_note(idx=5,folder="memories") will remove event "5. I saw the user being sad[7]" from the "memories" folder'),
#                   #openai_format('when selecting a wakeup/event the index is an integer DONT USE THE NAME'),
#                  ]
functions = [
    {
        "name": "set_ping",
        "description": "Sets the delay and prompt for the bot's ping message.",
        "parameters": {
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "description": "The message to be displayed when the ping is sent."
                },
                "duration": {
                    "type": ["string", "integer"],
                    "description": "The delay before the ping is sent. Can be an integer (number of seconds) or a string (representing a duration such as '1h 30m')."
                }
            },
        }
    },

    {
        "name": "word_search_calander",
        "description": "Searches calendar for a range from start to end",
        "parameters": {
            "type": "object",
            "properties": {
                "key": {
                    "type": "string",
                    "description": "a phrase to be searched"
                }
            },
            
    }
    },
    {
        "name": "range_search_calander",
        "description": "Searches calendar for a range from start to end",
        "parameters": {
            "type": "object",
            "properties": {
                "start": {
                    "type": "object",
                    "description": "Start date and time in dict format"
                },
                "end": {
                    "type": "object",
                    "description": "End date and time in dict format"
                }
            },
            "required": ["start", "end"],
        }
    },
    {
        "name": "modify_note",
        "description": "Modifies note in a specified folder by idx. Creates a new note if idx is None. Removes note if all other fields are None.",
        "parameters": {
            "type": "object",
            "properties": {
                "folder": {
                    "type": "string",
                    "enum": ["user profile", "goals", "memories", "reflections"],
                    "description": "One of the four folder names: 'user profile', 'goals', 'memories', 'reflections'."
                },
                "idx": {
                    "type": ["integer", "null"],
                    "description": "Index of the note. Pass None for a new note."
                },
                "text": {
                    "type": ["string", "null"],
                    "description": "The desired text. Pass None if no change is required."
                },
                "importance": {
                    "type": ["integer", "null"],
                    "minimum": 0,
                    "maximum": 10,
                    "description": "A rank from 0 to 10. Pass None if no change is required."
                }
            },
            "required": ["folder", "idx"],
            "additionalProperties": False
        }
    },
        {
            "name": "modify_event",
            "description": "Modifies event by idx. Creates a new event if idx is None. Removes event if all other fields are None.",
            "parameters": {
                "type": "object",
                "properties": {
                    "idx": {
                        "type": ["integer", "null"],
                        "description": "Index of the event. Pass None for a new event."
                    },
                    "start": {
                        "type": ["object","string", "null"],
                        "description": f"Start date Pass None if no change is required."
                    },
                    "end": {
                        "type": ["object","string", "null"],
                        "description": f"End date Pass None if no change is required."
                    },
                    "name": {
                        "type": ["string", "null"],
                        "description": "Event name. Pass None if no change is required."
                    }
                      
                },
                "additionalProperties": False
            }
        },
        {
            "name": "modify_wakeup",
            "description": "Modifies wakeup session by idx. Creates a new wakeup if idx is None. Removes wakeup if all other fields are None.",
            "parameters": {
                "type": "object",
                "properties": {
                    "idx": {
                        "type": ["integer", "null"],
                        "description": "Index of the event. Pass None for a new event."
                    },
                    "name": {
                                "type": ["string", "null"],
                                "description": "Wakeup name. Pass None if no change is required."
                            },
                 "message": {
                            "type": ["string", "null"],
                            "description": "Wakeup message that will guide that session. Pass None if no change is required."
                        } ,
                   "time":  {
                            "type": ["object","string", "null"],
                            "description": f"End date and time . Pass None if no change is required."
                    } ,          
                    
                },
                "additionalProperties": False
            }
        }
]






if __name__=='__main__':
    from embedding import Lazy_embed 
    from utills import un_async

    with open('secrets') as f:
        tel,ai=tuple(f.read().split('\n'))[:2]

    openai.api_key=ai
    #print(openai_format('hi'))
    x=[openai_format('hi')]
    #print(x)
    #print(un_async(gpt_response(x)))
    async def filler(x):
        return openai_format('XXX')
    rate_limiter = RateLimitedAPICall(filler,5)  # allow up to 5 calls per second
    rate_limiter=LogAPICall(rate_limiter)
    # Assuming 'api_func' is the function you're calling
    for i in range(30):
        print(un_async(rate_limiter(x)))
