import base64
import bs4
import calendar
import collections
import html
import json
import os
import re
import typing
import time
import urllib.parse

from hydrus.core import HydrusConstants as HC
from hydrus.core import HydrusData
from hydrus.core import HydrusExceptions
from hydrus.core import HydrusGlobals as HG
from hydrus.core import HydrusSerialisable
from hydrus.core import HydrusTags
from hydrus.core import HydrusText

from hydrus.client.networking import ClientNetworkingDomain
from hydrus.client.networking import ClientNetworkingJobs

try:
    
    import html5lib
    
    HTML5LIB_IS_OK = True
    
except ImportError:
    
    HTML5LIB_IS_OK = False
    
try:
    
    import lxml
    
    LXML_IS_OK = True
    
except ImportError:
    
    LXML_IS_OK = False
    
def ConvertParseResultToPrettyString( result ):
    
    ( ( name, content_type, additional_info ), parsed_text ) = result
    
    if content_type == HC.CONTENT_TYPE_URLS:
        
        ( url_type, priority ) = additional_info
        
        if url_type == HC.URL_TYPE_DESIRED:
            
            return 'downloadable/pursuable url (priority ' + str( priority ) + '): ' + parsed_text
            
        elif url_type == HC.URL_TYPE_SOURCE:
            
            return 'associable/source url (priority ' + str( priority ) + '): ' + parsed_text
            
        elif url_type == HC.URL_TYPE_NEXT:
            
            return 'next page url (priority ' + str( priority ) + '): ' + parsed_text
            
        elif url_type == HC.URL_TYPE_SUB_GALLERY:
            
            return 'sub-gallery url (priority ' + str( priority ) + '): ' + parsed_text
            
        
    elif content_type == HC.CONTENT_TYPE_MAPPINGS:
        
        try:
            
            tag = HydrusTags.CleanTag( HydrusTags.CombineTag( additional_info, parsed_text ) )
            
        except:
            
            tag = 'unparsable tag, will likely be discarded'
            
        
        return 'tag: ' + tag
        
    elif content_type == HC.CONTENT_TYPE_HASH:
        
        ( hash_type, hash_encoding ) = additional_info
        
        try:
            
            hash = GetHashFromParsedText( hash_encoding, parsed_text )
            
            parsed_text = hash.hex()
            
        except Exception as e:
            
            parsed_text = 'Could not decode a hash from {}: {}'.format( parsed_text, str( e ) )
            
        
        return '{} hash: {}'.format( hash_type, parsed_text )
        
    elif content_type == HC.CONTENT_TYPE_TIMESTAMP:
        
        timestamp_type = additional_info
        
        try:
            
            timestamp = int( parsed_text )
            
            timestamp_string = HydrusData.ConvertTimestampToPrettyTime( timestamp )
            
        except:
            
            timestamp_string = 'could not convert to integer'
            
        
        if timestamp_type == HC.TIMESTAMP_TYPE_SOURCE:
            
            return 'source time: ' + timestamp_string
            
        
    elif content_type == HC.CONTENT_TYPE_TITLE:
        
        priority = additional_info
        
        return 'watcher page title (priority ' + str( priority ) + '): ' + parsed_text
        
    elif content_type == HC.CONTENT_TYPE_VETO:
        
        return 'veto: ' + name
        
    elif content_type == HC.CONTENT_TYPE_VARIABLE:
        
        temp_variable_name = additional_info
        
        return 'temp variable "' + temp_variable_name + '": ' + parsed_text
        
    
    raise NotImplementedError()
    
def ConvertParsableContentToPrettyString( parsable_content, include_veto = False ):
    
    try:
        
        pretty_strings = []
        
        content_type_to_additional_infos = HydrusData.BuildKeyToSetDict( ( ( ( content_type, name ), additional_infos ) for ( name, content_type, additional_infos ) in parsable_content ) )
        
        data = list( content_type_to_additional_infos.items() )
        
        for ( ( content_type, name ), additional_infos ) in data:
            
            if content_type == HC.CONTENT_TYPE_URLS:
                
                for ( url_type, priority ) in additional_infos:
                    
                    if url_type == HC.URL_TYPE_DESIRED:
                        
                        pretty_strings.append( 'downloadable/pursuable url' )
                        
                    elif url_type == HC.URL_TYPE_SOURCE:
                        
                        pretty_strings.append( 'associable/source url' )
                        
                    elif url_type == HC.URL_TYPE_NEXT:
                        
                        pretty_strings.append( 'gallery next page url' )
                        
                    elif url_type == HC.URL_TYPE_SUB_GALLERY:
                        
                        pretty_strings.append( 'sub-gallery url' )
                        
                    
                
            elif content_type == HC.CONTENT_TYPE_MAPPINGS:
                
                namespaces = [ namespace for namespace in additional_infos if namespace != '' ]
                
                if '' in additional_infos:
                    
                    namespaces.append( 'unnamespaced' )
                    
                
                pretty_strings.append( 'tags: ' + ', '.join( namespaces ) )
                
            elif content_type == HC.CONTENT_TYPE_HASH:
                
                s = 'hash: {}'.format( ', '.join( ( '{} in {}'.format( hash_type, hash_encoding ) for ( hash_type, hash_encoding ) in additional_infos ) ) )
                
                pretty_strings.append( s )
                
            elif content_type == HC.CONTENT_TYPE_TIMESTAMP:
                
                for timestamp_type in additional_infos:
                    
                    if timestamp_type == HC.TIMESTAMP_TYPE_SOURCE:
                        
                        pretty_strings.append( 'source time' )
                        
                    
                
            elif content_type == HC.CONTENT_TYPE_TITLE:
                
                pretty_strings.append( 'watcher page title' )
                
            elif content_type == HC.CONTENT_TYPE_VETO:
                
                if include_veto:
                    
                    pretty_strings.append( 'veto: ' + name )
                    
                
            elif content_type == HC.CONTENT_TYPE_VARIABLE:
                
                pretty_strings.append( 'temp variables: ' + ', '.join( additional_infos ) )
                
            
        
    except:
        
        return 'COULD NOT RENDER--probably a broken object!'
        
    
    pretty_strings.sort()
    
    if len( pretty_strings ) == 0:
        
        return 'nothing'
        
    else:
        
        return ', '.join( pretty_strings )
        
    
def GetChildrenContent( job_key, children, parsing_text, referral_url ):
    
    content = []
    
    for child in children:
        
        try:
            
            if isinstance( child, ParseNodeContentLink ):
                
                child_content = child.Parse( job_key, parsing_text, referral_url )
                
            elif isinstance( child, ContentParser ):
                
                child_content = child.Parse( {}, parsing_text )
                
            
        except HydrusExceptions.VetoException:
            
            return []
            
        
        content.extend( child_content )
        
    
    return content
    
def GetHashFromParsedText( hash_encoding, parsed_text ) -> bytes:
    
    encodings_to_attempt = []
    
    if hash_encoding == 'hex':
        
        encodings_to_attempt = [ 'hex', 'base64' ]
        
    elif hash_encoding == 'base64':
        
        encodings_to_attempt = [ 'base64' ]
        
    
    main_error_text = None
    
    for encoding_to_attempt in encodings_to_attempt:
        
        try:
            
            if encoding_to_attempt == 'hex':
                
                return bytes.fromhex( parsed_text )
                
            elif encoding_to_attempt == 'base64':
                
                return base64.b64decode( parsed_text )
                
            
        except Exception as e:
            
            if main_error_text is None:
                
                main_error_text = str( e )
                
            
            continue
            
        
    
    raise Exception( 'Could not decode hash: {}'.format( main_error_text ) )
    
def GetHashesFromParseResults( results ):
    
    hash_results = []
    
    for ( ( name, content_type, additional_info ), parsed_text ) in results:
        
        if content_type == HC.CONTENT_TYPE_HASH:
            
            ( hash_type, hash_encoding ) = additional_info
            
            try:
                
                hash = GetHashFromParsedText( hash_encoding, parsed_text )
                
            except:
                
                continue
                
            
            hash_results.append( ( hash_type, hash ) )
            
        
    
    return hash_results
    
def GetHTMLTagString( tag ):
    
    try:
        
        all_strings = [ s for s in tag.strings if len( s ) > 0 ]
        
    except:
        
        return ''
        
    
    if len( all_strings ) == 0:
        
        result = ''
        
    else:
        
        result = all_strings[0]
        
    
    return result
    
def GetNamespacesFromParsableContent( parsable_content ):
    
    content_type_to_additional_infos = HydrusData.BuildKeyToSetDict( ( ( content_type, additional_infos ) for ( name, content_type, additional_infos ) in parsable_content ) )
    
    namespaces = content_type_to_additional_infos[ HC.CONTENT_TYPE_MAPPINGS ] # additional_infos is a set of namespaces
    
    return namespaces
    
def GetSoup( html ):
    
    if HTML5LIB_IS_OK:
        
        parser = 'html5lib'
        
    elif LXML_IS_OK:
        
        parser = 'lxml'
        
    else:
        
        message = 'This client does not have access to either lxml or html5lib, and so it cannot parse html. Please install one of these parsing libraries and restart the client.'
        
        raise HydrusExceptions.ParseException( message )
        
    
    return bs4.BeautifulSoup( html, parser )
    
def GetTagsFromParseResults( results ):
    
    tag_results = []
    
    for ( ( name, content_type, additional_info ), parsed_text ) in results:
        
        if content_type == HC.CONTENT_TYPE_MAPPINGS:
            
            tag_results.append( HydrusTags.CombineTag( additional_info, parsed_text ) )
            
        
    
    tag_results = HydrusTags.CleanTags( tag_results )
    
    return tag_results
    
def GetTimestampFromParseResults( results, desired_timestamp_type ):
    
    timestamp_results = []
    
    for ( ( name, content_type, additional_info ), parsed_text ) in results:
        
        if content_type == HC.CONTENT_TYPE_TIMESTAMP:
            
            timestamp_type = additional_info
            
            if timestamp_type == desired_timestamp_type:
                
                try:
                    
                    timestamp = int( parsed_text )
                    
                except:
                    
                    continue
                    
                
                if timestamp_type == HC.TIMESTAMP_TYPE_SOURCE:
                    
                    timestamp = min( HydrusData.GetNow() - 30, timestamp )
                    
                
                timestamp_results.append( timestamp )
                
            
        
    
    if len( timestamp_results ) == 0:
        
        return None
        
    else:
        
        return min( timestamp_results )
        
    
def GetTitleFromAllParseResults( all_parse_results ):
    
    titles = []
    
    for results in all_parse_results:
        
        for ( ( name, content_type, additional_info ), parsed_text ) in results:
            
            if content_type == HC.CONTENT_TYPE_TITLE:
                
                priority = additional_info
                
                titles.append( ( priority, parsed_text ) )
                
            
        
    
    if len( titles ) > 0:
        
        titles.sort( reverse = True ) # highest priority first
        
        ( priority, title ) = titles[0]
        
        return title
        
    else:
        
        return None
        
    
def GetURLsFromParseResults( results, desired_url_types, only_get_top_priority = False ):
    
    url_results = collections.defaultdict( list )
    
    for ( ( name, content_type, additional_info ), parsed_text ) in results:
        
        if content_type == HC.CONTENT_TYPE_URLS:
            
            ( url_type, priority ) = additional_info
            
            if url_type in desired_url_types:
                
                url_results[ priority ].append( parsed_text )
                
            
        
    
    if only_get_top_priority:
        
        # ( priority, url_list ) pairs
        
        url_results = list( url_results.items() )
        
        # ordered by descending priority
        
        url_results.sort( reverse = True )
        
        # url_lists of descending priority
        
        if len( url_results ) > 0:
            
            ( priority, url_list ) = url_results[0]
            
        else:
            
            url_list = []
            
        
    else:
        
        url_list = []
        
        for u_l in list(url_results.values()):
            
            url_list.extend( u_l )
            
        
    
    url_list = HydrusData.DedupeList( url_list )
    
    return url_list
    
def GetVariableFromParseResults( results ):
    
    timestamp_results = []
    
    for ( ( name, content_type, additional_info ), parsed_text ) in results:
        
        if content_type == HC.CONTENT_TYPE_VARIABLE:
            
            variable_name = additional_info
            
            return ( variable_name, parsed_text )
            
        
    
    return None
    
def MakeParsedTextPretty( parsed_text ):
    
    if isinstance( parsed_text, bytes ):
        
        return repr( parsed_text )
        
    
    return parsed_text
    
def ParseResultsHavePursuableURLs( results ):
    
    for ( ( name, content_type, additional_info ), parsed_text ) in results:
        
        if content_type == HC.CONTENT_TYPE_URLS:
            
            ( url_type, priority ) = additional_info
            
            if url_type == HC.URL_TYPE_DESIRED:
                
                return True
                
            
        
    
    return False
    
def RenderJSONParseRule( rule ):
    
    ( parse_rule_type, parse_rule ) = rule
    
    if parse_rule_type == JSON_PARSE_RULE_TYPE_ALL_ITEMS:
        
        s = 'get all items'
        
    elif parse_rule_type == JSON_PARSE_RULE_TYPE_INDEXED_ITEM:
        
        index = parse_rule
        
        s = 'get the ' + HydrusData.ConvertIndexToPrettyOrdinalString( index ) + ' item (for Objects, keys sorted)'
        
    elif parse_rule_type == JSON_PARSE_RULE_TYPE_DICT_KEY:
        
        s = 'get the entries that match "' + parse_rule.ToString() + '"'
        
    
    return s
    
class ParsingTestData( object ):
    
    def __init__( self, parsing_context, texts ):
        
        self.parsing_context = parsing_context
        self.texts = texts
        
    
    def LooksLikeHTML( self ):
        
        return True in ( HydrusText.LooksLikeHTML( text ) for text in self.texts )
        
    
    def LooksLikeJSON( self ):
        
        return True in ( HydrusText.LooksLikeJSON( text ) for text in self.texts )
        
    
