import openai 
import numpy as np
import json
from datetime import datetime

from utills import openai_format


async def get_embedding(text, model="text-embedding-ada-002"):
   text = text.replace("\n", " ")
   x= await openai.Embedding.acreate(input = [text], model=model)
   return np.array(x['data'][0]['embedding'])

async def gpt_response(messages,model='gpt-3.5-turbo',full=False):
	#input validation
	for m in messages:
		assert m['role'] in alowed_roles
		if m['role']=='function':
			assert 'name' in m.keys()
		assert 'content' in m.keys()

	x=await openai.ChatCompletion.acreate(model=model,messages=messages,functions=functions)
	if full:
		return x
	#print(x)	
	x=x["choices"][0]["message"]
	return x,x.get('content'),x.get("function_call")

alowed_roles=('system','user','assistant','function')


deafualt_messages=[openai_format('you are a robo asistent'),
                   openai_format('''at your disposal you have 3 diffrent system: 
                   calander that keeps events wakeup manager that alows you to scedual runing sessions for yourself and a note system with 4 folders'''),
          openai_format('when passing in datetimes to functions make sure to only use the alowed keywords and integers inside of a dict clearly stating their purpose {year:2000,month:3,day:5,hour:23,minute:3}'),
          openai_format('modify event only takes "start" and "end" as its time arguments and modify wakeup takes only "time" as its time argument'),
                   #openai_format('if you want to delete an event/wakeup/note make sure to pass JUST ITS INDEX (and folder for notes) so modify_event(idx=5) will remove: "5. wedding; start: 2023-07-20 21:06; end:2023-07-20 23:06"'),
                  openai_format('if you want to delete an event/wakeup/note make sure to pass JUST ITS INDEX (and folder for notes) so modify_note(idx=5) will remove event "5. I saw the user being sad[7]"'),
                   openai_format('when selecting a wakeup/event the index is an integer DONT USE THE NAME'),
                  ]
functions = [
    {
        "name": "search_calander",
        "description": "Searches calendar for a range from start to end",
        "parameters": {
            "type": "object",
            "properties": {
                "start": {
                    "type": ["object", "null"],
                    "description": "Start date and time in dict format"
                },
                "end": {
                    "type": ["object", "null"],
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
                    "d": {
                        "type": ["object", "null"],
                        "description": "Event details. Pass None for deletion.",
                        "properties": {
                            "start": {
                                "type": ["object", "null"],
                                "description": f"Start date Pass None if no change is required."
                            },
                            "end": {
                                "type": ["object", "null"],
                                "description": f"End date Pass None if no change is required."
                            },
                            "name": {
                                "type": ["string", "null"],
                                "description": "Event name. Pass None if no change is required."
                            }
                        },
                        "required": ["start", "end", "name"],
                        "additionalProperties": False
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
                            "type": ["object", "null"],
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
    print(x)
    #print(un_async(gpt_response(x)))
