#!/usr/bin/env python3
# Get related documents: images, stylesheets, scripts
import urllib.request
import urllib.parse
import optparse
import sys
import re
#import traceback

from html.parser import HTMLParser

# TODO: Move this to some other class to handle the char detection stuff
def _s2bytes(s):
	# Convert a UTF-8 str to bytes if the interpreter is Python 3
	try:
		return bytes(s, 'utf8')
	except (NameError, TypeError):
		# In Python 2.5 and below, bytes doesn't exist (NameError)
		# In Python 2.6 and above, bytes and str are the same (TypeError)
		return s

class zeroDict(dict):
	'''
	A class like a dict, but it overrides the ['key'] accessor (__getitem__)
  to return 0 if a key does not exist yet, instead of a KeyError
  The += operator can then be safely used on it ;-)
	'''
	def __getitem__(self, key):
		if key not in self:
			return 0
		return dict.__getitem__(self, key)

class resourceCollection():
	'''
	A class to represent the collection of resources on a page.
	
	This includes:
		images
		stylesheets (accessible as 'styles')
		links
		scripts
	
	Uses zeroDict to store an object keyed array/dictionary  
	The number of references to each image,stylesheet,script, or link are stored
	in order to ensure we keep track of which unique resources we have, and how
	many times a page references them
	 ie: { 'http://example.com/': 1 }
	'''
	images  = zeroDict()      
	styles  = zeroDict()
	scripts = zeroDict()
	links   = zeroDict()
	emails  = zeroDict()