class ParseFormula( HydrusSerialisable.SerialisableBase ):
    
    def __init__( self, string_processor = None ):
        
        if string_processor is None:
            
            string_processor = StringProcessor()
            
        
        self._string_processor = string_processor
        
    
    def _GetParsePrettySeparator( self ):
        
        return os.linesep
        
    
    def _ParseRawTexts( self, parsing_context, parsing_text ):
        
        raise NotImplementedError()
        
    
    def GetStringProcessor( self ):
        
        return self._string_processor
        
    
    def Parse( self, parsing_context, parsing_text ):
        
        raw_texts = self._ParseRawTexts( parsing_context, parsing_text )
        
        raw_texts = [ HydrusText.RemoveNewlines( raw_text ) for raw_text in raw_texts ]
        
        texts = self._string_processor.ProcessStrings( raw_texts )
        
        return texts
        
    
    def ParsePretty( self, parsing_context, parsing_text ):
        
        texts = self.Parse( parsing_context, parsing_text )
        
        pretty_texts = [ MakeParsedTextPretty( text ) for text in texts ]
        
        pretty_texts = [ '*** ' + HydrusData.ToHumanInt( len( pretty_texts ) ) + ' RESULTS BEGIN ***' ] + pretty_texts + [ '*** RESULTS END ***' ]
        
        separator = self._GetParsePrettySeparator()
        
        result = separator.join( pretty_texts )
        
        return result
        
    
    def ParsesSeparatedContent( self ):
        
        return False
        
    
    def SetStringProcessor( self, string_processor: "StringProcessor" ):
        
        self._string_processor = string_processor
        
    
    def ToPrettyString( self ):
        
        raise NotImplementedError()
        
    
    def ToPrettyMultilineString( self ):
        
        raise NotImplementedError()
        
    
class ParseFormulaCompound( ParseFormula ):
    
    SERIALISABLE_TYPE = HydrusSerialisable.SERIALISABLE_TYPE_PARSE_FORMULA_COMPOUND
    SERIALISABLE_NAME = 'Compound Parsing Formula'
    SERIALISABLE_VERSION = 2
    
    def __init__( self, formulae = None, sub_phrase = None, string_processor = None ):
        
        ParseFormula.__init__( self, string_processor )
        
        if formulae is None:
            
            formulae = HydrusSerialisable.SerialisableList()
            
            formulae.append( ParseFormulaHTML() )
            
        
        if sub_phrase is None:
            
            sub_phrase = '\\1'
            
        
        self._formulae = formulae
        
        self._sub_phrase = sub_phrase
        
    
    def _GetSerialisableInfo( self ):
        
        serialisable_formulae = HydrusSerialisable.SerialisableList( self._formulae ).GetSerialisableTuple()
        serialisable_string_processor = self._string_processor.GetSerialisableTuple()
        
        return ( serialisable_formulae, self._sub_phrase, serialisable_string_processor )
        
    
    def _InitialiseFromSerialisableInfo( self, serialisable_info ):
        
        ( serialisable_formulae, self._sub_phrase, serialisable_string_processor ) = serialisable_info
        
        self._formulae = HydrusSerialisable.CreateFromSerialisableTuple( serialisable_formulae )
        self._string_processor = HydrusSerialisable.CreateFromSerialisableTuple( serialisable_string_processor )
        
    
    def _ParseRawTexts( self, parsing_context, parsing_text ):
        
        def get_stream_string( index, s ):
            
            if len( s ) == 0:
                
                return ''
                
            elif index >= len( s ):
                
                return s[-1]
                
            else:
                
                return s[ index ]
                
            
        
        streams = []
        
        for formula in self._formulae:
            
            stream = formula.Parse( parsing_context, parsing_text )
            
            if len( stream ) == 0: # no contents were found for one of the /1 replace components, so no valid strings can be made.
                
                return []
                
            
            streams.append( stream )
            
        
        # let's make a text result for every item in the longest list of subtexts
        num_raw_texts_to_make = max( ( len( stream ) for stream in streams ) )
        
        raw_texts = []
        
        for stream_index in range( num_raw_texts_to_make ):
            
            raw_text = self._sub_phrase
            
            for ( stream_num, stream ) in enumerate( streams, 1 ): # starts counting from 1
                
                sub_component = '\\' + str( stream_num )
                
                replace_string = get_stream_string( stream_index, stream )
                
                raw_text = raw_text.replace( sub_component, replace_string )
                
            
            raw_texts.append( raw_text )
            
        
        return raw_texts
        
    
    def _UpdateSerialisableInfo( self, version, old_serialisable_info ):
        
        if version == 1:
            
            ( serialisable_formulae, sub_phrase, serialisable_string_match, serialisable_string_converter ) = old_serialisable_info
            
            string_match = HydrusSerialisable.CreateFromSerialisableTuple( serialisable_string_match )
            string_converter = HydrusSerialisable.CreateFromSerialisableTuple( serialisable_string_converter )
            
            processing_steps = [ processing_step for processing_step in ( string_match, string_converter ) if processing_step.MakesChanges() ]
            
            string_processor = StringProcessor()
            
            string_processor.SetProcessingSteps( processing_steps )
            
            serialisable_string_processor = string_processor.GetSerialisableTuple()
            
            new_serialisable_info = ( serialisable_formulae, sub_phrase, serialisable_string_processor )
            
            return ( 2, new_serialisable_info )
            
        
    
    def GetFormulae( self ):
        
        return self._formulae
        
    
    def GetSubstitutionPhrase( self ):
        
        return self._sub_phrase
        
    
    def ToPrettyString( self ):
        
        return 'COMPOUND with ' + HydrusData.ToHumanInt( len( self._formulae ) ) + ' formulae.'
        
    
    def ToPrettyMultilineString( self ):
        
        s = []
        
        for formula in self._formulae:
            
            s.append( formula.ToPrettyMultilineString() )
            
        
        s.append( 'and substitute into ' + self._sub_phrase )
        
        separator = os.linesep * 2
        
        text = '--COMPOUND--' + os.linesep * 2 + separator.join( s )
        
        return text
        
    
HydrusSerialisable.SERIALISABLE_TYPES_TO_OBJECT_TYPES[ HydrusSerialisable.SERIALISABLE_TYPE_PARSE_FORMULA_COMPOUND ] = ParseFormulaCompound

class ParseFormulaContextVariable( ParseFormula ):
    
    SERIALISABLE_TYPE = HydrusSerialisable.SERIALISABLE_TYPE_PARSE_FORMULA_CONTEXT_VARIABLE
    SERIALISABLE_NAME = 'Context Variable Formula'
    SERIALISABLE_VERSION = 2
    
    def __init__( self, variable_name = None, string_processor = None ):
        
        ParseFormula.__init__( self, string_processor )
        
        if variable_name is None:
            
            variable_name = 'url'
            
        
        self._variable_name = variable_name
        
    
    def _GetSerialisableInfo( self ):
        
        serialisable_string_processor = self._string_processor.GetSerialisableTuple()
        
        return ( self._variable_name, serialisable_string_processor )
        
    
    def _InitialiseFromSerialisableInfo( self, serialisable_info ):
        
        ( self._variable_name, serialisable_string_processor ) = serialisable_info
        
        self._string_processor = HydrusSerialisable.CreateFromSerialisableTuple( serialisable_string_processor )
        
    
    def _ParseRawTexts( self, parsing_context, parsing_text ):
        
        raw_texts = []
        
        if self._variable_name in parsing_context:
            
            raw_texts.append( str( parsing_context[ self._variable_name ] ) )
            
        
        return raw_texts
        
    
    def _UpdateSerialisableInfo( self, version, old_serialisable_info ):
        
        if version == 1:
            
            ( variable_name, serialisable_string_match, serialisable_string_converter ) = old_serialisable_info
            
            string_match = HydrusSerialisable.CreateFromSerialisableTuple( serialisable_string_match )
            string_converter = HydrusSerialisable.CreateFromSerialisableTuple( serialisable_string_converter )
            
            processing_steps = [ processing_step for processing_step in ( string_match, string_converter ) if processing_step.MakesChanges() ]
            
            string_processor = StringProcessor()
            
            string_processor.SetProcessingSteps( processing_steps )
            
            serialisable_string_processor = string_processor.GetSerialisableTuple()
            
            new_serialisable_info = ( variable_name, serialisable_string_processor )
            
            return ( 2, new_serialisable_info )
            
        
    
    def GetVariableName( self ):
        
        return self._variable_name
        
    
    def ToPrettyString( self ):
        
        return 'CONTEXT VARIABLE: ' + self._variable_name
        
    
    def ToPrettyMultilineString( self ):
        
        s = []
        
        s.append( 'fetch the "' + self._variable_name + '" variable from the parsing context' )
        
        separator = os.linesep * 2
        
        text = '--CONTEXT VARIABLE--' + os.linesep * 2 + separator.join( s )
        
        return text
        
    
HydrusSerialisable.SERIALISABLE_TYPES_TO_OBJECT_TYPES[ HydrusSerialisable.SERIALISABLE_TYPE_PARSE_FORMULA_CONTEXT_VARIABLE ] = ParseFormulaContextVariable

HTML_CONTENT_ATTRIBUTE = 0
HTML_CONTENT_STRING = 1
HTML_CONTENT_HTML = 2

class ParseFormulaHTML( ParseFormula ):
    
    SERIALISABLE_TYPE = HydrusSerialisable.SERIALISABLE_TYPE_PARSE_FORMULA_HTML
    SERIALISABLE_NAME = 'HTML Parsing Formula'
    SERIALISABLE_VERSION = 7
    
    def __init__( self, tag_rules = None, content_to_fetch = None, attribute_to_fetch = None, string_processor = None ):
        
        ParseFormula.__init__( self, string_processor )
        
        if tag_rules is None:
            
            tag_rules = HydrusSerialisable.SerialisableList()
            
            tag_rules.append( ParseRuleHTML() )
            
        
        if content_to_fetch is None:
            
            content_to_fetch = HTML_CONTENT_ATTRIBUTE
            
        
        if attribute_to_fetch is None:
            
            attribute_to_fetch = 'href'
            
        
        self._tag_rules = HydrusSerialisable.SerialisableList( tag_rules )
        
        self._content_to_fetch = content_to_fetch
        
        self._attribute_to_fetch = attribute_to_fetch
        
    
    def _FindHTMLTags( self, root ):
        
        tags = ( root, )
        
        for tag_rule in self._tag_rules:
            
            tags = list( tag_rule.GetNodes( tags ) )
            
        
        return tags
        
    
    def _GetParsePrettySeparator( self ):
        
        if self._content_to_fetch == HTML_CONTENT_HTML:
            
            return os.linesep * 2
            
        else:
            
            return os.linesep
            
        
    
    def _GetRawTextFromTag( self, tag ):
        
        if tag is None:
            
            result = None
            
        elif self._content_to_fetch == HTML_CONTENT_ATTRIBUTE:
            
            if tag.has_attr( self._attribute_to_fetch ):
                
                unknown_attr_result = tag[ self._attribute_to_fetch ]
                
                # 'class' attr returns a list because it has multiple values under html spec, wew
                if isinstance( unknown_attr_result, list ):
                    
                    if len( unknown_attr_result ) == 0:
                        
                        raise HydrusExceptions.ParseException( 'Attribute ' + self._attribute_to_fetch + ' not found!' )
                        
                    else:
                        
                        result = ' '.join( unknown_attr_result )
                        
                    
                else:
                    
                    result = unknown_attr_result
                    
                
            else:
                
                raise HydrusExceptions.ParseException( 'Attribute ' + self._attribute_to_fetch + ' not found!' )
                
            
        elif self._content_to_fetch == HTML_CONTENT_STRING:
            
            result = GetHTMLTagString( tag )
            
        elif self._content_to_fetch == HTML_CONTENT_HTML:
            
            result = str( tag )
            
        
        if result is None or result == '':
            
            raise HydrusExceptions.ParseException( 'Empty/No results found!' )
            
        
        return result
        
    
    def _GetRawTextsFromTags( self, tags ):
        
        raw_texts = []
        
        for tag in tags:
            
            try:
                
                raw_text = self._GetRawTextFromTag( tag )
                
                raw_texts.append( raw_text )
                
            except HydrusExceptions.ParseException:
                
                continue
                
            
        
        return raw_texts
        
    
    def _GetSerialisableInfo( self ):
        
        serialisable_tag_rules = self._tag_rules.GetSerialisableTuple()
        
        serialisable_string_processor = self._string_processor.GetSerialisableTuple()
        
        return ( serialisable_tag_rules, self._content_to_fetch, self._attribute_to_fetch, serialisable_string_processor )
        
    
    def _InitialiseFromSerialisableInfo( self, serialisable_info ):
        
        ( serialisable_tag_rules, self._content_to_fetch, self._attribute_to_fetch, serialisable_string_processor ) = serialisable_info
        
        self._tag_rules = HydrusSerialisable.CreateFromSerialisableTuple( serialisable_tag_rules )
        
        self._string_processor = HydrusSerialisable.CreateFromSerialisableTuple( serialisable_string_processor )
        
    
    def _ParseRawTexts( self, parsing_context, parsing_text ):
        
        try:
            
            root = HG.client_controller.parsing_cache.GetSoup( parsing_text )
            
        except Exception as e:
            
            raise HydrusExceptions.ParseException( 'Unable to parse that HTML: {}. HTML Sample: {}'.format( str( e ), parsing_text[:1024] ) )
            
        
        tags = self._FindHTMLTags( root )
        
        raw_texts = self._GetRawTextsFromTags( tags )
        
        return raw_texts
        
    
    def _UpdateSerialisableInfo( self, version, old_serialisable_info ):
        
        if version == 1:
            
            ( tag_rules, attribute_to_fetch ) = old_serialisable_info
            
            culling_and_adding = ( 0, 0, '', '' )
            
            new_serialisable_info = ( tag_rules, attribute_to_fetch, culling_and_adding )
            
            return ( 2, new_serialisable_info )
            
        
        if version == 2:
            
            ( tag_rules, attribute_to_fetch, culling_and_adding ) = old_serialisable_info
            
            ( cull_front, cull_back, prepend, append ) = culling_and_adding
            
            conversions = []
            
            if cull_front > 0:
                
                conversions.append( ( STRING_CONVERSION_CLIP_TEXT_FROM_BEGINNING, cull_front ) )
                
            elif cull_front < 0:
                
                conversions.append( ( STRING_CONVERSION_REMOVE_TEXT_FROM_END, cull_front ) )
                
            
            if cull_back > 0:
                
                conversions.append( ( STRING_CONVERSION_CLIP_TEXT_FROM_END, cull_back ) )
                
            elif cull_back < 0:
                
                conversions.append( ( STRING_CONVERSION_REMOVE_TEXT_FROM_BEGINNING, cull_back ) )
                
            
            if prepend != '':
                
                conversions.append( ( STRING_CONVERSION_PREPEND_TEXT, prepend ) )
                
            
            if append != '':
                
                conversions.append( ( STRING_CONVERSION_APPEND_TEXT, append ) )
                
            
            string_converter = StringConverter( conversions, 'parsed information' )
            
            serialisable_string_converter = string_converter.GetSerialisableTuple()
            
            new_serialisable_info = ( tag_rules, attribute_to_fetch, serialisable_string_converter )
            
            return ( 3, new_serialisable_info )
            
        
        if version == 3:
            
            ( tag_rules, attribute_to_fetch, serialisable_string_converter ) = old_serialisable_info
            
            string_match = StringMatch()
            
            serialisable_string_match = string_match.GetSerialisableTuple()
            
            new_serialisable_info = ( tag_rules, attribute_to_fetch, serialisable_string_match, serialisable_string_converter )
            
            return ( 4, new_serialisable_info )
            
        
        if version == 4:
            
            ( tag_rules, attribute_to_fetch, serialisable_string_match, serialisable_string_converter ) = old_serialisable_info
            
            if attribute_to_fetch is None:
                
                content_to_fetch = HTML_CONTENT_STRING
                attribute_to_fetch = ''
                
            else:
                
                content_to_fetch = HTML_CONTENT_ATTRIBUTE
                
            
            new_serialisable_info = ( tag_rules, content_to_fetch, attribute_to_fetch, serialisable_string_match, serialisable_string_converter )
            
            return ( 5, new_serialisable_info )
            
        
        if version == 5:
            
            ( tag_rules, content_to_fetch, attribute_to_fetch, serialisable_string_match, serialisable_string_converter ) = old_serialisable_info
            
            new_tag_rules = HydrusSerialisable.SerialisableList()
            
            for ( name, attrs, index ) in tag_rules:
                
                tag_rule = ParseRuleHTML( rule_type = HTML_RULE_TYPE_DESCENDING, tag_name = name, tag_attributes = attrs, tag_index = index )
                
                new_tag_rules.append( tag_rule )
                
            
            serialisable_new_tag_rules = new_tag_rules.GetSerialisableTuple()
            
            new_serialisable_info = ( serialisable_new_tag_rules, content_to_fetch, attribute_to_fetch, serialisable_string_match, serialisable_string_converter )
            
            return ( 6, new_serialisable_info )
            
        
        if version == 6:
            
            ( serialisable_new_tag_rules, content_to_fetch, attribute_to_fetch, serialisable_string_match, serialisable_string_converter ) = old_serialisable_info
            
            string_match = HydrusSerialisable.CreateFromSerialisableTuple( serialisable_string_match )
            string_converter = HydrusSerialisable.CreateFromSerialisableTuple( serialisable_string_converter )
            
            processing_steps = [ processing_step for processing_step in ( string_match, string_converter ) if processing_step.MakesChanges() ]
            
            string_processor = StringProcessor()
            
            string_processor.SetProcessingSteps( processing_steps )
            
            serialisable_string_processor = string_processor.GetSerialisableTuple()
            
            new_serialisable_info = ( serialisable_new_tag_rules, content_to_fetch, attribute_to_fetch, serialisable_string_processor )
            
            return ( 7, new_serialisable_info )
            
        
    
    def GetAttributeToFetch( self ):
        
        return self._attribute_to_fetch
        
    
    def GetContentToFetch( self ):
        
        return self._content_to_fetch
        
    
    def GetTagRules( self ):
        
        return self._tag_rules
        
    
    def ParsesSeparatedContent( self ):
        
        return self._content_to_fetch == HTML_CONTENT_HTML
        
    
    def ToPrettyString( self ):
        
        return 'HTML with ' + HydrusData.ToHumanInt( len( self._tag_rules ) ) + ' tag rules.'
        
    
    def ToPrettyMultilineString( self ):
        
        pretty_strings = [ t_r.ToString() for t_r in self._tag_rules ]
        
        if self._content_to_fetch == HTML_CONTENT_ATTRIBUTE:
            
            pretty_strings.append( 'get the ' + self._attribute_to_fetch + ' attribute of those tags' )
            
        elif self._content_to_fetch == HTML_CONTENT_STRING:
            
            pretty_strings.append( 'get the text content of those tags' )
            
        elif self._content_to_fetch == HTML_CONTENT_HTML:
            
            pretty_strings.append( 'get the html of those tags' )
            
        
        pretty_strings.extend( self._string_processor.GetProcessingStrings() )
        
        separator = os.linesep + 'and then '
        
        pretty_multiline_string = '--HTML--' + os.linesep + separator.join( pretty_strings )
        
        return pretty_multiline_string
        
    
