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
		#static replacements		
		#self.imageReplace = '[COLOR FFFF0000]I[/COLOR][COLOR FFFF8000]M[/COLOR][COLOR FF00FF00]G[/COLOR][COLOR FF0000FF]#[/COLOR][COLOR FFFF00FF]%s[/COLOR]: [I]%s[/I] '
		self.imageReplace = '[COLOR FFFF0000]I[/COLOR][COLOR FFFF8000]M[/COLOR][COLOR FF00FF00]G[/COLOR][COLOR FF0000FF]#[/COLOR][COLOR FFFF00FF]%s[/COLOR]:%s'

#		self.linkReplace = unicode.encode('[CR]\g<text> (%s: [B]\g<url>[/B])' % u'Link','utf8')
		self.linkReplace = '[COLOR FF015602]%s[/COLOR] '
		self.formReplace = '[B]FORM:\g<id>[/B]'
		#static filters
		self.imageFilter = re.compile('<img[^>]+?src="(?P<url>(?:http://)?[^>"]+?)"[^>]*?/>')
		self.linkFilter = re.compile('<a[^>]+?href="(?P<url>[^>"]+?)"[^>]*?(?:title="(?P<title>[^>"]+?)"[^>]*?)?>(?P<text>.*?)</a>')
		self.scriptFilter = re.compile('<script[^>]*?>.*?</script>')
		self.styleFilter = re.compile('<style[^>]*?>.+?</style>')
		self.formFilter = re.compile('<form[^>]*?(?:id="(?P<id>[^>"]+?)"[^>]*?)?>.+?</form>')
		self.lineItemFilter = re.compile('<(li|/li|ul|ol|/ul|/ol)[^>]*?>')
		self.ulFilter = re.compile('<ul[^>]*?>(.+?)</ul>')
		self.olFilter = re.compile('<ol[^>]+?>(.+?)</ol>')
		self.brFilter = re.compile('<br[ /]{0,2}>')
		self.blockQuoteFilter = re.compile('<blockquote>(.+?)</blockquote>',re.S)
		self.colorFilter = re.compile('<font color="([^>"]+?)">(.+?)</font>')
		self.colorFilter2 = re.compile('<span[^>]*?style="[^>"]*?color: ?([^>]+?)"[^>]*?>(.+?)</span>')
		self.tagFilter = re.compile('<[^>]+?>',re.S)
		self.lineFilter = re.compile('[\n\r\t]')
		self.titleFilter = re.compile('<title>(.+?)</title>')
		self.bodyFilter = re.compile('<body[^>]*?>(.+)</body>',re.S)
		
		self.idFilter=re.compile('<[^>]+?id="([^>"]+?)"[^>]*?>',re.S)
		
	def htmlToDisplay(self,html):
		if not html: return 'NO PAGE','NO PAGE'
		html = unicode(html,'utf8','replace')
		try:
			title = self.titleFilter.search(html).group(1)
		except:
			title = ''
		try:
			html = self.bodyFilter.search(html).group(1)
		except:
			print 'ERROR - Could not parse <body> contents'
		html = self.lineFilter.sub('',html)
		#html = self.styleFilter.sub('',html)
		html = self.scriptFilter.sub('',html)
		
		self.imageCount = 0
		self.imageDict = {}
		html = self.linkFilter.sub(self.linkConvert,html)
		html = self.imageFilter.sub(self.imageConvert,html)
		html = self.formFilter.sub(self.formReplace,html)
		
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
		html = html.replace('<b>','[B]').replace('</b>','[/B]')
		html = html.replace('<i>','[I]').replace('</i>','[/I]')
		html = html.replace('<u>','_').replace('</u>','_')
		html = re.sub('<strong[^>]*?>','[B]',html).replace('</strong>','[/B]')
		html = re.sub('<h\d[^>]*?>','[CR][CR][B]',html)
		html = re.sub('</h\d>','[/B][CR][CR]',html)
		html = html.replace('<em>','[I]').replace('</em>','[/I]')
		html = html.replace('<table>','[CR]')
		html = html.replace('</table>','[CR][CR]')
		html = html.replace('</div></div>','[CR]') #to get rid of excessive new lines
		html = html.replace('</div>','[CR]')
		html = html.replace('</tr>','[CR]')
		html = html.replace('</td><td>',self.tdSeperator)
		html = self.tagFilter.sub('',html)
		html = self.removeNested(html,'\[/?B\]','[B]')
		html = self.removeNested(html,'\[/?I\]','[I]')
		html = html.replace('[CR]','\n').strip().replace('\n','[CR]') #TODO Make this unnecessary
		return self.convertHTMLCodes(html),self.convertHTMLCodes(title)
	
	def htmlToDisplayWithIDs(self,html):
		html = self.idFilter.sub(r'\g<0>[[\g<1>]]',html)
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
			self.ordered_count += 1
			if self.ordered: bullet = str(self.ordered_count) + '.'
			else: bullet = self.bullet
			ret =  '%s%s' % ('   ' * self.indent,bullet)
		elif li_type == '/li':
			ret = '\n'
			if self.lastLI == 'ul' or self.lastLI == 'ol' or self.lastLI == '/ul' or self.lastLI == '/ol': ret = ''
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
		return self.imageReplace % (self.getImageNumber(m.group(1)),alt)
		#return self.imageReplace % (self.imageCount,m.group('url'))

	def linkConvert(self,m):
		text = m.group('text')
		if '<img' in text and not re.search('alt="[^"]+?"',text): text += 'LINK'
		elif not text:
			text = text = m.groupdict().get('title','LINK')
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
	