class Spyder (HTMLParser):
	'''
	An HTML parser that spiders links and keeps track of resources found per page.
	
	Lists of resources per-spyder/page and a global list (for all spyders/pages) are
	maintained.
	'''
	
	def __init__(self, url, spanHosts=False, depthLimit=100, debug=False, globalResources=resourceCollection()):
		super(Spyder, self).__init__()
		if debug:
			print( "Constructor was called" )
			print( "Spider Level Limit: ", depthLimit )
		self.url = url
		self.depthLimit = depthLimit
		self.spanHosts = spanHosts
		self.__debug = debug
		self.pageData = ''
		self.localResources = resourceCollection()
		self.globalResources = resourceCollection()
		self.globalResources = globalResources
		# Make sure we don't spider the root url more than once!
		self.localResources.links[url]=1
		self.globalResources.links[url]=1
		# Keep track of the baby spiders we spawn in a list
		self.children = []


	
	def readUrl (self):
		'''
		Read data from this spyder object's url, and feeds the parser with it.
		
		Handles content-type detection and decodes text data according to it.
		Defaults to utf8 if no content-type is detected in header or page
		'''
		try:
			furl = urllib.request.urlopen(self.url)
		except urllib.error.URLError:
			if self.__debug:
				# Source from: traceback.print_exc()
				try:
					etype, value, tb = sys.exc_info()
					print ("Error: ", value)
					#traceback.print_exception(etype, value, tb, 0, None)
				finally:
					etype = value = tb = None
			return
		self.pageData = furl.read()
		
		#encoding = furl.headers.getparam('charset')
		
		#http_content_type, http_encoding = _parseHTTPContentType(http_headers.get('content-type', http_headers.get('Content-type')))
		
		headers = furl.info()
		# Regex for capturing the charset from http headers
		#content_type_str = ""
		if headers['content-type']:
			content_type_str = headers['content-type']
		elif headers['Content-type']:
			content_type_str = headers['Content-type']
		header_ctype = re.search( '.*charset=(.*)', content_type_str, re.IGNORECASE )
		# Regex for capturing the charset from a meta tag like this:
		#<META http-equiv="Content-Type" content="text/html; charset=EUC-JP">
		page_ctype = re.search( b'.*<meta\s+http-equiv="Content-Type"\s+content=".*?charset=(.+?)"\s*?/?>', self.pageData, re.IGNORECASE)
		
		if self.__debug:
			print( "####################################################" )
			print( "CHARACTER ENCODING DEBUG" )
			print( 'header: ', header_ctype )
			print( 'page: ', page_ctype )
			if header_ctype:
				print( "####################################################" )
				print( 'header_match: ', header_ctype.group(0) )
				print( 'header_ctype: ', header_ctype.group(1) )
			if page_ctype:
				print( "####################################################" )
				print( 'page_match: ', page_ctype.group(0) )
				print( 'page_ctype: ', page_ctype.group(1) )
				print( "####################################################" )
		if header_ctype:
			self.pageData = self.pageData.decode( header_ctype.group(1) )
		elif page_ctype:
			if re.match( b'utf-8', page_ctype.group(1), re.IGNORECASE):
				ctype = 'utf-8'
			elif re.match( b'us-ascii', page_ctype.group(1), re.IGNORECASE):
				ctype = 'us-ascii'
			elif re.match( b'iso-8859-1', page_ctype.group(1), re.IGNORECASE):
				ctype = 'iso-8859-1'
			elif re.match( b'utf-16', page_ctype.group(1), re.IGNORECASE):
				ctype = 'utf-16'
			elif re.match( b'utf_16', page_ctype.group(1), re.IGNORECASE):
				ctype = 'utf_16'
			elif re.match( b'utf16', page_ctype.group(1), re.IGNORECASE):
				ctype = 'utf16'
			elif re.match( b'utf-32', page_ctype.group(1), re.IGNORECASE):
				ctype = 'utf-32'
			elif re.match( b'utf_32', page_ctype.group(1), re.IGNORECASE):
				ctype = 'utf_32'
			elif re.match( b'utf16', page_ctype.group(1), re.IGNORECASE):
				ctype = 'utf16'
			elif re.match( b'u16', page_ctype.group(1), re.IGNORECASE):
				ctype = 'u16'
			elif re.match( b'csunicode', page_ctype.group(1), re.IGNORECASE):
				ctype = 'csunicode'
			elif re.match( b'ucs-4', page_ctype.group(1), re.IGNORECASE):
				ctype = 'ucs-4'
			elif re.match( b'iso-10646-ucs-4', page_ctype.group(1), re.IGNORECASE):
				ctype = 'iso-10646-ucs-4'
			elif re.match( b'csucs4', page_ctype.group(1), re.IGNORECASE):
				ctype = 'csucs4'
			elif re.match( b'ucs-2', page_ctype.group(1), re.IGNORECASE):
				ctype = 'ucs-2'
			elif re.match( b'iso-10646-ucs-2', page_ctype.group(1), re.IGNORECASE):
				ctype = 'iso-10646-ucs-2'
			else:
				ctype = 'utf-8'
			
			self.pageData = self.pageData.decode( ctype )
		else:
			self.pageData = self.pageData.decode( 'utf-8' )
		
		# update url in case it redirected us
		self.url = furl.geturl()
		furl.close()
		# Feed the parser with this page's data
		self.feed(self.pageData)
	
	def spyder (self, url):
		'''
		Recursively spider links
		
		If depthLimit is <0, we treat this as an infinite depth limit
		If spanHosts is True, links will not be checked against the parent host
		'''
		(target_scheme, target_netloc, target_path, target_query, target_fragment) = urllib.parse.urlsplit(url)
		(scheme, netloc, path, query, fragment) = urllib.request.urlsplit(self.url)
		if self.__debug:
			print ( '%-10s  %-70s   %-70s' % (' ', 'This Spyder Target', 'Parent Spyder Target') )
			print ( '%-10s: %-70s   %-70s' % ( 'scheme',   target_scheme,   scheme  ) )
			print ( '%-10s: %-70s   %-70s' % ( 'netloc',   target_netloc,   netloc  ) )
			print ( '%-10s: %-70s   %-70s' % ( 'path',     target_path,     path    ) )
			print ( '%-10s: %-70s   %-70s' % ( 'query',    target_query,    query   ) )
			print ( '%-10s: %-70s   %-70s' % ( 'fragment', target_fragment, fragment) )
		
		if self.depthLimit == 0:
			if self.__debug:
				print( "depth limit reached will go no further!" )
			return
		print( "####################################################" )
		print ("SPANHOSTS: ", self.spanHosts)
		print( "####################################################" )
		if not self.spanHosts and (target_netloc != netloc):
			if self.__debug:
				print( "Spyder link target does not match parent domain... skipping")
			return
		if self.__debug:
			print( "spidering: " + url )
			print( "limit: ", self.depthLimit )
		# Spawn a baby spyder on the new url,
		# decrement the depthLimit,
		# pass it the globalResources collection,
		# and make it read & parse the page
		a = Spyder(url, self.spanHosts, self.depthLimit-1, self.__debug, self.globalResources)
		self.children.append( a )
		a.readUrl()
		a.close()
	
	def printResources(self):
		'''
		Function to print the resources found for this Spyder object's page
		'''
		print ( '## Images: ' )
		for k, v in self.localResources.images.items():  print( '%2d => %s' % (v, k) )
		print ( '## Stylesheets: ' )
		for k, v in self.localResources.styles.items():  print( '%2d => %s' % (v, k) )
		print ( '## Scripts: ' )
		for k, v in self.localResources.scripts.items(): print( '%2d => %s' % (v, k) )
		print ( '## Links: ' )
		for k, v in self.localResources.links.items():   print( '%2d => %s' % (v, k) )
	
	def printGlobalResources(self, filter_resources):
		'''
		Function to print the global resources collection for all Spyder objects & pages
		'''
		# Get the parent's domain
		#(scheme, netloc, path, query, fragment) = urllib.request.urlsplit(self.url)
		#if filter_resources:
			#self.globalResources.images = { your_key: self.globalResources.images[your_key] for your_key in your_keys }
			
		#	for k, v in self.globalResources.images.items():
		#		(res_scheme, res_netloc, res_path, res_query, res_fragment) = urllib.request.urlsplit(k)
				
		for k, v in self.globalResources.images.items():  print( '%2d => %s' % (v, k) )
		for k, v in self.globalResources.styles.items():  print( '%2d => %s' % (v, k) )
		for k, v in self.globalResources.scripts.items(): print( '%2d => %s' % (v, k) )
		for k, v in self.globalResources.emails.items():   print( '%2d => %s' % (v, k) )
		for k, v in self.globalResources.links.items():   print( '%2d => %s' % (v, k) )
	
	def verifyGlobalResources(self):
		'''
		Function to test whether the global resources collection matches the sum of all
		child Spyder's localResources
		'''
		testResources = resourceCollection()
		for baby in self.children:
			for k, v in baby.localResources.images.items():  testResources.images[k]  += v
			for k, v in baby.localResources.styles.items():  testResources.styles[k]  += v
			for k, v in baby.localResources.scripts.items(): testResources.scripts[k] += v
			for k, v in baby.localResources.emails.items():  testResources.emails[k]  += v
			for k, v in baby.localResources.links.items():   testResources.links[k]   += v
		
		# Assert each resource has the same count
		for k, v in self.globalResources.images.items():   assert( self.globalResources.images[k]  == testResources.images[k] )
		for k, v in self.globalResources.styles.items():   assert( self.globalResources.styles[k]  == testResources.styles[k] )
		for k, v in self.globalResources.scripts.items():  assert( self.globalResources.scripts[k] == testResources.scripts[k] )
		for k, v in self.globalResources.emails.items():   assert( self.globalResources.emails[k]  == testResources.emails[k] )			
		for k, v in self.globalResources.links.items():    assert( self.globalResources.links[k]   == testResources.links[k] )
		
	def handle_starttag (self, tag, attrs):
		'''
		Function hook into the inherited HTMLParser's handle_starttag handler
		
		This gets all images, stylesheets, scripts, and links on the page, 
		and tracks the occurrences of unique resources.
		Each resource occurrence is stored both in global & per-spyder/page contexts
		'''
		arr = dict (attrs)
		if tag=="img" and 'src' in arr:
			# Images
			src = urllib.request.urljoin( self.url, arr['src'] )
			self.localResources.images[src]  += 1
			self.globalResources.images[src] += 1
		elif tag=="link" and 'rel' in arr and arr["rel"]=="stylesheet" and 'src' in arr:
			# Linked styslesheets
			href = urllib.request.urljoin( self.url, arr['src'] )
			self.localResources.styles[href]  += 1
			self.globalResources.styles[href] += 1
		elif tag=="script" and 'src' in arr:
			# Linked scripts
			src = urllib.request.urljoin( self.url, arr['src'] )
			self.localResources.scripts[src]  += 1
			self.globalResources.scripts[src] += 1
		elif tag=="a" and 'href' in arr:
			href = urllib.request.urljoin( self.url, arr['href'] )
			# Spyder all links below rooturl!
			# Only follow the same link once, don't count anchor label links as unique
			# (simply discard the fragment)
			(scheme, netloc, path, query, fragment) = urllib.request.urlsplit(href)
			if fragment and self.__debug:
				print( "Discarding fragment: #", fragment)
			href = urllib.parse.urlunsplit( (scheme, netloc, path, query, '') )
			
			# Handle mailto: links by adding them to resources
			# Else, try to spider the link whatever scheme it is
			if scheme == 'mailto':
				self.localResources.emails[href]  += 1
				self.globalResources.emails[href] += 1
			else:
				if self.globalResources.links[href] == 0:
					self.spyder(href)
				else:
					if self.__debug:
						print('Already followed: ', href)
						# Keep a count of occurrences whether we follow them or not
				self.localResources.links[href]  += 1
				self.globalResources.links[href] += 1
	
	def handle_endtag (self, tag):
		if tag=="style":
			# Stylesheets included as: 
			# <style>@import url(...);</style>
			text = self.lastdata.strip()
			if text[:12] == "@import url(":
				style = urllib.request.urljoin( self.url, text[12:-2] )
				self.localResources.styles[style]  += 1
				self.globalResources.styles[style] += 1
	
	def handle_data (self, data):
		self.lastdata = data
	