HydrusSerialisable.SERIALISABLE_TYPES_TO_OBJECT_TYPES[ HydrusSerialisable.SERIALISABLE_TYPE_PARSE_FORMULA_HTML ] = ParseFormulaHTML

HTML_RULE_TYPE_DESCENDING = 0
HTML_RULE_TYPE_ASCENDING = 1

class ParseRuleHTML( HydrusSerialisable.SerialisableBase ):
    
    SERIALISABLE_TYPE = HydrusSerialisable.SERIALISABLE_TYPE_PARSE_RULE_HTML
    SERIALISABLE_NAME = 'HTML Parsing Rule'
    SERIALISABLE_VERSION = 2
    
    def __init__( self, rule_type = None, tag_name = None, tag_attributes = None, tag_index = None, tag_depth = None, should_test_tag_string = False, tag_string_string_match = None ):
        
        HydrusSerialisable.SerialisableBase.__init__( self )
        
        if rule_type is None:
            
            rule_type = HTML_RULE_TYPE_DESCENDING
            
            if tag_name is None:
                
                tag_name = 'a'
                
            
        
        if rule_type == HTML_RULE_TYPE_DESCENDING:
            
            if tag_attributes is None:
                
                tag_attributes = {}
                
            
        elif rule_type == HTML_RULE_TYPE_ASCENDING:
            
            if tag_depth is None:
                
                tag_depth = 1
                
            
        
        if tag_string_string_match is None:
            
            tag_string_string_match = StringMatch()
            
        
        self._rule_type = rule_type
        self._tag_name = tag_name
        self._tag_attributes = tag_attributes
        self._tag_index = tag_index
        self._tag_depth = tag_depth
        self._should_test_tag_string = should_test_tag_string
        self._tag_string_string_match = tag_string_string_match
        
        
    
    def _GetSerialisableInfo( self ):
        
        serialisable_tag_string_string_match = self._tag_string_string_match.GetSerialisableTuple()
        
        return ( self._rule_type, self._tag_name, self._tag_attributes, self._tag_index, self._tag_depth, self._should_test_tag_string, serialisable_tag_string_string_match )
        
    
    def _InitialiseFromSerialisableInfo( self, serialisable_info ):
        
        ( self._rule_type, self._tag_name, self._tag_attributes, self._tag_index, self._tag_depth, self._should_test_tag_string, serialisable_tag_string_string_match ) = serialisable_info
        
        self._tag_string_string_match = HydrusSerialisable.CreateFromSerialisableTuple( serialisable_tag_string_string_match )
        
    
    def _UpdateSerialisableInfo( self, version, old_serialisable_info ):
        
        if version == 1:
            
            ( rule_type, tag_name, tag_attributes, tag_index, tag_depth ) = old_serialisable_info
            
            should_test_tag_string = False
            
            tag_string_string_match = StringMatch()
            
            serialisable_tag_string_string_match = tag_string_string_match.GetSerialisableTuple()
            
            new_serialisable_info = ( rule_type, tag_name, tag_attributes, tag_index, tag_depth, should_test_tag_string, serialisable_tag_string_string_match )
            
            return ( 2, new_serialisable_info )
            
        
    
    def GetNodes( self, nodes ):
        
        new_nodes = []
        
        for node in nodes:
            
            if self._rule_type == HTML_RULE_TYPE_DESCENDING:
                
                # having class : [ 'a', 'b' ] works here, but it does OR not AND
                # instead do node.find_all( lambda tag: 'class' in tag.attrs and 'a' in tag[ 'class' ] and 'b' in tag[ 'class' ] )
                # which means we want to just roll all this into one method to support multiple class matching
                
                kwargs = { 'attrs' : self._tag_attributes }
                
                if self._tag_name is not None:
                    
                    kwargs[ 'name' ] = self._tag_name
                    
                
                found_nodes = node.find_all( **kwargs )
                
                if self._tag_index is not None:
                    
                    try:
                        
                        indexed_node = found_nodes[ self._tag_index ]
                        
                    except IndexError:
                        
                        continue
                        
                    
                    found_nodes = [ indexed_node ]
                    
                
            elif self._rule_type == HTML_RULE_TYPE_ASCENDING:
                
                found_nodes = []
                
                still_in_tree = lambda node: isinstance( node, bs4.element.Tag ) # if we go one above html, we get the BS document itself
                
                num_found = 0
                
                potential_parent = node.parent
                
                while still_in_tree( potential_parent ):
                    
                    if self._tag_name is None:
                        
                        num_found += 1
                        
                    else:
                        
                        if potential_parent.name == self._tag_name:
                            
                            num_found += 1
                            
                        
                    
                    if num_found == self._tag_depth:
                        
                        found_nodes = [ potential_parent ]
                        
                        break
                        
                    
                    potential_parent = potential_parent.parent
                    
                
            
            new_nodes.extend( found_nodes )
            
        
        if self._should_test_tag_string:
            
            potential_nodes = new_nodes
            
            new_nodes = []
            
            for node in potential_nodes:
                
                s = GetHTMLTagString( node )
                
                if self._tag_string_string_match.Matches( s ):
                    
                    new_nodes.append( node )
                    
                
            
        
        return new_nodes
        
    
    def ToString( self ):
        
        if self._rule_type == HTML_RULE_TYPE_DESCENDING:
            
            s = 'search descendants for'
            
            if self._tag_index is None:
                
                s += ' every'
                
            else:
                
                s += ' the ' + HydrusData.ConvertIndexToPrettyOrdinalString( self._tag_index )
                
            
            if self._tag_name is not None:
                
                s += ' <' + self._tag_name + '>'
                
            
            s += ' tag'
            
            if len( self._tag_attributes ) > 0:
                
                s += ' with attributes ' + ', '.join( key + '=' + value for ( key, value ) in list(self._tag_attributes.items()) )
                
            
        elif self._rule_type == HTML_RULE_TYPE_ASCENDING:
            
            s = 'walk back up ancestors'
            
            if self._tag_name is None:
                
                s += ' ' + HydrusData.ToHumanInt( self._tag_depth ) + ' tag levels'
                
            else:
                
                s += ' to the ' + HydrusData.ConvertIntToPrettyOrdinalString( self._tag_depth ) + ' <' + self._tag_name + '> tag'
                
            
        
        if self._should_test_tag_string:
            
            s += ' with strings that match ' + self._tag_string_string_match.ToString()
            
        
        return s
        
    
    def ToTuple( self ):
        
        return ( self._rule_type, self._tag_name, self._tag_attributes, self._tag_index, self._tag_depth, self._should_test_tag_string, self._tag_string_string_match )
        
    
HydrusSerialisable.SERIALISABLE_TYPES_TO_OBJECT_TYPES[ HydrusSerialisable.SERIALISABLE_TYPE_PARSE_RULE_HTML ] = ParseRuleHTML

JSON_CONTENT_STRING = 0
JSON_CONTENT_JSON = 1
JSON_CONTENT_DICT_KEYS = 2

JSON_PARSE_RULE_TYPE_DICT_KEY = 0
JSON_PARSE_RULE_TYPE_ALL_ITEMS = 1
JSON_PARSE_RULE_TYPE_INDEXED_ITEM = 2

