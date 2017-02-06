import urllib
import re
import os
import shutil
from page_getter import PageGetter
from titles import create_tokens
from fix_html import fix_htmls
import sys
import threading
import time
import multiprocessing

# documentation for creating docsets for Dash: http://kapeli.com/docsets/

base_url = "http://msdn.microsoft.com/en-us/library/windows/desktop/"
docset_root = "MSDN.docset"
root_path = "{}/Contents/Resources/Documents/docs/".format(docset_root)
crawl_path = "download_folder/"


urls_to_visit = ["ee663300.aspx"]   # MSDN page: "Windows desktop app development"
known_urls = set(urls_to_visit)   # URLs we visited or will visit
visited_count = 0
globals_lock = threading.Lock()
update_condition = threading.Condition(globals_lock)

def crawl():
    page_getter  = PageGetter(base_url)
    global urls_to_visit
    global visited_count
    global known_urls
    global globals_lock
    global update_condition
    while True:
	globals_lock.acquire()
        if len(urls_to_visit) is 0:
            update_condition.wait()
            if len(urls_to_visit) is 0:
                globals_lock.release()
                break
        cur_url = urls_to_visit.pop(0)
        globals_lock.release()
        local_url = os.path.join(crawl_path, cur_url)
        remote_url = base_url + cur_url
        globals_lock.acquire()
        print cur_url, "(%d remaining, %d visited)" % (len(urls_to_visit), visited_count), "\r",
        sys.stdout.flush()
        globals_lock.release()
        if os.path.exists(local_url):
            cur_url_html = open(local_url, "rb").read()
            globals_lock.acquire()
            print "                                                                           \r",
        else:            
            cur_url_html = page_getter.urlretrieve(remote_url, local_url)
            globals_lock.acquire()
        visited_count += 1
        globals_lock.release();
        new_urls = re.findall("(?:href|src)=['\"].*?en-us/library/windows/desktop/(\w\w\d{6}\(v=vs.85\).aspx)['\"]", cur_url_html, re.I)
        globals_lock.acquire()
        new_urls = set(url for url in new_urls if url not in known_urls)
        urls_to_visit.extend(list(new_urls))
        known_urls.update(new_urls)
        update_condition.notify(n=len(urls_to_visit))
        globals_lock.release();

def main():
    global visited_count
    visited_count = 0
    if not os.path.exists(root_path):
        os.makedirs(root_path)
    if not os.path.exists(crawl_path):
        os.makedirs(crawl_path)
    threads = []
    thread_count = multiprocessing.cpu_count() + 1
    print "Spawning %d worker threads..." % thread_count
    for i in range(thread_count):
        threads.append(threading.Thread(target=crawl))
    for thread in threads:
        thread.daemon = True
        thread.start()
        time.sleep(1)
    for thread in threads:
        thread.join()
    print "Done crawling. Crawled %d pages" % (visited_count,)
    fix_htmls()
    create_tokens("{}/Contents/Resources/Tokens.xml".format(docset_root))
    shutil.copy("static/icon.png", "{}/".format(docset_root))
    shutil.copy("static/Info.plist", "{}/Contents/".format(docset_root))
    shutil.copy("static/Nodes.xml", "{}/Contents/Resources/".format(docset_root))
    os.system("/Applications/Xcode.app/Contents/Developer/usr/bin/docsetutil index {}".format(docset_root))

if __name__ == "__main__":
    main()
