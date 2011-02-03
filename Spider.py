#!/usr/bin/env python3
# Get related documents: images, stylesheets, scripts
import urllib
import sys
import re

from urllib.parse import urljoin, urlsplit
from urllib.request import urlopen
#from urllib.response import info
from html.parser import HTMLParser

# Function timing stuff
#from numpy import *
#import time

#times = array([])
#def get_timing(func):
#	def wrapper(*arg):
#		global times
#		t1 = time.time()                                  
#		res = func(*arg)
#		t2 = time.time()
#		times = append(times, (t2-t1)*1000.0 )
		#print( '%s took %0.3f ms' % (func.__name__, (t2-t1)*1000.0) )
#		return res
#	return wrapper


#class zeroDict (dict):
	# declare the @ decorator just before the function, invokes print_timing()
#	@get_timing
#	def __getitem__(self, k):
#		try:
#			v = dict.__getitem__(self, k)
#		except KeyError:
#			return 0
#		return v


# The above way is my implementation... after searching google, I found this:
# src: http://www.velocityreviews.com/forums/t641768-re-type-feedback-tool.html
# Turns out this version is faster

# zeroDict
# A class like a dict, but it overrides the ['key'] accessor (__getitem__)
# to return 0 if a key does not exist yet
# The += operator can then be safely used on it ;-)
class zeroDict(dict):
	def __getitem__(self, key):
		if key not in self:
			return 0
		return dict.__getitem__(self, key)


# Global dictionaries (used to ensure unique links are only processed once)
# These will provide an object keyed array 
# The number of references to each image,stylesheet,script, or link are stored
# ie: { 'http://example.com/': 1 }
images  = zeroDict()        
styles  = zeroDict()
scripts = zeroDict()
links   = zeroDict()
top_lvl = ''

class Spider (HTMLParser):
	"""An HTML parser to get lists of related content"""
	global images
	global styles
	global links
	
	def __init__(self, url, domainLimit=False, depthLimit=100, debug=False):
		super(Spider, self).__init__()
		if debug: 
			print( "Constructor was called" )
			print( "Spider Level Limit: ", depthLimit )
		self.url = url
		self.depthLimit = depthLimit
		self.domainLimit = domainLimit
		self.__debug = debug
		self.pageData = ''
		self.child = object
		self.images  = zeroDict()
		self.styles  = zeroDict()
		self.scripts = zeroDict()
		self.links   = zeroDict()
	
	def readUrl (self):
		# Read data from 'my' url
		furl = urllib.request.urlopen (self.url)
		self.pageData = furl.read()
		headers = furl.info()
		header_ctype = re.sub( '(?i).*charset=(.+)', '\\1', headers['content-type'] )
		#page_ctype = re.sub( '(?i)meta\s+http-equiv="Content-Type"\s+content=".*charset=(.+)', '\\1', self.pageData )
		page_ctype = ''
		
		print( 'header: ', header_ctype )
		print( 'page: ', page_ctype )
		if header_ctype:
			self.pageData = self.pageData.decode( header_ctype )
		elif page_ctype:
			self.pageData = self.pageData.decode( page_ctype )
		else:
			self.pageData = self.pageData.decode( 'utf8' )
		
		# update url in case it redirected us
		self.url = furl.geturl()
		furl.close()
		
		self.feed(self.pageData)
	
	# function to recursively spider links
	# if depthLimit is <0, we treat this as an 'infinite' depth limit
	# if we're limited to the root domain, exit
	#or ( self.domainLimit and  == ):
	def spider (self, url):
		parts = urlsplit( url )
		print ( 'netloc: ', parts[1] )
		print ( 'path: ', parts[2] )
		print ( 'query: ', parts[3] )
		print ( 'fragment: ', parts[4] )
		
		if self.depthLimit == 0:
			if self.__debug:
				print( "depth limit reached will go no further!" )
			return
		else:
			if self.__debug: 
				print( "spidering: " + url )
				print( "limit: ", self.depthLimit )
			a = Spider(url, self.domainLimit, self.depthLimit-1, self.__debug)
			a.readUrl()
			a.close()
	
	# Function to print the resources found for this Spider
	def printResources(self):
		print ( '## Images: ' )
		for k, v in images.items():  print( '%2d => %s' % (v, k) )
		print ( '## Stylesheets: ' )
		for k, v in styles.items():  print( '%2d => %s' % (v, k) )
		print ( '## Scripts: ' )
		for k, v in scripts.items(): print( '%2d => %s' % (v, k) )
		print ( '## Links: ' )
		for k, v in links.items():   print( '%2d => %s' % (v, k) )
	
	# Function hook into the parser's handle_starttag handler
	# This gets all images, stylesheets, scripts, and links on the page, 
	# and track the occurrences of unique objects.
	# Each object occurrence is stored both in global & per-url contexts
	def handle_starttag (self, tag, attrs):
		arr = dict (attrs)
		if tag=="img":
			# Images
			src = urljoin (self.url, arr['src'])
			self.images[src] += 1
			images[src] += 1
		elif tag=="link" and arr["rel"]=="stylesheet" and 'src' in arr:
			# Linked styslesheets
			href = urljoin (self.url, arr['src'])
			self.styles[href] += 1
			styles[href] += 1
		elif tag=="script" and 'src' in arr:
			# Linked scripts
			src = urljoin (self.url, arr['src'])
			self.scripts[src] += 1
			scripts[src] += 1
		elif tag=="a" and 'href' in arr:
			href = urljoin (self.url, arr['href'])
			# Spider all links below rooturl!
			# Only follow the same link once!
			# How do we keep global links/styles/images arrays 
			# to keep track of all object counts?
			if links[href] == 0:
				self.spider(href)
			else:
				if self.__debug:
					print('Already followed: ', href)
			self.links[href] += 1
			links[href] += 1
	
	def handle_endtag (self, tag):
		if tag=="style":
			# Stylesheets included as: 
			# <style>@import url(...);</style>
			text = self.lastdata.strip()
			if text[:12] == "@import url(":
				style = urljoin (self.url, text[12:-2])
				self.styles[style]=1
	
	def handle_data (self, data):
		self.lastdata = data
	
#url = "http://localhost:8080/Plone-test/sample-content/sitemap"
url = "http://ubuntuforums.org/"
if len (sys.argv)>1:
	url = sys.argv[1]

# Read data from given url
furl = urllib.request.urlopen (url)
data = furl.read()
furl.close()

# Parse the data
a = Spider(furl.geturl(), True, 2, True)
a.readUrl()
#a.feed (data)
a.close()

# Print output
print( '###################  DONE SPIDERING  ###################\n')
print( furl.geturl() )
#for k in a.images.keys(): print( k )
#for k in a.styles.keys(): print( k )
#for k in a.scripts.keys(): print( k )
#for k in a.links.keys(): print( k )
for k, v in images.items():  print( '%2d => %s' % (v, k) )
for k, v in styles.items():  print( '%2d => %s' % (v, k) )
for k, v in scripts.items(): print( '%2d => %s' % (v, k) )
for k, v in links.items():   print( '%2d => %s' % (v, k) )


#print( 'Runtime statistics: ' )
#for i in times: print ( '__getitem__ took %0.3f ms' % i )
#print( 'Number of executions: ', times.size )
#print( 'Min time: %0.3f ms' % times.min() )
#print( 'Max time: %0.3f ms' % times.max() )
#print( 'Average time: ', average(times) )
#print( 'Std Dev: %0.3f ms' % times.std() )
#print( 'Total time: %0.3f ms' % times.sum() )