class ParseFormulaJSON( ParseFormula ):
    
    SERIALISABLE_TYPE = HydrusSerialisable.SERIALISABLE_TYPE_PARSE_FORMULA_JSON
    SERIALISABLE_NAME = 'JSON Parsing Formula'
    SERIALISABLE_VERSION = 3
    
    def __init__( self, parse_rules = None, content_to_fetch = None, string_processor = None ):
        
        ParseFormula.__init__( self, string_processor )
        
        if parse_rules is None:
            
            parse_rules = [ ( JSON_PARSE_RULE_TYPE_DICT_KEY, StringMatch( match_type = STRING_MATCH_FIXED, match_value = 'posts', example_string = 'posts' ) ) ]
            
        
        if content_to_fetch is None:
            
            content_to_fetch = JSON_CONTENT_STRING
            
        
        self._parse_rules = parse_rules
        
        self._content_to_fetch = content_to_fetch
        
    
    def _GetParsePrettySeparator( self ):
        
        if self._content_to_fetch == JSON_CONTENT_JSON:
            
            return os.linesep * 2
            
        else:
            
            return os.linesep
            
        
    
    def _GetRawTextsFromJSON( self, j ):
        
        roots = ( j, )
        
        for ( parse_rule_type, parse_rule ) in self._parse_rules:
            
            next_roots = []
            
            for root in roots:
                
                if parse_rule_type == JSON_PARSE_RULE_TYPE_ALL_ITEMS:
                    
                    if isinstance( root, list ):
                        
                        next_roots.extend( root )
                        
                    elif isinstance( root, dict ):
                        
                        pairs = sorted( root.items() )
                        
                        for ( key, value ) in pairs:
                            
                            next_roots.append( value )
                            
                        
                    else:
                        
                        continue
                        
                    
                elif parse_rule_type == JSON_PARSE_RULE_TYPE_INDEXED_ITEM:
                    
                    index = parse_rule
                    
                    if isinstance( root, ( list, dict ) ):
                        
                        if isinstance( root, list ):
                            
                            list_to_index = root
                            
                        elif isinstance( root, dict ):
                            
                            list_to_index = list( root.keys() )
                            
                            HydrusData.HumanTextSort( list_to_index )
                            
                        
                        try:
                            
                            indexed_item = list_to_index[ index ]
                            
                        except IndexError:
                            
                            continue
                            
                        
                        if isinstance( root, list ):
                            
                            next_roots.append( indexed_item )
                            
                        elif isinstance( root, dict ):
                            
                            next_roots.append( root[ indexed_item ] )
                            
                        
                    else:
                        
                        continue
                        
                    
                elif parse_rule_type == JSON_PARSE_RULE_TYPE_DICT_KEY:
                    
                    if not isinstance( root, dict ):
                        
                        continue
                        
                    
                    string_match = parse_rule
                    
                    pairs = sorted( root.items() )
                    
                    for ( key, value ) in pairs:
                        
                        if string_match.Matches( key ):
                            
                            next_roots.append( value )
                            
                        
                    
                
            
            roots = next_roots
            
        
        raw_texts = []
        
        for root in roots:
            
            if self._content_to_fetch == JSON_CONTENT_STRING:
                
                if isinstance( root, ( list, dict ) ):
                    
                    continue
                    
                
                if root is not None:
                    
                    raw_text = str( root )
                    
                    raw_texts.append( raw_text )
                    
                
            elif self._content_to_fetch == JSON_CONTENT_JSON:
                
                raw_text = json.dumps( root, ensure_ascii = False )
                
                raw_texts.append( raw_text )
                
            elif self._content_to_fetch == JSON_CONTENT_DICT_KEYS:
                
                if isinstance( root, dict ):
                    
                    pairs = sorted( root.items() )
                    
                    for ( key, value ) in pairs:
                        
                        raw_text = str( key )
                        
                        raw_texts.append( raw_text )
                        
                    
                
            
        
        return raw_texts
        
    
    def _GetSerialisableInfo( self ):
        
        serialisable_parse_rules = [ ( parse_rule_type, parse_rule.GetSerialisableTuple() ) if parse_rule_type == JSON_PARSE_RULE_TYPE_DICT_KEY else ( parse_rule_type, parse_rule ) for ( parse_rule_type, parse_rule ) in self._parse_rules ]
        serialisable_string_processor = self._string_processor.GetSerialisableTuple()
        
        return ( serialisable_parse_rules, self._content_to_fetch, serialisable_string_processor )
        
    
    def _InitialiseFromSerialisableInfo( self, serialisable_info ):
        
        ( serialisable_parse_rules, self._content_to_fetch, serialisable_string_processor ) = serialisable_info
        
        self._parse_rules = [ ( parse_rule_type, HydrusSerialisable.CreateFromSerialisableTuple( serialisable_parse_rule ) ) if parse_rule_type == JSON_PARSE_RULE_TYPE_DICT_KEY else ( parse_rule_type, serialisable_parse_rule ) for ( parse_rule_type, serialisable_parse_rule ) in serialisable_parse_rules ]
        self._string_processor = HydrusSerialisable.CreateFromSerialisableTuple( serialisable_string_processor )
        
    
    def _ParseRawTexts( self, parsing_context, parsing_text ):
        
        try:
            
            j = HG.client_controller.parsing_cache.GetJSON( parsing_text )
            
        except Exception as e:
            
            message = 'Unable to parse that JSON: {}. JSON sample: {}'.format( str( e ), parsing_text[:1024] )
            
            raise HydrusExceptions.ParseException( message )
            
        
        raw_texts = self._GetRawTextsFromJSON( j )
        
        return raw_texts
        
    
    def _UpdateSerialisableInfo( self, version, old_serialisable_info ):
        
        if version == 1:
            
            ( parse_rules, content_to_fetch, serialisable_string_match, serialisable_string_converter ) = old_serialisable_info
            
            new_parse_rules = []
            
            for parse_rule in parse_rules:
                
                if parse_rule is None:
                    
                    new_parse_rules.append( ( JSON_PARSE_RULE_TYPE_ALL_ITEMS, None ) )
                    
                elif isinstance( parse_rule, int ):
                    
                    new_parse_rules.append( ( JSON_PARSE_RULE_TYPE_INDEXED_ITEM, parse_rule ) )
                    
                else:
                    
                    sm = StringMatch( match_type = STRING_MATCH_FIXED, match_value = parse_rule, example_string = parse_rule )
                    
                    new_parse_rules.append( ( JSON_PARSE_RULE_TYPE_DICT_KEY, sm ) )
                    
                
            
            serialisable_parse_rules = [ ( parse_rule_type, parse_rule.GetSerialisableTuple() ) if parse_rule_type == JSON_PARSE_RULE_TYPE_DICT_KEY else ( parse_rule_type, parse_rule ) for ( parse_rule_type, parse_rule ) in new_parse_rules ]
            
            new_serialisable_info = ( serialisable_parse_rules, content_to_fetch, serialisable_string_match, serialisable_string_converter )
            
            return ( 2, new_serialisable_info )
            
        
        if version == 2:
            
            ( serialisable_parse_rules, content_to_fetch, serialisable_string_match, serialisable_string_converter ) = old_serialisable_info
            
            string_match = HydrusSerialisable.CreateFromSerialisableTuple( serialisable_string_match )
            string_converter = HydrusSerialisable.CreateFromSerialisableTuple( serialisable_string_converter )
            
            processing_steps = [ processing_step for processing_step in ( string_match, string_converter ) if processing_step.MakesChanges() ]
            
            string_processor = StringProcessor()
            
            string_processor.SetProcessingSteps( processing_steps )
            
            serialisable_string_processor = string_processor.GetSerialisableTuple()
            
            new_serialisable_info = ( serialisable_parse_rules, content_to_fetch, serialisable_string_processor )
            
            return ( 3, new_serialisable_info )
            
        
    
    def GetContentToFetch( self ):
        
        return self._content_to_fetch
        
    
    def GetParseRules( self ):
        
        return self._parse_rules
        
    
    def ParsesSeparatedContent( self ):
        
        return self._content_to_fetch == JSON_CONTENT_JSON
        
    
    def ToPrettyString( self ):
        
        return 'JSON with ' + HydrusData.ToHumanInt( len( self._parse_rules ) ) + ' parse rules.'
        
    
    def ToPrettyMultilineString( self ):
        
        pretty_strings = [ RenderJSONParseRule( p_r ) for p_r in self._parse_rules ]
        
        if self._content_to_fetch == JSON_CONTENT_STRING:
            
            pretty_strings.append( 'get final data content, converting to strings as needed' )
            
        elif self._content_to_fetch == JSON_CONTENT_JSON:
            
            pretty_strings.append( 'get the json beneath' )
            
        elif self._content_to_fetch == JSON_CONTENT_DICT_KEYS:
            
            pretty_strings.append( 'get the dictionary keys' )
            
        
        pretty_strings.extend( self._string_processor.GetProcessingStrings() )
        
        separator = os.linesep + 'and then '
        
        pretty_multiline_string = '--JSON--' + os.linesep + separator.join( pretty_strings )
        
        return pretty_multiline_string
        
    
HydrusSerialisable.SERIALISABLE_TYPES_TO_OBJECT_TYPES[ HydrusSerialisable.SERIALISABLE_TYPE_PARSE_FORMULA_JSON ] = ParseFormulaJSON

class SimpleDownloaderParsingFormula( HydrusSerialisable.SerialisableBaseNamed ):
    
    SERIALISABLE_TYPE = HydrusSerialisable.SERIALISABLE_TYPE_SIMPLE_DOWNLOADER_PARSE_FORMULA
    SERIALISABLE_NAME = 'Simple Downloader Parsing Formula'
    SERIALISABLE_VERSION = 1
    
    def __init__( self, name = None, formula = None ):
        
        if name is None:
            
            name = 'new parsing formula'
            
        
        if formula is None:
            
            formula = ParseFormulaHTML()
            
        
        HydrusSerialisable.SerialisableBaseNamed.__init__( self, name )
        
        self._formula = formula
        
    
    def _GetSerialisableInfo( self ):
        
        serialisable_formula = self._formula.GetSerialisableTuple()
        
        return serialisable_formula
        
    
    def _InitialiseFromSerialisableInfo( self, serialisable_info ):
        
        serialisable_formula = serialisable_info
        
        self._formula = HydrusSerialisable.CreateFromSerialisableTuple( serialisable_formula )
        
    
    def GetFormula( self ):
        
        return self._formula
        
    
HydrusSerialisable.SERIALISABLE_TYPES_TO_OBJECT_TYPES[ HydrusSerialisable.SERIALISABLE_TYPE_SIMPLE_DOWNLOADER_PARSE_FORMULA ] = SimpleDownloaderParsingFormula

CONTENT_PARSER_SORT_TYPE_NONE = 0
CONTENT_PARSER_SORT_TYPE_LEXICOGRAPHIC = 1
CONTENT_PARSER_SORT_TYPE_HUMAN_SORT = 2

class ContentParser( HydrusSerialisable.SerialisableBase ):
    
    SERIALISABLE_TYPE = HydrusSerialisable.SERIALISABLE_TYPE_CONTENT_PARSER
    SERIALISABLE_NAME = 'Content Parser'
    SERIALISABLE_VERSION = 6
    
    def __init__( self, name = None, content_type = None, formula = None, additional_info = None ):
        
        if name is None:
            
            name = ''
            
        
        if content_type is None:
            
            content_type = HC.CONTENT_TYPE_MAPPINGS
            
        
        if formula is None:
            
            formula = ParseFormulaHTML()
            
        
        if additional_info is None:
            
            if content_type == HC.CONTENT_TYPE_MAPPINGS:
                
                additional_info = ''
                
            
        
        self._name = name
        self._content_type = content_type
        self._formula = formula
        self._additional_info = additional_info
        
    
    def _GetSerialisableInfo( self ):
        
        serialisable_formula = self._formula.GetSerialisableTuple()
        
        if self._content_type == HC.CONTENT_TYPE_VETO:
            
            ( veto_if_matches_found, string_match ) = self._additional_info
            
            serialisable_additional_info = ( veto_if_matches_found, string_match.GetSerialisableTuple() )
            
        else:
            
            serialisable_additional_info = self._additional_info
            
        
        return ( self._name, self._content_type, serialisable_formula, serialisable_additional_info )
        
    
    def _InitialiseFromSerialisableInfo( self, serialisable_info ):
        
        ( self._name, self._content_type, serialisable_formula, serialisable_additional_info ) = serialisable_info
        
        if self._content_type == HC.CONTENT_TYPE_VETO:
            
            ( veto_if_matches_found, serialisable_string_match ) = serialisable_additional_info
            
            string_match = HydrusSerialisable.CreateFromSerialisableTuple( serialisable_string_match )
            
            self._additional_info = ( veto_if_matches_found, string_match )
            
        else:
            
            self._additional_info = serialisable_additional_info
            
            if isinstance( self._additional_info, list ):
                
                additional_info = []
                
                for item in self._additional_info:
                    
                    # this fixes some garbage accidental update caused by borked version numbers that made ( [ 'md5', 'hex' ], 'hex' )
                    if isinstance( item, list ):
                        
                        additional_info = tuple( item )
                        
                        break
                        
                    
                    additional_info.append( item )
                    
                
                self._additional_info = tuple( additional_info )
                
            
        
        self._formula = HydrusSerialisable.CreateFromSerialisableTuple( serialisable_formula )
        
    
    def _UpdateSerialisableInfo( self, version, old_serialisable_info ):
        
        if version == 1:
            
            ( name, content_type, serialisable_formula, additional_info ) = old_serialisable_info
            
            if content_type == HC.CONTENT_TYPE_VETO:
                
                ( veto_if_matches_found, match_if_text_present, search_text ) = additional_info
                
                if match_if_text_present:
                    
                    string_match = StringMatch( match_type = STRING_MATCH_REGEX, match_value = search_text, example_string = search_text )
                    
                else:
                    
                    string_match = StringMatch()
                    
                
                serialisable_string_match = string_match.GetSerialisableTuple()
                
                additional_info = ( veto_if_matches_found, serialisable_string_match )
                
            
            new_serialisable_info = ( name, content_type, serialisable_formula, additional_info )
            
            return ( 2, new_serialisable_info )
            
        
        if version == 2:
            
            ( name, content_type, serialisable_formula, additional_info ) = old_serialisable_info
            
            if content_type == HC.CONTENT_TYPE_URLS:
                
                ( url_type, priority ) = additional_info
                
                if url_type == HC.URL_TYPE_FILE:
                    
                    url_type = HC.URL_TYPE_DESIRED
                    
                elif url_type == HC.URL_TYPE_POST:
                    
                    url_type = HC.URL_TYPE_SOURCE
                    
                else:
                    
                    url_type = HC.URL_TYPE_NEXT
                    
                
                additional_info = ( url_type, priority )
                
            
            new_serialisable_info = ( name, content_type, serialisable_formula, additional_info )
            
            return ( 3, new_serialisable_info )
            
        
        if version == 3:
            
            ( name, content_type, serialisable_formula, additional_info ) = old_serialisable_info
            
            sort_type = CONTENT_PARSER_SORT_TYPE_NONE
            sort_asc = False
            
            new_serialisable_info = ( name, content_type, serialisable_formula, sort_type, sort_asc, additional_info )
            
            return ( 4, new_serialisable_info )
            
        
        if version == 4:
            
            ( name, content_type, serialisable_formula, sort_type, sort_asc, additional_info ) = old_serialisable_info
            
            if content_type == HC.CONTENT_TYPE_HASH and not isinstance( additional_info, list ):
                
                hash_encoding = 'hex'
                
                if '"base64"' in json.dumps( serialisable_formula ): # lmao, top code
                    
                    hash_encoding = 'base64'
                    
                
                hash_type = additional_info
                
                additional_info = ( hash_type, hash_encoding )
                
            
            new_serialisable_info = ( name, content_type, serialisable_formula, sort_type, sort_asc, additional_info )
            
            return ( 5, new_serialisable_info )
            
        
        if version == 5:
            
            ( name, content_type, serialisable_formula, sort_type, sort_asc, additional_info ) = old_serialisable_info
            
            if sort_type != CONTENT_PARSER_SORT_TYPE_NONE:
                
                formula = HydrusSerialisable.CreateFromSerialisableTuple( serialisable_formula )
                
                string_processor = formula.GetStringProcessor()
                
                processing_steps = string_processor.GetProcessingSteps()
                
                processing_steps.append( StringSorter( sort_type = sort_type, asc = sort_asc ) )
                
                string_processor.SetProcessingSteps( processing_steps )
                
                serialisable_formula = formula.GetSerialisableTuple()
                
            
            new_serialisable_info = ( name, content_type, serialisable_formula, additional_info )
            
            return ( 6, new_serialisable_info )
            
        
    
    def GetName( self ):
        
        return self._name
        
    
    def GetParsableContent( self ):
        
        return { ( self._name, self._content_type, self._additional_info ) }
        
    
    def Parse( self, parsing_context, parsing_text ):
        
        try:
            
            parsed_texts = list( self._formula.Parse( parsing_context, parsing_text ) )
            
        except HydrusExceptions.ParseException as e:
            
            prefix = 'Content Parser ' + self._name + ': '
            
            e = HydrusExceptions.ParseException( prefix + str( e ) )
            
            raise e
            
        
        if self._content_type == HC.CONTENT_TYPE_URLS:
            
            if 'url' in parsing_context:
                
                base_url = parsing_context[ 'url' ]
                
                def clean_url( u ):
                    
                    # clears up when a source field starts with gubbins for some reason. e.g.:
                    # (jap characters).avi | ranken [pixiv] http:/www.pixiv.net/member_illust.php?illust_id=48114073&mode=medium
                    # ->
                    # http:/www.pixiv.net/member_illust.php?illust_id=48114073&mode=medium
                    
                    while re.search( r'\shttp', u ) is not None:
                        
                        u = re.sub( r'^.*\shttp', 'http', u )
                        
                    
                    while u.startswith( 'https://https://' ):
                        
                        u = u[8:]
                        
                    
                    return u
                    
                
                clean_parsed_texts = []
                
                for parsed_text in parsed_texts:
                    
                    if not parsed_text.startswith( 'http' ) and ( 'http://' in parsed_text or 'https://' in parsed_text ):
                        
                        parsed_text = clean_url( parsed_text )
                        
                    
                    clean_parsed_texts.append( parsed_text )
                    
                
                parsed_texts = clean_parsed_texts
                
                parsed_texts = [ urllib.parse.urljoin( base_url, parsed_text ) for parsed_text in parsed_texts ]
                
            
        
        if self._content_type == HC.CONTENT_TYPE_VETO:
            
            ( veto_if_matches_found, string_match ) = self._additional_info
            
            match_found = True in ( string_match.Matches( parsed_text ) for parsed_text in parsed_texts )
            
            veto_if_missing = not veto_if_matches_found
            
            do_veto = ( veto_if_matches_found and match_found ) or ( veto_if_missing and not match_found )
            
            if do_veto:
                
                raise HydrusExceptions.VetoException( self._name )
                
            else:
                
                return []
                
            
        else:
            
            content_description = ( self._name, self._content_type, self._additional_info )
            
            return [ ( content_description, parsed_text ) for parsed_text in parsed_texts ]
            
        
    
    def ParsePretty( self, parsing_context, parsing_text ):
        
        try:
            
            parse_results = self.Parse( parsing_context, parsing_text )
            
            results = [ ConvertParseResultToPrettyString( parse_result ) for parse_result in parse_results ]
            
        except HydrusExceptions.VetoException as e:
            
            results = [ 'veto: ' + str( e ) ]
            
        except HydrusExceptions.ParseException as e:
            
            prefix = 'Content Parser ' + self._name + ': '
            
            e = HydrusExceptions.ParseException( prefix + str( e ) )
            
            raise e
            
        
        result_lines = [ '*** ' + HydrusData.ToHumanInt( len( results ) ) + ' RESULTS BEGIN ***' ]
        
        result_lines.extend( results )
        
        result_lines.append( '*** RESULTS END ***' )
        
        results_text = os.linesep.join( result_lines )
        
        return results_text
        
    
    def SetName( self, name ):
        
        self._name = name
        
    
    def ToPrettyStrings( self ):
        
        return ( self._name, 'content', ConvertParsableContentToPrettyString( self.GetParsableContent(), include_veto = True ) )
        
    
    def ToTuple( self ):
        
        return ( self._name, self._content_type, self._formula, self._additional_info )
        
    
