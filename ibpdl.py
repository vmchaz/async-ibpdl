import html
from html.parser import HTMLParser
from urllib import request
import sys
import tarfile
import time
from io import BytesIO

import aiohttp
import asyncio

import hashlib

from asyncworkers import DownloadTask, TaskList, async_worker, run_download_loop



def handler_proc(ldict, handler_arg):
    tf = handler_arg
    
    fb = BytesIO(ldict["data"])
    ti = tarfile.TarInfo(name=ldict["local_name"])
    ti.size = len(ldict["data"])
    ti.mtime = time.time()
    tf.addfile(tarinfo=ti, fileobj=fb)
    

class MyHTMLParserB1(HTMLParser):

    def __init__(self, tasklist, site_address):
        HTMLParser.__init__(self)
        self.tasklist = tasklist
        self.site_address = site_address
        self.addresses = []
        self.replace_table = {}
        self.in_image_block = False
        self.in_figure = False
        self.in_figcaption = False
        self.in_preview_link = False


    def handle_starttag(self, tag, attrs):
    
        
        
        attrs_dict = {}
        for attr in attrs:
            attrs_dict[attr[0]] = attr[1]
                
        #if hashlib.md5(tag.encode).hexdigest().startswith("d5"):
        #    pass
        
        if (tag == "figure") and attrs_dict.get("class") == "post__image":
            self.in_image_block = True
            self.in_figure = True
            
        elif (tag == "figcaption") and ("class" in attrs_dict) and (attrs_dict["class"] == "post__file-attr"):
            self.in_figcaption = True
            
        elif tag == "img":
            if self.in_figure:
                h = attrs_dict["src"]
                if not h in self.addresses:
                    self.addresses.append(h)
                    
        elif tag == "link":
            if ("type" in attrs_dict) and (attrs_dict["type"] == "text/css"):
                h = attrs_dict["href"]
                if "?" in h:
                    h = h[0:h.index("?")]
                if not h in self.addresses:
                    self.addresses.append(h)
            
        elif (tag == "a"):
            if attrs_dict.get("class") == "post__image-link":
                self.in_preview_link = True
                
                h2 = attrs_dict["href"].lower()
                #if h.startswith("//"):
                #    h = h[2:]
                #h = "https://" + self.site_address + h
                #h2 = h.lower()
                if h2.endswith(".png") or h2.endswith(".jpg") or h2.endswith(".jpeg") or h2.endswith(".webm") or h2.endswith(".mp4"):
                    if h2 not in self.addresses:
                        self.addresses.append(h2)
                        
                    #if h not in self.imgs:
                    #    self.imgs.append(h)

    def handle_endtag(self, tag):
        if tag == "a":
            if self.in_preview_link:
                self.in_preview_link = False
        if tag == "figure":
            if self.in_preview_link:
                self.in_preview_link = False                
            self.in_figure = False
        if tag == "figcaption":
            self.in_figcaption = False
        pass
        #print("Encountered an end tag :", tag)

    def handle_data(self, data):
        pass
        #print("Encountered some data  :", data)
        
def process_addresses_b1(addresses, protocol, site):
    addresses_f = []
    for a in addresses:
        a2 = a
        mc = False
        
        if a2.startswith("//") and (not mc):
            a2 = f"{protocol}:{a2}"
            mc = True
            
        if (len(a2) >= 2) and (a2[0] == "/") and (a2[1] != "/") and (not mc):
            a2 = f"{protocol}://{site}{a2}"
            mc = True
        
        addresses_f.append(a2)
        
    return addresses_f
        
        



def split_address(a):
    if a.startswith("http://"):
        source_protocol = "http"
    elif a.startswith("https://"):
        source_protocol = "https"
    elif a.startswith("file://"):
        source_protocol = "file"
    else:
        source_protocol = None
        
        
    site_addr = None
    board_addr = None
    page_addr = None
    
    if source_protocol == "http" or source_protocol == "https":
        a2 = a[len(source_protocol)+3:]
        
        site_addr = a2.split("/")[0]
        board_addr = a2.split("/")[1]
        page_addr = a2.split("/")[-1]
        if page_addr.endswith(".html"):
            page_addr = page_addr[:-5]
        
    return source_protocol, site_addr, board_addr, page_addr


gFlags = {}        
gAddress = ""

def main():
    if len(sys.argv) < 2:
        return
        
    addr = ""
    
    for a in sys.argv[1:]:
        if a.startswith("--"):
            arg_name = a[2:].split("=", 1)[0]
            if "=" in a:            
                gFlags[arg_name] = a[2:].split("=", 1)[1]
            else:
                gFlags[arg_name] = True
        else:
            if addr == "":
                addr = a
            else:
                addr += " " + a
        
    imgs = []
    imgdata = {}
    htmldata = None
    #print(addr)
    #addr = sys.argv[1]
    
    
    tasklist = TaskList()
    
    
    
    protocol, site_addr, board_name, page_addr = split_address(addr)
    
    parser = MyHTMLParserB1(tasklist, site_addr)
    
    if protocol == "http" or protocol == "https":
        print("Getting page")
        #print(dir(request))
        with request.urlopen(addr) as r:
            htmldata = r.read().decode()
    else:
        print("Unknown protocol")
        return
        
    
    parser.feed(htmldata)
    
    addresses_f = process_addresses_b1(parser.addresses, "https", "2ch.hk")
    addresses_l = []
    htmldata2 = htmldata[:]
    for r in parser.addresses:
        r2 = r.split("/")[-1]
        if r2 == "makaba.css":
            r2 = "mk.css"
        addresses_l.append((r, r2))
        htmldata2 = htmldata2.replace(r, r2)
        #print(r, r2)
        
        
    tarfn =  f"{site_addr} - {board_name} - {page_addr}.tar"
    tar = tarfile.open(tarfn, "w")
    
    if "noindex" not in gFlags:
        hde = htmldata.encode("utf8")
        fb = BytesIO(hde)
        ti = tarfile.TarInfo(name="index.orig.html")
        ti.size = len(hde)
        ti.mtime = time.time()
        tar.addfile(tarinfo=ti, fileobj=fb)
        
        hde2 = htmldata2.encode("utf8")
        fb = BytesIO(hde2)
        ti = tarfile.TarInfo(name="index.html")
        ti.size = len(hde2)
        ti.mtime = time.time()
        tar.addfile(tarinfo=ti, fileobj=fb)


    for a in addresses_f:
        tasklist.add_task(DownloadTask(a))
    
    run_download_loop(2, handler_proc, tar)
    
    tar.close()
    print("Saved to", tarfn)

if __name__ == "__main__":
    main()
