from html.parser import HTMLParser
from urllib import request
import tarfile
import time
from io import BytesIO
import argparse
from logger import logging

from asyncworkers import DownloadTask, TaskList, async_worker, run_download_loop


def handler_proc(address, local_name, data, worker_num, handler_arg):
    if local_name.startswith("mak") and local_name.endswith(".css"):
        local_name = "mk.css"

    tf = handler_arg
    
    fb = BytesIO(data)
    ti = tarfile.TarInfo(name=local_name)
    ti.size = len(data)
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
                if h2.endswith(".png") or h2.endswith(".jpg") or h2.endswith(".jpeg") or h2.endswith(".webm") or h2.endswith(".mp4"):
                    if h2 not in self.addresses:
                        self.addresses.append(h2)


    def handle_endtag(self, tag):
        if tag == "a":
            if self.in_preview_link:
                self.in_preview_link = False

        elif tag == "figure":
            if self.in_preview_link:
                self.in_preview_link = False                
            self.in_figure = False

        elif tag == "figcaption":
            self.in_figcaption = False


    def handle_data(self, data):
        pass
        


def process_addresses_b1(addresses, protocol, site):
    return [f"{protocol}:{a}" for a in addresses if a.startswith("//")] \
    + [f"{protocol}://{site}{a}" for a in addresses if (len(a) >= 2) and (a[0] == "/") and (a[1] != "/")]


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
    argparser = argparse.ArgumentParser()
    argparser.add_argument("address", type=str, help="Address of the thread to save")
    argparser.add_argument("-n", "--noindex", action="store_true", help="dont save index.html")

    args = argparser.parse_args()

    gFlags["noindex"] = args.noindex
    addr = args.address
    
    tasklist = TaskList()
    
    protocol, site_addr, board_name, page_addr = split_address(addr)
    
    parser = MyHTMLParserB1(tasklist, site_addr)
    
    if protocol == "http" or protocol == "https":
        logging.info("Getting page")
        with request.urlopen(addr) as r:
            htmldata = r.read().decode()
    else:
        logging.error("Unknown protocol")
        return
    
    parser.feed(htmldata)
    
    addresses_f = process_addresses_b1(parser.addresses, "https", site_addr)
    addresses_l = []
    htmldata2 = htmldata[:]

    #TODO: use only 1 local name list
    #TODO: optimize replace

    for full_address in parser.addresses:
        local_address = r.split("/")[-1]
        if local_address.startswith("mak") and local_address.endswith(".css"):
            local_address = "mk.css"

        addresses_l.append((full_address, local_address))
        htmldata2 = htmldata2.replace(full_address, local_address)
        
        
    tarfn =  f"{site_addr} - {board_name} - {page_addr}.tar"
    tar = tarfile.open(tarfn, "w")
    
    if "noindex" not in gFlags:
        hde = htmldata.encode("utf8")
        fb = BytesIO(hde)
        ti = tarfile.TarInfo(name="index.orig.html")
        ti.size = len(hde)
        ti.mtime = time.time()
        tar.addfile(tarinfo=ti, fileobj=fb)
        
        htmldata_encoded = htmldata2.encode("utf8")
        fb = BytesIO(htmldata_encoded)
        ti = tarfile.TarInfo(name="index.html")
        ti.size = len(htmldata_encoded)
        ti.mtime = time.time()
        tar.addfile(tarinfo=ti, fileobj=fb)

    for a in addresses_f:
        tasklist.add_task(DownloadTask(a))
    
    run_download_loop(2, tasklist, handler_proc, tar)
    
    tar.close()
    logging.info("Saved to", tarfn)

if __name__ == "__main__":
    main()