HydrusSerialisable.SERIALISABLE_TYPES_TO_OBJECT_TYPES[ HydrusSerialisable.SERIALISABLE_TYPE_CONTENT_PARSER ] = ContentParser

class PageParser( HydrusSerialisable.SerialisableBaseNamed ):
    
    SERIALISABLE_TYPE = HydrusSerialisable.SERIALISABLE_TYPE_PAGE_PARSER
    SERIALISABLE_NAME = 'Page Parser'
    SERIALISABLE_VERSION = 2
    
    def __init__( self, name, parser_key = None, string_converter = None, sub_page_parsers = None, content_parsers = None, example_urls = None, example_parsing_context = None ):
        
        if parser_key is None:
            
            parser_key = HydrusData.GenerateKey()
            
        
        if string_converter is None:
            
            string_converter = StringConverter()
            
        
        if sub_page_parsers is None:
            
            sub_page_parsers = []
            
        
        if content_parsers is None:
            
            content_parsers = []
            
        
        if example_urls is None:
            
            example_urls = []
            
        
        if example_parsing_context is None:
            
            example_parsing_context = {}
            
            example_parsing_context[ 'url' ] = 'https://example.com/posts/index.php?id=123456'
            
        
        HydrusSerialisable.SerialisableBaseNamed.__init__( self, name )
        
        self._parser_key = parser_key
        self._string_converter = string_converter
        self._sub_page_parsers = sub_page_parsers
        self._content_parsers = content_parsers
        self._example_urls = example_urls
        self._example_parsing_context = example_parsing_context
        
    
    def _GetSerialisableInfo( self ):
        
        serialisable_parser_key = self._parser_key.hex()
        serialisable_string_converter = self._string_converter.GetSerialisableTuple()
        
        serialisable_sub_page_parsers = [ ( formula.GetSerialisableTuple(), page_parser.GetSerialisableTuple() ) for ( formula, page_parser ) in self._sub_page_parsers ]
        
        serialisable_content_parsers = HydrusSerialisable.SerialisableList( self._content_parsers ).GetSerialisableTuple()
        
        return ( self._name, serialisable_parser_key, serialisable_string_converter, serialisable_sub_page_parsers, serialisable_content_parsers, self._example_urls, self._example_parsing_context )
        
    
    def _InitialiseFromSerialisableInfo( self, serialisable_info ):
        
        ( self._name, serialisable_parser_key, serialisable_string_converter, serialisable_sub_page_parsers, serialisable_content_parsers, self._example_urls, self._example_parsing_context ) = serialisable_info
        
        self._parser_key = bytes.fromhex( serialisable_parser_key )
        self._string_converter = HydrusSerialisable.CreateFromSerialisableTuple( serialisable_string_converter )
        self._sub_page_parsers = [ ( HydrusSerialisable.CreateFromSerialisableTuple( serialisable_formula ), HydrusSerialisable.CreateFromSerialisableTuple( serialisable_page_parser ) ) for ( serialisable_formula, serialisable_page_parser ) in serialisable_sub_page_parsers ]
        self._content_parsers = HydrusSerialisable.CreateFromSerialisableTuple( serialisable_content_parsers )
        
    
    def _UpdateSerialisableInfo( self, version, old_serialisable_info ):
        
        if version == 1:
            
            ( name, serialisable_parser_key, serialisable_string_converter, serialisable_sub_page_parsers, serialisable_content_parsers, example_urls ) = old_serialisable_info
            
            example_parsing_context = {}
            
            example_parsing_context[ 'url' ] = 'https://example.com/posts/index.php?id=123456'
            
            new_serialisable_info = ( name, serialisable_parser_key, serialisable_string_converter, serialisable_sub_page_parsers, serialisable_content_parsers, example_urls, example_parsing_context )
            
            return ( 2, new_serialisable_info )
            
        
    
    def CanOnlyGenerateGalleryURLs( self ):
        
        can_generate_gallery_urls = False
        can_generate_other_urls = False
        
        parsable_content = self.GetParsableContent()
        
        for ( name, content_type, additional_info ) in parsable_content:
            
            if content_type == HC.CONTENT_TYPE_URLS:
                
                ( url_type, priority ) = additional_info
                
                if url_type == HC.URL_TYPE_GALLERY:
                    
                    can_generate_gallery_urls = True
                    
                else:
                    
                    can_generate_other_urls = True
                    
                
            
        
        return can_generate_gallery_urls and not can_generate_other_urls
        
    
    def GetContentParsers( self ):
        
        return ( self._sub_page_parsers, self._content_parsers )
        
    
    def GetExampleParsingContext( self ):
        
        return self._example_parsing_context
        
    
    def GetExampleURLs( self ):
        
        return self._example_urls
        
    
    def GetNamespaces( self ):
        
        # this in future could expand to be more granular like:
        # 'I want the artist tags, but not the user-submitted.'
        # 'I want the title here, but not the title there.'
        # 'I want the original filename, but not the UNIX timestamp filename.'
        # which the parser could present with its sub-parsing element names
        
        return GetNamespacesFromParsableContent( self.GetParsableContent() )
        
    
    def GetParsableContent( self ):
        
        parsable_content = set()
        
        for ( formula, page_parser ) in self._sub_page_parsers:
            
            parsable_content.update( page_parser.GetParsableContent() )
            
        
        for content_parser in self._content_parsers:
            
            parsable_content.update( content_parser.GetParsableContent() )
            
        
        return parsable_content
        
    
    def GetParserKey( self ):
        
        return self._parser_key
        
    
    def GetSafeSummary( self ):
        
        domains = sorted( { ClientNetworkingDomain.ConvertURLIntoDomain( url ) for url in self._example_urls } )
        
        return 'Parser "' + self._name + '" - ' + ', '.join( domains )
        
    
    def GetStringConverter( self ):
        
        return self._string_converter
        
    
    def Parse( self, parsing_context, parsing_text ):
        
        try:
            
            converted_parsing_text = self._string_converter.Convert( parsing_text )
            
        except HydrusExceptions.StringConvertException as e:
            
            raise HydrusExceptions.ParseException( str( e ) )
            
        except HydrusExceptions.ParseException as e:
            
            prefix = 'Page Parser ' + self._name + ': '
            
            e = HydrusExceptions.ParseException( prefix + str( e ) )
            
            raise e
            
        
        
        #
        
        whole_page_parse_results = []
        
        try:
            
            if 'post_index' not in parsing_context:
                
                parsing_context[ 'post_index' ] = '0'
                
            
            for content_parser in self._content_parsers:
                
                whole_page_parse_results.extend( content_parser.Parse( parsing_context, converted_parsing_text ) )
                
            
            if ParseResultsHavePursuableURLs( whole_page_parse_results ):
                
                parsing_context[ 'post_index' ] = str( int( parsing_context[ 'post_index' ] ) + 1 )
                
            
        except HydrusExceptions.ParseException as e:
            
            prefix = 'Page Parser ' + self._name + ': '
            
            e = HydrusExceptions.ParseException( prefix + str( e ) )
            
            raise e
            
        
        #
        
        all_parse_results = []
        
        if len( self._sub_page_parsers ) == 0:
            
            if len( whole_page_parse_results ) > 0:
                
                all_parse_results = [ whole_page_parse_results ]
                
            
        else:
            
            def sort_key( sub_page_parser ):
                
                ( formula, page_parser ) = sub_page_parser
                
                return page_parser.GetName()
                
            
            sub_page_parsers = list( self._sub_page_parsers )
            
            sub_page_parsers.sort( key = sort_key )
            
            try:
                
                for ( formula, page_parser ) in self._sub_page_parsers:
                    
                    try:
                        
                        posts = formula.Parse( parsing_context, converted_parsing_text )
                        
                    except HydrusExceptions.ParseException:
                        
                        continue
                        
                    
                    for ( i, post ) in enumerate( posts ):
                        
                        try:
                            
                            page_parser_all_parse_results = page_parser.Parse( parsing_context, post )
                            
                        except HydrusExceptions.VetoException:
                            
                            continue
                            
                        
                        for page_parser_parse_results in page_parser_all_parse_results:
                            
                            page_parser_parse_results.extend( whole_page_parse_results )
                            
                            all_parse_results.append( page_parser_parse_results )
                            
                        
                    
                
            except HydrusExceptions.ParseException as e:
                
                prefix = 'Page Parser ' + self._name + ': '
                
                e = HydrusExceptions.ParseException( prefix + str( e ) )
                
                raise e
                
            
        
        return all_parse_results
        
    
    def ParsePretty( self, parsing_context, parsing_text ):
        
        try:
            
            all_parse_results = self.Parse( parsing_context, parsing_text )
            
            pretty_groups_of_parse_results = [ os.linesep.join( [ ConvertParseResultToPrettyString( parse_result ) for parse_result in parse_results ] ) for parse_results in all_parse_results ]
            
            group_separator = os.linesep * 2 + '*** SEPARATE FILE RESULTS BREAK ***' + os.linesep * 2
            
            pretty_parse_result_text = group_separator.join( pretty_groups_of_parse_results )
            
        except HydrusExceptions.VetoException as e:
            
            all_parse_results = [ 1 ]
            
            pretty_parse_result_text = 'veto: ' + str( e )
            
        
        result_lines = []
        
        result_lines.append( '*** ' + HydrusData.ToHumanInt( len( all_parse_results ) ) + ' RESULTS BEGIN ***' + os.linesep )
        
        result_lines.append( pretty_parse_result_text )
        
        result_lines.append( os.linesep + '*** RESULTS END ***' )
        
        results_text = os.linesep.join( result_lines )
        
        return results_text
        
    
    def RegenerateParserKey( self ):
        
        self._parser_key = HydrusData.GenerateKey()
        
    
    def SetExampleURLs( self, example_urls ):
        
        self._example_urls = list( example_urls )
        
    
    def SetExampleParsingContext( self, example_parsing_context ):
        
        self._example_parsing_context = example_parsing_context
        
    
    def SetParserKey( self, parser_key ):
        
        self._parser_key = parser_key
        
    
HydrusSerialisable.SERIALISABLE_TYPES_TO_OBJECT_TYPES[ HydrusSerialisable.SERIALISABLE_TYPE_PAGE_PARSER ] = PageParser

class ParseNodeContentLink( HydrusSerialisable.SerialisableBase ):
    
    SERIALISABLE_TYPE = HydrusSerialisable.SERIALISABLE_TYPE_PARSE_NODE_CONTENT_LINK
    SERIALISABLE_NAME = 'Content Parsing Link'
    SERIALISABLE_VERSION = 1
    
    def __init__( self, name = None, formula = None, children = None ):
        
        if name is None:
            
            name = ''
            
        
        if formula is None:
            
            formula = ParseFormulaHTML()
            
        
        if children is None:
            
            children = []
            
        
        self._name = name
        self._formula = formula
        self._children = children
        
    
    def _GetSerialisableInfo( self ):
        
        serialisable_formula = self._formula.GetSerialisableTuple()
        serialisable_children = [ child.GetSerialisableTuple() for child in self._children ]
        
        return ( self._name, serialisable_formula, serialisable_children )
        
    
    def _InitialiseFromSerialisableInfo( self, serialisable_info ):
        
        ( self._name, serialisable_formula, serialisable_children ) = serialisable_info
        
        self._formula = HydrusSerialisable.CreateFromSerialisableTuple( serialisable_formula )
        self._children = [ HydrusSerialisable.CreateFromSerialisableTuple( serialisable_child ) for serialisable_child in serialisable_children ]
        
    
    def GetParsableContent( self ):
        
        children_parsable_content = set()
        
        for child in self._children:
            
            children_parsable_content.update( child.GetParsableContent() )
            
        
        return children_parsable_content
        
    
    def Parse( self, job_key, parsing_text, referral_url ):
        
        search_urls = self.ParseURLs( job_key, parsing_text, referral_url )
        
        content = []
        
        for search_url in search_urls:
            
            job_key.SetVariable( 'script_status', 'fetching ' + HydrusText.ElideText( search_url, 32 ) )
            
            network_job = ClientNetworkingJobs.NetworkJob( 'GET', search_url, referral_url = referral_url )
            
            network_job.OverrideBandwidth()
            
            HG.client_controller.network_engine.AddJob( network_job )
            
            try:
                
                network_job.WaitUntilDone()
                
            except HydrusExceptions.CancelledException:
                
                break
                
            except HydrusExceptions.NetworkException as e:
                
                if isinstance( e, HydrusExceptions.NotFoundException ):
                    
                    job_key.SetVariable( 'script_status', '404 - nothing found' )
                    
                    time.sleep( 2 )
                    
                    continue
                    
                elif isinstance( e, HydrusExceptions.NetworkException ):
                    
                    job_key.SetVariable( 'script_status', 'Network error! Details written to log.' )
                    
                    HydrusData.Print( 'Problem fetching ' + HydrusText.ElideText( search_url, 32 ) + ':' )
                    HydrusData.PrintException( e )
                    
                    time.sleep( 2 )
                    
                    continue
                    
                else:
                    
                    raise
                    
                
            
            linked_text = network_job.GetContentText()
            
            children_content = GetChildrenContent( job_key, self._children, linked_text, search_url )
            
            content.extend( children_content )
            
            if job_key.IsCancelled():
                
                raise HydrusExceptions.CancelledException( 'Job was cancelled.' )
                
            
        
        return content
        
    
    def ParseURLs( self, job_key, parsing_text, referral_url ):
        
        basic_urls = self._formula.Parse( {}, parsing_text )
        
        absolute_urls = [ urllib.parse.urljoin( referral_url, basic_url ) for basic_url in basic_urls ]
        
        for url in absolute_urls:
            
            job_key.AddURL( url )
            
        
        return absolute_urls
        
    
    def ToPrettyStrings( self ):
        
        return ( self._name, 'link', ConvertParsableContentToPrettyString( self.GetParsableContent() ) )
        
    
    def ToTuple( self ):
        
        return ( self._name, self._formula, self._children )
        
    
