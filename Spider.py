#!/usr/bin/env python3
# Get related documents: images, stylesheets, scripts
import urllib
import optparse
import sys
import re
import cgi
import traceback

from urllib.parse import urljoin, urlsplit, urlunsplit
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
##################################################
###  This tricky character encoding detection was
###  copied from the Universal FeedParser source
###  at http://feedparser.org/
###  and adapted into a small class to handle basic
###  character detection handling per RFC 3023
##################################################
class charHandler(dict):
	'''
	A class that was hacked together from bits in the well known
	Universal Feed Parser class written by the great Mark Pilgrim
	'''
	def _s2bytes(s):
		# Convert a UTF-8 str to bytes if the interpreter is Python 3
		try:
			return bytes(s, 'utf8')
		except (NameError, TypeError):
			# In Python 2.5 and below, bytes doesn't exist (NameError)
			# In Python 2.6 and above, bytes and str are the same (TypeError)
			return s
	
	def _l2bytes(l):
		# Convert a list of ints to bytes if the interpreter is Python 3
		try:
			if bytes is not str:
				# In Python 2.6 and above, this call won't raise an exception
				# but it will return bytes([65]) as '[65]' instead of 'A'
				return bytes(l)
			raise NameError
		except NameError:
			return ''.join(map(chr, l))
	
	def _parseHTTPContentType(content_type):
		'''takes HTTP Content-Type header and returns (content type, charset)
		If no charset is specified, returns (content type, '')
		If no content type is specified, returns ('', '')
		Both return parameters are guaranteed to be lowercase strings
		'''
		content_type = content_type or ''
		content_type, params = cgi.parse_header(content_type)
		return content_type, params.get('charset', '').replace("'", '')
	
	def _getCharacterEncoding(http_headers, xml_data):
		'''Get the character encoding of the XML document
	
		http_headers is a dictionary
		xml_data is a raw string (not Unicode)
		
		This is so much trickier than it sounds, it's not even funny.
		According to RFC 3023 ('XML Media Types'), if the HTTP Content-Type
		is application/xml, application/*+xml,
		application/xml-external-parsed-entity, or application/xml-dtd,
		the encoding given in the charset parameter of the HTTP Content-Type
		takes precedence over the encoding given in the XML prefix within the
		document, and defaults to 'utf-8' if neither are specified.  But, if
		the HTTP Content-Type is text/xml, text/*+xml, or
		text/xml-external-parsed-entity, the encoding given in the XML prefix
		within the document is ALWAYS IGNORED and only the encoding given in
		the charset parameter of the HTTP Content-Type header should be
		respected, and it defaults to 'us-ascii' if not specified.
		
		Furthermore, discussion on the atom-syntax mailing list with the
		author of RFC 3023 leads me to the conclusion that any document
		served with a Content-Type of text/* and no charset parameter
		must be treated as us-ascii.  (We now do this.)  And also that it
		must always be flagged as non-well-formed.  (We now do this too.)
		
		If Content-Type is unspecified (input was local file or non-HTTP source)
		or unrecognized (server just got it totally wrong), then go by the
		encoding given in the XML prefix of the document and default to
		'iso-8859-1' as per the HTTP specification (RFC 2616).
		
		Then, assuming we didn't find a character encoding in the HTTP headers
		(and the HTTP Content-type allowed us to look in the body), we need
		to sniff the first few bytes of the XML data and try to determine
		whether the encoding is ASCII-compatible.  Section F of the XML
		specification shows the way here:
		http://www.w3.org/TR/REC-xml/#sec-guessing-no-ext-info
		
		If the sniffed encoding is not ASCII-compatible, we need to make it
		ASCII compatible so that we can sniff further into the XML declaration
		to find the encoding attribute, which will tell us the true encoding.
		
		Of course, none of this guarantees that we will be able to parse the
		feed in the declared character encoding (assuming it was declared
		correctly, which many are not).  CJKCodecs and iconv_codec help a lot;
		you should definitely install them if you can.
		http://cjkpython.i18n.org/
		'''
		sniffed_xml_encoding = ''
		xml_encoding = ''
		true_encoding = ''
		http_content_type, http_encoding = _parseHTTPContentType(http_headers.get('content-type', http_headers.get('Content-type')))
		# Must sniff for non-ASCII-compatible character encodings before
		# searching for XML declaration.  This heuristic is defined in
		# section F of the XML specification:
		# http://www.w3.org/TR/REC-xml/#sec-guessing-no-ext-info
		try:
			if xml_data[:4] == _l2bytes([0x4c, 0x6f, 0xa7, 0x94]):
				# EBCDIC
				xml_data = _ebcdic_to_ascii(xml_data)
			elif xml_data[:4] == _l2bytes([0x00, 0x3c, 0x00, 0x3f]):
				# UTF-16BE
				sniffed_xml_encoding = 'utf-16be'
				xml_data = unicode(xml_data, 'utf-16be').encode('utf-8')
			elif (len(xml_data) >= 4) and (xml_data[:2] == _l2bytes([0xfe, 0xff])) and (xml_data[2:4] != _l2bytes([0x00, 0x00])):
				# UTF-16BE with BOM
				sniffed_xml_encoding = 'utf-16be'
				xml_data = unicode(xml_data[2:], 'utf-16be').encode('utf-8')
			elif xml_data[:4] == _l2bytes([0x3c, 0x00, 0x3f, 0x00]):
				# UTF-16LE
				sniffed_xml_encoding = 'utf-16le'
				xml_data = unicode(xml_data, 'utf-16le').encode('utf-8')
			elif (len(xml_data) >= 4) and (xml_data[:2] == _l2bytes([0xff, 0xfe])) and (xml_data[2:4] != _l2bytes([0x00, 0x00])):
				# UTF-16LE with BOM
				sniffed_xml_encoding = 'utf-16le'
				xml_data = unicode(xml_data[2:], 'utf-16le').encode('utf-8')
			elif xml_data[:4] == _l2bytes([0x00, 0x00, 0x00, 0x3c]):
				# UTF-32BE
				sniffed_xml_encoding = 'utf-32be'
				xml_data = unicode(xml_data, 'utf-32be').encode('utf-8')
			elif xml_data[:4] == _l2bytes([0x3c, 0x00, 0x00, 0x00]):
				# UTF-32LE
				sniffed_xml_encoding = 'utf-32le'
				xml_data = unicode(xml_data, 'utf-32le').encode('utf-8')
			elif xml_data[:4] == _l2bytes([0x00, 0x00, 0xfe, 0xff]):
				# UTF-32BE with BOM
				sniffed_xml_encoding = 'utf-32be'
				xml_data = unicode(xml_data[4:], 'utf-32be').encode('utf-8')
			elif xml_data[:4] == _l2bytes([0xff, 0xfe, 0x00, 0x00]):
				# UTF-32LE with BOM
				sniffed_xml_encoding = 'utf-32le'
				xml_data = unicode(xml_data[4:], 'utf-32le').encode('utf-8')
			elif xml_data[:3] == _l2bytes([0xef, 0xbb, 0xbf]):
				# UTF-8 with BOM
				sniffed_xml_encoding = 'utf-8'
				xml_data = unicode(xml_data[3:], 'utf-8').encode('utf-8')
			else:
				# ASCII-compatible
				pass
			xml_encoding_match = re.compile(_s2bytes('^<\?.*encoding=[\'"](.*?)[\'"].*\?>')).match(xml_data)
		except:
			xml_encoding_match = None
			if xml_encoding_match:
				xml_encoding = xml_encoding_match.groups()[0].decode('utf-8').lower()
				if sniffed_xml_encoding and (xml_encoding in ('iso-10646-ucs-2', 'ucs-2', 'csunicode', 'iso-10646-ucs-4', 'ucs-4', 'csucs4', 'utf-16', 'utf-32', 'utf_16', 'utf_32', 'utf16', 'u16')):
					xml_encoding = sniffed_xml_encoding
			acceptable_content_type = 0
			application_content_types = ('application/xml', 'application/xml-dtd', 'application/xml-external-parsed-entity')
			text_content_types = ('text/xml', 'text/xml-external-parsed-entity')
			if (http_content_type in application_content_types) or \
				(http_content_type.startswith('application/') and http_content_type.endswith('+xml')):
				acceptable_content_type = 1
				true_encoding = http_encoding or xml_encoding or 'utf-8'
			elif (http_content_type in text_content_types) or \
				(http_content_type.startswith('text/')) and http_content_type.endswith('+xml'):
				acceptable_content_type = 1
				true_encoding = http_encoding or 'us-ascii'
			elif http_content_type.startswith('text/'):
				true_encoding = http_encoding or 'us-ascii'
			elif http_headers and (not (http_headers.has_key('content-type') or http_headers.has_key('Content-type'))):
				true_encoding = xml_encoding or 'iso-8859-1'
			else:
				true_encoding = xml_encoding or 'utf-8'
			# some feeds claim to be gb2312 but are actually gb18030.
			# apparently MSIE and Firefox both do the following switch:
			if true_encoding.lower() == 'gb2312':
				true_encoding = 'gb18030'
			return true_encoding, http_encoding, xml_encoding, sniffed_xml_encoding, acceptable_content_type
 

