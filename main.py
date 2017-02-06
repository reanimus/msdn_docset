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
sleeping_threads = 0
running_threads = 0

def watchdog():
    global sleeping_threads
    global running_threads
    global globals_lock
    global update_condition
    while True:
        time.sleep(1)
        with globals_lock:
            if running_threads == 0:
                break
            if running_threads == sleeping_threads:
                print "[DBG] All threads deadlocked! Waking..."
                update_condition.notifyAll()

def crawl():
    page_getter  = PageGetter(base_url)
    global urls_to_visit
    global visited_count
    global known_urls
    global globals_lock
    global update_condition
    global sleeping_threads
    global running_threads
    while True:
	globals_lock.acquire()
        if len(urls_to_visit) is 0:
            sleeping_threads += 1
            update_condition.wait()
            sleeping_threads -= 1
            if len(urls_to_visit) is 0:
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
        else:            
            cur_url_html = page_getter.urlretrieve(remote_url, local_url)
        new_urls = re.findall("(?:href|src)=['\"].*?en-us/library/windows/desktop/(\w\w\d{6}\(v=vs.85\).aspx)['\"]", cur_url_html, re.I)
        globals_lock.acquire()
        visited_count += 1
        new_urls = set(url for url in new_urls if url not in known_urls)
        urls_to_visit.extend(list(new_urls))
        known_urls.update(new_urls)
        update_condition.notify(n=len(urls_to_visit))
        if len(urls_to_visit) is 0:
            break
        globals_lock.release()
    running_threads -= 1
    print "Crawler done. %d remaining." % running_threads
    globals_lock.release()

def main():
    global visited_count
    global globals_lock
    global update_condition
    global running_threads
    visited_count = 0
    if not os.path.exists(root_path):
        os.makedirs(root_path)
    if not os.path.exists(crawl_path):
        os.makedirs(crawl_path)
    threads = []
    thread_count = (multiprocessing.cpu_count() * 3) + 1
    running_threads = thread_count
    print "Spawning %d worker threads..." % thread_count
    for i in range(thread_count):
        threads.append(threading.Thread(target=crawl))
    for thread in threads:
        thread.daemon = True
        thread.start()
        time.sleep(0.1)
    threading.Thread(target=watchdog).start()
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