HydrusSerialisable.SERIALISABLE_TYPES_TO_OBJECT_TYPES[ HydrusSerialisable.SERIALISABLE_TYPE_PARSE_NODE_CONTENT_LINK ] = ParseNodeContentLink

FILE_IDENTIFIER_TYPE_FILE = 0
FILE_IDENTIFIER_TYPE_MD5 = 1
FILE_IDENTIFIER_TYPE_SHA1 = 2
FILE_IDENTIFIER_TYPE_SHA256 = 3
FILE_IDENTIFIER_TYPE_SHA512 = 4
FILE_IDENTIFIER_TYPE_USER_INPUT = 5

file_identifier_string_lookup = {}

file_identifier_string_lookup[ FILE_IDENTIFIER_TYPE_FILE ] = 'the actual file (POST only)'
file_identifier_string_lookup[ FILE_IDENTIFIER_TYPE_MD5 ] = 'md5 hash'
file_identifier_string_lookup[ FILE_IDENTIFIER_TYPE_SHA1 ] = 'sha1 hash'
file_identifier_string_lookup[ FILE_IDENTIFIER_TYPE_SHA256 ] = 'sha256 hash'
file_identifier_string_lookup[ FILE_IDENTIFIER_TYPE_SHA512 ] = 'sha512 hash'
file_identifier_string_lookup[ FILE_IDENTIFIER_TYPE_USER_INPUT ] = 'custom user input'

# eventually transition this to be a flat 'generate page/gallery urls'
# the rest of the parsing system can pick those up automatically
# this nullifies the need for contentlink stuff, at least in its current borked form
class ParseRootFileLookup( HydrusSerialisable.SerialisableBaseNamed ):
    
    SERIALISABLE_TYPE = HydrusSerialisable.SERIALISABLE_TYPE_PARSE_ROOT_FILE_LOOKUP
    SERIALISABLE_NAME = 'File Lookup Script'
    SERIALISABLE_VERSION = 2
    
    def __init__( self, name, url = None, query_type = None, file_identifier_type = None, file_identifier_string_converter = None, file_identifier_arg_name = None, static_args = None, children = None ):
        
        HydrusSerialisable.SerialisableBaseNamed.__init__( self, name )
        
        self._url = url
        self._query_type = query_type
        self._file_identifier_type = file_identifier_type
        self._file_identifier_string_converter = file_identifier_string_converter
        self._file_identifier_arg_name = file_identifier_arg_name
        self._static_args = static_args
        self._children = children
        
    
    def _GetSerialisableInfo( self ):
        
        serialisable_children = [ child.GetSerialisableTuple() for child in self._children ]
        serialisable_file_identifier_string_converter = self._file_identifier_string_converter.GetSerialisableTuple()
        
        return ( self._url, self._query_type, self._file_identifier_type, serialisable_file_identifier_string_converter, self._file_identifier_arg_name, self._static_args, serialisable_children )
        
    
    def _InitialiseFromSerialisableInfo( self, serialisable_info ):
        
        ( self._url, self._query_type, self._file_identifier_type, serialisable_file_identifier_string_converter, self._file_identifier_arg_name, self._static_args, serialisable_children ) = serialisable_info
        
        self._children = [ HydrusSerialisable.CreateFromSerialisableTuple( serialisable_child ) for serialisable_child in serialisable_children ]
        self._file_identifier_string_converter = HydrusSerialisable.CreateFromSerialisableTuple( serialisable_file_identifier_string_converter )
        
    
    def _UpdateSerialisableInfo( self, version, old_serialisable_info ):
        
        if version == 1:
            
            ( url, query_type, file_identifier_type, file_identifier_encoding, file_identifier_arg_name, static_args, serialisable_children ) = old_serialisable_info
            
            conversions = []
            
            if file_identifier_encoding == HC.ENCODING_RAW:
                
                pass
                
            elif file_identifier_encoding == HC.ENCODING_HEX:
                
                conversions.append( ( STRING_CONVERSION_ENCODE, 'hex' ) )
                
            elif file_identifier_encoding == HC.ENCODING_BASE64:
                
                conversions.append( ( STRING_CONVERSION_ENCODE, 'base64' ) )
                
            
            file_identifier_string_converter = StringConverter( conversions, 'some hash bytes' )
            
            serialisable_file_identifier_string_converter = file_identifier_string_converter.GetSerialisableTuple()
            
            new_serialisable_info = ( url, query_type, file_identifier_type, serialisable_file_identifier_string_converter, file_identifier_arg_name, static_args, serialisable_children )
            
            return ( 2, new_serialisable_info )
            
        
    
    def ConvertMediaToFileIdentifier( self, media ):
        
        if self._file_identifier_type == FILE_IDENTIFIER_TYPE_USER_INPUT:
            
            raise Exception( 'Cannot convert media to file identifier--this script takes user input!' )
            
        elif self._file_identifier_type == FILE_IDENTIFIER_TYPE_SHA256:
            
            return media.GetHash()
            
        elif self._file_identifier_type in ( FILE_IDENTIFIER_TYPE_MD5, FILE_IDENTIFIER_TYPE_SHA1, FILE_IDENTIFIER_TYPE_SHA512 ):
            
            sha256_hash = media.GetHash()
            
            if self._file_identifier_type == FILE_IDENTIFIER_TYPE_MD5:
                
                hash_type = 'md5'
                
            elif self._file_identifier_type == FILE_IDENTIFIER_TYPE_SHA1:
                
                hash_type = 'sha1'
                
            elif self._file_identifier_type == FILE_IDENTIFIER_TYPE_SHA512:
                
                hash_type = 'sha512'
                
            
            try:
                
                ( other_hash, ) = HG.client_controller.Read( 'file_hashes', ( sha256_hash, ), 'sha256', hash_type )
                
                return other_hash
                
            except:
                
                raise Exception( 'I do not know that file\'s ' + hash_type + ' hash, so I cannot look it up!' )
                
            
        elif self._file_identifier_type == FILE_IDENTIFIER_TYPE_FILE:
            
            hash = media.GetHash()
            mime = media.GetMime()
            
            client_files_manager = HG.client_controller.client_files_manager
            
            try:
                
                path = client_files_manager.GetFilePath( hash, mime )
                
                return path
                
            except HydrusExceptions.FileMissingException as e:
                
                raise Exception( 'That file is not in the database\'s local files, so I cannot look it up!' )
                
            
        
    
    def FetchParsingText( self, job_key, file_identifier ):
        
        # add gauge report hook and in-stream cancel support to the get/post calls
        
        request_args = dict( self._static_args )
        
        if self._file_identifier_type != FILE_IDENTIFIER_TYPE_FILE:
            
            request_args[ self._file_identifier_arg_name ] = self._file_identifier_string_converter.Convert( file_identifier )
            
        
        f = None
        
        if self._query_type == HC.GET:
            
            if self._file_identifier_type == FILE_IDENTIFIER_TYPE_FILE:
                
                raise Exception( 'Cannot have a file as an argument on a GET query!' )
                
            
            full_request_url = self._url + '?' + ClientNetworkingDomain.ConvertQueryDictToText( request_args )
            
            job_key.SetVariable( 'script_status', 'fetching ' + HydrusText.ElideText( full_request_url, 32 ) )
            
            job_key.AddURL( full_request_url )
            
            network_job = ClientNetworkingJobs.NetworkJob( 'GET', full_request_url )
            
        elif self._query_type == HC.POST:
            
            additional_headers = {}
            files = None
            
            if self._file_identifier_type == FILE_IDENTIFIER_TYPE_FILE:
                
                job_key.SetVariable( 'script_status', 'uploading file' )
                
                path  = file_identifier
                
                if self._file_identifier_string_converter.MakesChanges():
                    
                    with open( path, 'rb' ) as f:
                        
                        file_bytes = f.read()
                        
                    
                    f_altered = self._file_identifier_string_converter.Convert( file_bytes )
                    
                    request_args[ self._file_identifier_arg_name ] = f_altered
                    
                    additional_headers[ 'content-type' ] = 'application/x-www-form-urlencoded'
                    
                else:
                    
                    f = open( path, 'rb' )
                    
                    files = { self._file_identifier_arg_name : f }
                    
                
            else:
                
                job_key.SetVariable( 'script_status', 'uploading identifier' )
                
                files = None
                
            
            network_job = ClientNetworkingJobs.NetworkJob( 'POST', self._url, body = request_args )
            
            if files is not None:
                
                network_job.SetFiles( files )
                
            
            for ( key, value ) in additional_headers.items():
                
                network_job.AddAdditionalHeader( key, value )
                
            
        
        # send nj to nj control on this panel here
        
        network_job.OverrideBandwidth()
        
        HG.client_controller.network_engine.AddJob( network_job )
        
        try:
            
            network_job.WaitUntilDone()
            
        except HydrusExceptions.NotFoundException:
            
            job_key.SetVariable( 'script_status', '404 - nothing found' )
            
            raise
            
        except HydrusExceptions.NetworkException as e:
            
            job_key.SetVariable( 'script_status', 'Network error!' )
            
            HydrusData.ShowException( e )
            
            raise
            
        finally:
            
            if f is not None:
                
                f.close()
                
            
        
        if job_key.IsCancelled():
            
            raise HydrusExceptions.CancelledException( 'Job was cancelled.' )
            
        
        parsing_text = network_job.GetContentText()
        
        return parsing_text
        
    
    def GetParsableContent( self ):
        
        children_parsable_content = set()
        
        for child in self._children:
            
            children_parsable_content.update( child.GetParsableContent() )
            
        
        return children_parsable_content
        
    
    def DoQuery( self, job_key, file_identifier ):
        
        try:
            
            try:
                
                parsing_text = self.FetchParsingText( job_key, file_identifier )
                
            except HydrusExceptions.NetworkException as e:
                
                return []
                
            
            parse_results = self.Parse( job_key, parsing_text )
            
            return parse_results
            
        except HydrusExceptions.CancelledException:
            
            job_key.SetVariable( 'script_status', 'Cancelled!' )
            
            return []
            
        finally:
            
            job_key.Finish()
            
        
    
    def UsesUserInput( self ):
        
        return self._file_identifier_type == FILE_IDENTIFIER_TYPE_USER_INPUT
        
    
    def Parse( self, job_key, parsing_text ):
        
        parse_results = GetChildrenContent( job_key, self._children, parsing_text, self._url )
        
        if len( parse_results ) == 0:
            
            job_key.SetVariable( 'script_status', 'Did not find anything.' )
            
        else:
            
            job_key.SetVariable( 'script_status', 'Found ' + HydrusData.ToHumanInt( len( parse_results ) ) + ' rows.' )
            
        
        return parse_results
        
    
    def SetChildren( self, children ):
        
        self._children = children
        
    
    def ToPrettyStrings( self ):
        
        return ( self._name, HC.query_type_string_lookup[ self._query_type ], 'File Lookup', ConvertParsableContentToPrettyString( self.GetParsableContent() ) )
        
    
    def ToTuple( self ):
        
        return ( self._name, self._url, self._query_type, self._file_identifier_type, self._file_identifier_string_converter,  self._file_identifier_arg_name, self._static_args, self._children )
        
    
HydrusSerialisable.SERIALISABLE_TYPES_TO_OBJECT_TYPES[ HydrusSerialisable.SERIALISABLE_TYPE_PARSE_ROOT_FILE_LOOKUP ] = ParseRootFileLookup

STRING_CONVERSION_REMOVE_TEXT_FROM_BEGINNING = 0
STRING_CONVERSION_REMOVE_TEXT_FROM_END = 1
STRING_CONVERSION_PREPEND_TEXT = 2
STRING_CONVERSION_APPEND_TEXT = 3
STRING_CONVERSION_ENCODE = 4
STRING_CONVERSION_DECODE = 5
STRING_CONVERSION_CLIP_TEXT_FROM_BEGINNING = 6
STRING_CONVERSION_CLIP_TEXT_FROM_END = 7
STRING_CONVERSION_REVERSE = 8
STRING_CONVERSION_REGEX_SUB = 9
STRING_CONVERSION_DATE_DECODE = 10
STRING_CONVERSION_INTEGER_ADDITION = 11
STRING_CONVERSION_DATE_ENCODE = 12

conversion_type_str_lookup = {}

conversion_type_str_lookup[ STRING_CONVERSION_REMOVE_TEXT_FROM_BEGINNING ] = 'remove text from beginning of string'
conversion_type_str_lookup[ STRING_CONVERSION_REMOVE_TEXT_FROM_END ] = 'remove text from end of string'
conversion_type_str_lookup[ STRING_CONVERSION_PREPEND_TEXT ] = 'prepend text'
conversion_type_str_lookup[ STRING_CONVERSION_APPEND_TEXT ] = 'append text'
conversion_type_str_lookup[ STRING_CONVERSION_ENCODE ] = 'encode'
conversion_type_str_lookup[ STRING_CONVERSION_DECODE ] = 'decode'
conversion_type_str_lookup[ STRING_CONVERSION_CLIP_TEXT_FROM_BEGINNING ] = 'take the start of the string'
conversion_type_str_lookup[ STRING_CONVERSION_CLIP_TEXT_FROM_END ] = 'take the end of the string'
conversion_type_str_lookup[ STRING_CONVERSION_REVERSE ] = 'reverse text'
conversion_type_str_lookup[ STRING_CONVERSION_REGEX_SUB ] = 'regex substitution'
conversion_type_str_lookup[ STRING_CONVERSION_DATE_DECODE ] = 'datestring to timestamp'
conversion_type_str_lookup[ STRING_CONVERSION_INTEGER_ADDITION ] = 'integer addition'
conversion_type_str_lookup[ STRING_CONVERSION_DATE_ENCODE ] = 'timestamp to datestring'

