import aiohttp
import asyncio
from io import BytesIO
import time
import concurrent

class DownloadTask:
    DEFAULT = 0
    IN_PROGRESS = 1
    SUCCESS = 2
    FAILURE = 3
    
    def __init__(self, address):
        self.address = address
        self.retry_count = 15
        self.status = DownloadTask.DEFAULT
        self.data = None
        
    def update_status(self, new_status):
        self.status = new_status
        
    def decrease_retry_count(self):
        if self.retry_count > 0:
            self.retry_count -= 1


class TaskList:
    def __init__(self):
        self.tasks = []
        self.allow_duplicates = False
        self.finished_tasks = {}
        self.failed_tasks = {}
        
    def get_task(self):
        print(len(self.tasks))
        return self.tasks.pop()        
        
    def add_task(self, task):
        if (self.allow_duplicates) or ((not self.allow_duplicates) and (task not in self.tasks)):
            self.tasks.append(task)
        
    def is_empty(self):
        return len(self.tasks) == 0
        

async def async_worker(tl, handler_proc, handler_arg, worker_num):
    print(f"Worker #{worker_num} started working")
    while not tl.is_empty():
        dt = tl.get_task()
        dt.decrease_retry_count()
        address = dt.address
        ltime = time.time()
        print(f"Worker #{worker_num} started downloading {address} at time {ltime}")
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(address) as response:

                    print("Status:", response.status)
                    print("Content-type:", response.headers['content-type'])

                    http_response = await response.read()
                    #tl.finished_tasks[address] = http_response
                    print("Finished downloading ", address)                   
                    
                    local_name = address.split("/")[-1]
                    
                    if local_name == "makaba.css":
                        local_name = "mk.css"
                        
                    ldict = {"data": http_response, "address": address, "local_name": local_name, "worker":worker_num}
                    handler_proc(ldict, handler_arg)
                    
                    #print("Body:", html[:100], "...")
        except (aiohttp.client_exceptions.ClientOSError, aiohttp.client_exceptions.ServerDisconnectedError, 
            concurrent.futures._base.TimeoutError, aiohttp.client_exceptions.ClientPayloadError) as E:
            print("Exception while downloading", address)
            print("Exception type", E)
            print("Adding task to the end of the queue... (retries:", dt.retry_count, ")")
            
            if dt.retry_count > 0:
                tl.add_task(dt)
            
        except aiohttp.client_exceptions.InvalidURL as E:
            print("Exception while downloading", address)
            print("Exception type", E)
            tl.failed_tasks[address] = "" 
        
        ltime = time.time()                
        print(f"Worker #{worker_num} finished downloading {address} at time {ltime}")
    print(f"Worker #{worker_num} finished working")
    
def run_download_loop(workers_count, handler_proc, handler_tag):
    loop = asyncio.get_event_loop()
    tasks = [async_worker(tasklist, handler_proc, handler_tag, i) for i in range(workers_count)]
    wait_tasks = asyncio.wait(tasks)
    loop.run_until_complete(wait_tasks)