def main():
	usage = "usage: %prog -u http://www.example.com"
	parser = optparse.OptionParser(usage)
	parser.set_defaults( span_hosts=False, level=5, debug=False, filter_hosts=False )
	parser.add_option("-u", "--url", dest="url", \
                    help="The url to start spidering from.")
	parser.add_option("-d", "--debug", dest="debug", action="store_true", \
                    help="Print debugging information (very verbose).")
	parser.add_option("-l", "--level", dest="level", \
                    help="Specify recursion maximum depth level depth.  The default maximum depth is 5.")
	parser.add_option("-H", "--span-hosts", dest="span_hosts", \
                    help="Enable spanning across hosts when spidering. The default is to limit spidering to one domain.")
	parser.add_option("-F", "--filter-hosts", dest="filter_hosts", \
                    help="After finished, filter the list of resources printed to the target domain. The default is to print ALL resources found.")
	
	(options, args) = parser.parse_args()
	
	print( "URL: %s" % options.url)
	if args:
		parser.error("Invalid option %s" % args)
	if options.url == '' or options.url == None:
		parser.print_help()
	else:
		#url = "http://localhost:8080/Plone-test/sample-content/sitemap"
		#url = "http://ubuntuforums.org/"
		
		# Read data from given url
		try:
			furl = urllib.request.urlopen(options.url)
		except ValueError:
			parser.error("Invalid url: %s" % options.url)
		#data = furl.read()
		furl.close()
		
		# Parse the data
		sp = Spyder(furl.geturl(), options.span_hosts, options.level, options.debug)
		sp.readUrl()
		#url = "http://localhost:8080/Plone-test/sample-content/sitemap"
		
		# Print output
		print( '###################  DONE SPIDERING  ###################\n')
		print( furl.geturl() )
		sp.verifyGlobalResources()
		sp.printGlobalResources(options.filter_hosts)
		#print( 'Runtime statistics: ' )
		#for i in times: print ( '__getitem__ took %0.3f ms' % i )
		#print( 'Number of executions: ', times.size )
		#print( 'Min time: %0.3f ms' % times.min() )
		#print( 'Max time: %0.3f ms' % times.max() )
		#print( 'Average time: ', average(times) )
		#print( 'Std Dev: %0.3f ms' % times.std() )
		#print( 'Total time: %0.3f ms' % times.sum() )#sp.feed (data)
		sp.close()

if __name__ == '__main__':
	main()