class StringProcessingStep( HydrusSerialisable.SerialisableBase ):
    
    def MakesChanges( self ) -> bool:
        
        raise NotImplementedError()
        
    
    def ToString( self, simple = False, with_type = False ) -> str:
        
        raise NotImplementedError()
        
    
class StringConverter( StringProcessingStep ):
    
    SERIALISABLE_TYPE = HydrusSerialisable.SERIALISABLE_TYPE_STRING_CONVERTER
    SERIALISABLE_NAME = 'String Converter'
    SERIALISABLE_VERSION = 1
    
    def __init__( self, conversions = None, example_string = None ):
        
        if conversions is None:
            
            conversions = []
            
        
        if example_string is None:
            
            example_string = 'example string'
            
        
        StringProcessingStep.__init__( self )
        
        self.conversions = conversions
        
        self.example_string = example_string
        
    
    def _GetSerialisableInfo( self ):
        
        return ( self.conversions, self.example_string )
        
    
    def _InitialiseFromSerialisableInfo( self, serialisable_info ):
        
        ( serialisable_conversions, self.example_string ) = serialisable_info
        
        self.conversions = []
        
        try: # I initialised this bad one time and broke a dialog on subsequent loads, fugg
            
            for ( conversion_type, data ) in serialisable_conversions:
                
                if isinstance( data, list ):
                    
                    data = tuple( data ) # convert from list to tuple thing
                    
                
                self.conversions.append( ( conversion_type, data ) )
                
            
        except:
            
            pass
            
        
    
    def Convert( self, s, max_steps_allowed = None ):
        
        for ( i, conversion ) in enumerate( self.conversions ):
            
            if max_steps_allowed is not None and i >= max_steps_allowed:
                
                return s
                
            
            try:
                
                ( conversion_type, data ) = conversion
                
                if conversion_type == STRING_CONVERSION_REMOVE_TEXT_FROM_BEGINNING:
                    
                    num_chars = data
                    
                    s = s[ num_chars : ]
                    
                elif conversion_type == STRING_CONVERSION_REMOVE_TEXT_FROM_END:
                    
                    num_chars = data
                    
                    s = s[ : - num_chars ]
                    
                elif conversion_type == STRING_CONVERSION_CLIP_TEXT_FROM_BEGINNING:
                    
                    num_chars = data
                    
                    s = s[ : num_chars ]
                    
                elif conversion_type == STRING_CONVERSION_CLIP_TEXT_FROM_END:
                    
                    num_chars = data
                    
                    s = s[ - num_chars : ]
                    
                elif conversion_type == STRING_CONVERSION_PREPEND_TEXT:
                    
                    text = data
                    
                    s = text + s
                    
                elif conversion_type == STRING_CONVERSION_APPEND_TEXT:
                    
                    text = data
                    
                    s = s + text
                    
                elif conversion_type == STRING_CONVERSION_ENCODE:
                    
                    encode_type = data
                    
                    if encode_type == 'url percent encoding':
                        
                        s = urllib.parse.quote( s, safe = '' )
                        
                    elif encode_type == 'unicode escape characters':
                        
                        s = s.encode( 'unicode-escape' ).decode( 'utf-8' )
                        
                    elif encode_type == 'html entities':
                        
                        s = html.escape( s )
                        
                    else:
                        
                        # due to py3, this is now a bit of a pain
                        # _for now_, let's convert to bytes if not already and then spit out a str
                        
                        if isinstance( s, str ):
                            
                            s_bytes = bytes( s, 'utf-8' )
                            
                        else:
                            
                            s_bytes = s
                            
                        
                        if encode_type == 'hex':
                            
                            s = s_bytes.hex()
                            
                        elif encode_type == 'base64':
                            
                            s_bytes = base64.b64encode( s_bytes )
                            
                            s = str( s_bytes, 'utf-8' )
                            
                        
                    
                elif conversion_type == STRING_CONVERSION_DECODE:
                    
                    encode_type = data
                    
                    if encode_type == 'url percent encoding':
                        
                        s = urllib.parse.unquote( s )
                        
                    elif encode_type == 'unicode escape characters':
                        
                        s = s.encode( 'utf-8' ).decode( 'unicode-escape' )
                        
                    elif encode_type == 'html entities':
                        
                        s = html.unescape( s )
                        
                    
                    # the old 'hex' and 'base64' are now deprecated, no-ops
                    
                elif conversion_type == STRING_CONVERSION_REVERSE:
                    
                    s = s[::-1]
                    
                elif conversion_type == STRING_CONVERSION_REGEX_SUB:
                    
                    ( pattern, repl ) = data
                    
                    s = re.sub( pattern, repl, s )
                    
                elif conversion_type == STRING_CONVERSION_DATE_DECODE:
                    
                    ( phrase, timezone, timezone_offset ) = data
                    
                    struct_time = time.strptime( s, phrase )
                    
                    if timezone == HC.TIMEZONE_GMT:
                        
                        # the given struct is in GMT, so calendar.timegm is appropriate here
                        
                        timestamp = int( calendar.timegm( struct_time ) )
                        
                    elif timezone == HC.TIMEZONE_LOCAL:
                        
                        # the given struct is in local time, so time.mktime is correct
                        
                        timestamp = int( time.mktime( struct_time ) )
                        
                    elif timezone == HC.TIMEZONE_OFFSET:
                        
                        # the given struct is in server time, which is the same as GMT minus an offset
                        # if we are 7200 seconds ahead, the correct GMT timestamp needs to be 7200 smaller
                        
                        timestamp = int( calendar.timegm( struct_time ) ) - timezone_offset
                        
                    
                    s = str( timestamp )
                    
                elif conversion_type == STRING_CONVERSION_DATE_ENCODE:
                    
                    ( phrase, timezone ) = data
                    
                    try:
                        
                        timestamp = int( s )
                        
                    except:
                        
                        raise Exception( '"{}" was not an integer!'.format( s ) )
                        
                    
                    if timezone == HC.TIMEZONE_GMT:
                        
                        # user wants a UTC string, so we need UTC struct
                        
                        struct_time = time.gmtime( timestamp )
                        
                    elif timezone == HC.TIMEZONE_LOCAL:
                        
                        # user wants a local string, so we need localtime
                        
                        struct_time = time.localtime( timestamp )
                        
                    
                    s = time.strftime( phrase, struct_time )
                    
                elif conversion_type == STRING_CONVERSION_INTEGER_ADDITION:
                    
                    delta = data
                    
                    s = str( int( s ) + int( delta ) )
                    
                
            except Exception as e:
                
                raise HydrusExceptions.StringConvertException( 'ERROR: Could not apply "' + self.ConversionToString( conversion ) + '" to string "' + repr( s ) + '":' + str( e ) )
                
            
        
        return s
        
    
    def GetConversionStrings( self ):
        
        return [ self.ConversionToString( conversion ) for conversion in self.conversions ]
        
    
    def MakesChanges( self ):
        
        return len( self.conversions ) > 0
        
    
    def ToString( self, simple = False, with_type = False ) -> str:
        
        num_rules = len( self.conversions )
        
        if num_rules == 0:
            
            if simple:
                
                label = 'no changes'
                
            else:
                
                label = 'no string conversions'
                
            
        else:
            
            if simple:
                
                label = '{} changes'.format( HydrusData.ToHumanInt( num_rules ) )
                
            else:
                
                label = ', '.join( self.GetConversionStrings() )
                
            
        
        if with_type:
            
            label = 'CONVERT: {}'.format( label )
            
        
        return label
        
    
    @staticmethod
    def ConversionToString( conversion ):
        
        ( conversion_type, data ) = conversion
        
        if conversion_type == STRING_CONVERSION_REMOVE_TEXT_FROM_BEGINNING:
            
            return 'remove the first ' + HydrusData.ToHumanInt( data ) + ' characters'
            
        elif conversion_type == STRING_CONVERSION_REMOVE_TEXT_FROM_END:
            
            return 'remove the last ' + HydrusData.ToHumanInt( data ) + ' characters'
            
        elif conversion_type == STRING_CONVERSION_CLIP_TEXT_FROM_BEGINNING:
            
            return 'take the first ' + HydrusData.ToHumanInt( data ) + ' characters'
            
        elif conversion_type == STRING_CONVERSION_CLIP_TEXT_FROM_END:
            
            return 'take the last ' + HydrusData.ToHumanInt( data ) + ' characters'
            
        elif conversion_type == STRING_CONVERSION_PREPEND_TEXT:
            
            return 'prepend with "' + data + '"'
            
        elif conversion_type == STRING_CONVERSION_APPEND_TEXT:
            
            return 'append with "' + data + '"'
            
        elif conversion_type == STRING_CONVERSION_ENCODE:
            
            return 'encode to ' + data
            
        elif conversion_type == STRING_CONVERSION_DECODE:
            
            if data in ( 'hex', 'base64' ):
                
                return 'deprecated {} decode, now a no-op, can be deleted'.format( data )
                
            
            return 'decode from ' + data
            
        elif conversion_type == STRING_CONVERSION_REVERSE:
            
            return conversion_type_str_lookup[ STRING_CONVERSION_REVERSE ]
            
        elif conversion_type == STRING_CONVERSION_REGEX_SUB:
            
            return 'regex substitution: ' + str( data )
            
        elif conversion_type == STRING_CONVERSION_DATE_DECODE:
            
            return 'datestring to timestamp: ' + repr( data )
            
        elif conversion_type == STRING_CONVERSION_DATE_ENCODE:
            
            return 'timestamp to datestring: ' + repr( data )
            
        elif conversion_type == STRING_CONVERSION_INTEGER_ADDITION:
            
            return 'integer addition: add ' + str( data )
            
        else:
            
            return 'unknown conversion'
            
        
    
HydrusSerialisable.SERIALISABLE_TYPES_TO_OBJECT_TYPES[ HydrusSerialisable.SERIALISABLE_TYPE_STRING_CONVERTER ] = StringConverter

STRING_MATCH_FIXED = 0
STRING_MATCH_FLEXIBLE = 1
STRING_MATCH_REGEX = 2
STRING_MATCH_ANY = 3

ALPHA = 0
ALPHANUMERIC = 1
NUMERIC = 2

class StringMatch( StringProcessingStep ):
    
    SERIALISABLE_TYPE = HydrusSerialisable.SERIALISABLE_TYPE_STRING_MATCH
    SERIALISABLE_NAME = 'String Match'
    SERIALISABLE_VERSION = 1
    
    def __init__( self, match_type = STRING_MATCH_ANY, match_value = '', min_chars = None, max_chars = None, example_string = 'example string' ):
        
        StringProcessingStep.__init__( self )
        
        self._match_type = match_type
        self._match_value = match_value
        
        self._min_chars = min_chars
        self._max_chars = max_chars
        
        self._example_string = example_string
        
    
    def _GetSerialisableInfo( self ):
        
        return ( self._match_type, self._match_value, self._min_chars, self._max_chars, self._example_string )
        
    
    def _InitialiseFromSerialisableInfo( self, serialisable_info ):
        
        ( self._match_type, self._match_value, self._min_chars, self._max_chars, self._example_string ) = serialisable_info
        
    
    def GetExampleString( self ):
        
        return self._example_string
        
    
    def MakesChanges( self ) -> bool:
        
        if self._min_chars is not None or self._max_chars is not None:
            
            return True
            
        
        if self._match_type != STRING_MATCH_ANY:
            
            return True
            
        
        return False
        
    
    def Matches( self, text ):
        
        try:
            
            self.Test( text )
            
            return True
            
        except HydrusExceptions.StringMatchException:
            
            return False
            
        
    
    def SetMaxChars( self, max_chars ):
        
        self._max_chars = max_chars
        
    
    def SetMinChars( self, min_chars ):
        
        self._min_chars = min_chars
        
    
    def Test( self, text ):
        
        if isinstance( text, bytes ):
            
            raise HydrusExceptions.StringMatchException( 'Got a bytes value in a string match!' )
            
        
        text_len = len( text )
        
        presentation_text = '"{}"'.format( text )
        
        if self._min_chars is not None and text_len < self._min_chars:
            
            raise HydrusExceptions.StringMatchException( presentation_text + ' had fewer than ' + HydrusData.ToHumanInt( self._min_chars ) + ' characters' )
            
        
        if self._max_chars is not None and text_len > self._max_chars:
            
            raise HydrusExceptions.StringMatchException( presentation_text + ' had more than ' + HydrusData.ToHumanInt( self._max_chars ) + ' characters' )
            
        
        if self._match_type == STRING_MATCH_FIXED:
            
            if text != self._match_value:
                
                raise HydrusExceptions.StringMatchException( presentation_text + ' did not exactly match "' + self._match_value + '"' )
                
            
        elif self._match_type in ( STRING_MATCH_FLEXIBLE, STRING_MATCH_REGEX ):
            
            if self._match_type == STRING_MATCH_FLEXIBLE:
                
                if self._match_value == ALPHA:
                    
                    r = '^[a-zA-Z]+$'
                    fail_reason = ' had non-alpha characters'
                    
                elif self._match_value == ALPHANUMERIC:
                    
                    r = '^[a-zA-Z\\d]+$'
                    fail_reason = ' had non-alphanumeric characters'
                    
                elif self._match_value == NUMERIC:
                    
                    r = '^\\d+$'
                    fail_reason = ' had non-numeric characters'
                    
                
            elif self._match_type == STRING_MATCH_REGEX:
                
                r = self._match_value
                
                fail_reason = ' did not match "' + r + '"'
                
            
            try:
                
                result = re.search( r, text )
                
            except Exception as e:
                
                raise HydrusExceptions.StringMatchException( 'That regex did not work! ' + str( e ) )
                
            
            if result is None:
                
                raise HydrusExceptions.StringMatchException( presentation_text + fail_reason )
                
            
        elif self._match_type == STRING_MATCH_ANY:
            
            pass
            
        
    
    def ToTuple( self ):
        
        return ( self._match_type, self._match_value, self._min_chars, self._max_chars, self._example_string )
        
    
    def ToString( self, simple = False, with_type = False ) -> str:
        
        if simple:
            
            return 'filter'
            
        
        result = ''
        
        if self._min_chars is None:
            
            if self._max_chars is None:
                
                result += 'any number of '
                
            else:
                
                result += 'at most ' + str( self._max_chars ) + ' '
                
            
        else:
            
            if self._max_chars is None:
                
                result += 'at least ' + str( self._min_chars ) + ' '
                
            else:
                
                result += 'between ' + str( self._min_chars ) + ' and ' + str( self._max_chars ) + ' '
                
            
        
        show_example = True
        
        if self._match_type == STRING_MATCH_ANY:
            
            result += 'characters'
            
            show_example = False
            
        elif self._match_type == STRING_MATCH_FIXED:
            
            result = self._match_value
            
            show_example = False
            
        elif self._match_type == STRING_MATCH_FLEXIBLE:
            
            if self._match_value == ALPHA:
                
                result += 'alphabetical characters'
                
            elif self._match_value == ALPHANUMERIC:
                
                result += 'alphanumeric characters'
                
            elif self._match_value == NUMERIC:
                
                result += 'numeric characters'
                
            
        elif self._match_type == STRING_MATCH_REGEX:
            
            result += 'characters, matching regex "' + self._match_value + '"'
            
        
        if show_example:
            
            result += ', such as "' + self._example_string + '"'
            
        
        if with_type:
            
            result = 'MATCH: {}'.format( result )
            
        
        return result
        
    
