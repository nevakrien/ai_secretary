this is a nice simple repo for runing a server I am doing as a side project 

LIMITATIONS:
time zone support is not fully implemented (tools to add it are there tho)
post crash initiliation may mess the order of messages giving a diffrent answer
if there is an error in resolving changes the bot dosent know

TODO:
more robust checks for function calls (the error raised should be relevent to the situation)


add length constraints and checks for the input 
remove the halusinations made from the autocomplete behvior	

ODD BUGS:	
when changing the time of a wakeup that new time is used to search it causing an error (fixed? cause of the error is that search is called before resolution)