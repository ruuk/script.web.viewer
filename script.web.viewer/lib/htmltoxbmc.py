import re
import htmlentitydefs

'''
TODO:
Handle Nested Lists
'''
class HTMLConverter:
	def __init__(self):
		self.bullet = unichr(8226)
		self.tdSeperator = ' %s ' % self.bullet
		
		self.formColorA = 'FF010256'
		self.formColorB = 'FF010250'
		self.formColorC = 'FF010257'
		
		self.linkColor = 'FF015602'
		self.imageColor = 'FF0102FE'
		#static replacements		
		#self.imageReplace = '[COLOR FFFF0000]I[/COLOR][COLOR FFFF8000]M[/COLOR][COLOR FF00FF00]G[/COLOR][COLOR FF0000FF]#[/COLOR][COLOR FFFF00FF]%s[/COLOR]: [I]%s[/I] '
		self.imageReplace = '[COLOR FFFF0000]I[/COLOR][COLOR FFFF8000]M[/COLOR][COLOR FF00FF00]G[/COLOR][COLOR '+self.imageColor+']#%s%s [/COLOR]'

#		self.linkReplace = unicode.encode('[CR]\g<text> (%s: [B]\g<url>[/B])' % u'Link','utf8')
		self.linkReplace = '[COLOR '+self.linkColor+']%s[/COLOR] '
		self.formReplace = '[CR][COLOR '+self.formColorA+']______________________________[/COLOR][CR][COLOR '+self.formColorB+'][B]- FORM: %s -[/B][/COLOR][CR]%s[CR][COLOR '+self.formColorC+']______________________________[/COLOR][CR][CR]'
		self.submitReplace = '[\g<value>] '
		#static filters
		self.linkFilter = re.compile('<a[^>]+?href="(?P<url>[^>"]+?)"[^>]*?(?:title="(?P<title>[^>"]+?)"[^>]*?)?>(?P<text>.*?)</a>')
		self.imageFilter = re.compile('<img[^>]+?src="(?P<url>(?:http://)?[^>"]+?)"[^>]*?/>')
		self.scriptFilter = re.compile('<script[^>]*?>.*?</script>',re.S)
		self.styleFilter = re.compile('<style[^>]*?>.+?</style>')
		self.commentFilter = re.compile('<!--.*?-->')
		self.formFilter = re.compile('<form[^>]*?(?:id="(?P<id>[^>"]+?)"[^>]*?)?>(?P<contents>.+?)(?:</form>|<form>|$)')
		self.labelFilter = re.compile('<label[^>]*?(?:(?:for=")|(?:>\s*<input[^>]*?id="))(?P<inputid>[^>"].*?)"[^>]*?>(?P<label>.*?)</label>')
		self.altLabelFilter = re.compile('>(?:(?P<header>[^<>]*?)<(?!input|select)\w+[^>]*?>)?(?P<label>[^<>]+?)(?:<(?!input|select)\w+[^>]*?>)?(?:<input |<select )[^>]*?(?:id|name)="(?P<inputid>[^>"]+?)"')
		self.submitFilter = re.compile('<input type=["\']submit["\'][^>]+?value=["\'](?P<value>[^>"\']+?)["\'][^>]*?>')
		self.lineItemFilter = re.compile('<(li|/li|ul|ol|/ul|/ol)[^>]*?>')
		self.ulFilter = re.compile('<ul[^>]*?>(.+?)</ul>')
		self.olFilter = re.compile('<ol[^>]*?>(.+?)</ol>')
		self.brFilter = re.compile('<br[ /]{0,2}>')
		self.blockQuoteFilter = re.compile('<blockquote>(.+?)</blockquote>',re.S)
		self.colorFilter = re.compile('<font color="([^>"]+?)">(.+?)</font>')
		self.colorFilter2 = re.compile('<span[^>]*?style="[^>"]*?color: ?([^>]+?)"[^>]*?>(.+?)</span>')
		self.tagString = '<[^>]+?>'
		interTagWSString = '(%s)\s*(%s)' % (self.tagString,self.tagString)
		self.tagFilter = re.compile(self.tagString,re.S)
		self.interTagWSFilter = re.compile(interTagWSString)
		self.lineFilter = re.compile('[\n\r\t]')
		self.titleFilter = re.compile('<title>(.+?)</title>')
		self.bodyFilter = re.compile('<body[^>]*?>(.+)</body>',re.S)
		
		self.idFilter = re.compile('<[^>]+?(?:id|name)="([^>"]+?)"[^>]*?>',re.S)
		
	def htmlToDisplay(self,html):
		if not html: return 'NO PAGE','NO PAGE'
		html = unicode(html,'utf8','replace')
		try:
			title = self.titleFilter.search(html).group(1)
		except:
			title = ''
		
		html = self.cleanHTML(html)
		
		self.imageCount = 0
		self.imageDict = {}
		html = self.linkFilter.sub(self.linkConvert,html)
		html = self.imageFilter.sub(self.imageConvert,html)
		html = self.formFilter.sub(self.formConvert,html)
		html = self.submitFilter.sub(self.submitReplace,html)
		
		html = self.processLineItems(html)
		#LIP = LineItemProcessor(self)
		#html = self.ulFilter.sub(LIP.process,html)
		#LIP = LineItemProcessor(self,ordered=True)
		#html = self.olFilter.sub(LIP.process,html)
		
		#html = self.ulFilter.sub(self.processBulletedList,html)
		#html = self.olFilter.sub(self.processOrderedList,html)
		
		html = self.colorFilter.sub(self.convertColor,html)
		html = self.colorFilter2.sub(self.convertColor,html)
		html = self.brFilter.sub('[CR]',html)
		html = self.blockQuoteFilter.sub(self.processIndent,html)
		html = re.sub('<b(?: [^>]*?)?>','[B]',html).replace('</b>','[/B]')
		html = re.sub('<i(\s[^>]*?)?>','[I]',html).replace('</i>','[/I]')
		html = html.replace('<u>','_').replace('</u>','_')
		html = re.sub('<strong[^>]*?>','[B]',html).replace('</strong>','[/B]')
		html = re.sub('<h\d[^>]*?>','[CR][CR][B]',html)
		html = re.sub('</h\d>','[/B][CR][CR]',html)
		html = re.sub('<em(\s[^>]*?)?>','[I]',html).replace('</em>','[/I]')
		html = re.sub('<table[^>]*?>','[CR]',html)
		html = html.replace('</table>','[CR][CR]')
		html = html.replace('</div></div>','[CR]') #to get rid of excessive new lines
		html = html.replace('</div>','[CR]')
		html = html.replace('</p>','[CR][CR]')
		html = html.replace('</tr>','[CR][CR]')
		html = html.replace('</td><td>',self.tdSeperator)
		html = self.tagFilter.sub('',html)
		#print self.tagFilter.findall(html)
		#print 'Test: %s' % len(html.split('[COLOR %s]' % self.linkColor))
		html = self.removeNested(html,'\[/?B\]','[B]')
		html = self.removeNested(html,'\[/?I\]','[I]')
		#html = re.sub('(?:\[CR\]){2,}','[CR][CR]',html) #to get rid of excessive new lines
		html = html.replace('[CR]','\n').strip().replace('\n','[CR]') #TODO Make this unnecessary
		#import codecs
		#codecs.open('/home/ruuk/test.txt','w',encoding='utf-8').write(html)
		return self.convertHTMLCodes(html),self.convertHTMLCodes(title)
	
	def cleanHTML(self,html):
		try:
			html = html.split('</head>')[1]
			#html = self.bodyFilter.search(html).group(1)
		except:
			#print 'ERROR - Could not parse <body> contents'
			print 'ERROR - Could not find </head> tag'
		#html = self.lineFilter.sub(' ',html)
		
		#remove leading and trailing whitespace 
		html = re.sub('\s*([\n\r])\s*',r'\1',html)
		
		#Remove whitespace between tags
		html = self.interTagWSFilter.sub(r'\1\2',html)
		
		#Remove newlines from tags
		html = self.tagFilter.sub(self.cleanTags,html)
		#import codecs
		#codecs.open('/home/ruuk/test.txt','w',encoding='utf-8').write(html)
		
		html = self.lineReduce(html)
		#html = self.styleFilter.sub('',html)
		html = self.scriptFilter.sub('',html)
		html = self.commentFilter.sub('',html)
		return html
		
	def cleanTags(self,m):
		return self.lineFilter.sub('',m.group(0))
	
	def lineReduce(self,data):
		return re.sub('\n+',' ',self.lineFilter.sub('\n',data))
	
	def formConvert(self,m):
		return self.formReplace % (m.group('id'),m.group('contents'))
	
	def htmlToDisplayWithIDs(self,html):
		html = self.idFilter.sub(r'\g<0>[{\g<1>}]',html)
		return self.htmlToDisplay(html)

	def getImageNumber(self,url):
		if url in self.imageDict: return self.imageDict[url]
		self.imageCount += 1
		self.imageDict[url] = self.imageCount
		return self.imageCount
	
	def processLineItems(self,html):
		self.indent = -1
		self.oIndexes = []
		self.ordered_count = 0
		self.lastLI = ''
		return self.lineItemFilter.sub(self.lineItemProcessor,html)
		
	def resetOrdered(self,ordered):
		self.oIndexes.append(self.ordered_count)
		self.ordered = ordered
		self.ordered_count = 0
		
	def lineItemProcessor(self,m):
		li_type = m.group(1)
		ret = ''
		if li_type == 'li':
			if self.lastLI == '/li' or self.lastLI == 'li' or not self.indent: ret = '\n'
			#if self.lastLI == 'ul' or self.lastLI == 'ol' or self.lastLI == '/ul' or self.lastLI == '/ol': ret = ''
			self.ordered_count += 1
			if self.ordered: bullet = str(self.ordered_count) + '.'
			else: bullet = self.bullet
			ret += '%s%s' % ('   ' * self.indent,bullet)
		#elif li_type == '/li':
		#	
		elif li_type == 'ul':
			self.indent += 1
			self.resetOrdered(False)
			ret = '\n'
		elif li_type == 'ol':
			self.indent += 1
			self.resetOrdered(True)
			ret = '\n'
		elif li_type == '/ul':
			self.indent -= 1
			self.ordered_count = self.oIndexes.pop()
		elif li_type == '/ol':
			self.indent -= 1
			self.ordered_count = self.oIndexes.pop()
		self.lastLI = li_type
		return ret
		
	def removeNested(self,html,regex,starttag):
		self.nStart = starttag
		self.nCounter = 0
		return re.sub(regex,self.nestedSub,html)
		
	def nestedSub(self,m):
		tag = m.group(0)
		if tag == self.nStart:
			self.nCounter += 1
			if self.nCounter == 1: return tag
		else:
			self.nCounter -= 1
			if self.nCounter < 0: self.nCounter = 0
			if self.nCounter == 0: return tag
		return ''
		
	def imageConvert(self,m):
		am = re.search('alt="([^"]+?)"',m.group(0))
		alt = am and am.group(1) or ''
		alt = alt and ':' + alt or ''
		return self.imageReplace % (self.getImageNumber(m.group(1)),alt)
		#return self.imageReplace % (self.imageCount,m.group('url'))

	def linkConvert(self,m):
		text = m.group('text')
		if '<img' in text:
			am = re.search('alt="([^"]+?)"',text)
			if am:
				text = am.group(1) or 'LINK'
			else:
				text = self.imageFilter.sub('',text)
				text += 'LINK'
		elif not text:
			text = m.groupdict().get('title','LINK')
		#print 'x%sx' % unicode.encode(text,'ascii','replace')
		return self.linkReplace % text
	
	def processIndent(self,m):
		return '    ' + re.sub('\n','\n    ',m.group(1)) + '\n'
		
	def convertColor(self,m):
		if m.group(1).startswith('#'):
			color = 'FF' + m.group(1)[1:].upper()
		else:
			color = m.group(1).lower()
		return '[COLOR %s]%s[/COLOR]' % (color,m.group(2))

	def processBulletedList(self,m):
		self.resetOrdered(False)
		return self.processList(m.group(1))
		
	def processOrderedList(self,m):
		self.resetOrdered(True)
		return self.processList(m.group(1))
			
	def processList(self,html):
		return re.sub('<li[^>]*?>(.+?)</li>',self.processItem,html) + '\n'

	def processItem(self,m):
		self.ordered_count += 1
		if self.ordered: bullet = str(self.ordered_count) + '.'
		else: bullet = '*'
		return  '%s %s\n' % (bullet,m.group(1))
	
	def cUConvert(self,m): return unichr(int(m.group(1)))
	def cTConvert(self,m):
		return unichr(htmlentitydefs.name2codepoint.get(m.group(1),32))
		
	def convertHTMLCodes(self,html):
		try:
			html = re.sub('&#(\d{1,5});',self.cUConvert,html)
			html = re.sub('&(\w+?);',self.cTConvert,html)
		except:
			pass
		return html
	
