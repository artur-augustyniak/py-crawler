#!/usr/bin/python
# -*- coding: utf-8 -*-
import os
import optparse
import httplib
#import csv
import time
import urllib2
from bs4 import BeautifulSoup
from urlparse import urlparse, urlunsplit
import socket
import ucsv as csv

class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'

class Parametrizer(object):
    '''Crawler work env params'''
    def __init__(self):
        self.options = None
        self.SEARCH_COUNT = 2000
        self.VERBOSE = False
        self.ACCEPT_HTTP_CODES = [200, 301, 302]
        self.SOCKET_TIMEOUT = 10
        self.OUTPUT_FOLDER = "output"
        self.targetScheme = "http"
        self.targetUrl = None
        self.targetFileHandle = None
        socket.setdefaulttimeout(self.SOCKET_TIMEOUT)
    
    def pushSeoEntry(self, url, title, headings):

        self.targetFileHandle.writerow([url, title, headings[0], headings[1]])
     
    def onScreenInfo(self, message, header,  color):
        if self.VERBOSE:
            print color+header+bcolors.ENDC+message
        
    def processInitOpts(self, options):
        self.options = options
        try:
            count = int(self.options.count)
            if count and count > 0:
                self.SEARCH_COUNT = count
        except (ValueError, TypeError):
            pass
        if self.options.verbose:
            self.VERBOSE = self.options.verbose
        self._validateUrl()
        self._createCsvFile()
            
    def _validateUrl(self):
        """ 
        Check target url
        """
        path="/"
        try:
            conn = httplib.HTTPConnection(self.options.url)
            conn.request("HEAD", path)
            if not conn.getresponse().status in self.ACCEPT_HTTP_CODES:
                raise StandardError
            self.targetUrl = self.options.url
        except StandardError:
            raise RuntimeError("target domain unavaliable")
                
    def _createCsvFile(self):
        """ 
        Try to create or override output file
        """
        path = os.path.join(self.OUTPUT_FOLDER, time.strftime("%Y-%m-%d-%H.%M.%S")+"_"+self.options.output)
        try:
            self.targetFileHandle = csv.writer(open(path, 'w'))
            self.targetFileHandle.writerow(["URL", "TITLE", "H1", "H2"])
        except IOError:
            raise RuntimeError("cannot create target file")
        
class Crawler(object):
    '''Iterative crawler with max items restriction'''
    
    class SetElemPair:
        '''Redefine equality hash for set'''    
        def __init__(self, url, title=None, state=False):
            self.url = url
            self.title = title
            self.state = state      
        def __eq__(self, other):
            return self.url == other.url
        def __hash__(self):
            return hash(self.url)
            
    def __init__(self, prm):
        self.iterationCounter = 0
        self.p = prm
        self.linksSet = set()
        self.initialUrl =  urlunsplit([prm.targetScheme, prm.targetUrl, "", "", ""])
        self._processPage(self.initialUrl, "Initial")
               
        while self._crawl():
            pass
    
    def _processPage(self, url, title):
        self.p.onScreenInfo(url, "[Open]: " , bcolors.OKGREEN)
	opener = urllib2.build_opener(urllib2.HTTPCookieProcessor())
	content = opener.open(url)
        #content = urllib2.urlopen(url)
        cType =  content.info().getheader('Content-Type')
        if("text/html" in cType):
            bsPage = BeautifulSoup(content)
            headings = self._getSeoHedings(bsPage)
            hrefs = self._getSeoHrefs(bsPage)
            self.p.pushSeoEntry(url, title, headings)
            self._rebuildLinkQueue(hrefs)
    
    def _rebuildLinkQueue(self, hrefs):
        for href in hrefs: 
            fullUrl =  self._sanitizeUrl(href[0])
            title = href[1]
            if fullUrl:
                sElem = self.SetElemPair(fullUrl, title)
                self.linksSet.add(sElem)

            
    def _sanitizeUrl(self, href):
        url = urlparse(href)
        scheme = self.p.targetScheme
        if url.scheme and (url.scheme not in ["http", "https"]):
            return None 
        if url.scheme:
            scheme = url.scheme
        # Nie wyjdzie poza domenę self.p.targetUrl
        purl = urlunsplit([scheme, self.p.targetUrl, url.path, url.params, url.query])
        return purl
    
    def _getSeoHedings(self, bsObject):
        firstH1 = bsObject.find('h1')
        firstH2 = bsObject.find('h2')            
        return [firstH1, firstH2]
    
    def _getSeoHrefs(self, bsObject):
        links_pairs = []
        for a in bsObject.findAll('a',href=True):
            link_pair = ["", ""]
            try:
                link_pair[0] = str(a['href'].encode("utf-8")) 
                try:
                    link_pair[1] =  a['title']
                except KeyError:
                    
                    self.p.onScreenInfo(link_pair[0], "[Warning]: link without title - " , bcolors.WARNING)
            except UnicodeEncodeError:
                self.p.onScreenInfo()
                self.p.onScreenInfo("url utf damage", "[Warning]:  " , bcolors.WARNING)        
            links_pairs.append(link_pair)
        return links_pairs 
    
    def _crawl(self):
        while len(self.linksSet) > 0 and self.iterationCounter <= self.p.SEARCH_COUNT:
            it = None
            for tg in self.linksSet:
                if not tg.state:
                    it = tg
                    it.state = True
                    break
            if not it:
                return False
            try:
                self._processPage(it.url, it.title)
            except (urllib2.HTTPError, urllib2.URLError, httplib.BadStatusLine):
                self.p.onScreenInfo(it.url, "[ERROR] can't get contents: " , bcolors.FAIL)
            self.iterationCounter +=1
        return False     

def run():
    prm = Parametrizer()
    parser = optparse.OptionParser()
    parser.add_option('-u', '--url', help='mandatory, domain to crawl without http:// and slashes', dest='url')
    parser.add_option('-o', '--output', help='mandatory, output csv file', dest='output')
    parser.add_option('-c', '--count', help='max crawl items count, default :'+str(prm.SEARCH_COUNT), dest='count')
    parser.add_option('-v', '--verbose', help='verbose output, default :'+str(prm.VERBOSE), dest='verbose', default=False, action='store_true')
    (opts, args) = parser.parse_args()
    mandatories = ['url', 'output']
    for m in mandatories:
        if not opts.__dict__[m]:
            print "mandatory option [ "+m+" ] is missing\n"
            parser.print_help()
            exit(-1)
    try:
        prm.processInitOpts(opts)
    except RuntimeError as e:
        print e
        exit(-1)
    Crawler(prm)
if __name__ == "__main__":
    run()