HydrusSerialisable.SERIALISABLE_TYPES_TO_OBJECT_TYPES[ HydrusSerialisable.SERIALISABLE_TYPE_STRING_MATCH ] = StringMatch

class StringSlicer( StringProcessingStep ):
    
    SERIALISABLE_TYPE = HydrusSerialisable.SERIALISABLE_TYPE_STRING_SLICER
    SERIALISABLE_NAME = 'String Selector/Slicer'
    SERIALISABLE_VERSION = 1
    
    def __init__( self, index_start: typing.Optional[ int ] = None, index_end: typing.Optional[ int ] = None ):
        
        StringProcessingStep.__init__( self )
        
        self._index_start = index_start
        self._index_end = index_end
        
    
    def _GetSerialisableInfo( self ):
        
        return ( self._index_start, self._index_end )
        
    
    def _InitialiseFromSerialisableInfo( self, serialisable_info ):
        
        ( self._index_start, self._index_end ) = serialisable_info
        
    
    def GetIndexStartEnd( self ) -> typing.Tuple[ typing.Optional[ int ], typing.Optional[ int ] ]:
        
        return ( self._index_start, self._index_end )
        
    
    def MakesChanges( self ) -> bool:
        
        return self._index_start is not None or self._index_end is not None
        
    
    def SelectsNothingEver( self ) -> bool:
        
        if self._index_end == 0:
            
            return True
            
        
        if self._index_start is None or self._index_end is None:
            
            return False
            
        
        both_positive = self._index_start >= 0 and self._index_end >= 0
        both_negative = self._index_start < 0 and self._index_end < 0
        
        if both_positive or both_negative:
            
            if self._index_start >= self._index_end:
                
                return True
                
            
        
        return False
        
    
    def SelectsOne( self ) -> bool:
        
        if self.SelectsNothingEver():
            
            return False
            
        
        if self._index_start == -1 and self._index_end is None:
            
            return True
            
        
        if self._index_start is None or self._index_end is None:
            
            return False
            
        
        both_positive = self._index_start >= 0 and self._index_end >= 0
        both_negative = self._index_start < 0 and self._index_end < 0
        
        return ( both_positive or both_negative ) and self._index_start == self._index_end - 1
        
    
    def Slice( self, texts: typing.Sequence[ str ] ) -> typing.List[ str ]:
        
        try:
            
            if self._index_start is None and self._index_end is None:
                
                return list( texts )
                
            elif self._index_end is None:
                
                return texts[ self._index_start : ]
                
            elif self._index_start is None:
                
                return texts[ : self._index_end ]
                
            else:
                
                return texts[ self._index_start : self._index_end ]
                
            
        except IndexError as e:
            
            return []
            
        
    
    def ToString( self, simple = False, with_type = False ) -> str:
        
        if simple:
            
            return 'selector/slicer'
            
        
        if self.SelectsNothingEver():
            
            result = 'selecting nothing'
            
        elif self.SelectsOne():
            
            result = 'selecting the {} string'.format( HydrusData.ConvertIndexToPrettyOrdinalString( self._index_start ) )
            
        elif self._index_start is None and self._index_end is None:
            
            result = 'selecting everything'
            
        elif self._index_end is None:
            
            result = 'selecting the {} string and onwards'.format( HydrusData.ConvertIndexToPrettyOrdinalString( self._index_start ) )
            
        elif self._index_start is None:
            
            result = 'selecting up to and including the {} string'.format( HydrusData.ConvertIndexToPrettyOrdinalString( self._index_end - 1 ) )
            
        else:
            
            result = 'selecting the {} string up to and including the {} string'.format( HydrusData.ConvertIndexToPrettyOrdinalString( self._index_start ), HydrusData.ConvertIndexToPrettyOrdinalString( self._index_end - 1 ) )
            
        
        if with_type:
            
            if self.SelectsOne():
                
                result = 'SELECT: {}'.format( result )
                
            else:
                
                result = 'SLICE: {}'.format( result )
                
            
        
        return result
        
    
HydrusSerialisable.SERIALISABLE_TYPES_TO_OBJECT_TYPES[ HydrusSerialisable.SERIALISABLE_TYPE_STRING_SLICER ] = StringSlicer

sort_str_enum = {
    CONTENT_PARSER_SORT_TYPE_NONE : 'no sorting',
    CONTENT_PARSER_SORT_TYPE_LEXICOGRAPHIC : 'strict lexicographic',
    CONTENT_PARSER_SORT_TYPE_HUMAN_SORT : 'human sort'
}

class StringSorter( StringProcessingStep ):
    
    SERIALISABLE_TYPE = HydrusSerialisable.SERIALISABLE_TYPE_STRING_SORTER
    SERIALISABLE_NAME = 'String Sorter'
    SERIALISABLE_VERSION = 1
    
    def __init__( self, sort_type: int = CONTENT_PARSER_SORT_TYPE_HUMAN_SORT, asc: bool = False, regex: typing.Optional[ str ] = None ):
        
        StringProcessingStep.__init__( self )
        
        self._sort_type = sort_type
        self._asc = asc
        self._regex = regex
        
    
    def _GetSerialisableInfo( self ):
        
        return ( self._sort_type, self._asc, self._regex )
        
    
    def _InitialiseFromSerialisableInfo( self, serialisable_info ):
        
        ( self._sort_type, self._asc, self._regex ) = serialisable_info
        
    
    def GetAscending( self ) -> bool:
        
        return self._asc
        
    
    def GetRegex( self ) -> typing.Optional[ str ]:
        
        return self._regex
        
    
    def GetSortType( self ) -> int:
        
        return self._sort_type
        
    
    def MakesChanges( self ) -> bool:
        
        return True
        
    
    def Sort( self, texts: typing.Sequence[ str ] ) -> typing.List[ str ]:
        
        try:
            
            texts = list( texts )
            
            data_convert = lambda d_s: d_s
            invalid_data_convert_texts = []
            
            if self._regex is not None:
                
                re_job = re.compile( self._regex )
                
                def d( d_s ):
                    
                    m = re_job.search( d_s )
                    
                    if m is None:
                        
                        return ''
                        
                    else:
                        
                        return m.group()
                        
                    
                
                data_convert = d
                
                invalid_data_convert_texts = [ text for text in texts if data_convert( text ) == '' ]
                texts = [ text for text in texts if data_convert( text ) != '' ]
                
            
            sort_convert = lambda s: s
            
            if self._sort_type == CONTENT_PARSER_SORT_TYPE_HUMAN_SORT:
                
                sort_convert = HydrusData.HumanTextSortKey
                
            
            key = lambda k_s: sort_convert( data_convert( k_s ) )
            
            reverse = not self._asc
            
            texts.sort( key = key, reverse = reverse )
            
            invalid_data_convert_texts.sort( key = sort_convert, reverse = reverse )
            
            texts.extend( invalid_data_convert_texts )
            
            return texts
            
        except Exception as e:
            
            raise HydrusExceptions.StringSortException( e )
            
        
    
    def ToString( self, simple = False, with_type = False ) -> str:
        
        if simple:
            
            return 'sorter'
            
        
        result = 'sorting {} ({})'.format( sort_str_enum[ self._sort_type ], 'ascending' if self._asc else 'descending' )
        
        if self._regex is not None:
            
            result = '{} (with regex)'.format( result )
            
        
        if with_type:
            
            result = 'SORT: {}'.format( result )
            
        
        return result
        
    
HydrusSerialisable.SERIALISABLE_TYPES_TO_OBJECT_TYPES[ HydrusSerialisable.SERIALISABLE_TYPE_STRING_SORTER ] = StringSorter

class StringSplitter( StringProcessingStep ):
    
    SERIALISABLE_TYPE = HydrusSerialisable.SERIALISABLE_TYPE_STRING_SPLITTER
    SERIALISABLE_NAME = 'String Splitter'
    SERIALISABLE_VERSION = 1
    
    def __init__( self, separator: str = ',', max_splits: typing.Optional[ int ] = None ):
        
        StringProcessingStep.__init__( self )
        
        self._separator = separator
        self._max_splits = max_splits
        
    
    def _GetSerialisableInfo( self ):
        
        return ( self._separator, self._max_splits )
        
    
    def _InitialiseFromSerialisableInfo( self, serialisable_info ):
        
        ( self._separator, self._max_splits ) = serialisable_info
        
    
    def GetMaxSplits( self ):
        
        return self._max_splits
        
    
    def GetSeparator( self ):
        
        return self._separator
        
    
    def MakesChanges( self ) -> bool:
        
        return True
        
    
    def Split( self, text: str ) -> typing.List[ str ]:
        
        if isinstance( text, bytes ):
            
            raise HydrusExceptions.StringSplitterException( 'Got a bytes value in a string splitter!' )
            
        
        if self._max_splits is None:
            
            results = text.split( self._separator )
            
        else:
            
            results = text.split( self._separator, self._max_splits )
            
        
        return [ result for result in results if result != '' ]
        
    
    def ToString( self, simple = False, with_type = False ) -> str:
        
        if simple:
            
            return 'splitter'
            
        
        result = 'splitting by "{}"'.format( self._separator )
        
        if self._max_splits is not None:
            
            result = '{}, at most {} times'.format( result, HydrusData.ToHumanInt( self._max_splits ) )
            
        
        if with_type:
            
            result = 'SPLIT: {}'.format( result )
            
        
        return result
        
    
HydrusSerialisable.SERIALISABLE_TYPES_TO_OBJECT_TYPES[ HydrusSerialisable.SERIALISABLE_TYPE_STRING_SPLITTER ] = StringSplitter

class StringProcessor( HydrusSerialisable.SerialisableBase ):
    
    SERIALISABLE_TYPE = HydrusSerialisable.SERIALISABLE_TYPE_STRING_PROCESSOR
    SERIALISABLE_NAME = 'String Processor'
    SERIALISABLE_VERSION = 1
    
    def __init__( self ):
        
        StringProcessingStep.__init__( self )
        
        self._processing_steps = []
        
    
    def _GetSerialisableInfo( self ):
        
        return HydrusSerialisable.SerialisableList( self._processing_steps ).GetSerialisableTuple()
        
    
    def _InitialiseFromSerialisableInfo( self, serialisable_info ):
        
        serialisable_processing_steps = serialisable_info
        
        self._processing_steps = list( HydrusSerialisable.CreateFromSerialisableTuple( serialisable_processing_steps ) )
        
    
    def GetProcessingSteps( self ):
        
        return list( self._processing_steps )
        
    
    def GetProcessingStrings( self ):
        
        proc_strings = []
        
        for processing_step in self._processing_steps:
            
            if isinstance( processing_step, StringConverter ):
                
                proc_strings.extend( processing_step.GetConversionStrings() )
                
            else:
                
                proc_strings.append( processing_step.ToString() )
                
            
        
        return proc_strings
        
    
    def ProcessStrings( self, starting_strings: typing.Iterable[ str ], max_steps_allowed = None, no_slicing = False ) -> typing.List[ str ]:
        
        current_strings = list( starting_strings )
        
        for ( i, processing_step ) in enumerate( self._processing_steps ):
            
            if max_steps_allowed is not None and i >= max_steps_allowed:
                
                break
                
            
            if isinstance( processing_step, StringSorter ):
                
                try:
                    
                    next_strings = processing_step.Sort( current_strings )
                    
                except HydrusExceptions.StringSortException:
                    
                    next_strings = current_strings
                    
                
            elif isinstance( processing_step, StringSlicer ):
                
                if no_slicing:
                    
                    next_strings = current_strings
                    
                else:
                    
                    try:
                        
                        next_strings = processing_step.Slice( current_strings )
                        
                    except:
                        
                        next_strings = current_strings
                        
                    
                
            else:
                
                next_strings = []
                
                for current_string in current_strings:
                    
                    if isinstance( processing_step, StringConverter ):
                        
                        if isinstance( current_string, bytes ):
                            
                            continue
                            
                        
                        try:
                            
                            next_string = processing_step.Convert( current_string )
                            
                            next_strings.append( next_string )
                            
                        except HydrusExceptions.StringConvertException:
                            
                            continue
                            
                        
                    elif isinstance( processing_step, StringMatch ):
                        
                        try:
                            
                            if processing_step.Matches( current_string ):
                                
                                next_strings.append( current_string )
                                
                            
                        except HydrusExceptions.StringMatchException:
                            
                            continue
                            
                        
                    elif isinstance( processing_step, StringSplitter ):
                        
                        if isinstance( current_string, bytes ):
                            
                            continue
                            
                        
                        try:
                            
                            split_strings = processing_step.Split( current_string )
                            
                            next_strings.extend( split_strings )
                            
                        except HydrusExceptions.StringSplitterException:
                            
                            continue
                            
                        
                    
                
            
            current_strings = next_strings
            
        
        return current_strings
        
    
    def SetProcessingSteps( self, processing_steps: typing.List[ StringProcessingStep ] ):
        
        self._processing_steps = list( processing_steps )
        
    
    def ToString( self ) -> str:
        
        if len( self._processing_steps ) == 0:
            
            return 'no string processing'
            
        else:
            
            components = []
            
            if True in ( isinstance( ps, StringConverter ) for ps in self._processing_steps ):
                
                components.append( 'conversion' )
                
            
            if True in ( isinstance( ps, StringMatch ) for ps in self._processing_steps ):
                
                components.append( 'filtering' )
                
            
            if True in ( isinstance( ps, StringSplitter ) for ps in self._processing_steps ):
                
                components.append( 'splitting' )
                
            
            if True in ( isinstance( ps, StringSorter ) for ps in self._processing_steps ):
                
                components.append( 'sorting' )
                
            
            if True in ( isinstance( ps, StringSlicer ) for ps in self._processing_steps ):
                
                components.append( 'selecting/slicing' )
                
            
            return 'some {}'.format( ', '.join( components ) )
            
        
    
HydrusSerialisable.SERIALISABLE_TYPES_TO_OBJECT_TYPES[ HydrusSerialisable.SERIALISABLE_TYPE_STRING_PROCESSOR ] = StringProcessor