class Spider (HTMLParser):
	'''
	An HTML parser that spiders links and keeps track of resources found per page.
	
	Lists of resources per-spider/page and a global list (for all spiders/pages) are
	maintained.
	'''
	
	def __init__(self, url, spanHosts=False, depthLimit=100, debug=False, globalResources=resourceCollection()):
		super(Spider, self).__init__()
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
		Read data from this spider object's url, and feeds the parser with it.
		
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
		header_ctype = re.sub( '(?i).*charset=(.+)', '\\1', headers['content-type'] )
		page_ctype = re.sub( b'(?i)meta\s+http-equiv="Content-Type"\s+content=".*charset=(.+)', b'\\1', self.pageData )
		
		encoding = headers.get_charset()
		print( "##########################" )
		print( "encoding: ", encoding)
		print( "##########################" )
		
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
		# Feed the parser with this page's data
		self.feed(self.pageData)
	
	def spider (self, url):
		'''
		Recursively spider links
		
		If depthLimit is <0, we treat this as an infinite depth limit
		If spanHosts is True, links will not be checked against the parent host
		'''
		(target_scheme, target_netloc, target_path, target_query, target_fragment) = urlsplit(url)
		(scheme, netloc, path, query, fragment) = urlsplit(self.url)
		if self.__debug:
			print ( '%-10s  %-70s   %-70s' % (' ', 'This Spider Target', 'Parent Spider Target') )
			print ( '%-10s: %-70s   %-70s' % ( 'scheme',   target_scheme,   scheme  ) )
			print ( '%-10s: %-70s   %-70s' % ( 'netloc',   target_netloc,   netloc  ) )
			print ( '%-10s: %-70s   %-70s' % ( 'path',     target_path,     path    ) )
			print ( '%-10s: %-70s   %-70s' % ( 'query',    target_query,    query   ) )
			print ( '%-10s: %-70s   %-70s' % ( 'fragment', target_fragment, fragment) )
		
		if self.depthLimit == 0:
			if self.__debug:
				print( "depth limit reached will go no further!" )
			return
		elif not self.spanHosts and (target_netloc != netloc):
			if self.__debug:
				print( "Child link to spider does not match parent domain... skipping")
			return
		else:
			if self.__debug:
				print( "spidering: " + url )
				print( "limit: ", self.depthLimit )
			# Spawn a baby spider on the new url,
			# decrement the depthLimit,
			# pass it the globalResources collection,
			# and make it read & parse the page
			a = Spider(url, self.spanHosts, self.depthLimit-1, self.__debug, self.globalResources)
			self.children.append( a )
			a.readUrl()
			a.close()
	
	def printResources(self):
		'''
		Function to print the resources found for this Spider object's page
		'''
		print ( '## Images: ' )
		for k, v in images.items():  print( '%2d => %s' % (v, k) )
		print ( '## Stylesheets: ' )
		for k, v in styles.items():  print( '%2d => %s' % (v, k) )
		print ( '## Scripts: ' )
		for k, v in scripts.items(): print( '%2d => %s' % (v, k) )
		print ( '## Links: ' )
		for k, v in links.items():   print( '%2d => %s' % (v, k) )
	
	def printGlobalResources(self):
		'''
		Function to print the global resources collection for all Spider objects & pages
		'''
		for k, v in self.globalResources.images.items():  print( '%2d => %s' % (v, k) )
		for k, v in self.globalResources.styles.items():  print( '%2d => %s' % (v, k) )
		for k, v in self.globalResources.scripts.items(): print( '%2d => %s' % (v, k) )
		for k, v in self.globalResources.emails.items():   print( '%2d => %s' % (v, k) )
		for k, v in self.globalResources.links.items():   print( '%2d => %s' % (v, k) )
	
	def verifyGlobalResources(self):
		'''
		Function to test whether the global resources collection matches the sum of all
		child Spider's localResources
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
		Each resource occurrence is stored both in global & per-spider/page contexts
		'''
		arr = dict (attrs)
		if tag=="img" and 'src' in arr:
			# Images
			src = urljoin (self.url, arr['src'])
			self.localResources.images[src]  += 1
			self.globalResources.images[src] += 1
		elif tag=="link" and arr["rel"]=="stylesheet" and 'src' in arr:
			# Linked styslesheets
			href = urljoin (self.url, arr['src'])
			self.localResources.styles[href]  += 1
			self.globalResources.styles[href] += 1
		elif tag=="script" and 'src' in arr:
			# Linked scripts
			src = urljoin (self.url, arr['src'])
			self.localResources.scripts[src]  += 1
			self.globalResources.scripts[src] += 1
		elif tag=="a" and 'href' in arr:
			href = urljoin (self.url, arr['href'])
			# Spider all links below rooturl!
			# Only follow the same link once, don't count anchor label links as unique
			# (simply discard the fragment)
			(scheme, netloc, path, query, fragment) = urlsplit(href)
			if fragment and self.__debug:
				print( "Discarding fragment: #", fragment)
			href = urlunsplit( (scheme, netloc, path, query, '') )
			
			# Handle mailto: links by adding them to resources
			# Else, try to spider the link whatever scheme it is
			if scheme == 'mailto':
				self.localResources.emails[href]  += 1
				self.globalResources.emails[href] += 1
			else:
				if self.globalResources.links[href] == 0:
					self.spider(href)
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
				style = urljoin (self.url, text[12:-2])
				self.localResources.styles[style]  += 1
				self.globalResources.styles[style] += 1
	
	def handle_data (self, data):
		self.lastdata = data
	

def main():
	usage = "usage: %prog -u http://www.example.com"
	parser = optparse.OptionParser(usage)
	parser.set_defaults( span_hosts=False, level=5, debug=False)
	parser.add_option("-u", "--url", dest="url", \
                    help="The url to start spidering from.")
	parser.add_option("-d", "--debug", dest="debug", action="store_true", \
                    help="Print debugging information (very verbose).")
	parser.add_option("-l", "--level", dest="level", \
                    help="Specify recursion maximum depth level depth.  The default maximum depth is 5.")
	parser.add_option("-H", "--span-hosts", dest="span_hosts", \
                    help="Enable spanning across hosts when spidering. The default is to limit spidering to one domain.")
	
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
		data = furl.read()
		furl.close()
		
		# Parse the data
		sp = Spider(furl.geturl(), True, options.level, options.debug)
		sp.readUrl()
		#url = "http://localhost:8080/Plone-test/sample-content/sitemap"
		
		# Print output
		print( '###################  DONE SPIDERING  ###################\n')
		print( furl.geturl() )
		sp.verifyGlobalResources()
		sp.printGlobalResources()
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