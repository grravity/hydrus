import re
import typing

from qtpy import QtCore as QC
from qtpy import QtWidgets as QW

from hydrus.core import HydrusConstants as HC
from hydrus.core import HydrusData
from hydrus.core import HydrusExceptions

from hydrus.client import ClientConstants as CC
from hydrus.client import ClientParsing
from hydrus.client.gui import ClientGUIDialogsQuick
from hydrus.client.gui import ClientGUIFunctions
from hydrus.client.gui import ClientGUIScrolledPanels
from hydrus.client.gui import ClientGUITopLevelWindowsPanels
from hydrus.client.gui import QtPorting as QP
from hydrus.client.gui.lists import ClientGUIListBoxes
from hydrus.client.gui.lists import ClientGUIListConstants as CGLC
from hydrus.client.gui.lists import ClientGUIListCtrl
from hydrus.client.gui.widgets import ClientGUICommon

NO_RESULTS_TEXT = 'no results'

class MultilineStringConversionTestPanel( QW.QWidget ):
    
    textSelected = QC.Signal( str )
    
    def __init__( self, parent: QW.QWidget, string_processor: ClientParsing.StringProcessor ):
        
        QW.QWidget.__init__( self, parent )
        
        self._string_processor = string_processor
        
        self._test_data = QW.QListWidget( self )
        
        self._test_data.setSelectionMode( QW.QListWidget.SingleSelection )
        
        self._result_data = QW.QListWidget( self )
        
        self._result_data.setSelectionMode( QW.QListView.NoSelection )
        
        #
        
        left_vbox = QP.VBoxLayout()
        right_vbox = QP.VBoxLayout()
        
        QP.AddToLayout( left_vbox, ClientGUICommon.BetterStaticText( self, label = 'starting strings' ), CC.FLAGS_CENTER )
        QP.AddToLayout( left_vbox, self._test_data, CC.FLAGS_EXPAND_BOTH_WAYS )
        QP.AddToLayout( right_vbox, ClientGUICommon.BetterStaticText( self, label = 'processed strings' ), CC.FLAGS_CENTER )
        QP.AddToLayout( right_vbox, self._result_data, CC.FLAGS_EXPAND_BOTH_WAYS )
        
        hbox = QP.HBoxLayout()
        
        QP.AddToLayout( hbox, left_vbox, CC.FLAGS_EXPAND_SIZER_BOTH_WAYS )
        QP.AddToLayout( hbox, right_vbox, CC.FLAGS_EXPAND_SIZER_BOTH_WAYS )
        
        self.setLayout( hbox )
        
        self._test_data.itemSelectionChanged.connect( self.EventSelection )
        
    
    def _GetStartingTexts( self ):
        
        return [ self._test_data.item( i ).data( QC.Qt.UserRole ) for i in range( self._test_data.count() ) ]
        
    
    def _UpdateResults( self ):
        
        texts = self._GetStartingTexts()
        
        try:
            
            results = self._string_processor.ProcessStrings( texts )
            
        except HydrusExceptions.ParseException as e:
            
            results = [ 'error in processing: {}'.format( e ) ]
            
        
        self._result_data.clear()
        
        for ( insertion_index, result ) in enumerate( results ):
            
            item = QW.QListWidgetItem()
            
            item.setText( result )
            item.setData( QC.Qt.UserRole, result )
            
            self._result_data.insertItem( insertion_index, item )
            
        
    
    def EventSelection( self ):
        
        items = self._test_data.selectedItems()
        
        if len( items ) == 1:
            
            ( list_widget_item, ) = items
            
            text = list_widget_item.data( QC.Qt.UserRole )
            
            self.textSelected.emit( text )
            
        
    
    def GetResultTexts( self, step_index ):
        
        texts = self._GetStartingTexts()
        
        try:
            
            results = self._string_processor.ProcessStrings( texts, max_steps_allowed = step_index + 1 )
            
        except:
            
            results = []
            
        
        return results
        
    
    def SetStringProcessor( self, string_processor: ClientParsing.StringProcessor ):
        
        self._string_processor = string_processor
        
        self._UpdateResults()
        
    
    def SetTestData( self, test_data: ClientParsing.ParsingTestData ):
        
        self._test_data.clear()
        
        for ( insertion_index, text ) in enumerate( test_data.texts ):
            
            item = QW.QListWidgetItem()
            
            item.setText( text )
            item.setData( QC.Qt.UserRole, text )
            
            self._test_data.insertItem( insertion_index, item )
            
        
        self._UpdateResults()
        
        if len( test_data.texts ) > 0:
            
            self._test_data.item( 0 ).setSelected( False )
            self._test_data.item( 0 ).setSelected( True )
            
            #self.textSelected.emit( self._test_data.item( 0 ).data( QC.Qt.UserRole ) )
            
        
    
class SingleStringConversionTestPanel( QW.QWidget ):
    
    def __init__( self, parent: QW.QWidget, string_processor: ClientParsing.StringProcessor ):
        
        QW.QWidget.__init__( self, parent )
        
        self._string_processor = string_processor
        
        self._example_string = QW.QLineEdit( self )
        
        self._example_results = ClientGUICommon.BetterNotebook( self )
        
        #
        
        vbox = QP.VBoxLayout()
        
        QP.AddToLayout( vbox, ClientGUICommon.BetterStaticText( self, label = 'single example string' ), CC.FLAGS_CENTER )
        QP.AddToLayout( vbox, self._example_string, CC.FLAGS_EXPAND_SIZER_PERPENDICULAR )
        QP.AddToLayout( vbox, ClientGUICommon.BetterStaticText( self, label = 'results for each step' ), CC.FLAGS_CENTER )
        QP.AddToLayout( vbox, self._example_results, CC.FLAGS_EXPAND_BOTH_WAYS )
        
        self.setLayout( vbox )
        
        self._example_string.textChanged.connect( self._UpdateResults )
        
    
    def _UpdateResults( self ):
        
        processing_steps = self._string_processor.GetProcessingSteps()
        
        current_selected_index = self._example_results.currentIndex()
        
        self._example_results.DeleteAllPages()
        
        example_string = self._example_string.text()
        
        stop_now = False
        
        for i in range( len( processing_steps ) ):
            
            if isinstance( processing_steps[i], ClientParsing.StringSlicer ):
                
                continue
                
            
            try:
                
                results = self._string_processor.ProcessStrings( [ example_string ], max_steps_allowed = i + 1, no_slicing = True )
                
            except Exception as e:
                
                results = [ 'error: {}'.format( str( e ) ) ]
                
                stop_now = True
                
            
            results_list = QW.QListWidget( self._example_results )
            results_list.setSelectionMode( QW.QListWidget.NoSelection )  
            
            if len( results ) == 0:
                
                results_list.addItem( NO_RESULTS_TEXT )
                
                stop_now = True
                
            else:
                
                for result in results:
                    
                    if not isinstance( result, str ):
                        
                        result = repr( result )
                        
                    
                    results_list.addItem( result )
                    
                
            
            tab_label = '{} ({})'.format( processing_steps[i].ToString( simple = True ), HydrusData.ToHumanInt( len( results ) ) )
            
            self._example_results.addTab( results_list, tab_label )
            
            if stop_now:
                
                break
                
            
        
        if self._example_results.count() > current_selected_index:
            
            self._example_results.setCurrentIndex( current_selected_index )
            
        
    
    def GetResultText( self, step_index: int ):
        
        example_text = self._example_string.text()
        
        if 0 < step_index < self._example_results.count() + 1:
            
            try:
                
                t = self._example_results.widget( step_index - 1 ).item( 0 ).text()
                
                if t != NO_RESULTS_TEXT:
                    
                    example_text = t
                    
                
            except:
                
                pass
                
            
        
        return example_text
        
    
    def GetStartingText( self ):
        
        return self._example_string.text()
        
    
    def SetStringProcessor( self, string_processor: ClientParsing.StringProcessor ):
        
        self._string_processor = string_processor
        
        if True in ( isinstance( processing_step, ClientParsing.StringSlicer ) for processing_step in self._string_processor.GetProcessingSteps() ):
            
            self.setToolTip( 'String Slicing is ignored here.' )
            
        else:
            
            self.setToolTip( '' )
            
        
        self._UpdateResults()
        
    
    def SetExampleString( self, example_string: str ):
        
        self._example_string.setText( example_string )
        
        self._UpdateResults()
        
    
class EditStringConverterPanel( ClientGUIScrolledPanels.EditPanel ):
    
    def __init__( self, parent: QW.QWidget, string_converter: ClientParsing.StringConverter, example_string_override = None ):
        
        ClientGUIScrolledPanels.EditPanel.__init__( self, parent )
        
        conversions_panel = ClientGUIListCtrl.BetterListCtrlPanel( self )
        
        self._conversions = ClientGUIListCtrl.BetterListCtrl( conversions_panel, CGLC.COLUMN_LIST_STRING_CONVERTER_CONVERSIONS.ID, 7, self._ConvertConversionToListCtrlTuples, delete_key_callback = self._DeleteConversion, activation_callback = self._EditConversion )
        
        conversions_panel.SetListCtrl( self._conversions )
        
        conversions_panel.AddButton( 'add', self._AddConversion )
        conversions_panel.AddButton( 'edit', self._EditConversion, enabled_only_on_selection = True )
        conversions_panel.AddDeleteButton()
        
        conversions_panel.AddSeparator()
        
        conversions_panel.AddButton( 'move up', self._MoveUp, enabled_check_func = self._CanMoveUp )
        conversions_panel.AddButton( 'move down', self._MoveDown, enabled_check_func = self._CanMoveDown )
        
        self._example_string = QW.QLineEdit( self )
        
        #
        
        self._conversions.AddDatas( [ ( i + 1, conversion_type, data ) for ( i, ( conversion_type, data ) ) in enumerate( string_converter.conversions ) ] )
        
        if example_string_override is None:
            
            self._example_string.setText( string_converter.example_string )
            
        else:
            
            self._example_string.setText( example_string_override )
            
        
        self._conversions.UpdateDatas() # to refresh, now they are all in the list
        
        self._conversions.Sort()
        
        #
        
        rows = []
        
        rows.append( ( 'example string: ', self._example_string ) )
        
        gridbox = ClientGUICommon.WrapInGrid( self, rows )
        
        vbox = QP.VBoxLayout()
        
        QP.AddToLayout( vbox, conversions_panel, CC.FLAGS_EXPAND_BOTH_WAYS )
        QP.AddToLayout( vbox, gridbox, CC.FLAGS_EXPAND_SIZER_PERPENDICULAR )
        
        self.widget().setLayout( vbox )
        
        #
        
        self._example_string.textChanged.connect( self.EventUpdate )
        
    
    def _AddConversion( self ):
        
        conversion_type = ClientParsing.STRING_CONVERSION_APPEND_TEXT
        data = 'extra text'
        
        try:
            
            string_converter = self._GetValue()
            
            example_string_at_this_point = string_converter.Convert( self._example_string.text() )
            
        except:
            
            example_string_at_this_point = self._example_string.text()
            
        
        with ClientGUITopLevelWindowsPanels.DialogEdit( self, 'edit conversion', frame_key = 'deeply_nested_dialog' ) as dlg:
            
            panel = self._ConversionPanel( dlg, conversion_type, data, example_string_at_this_point )
            
            dlg.SetPanel( panel )
            
            if dlg.exec() == QW.QDialog.Accepted:
                
                number = self._conversions.topLevelItemCount() + 1
                
                ( conversion_type, data ) = panel.GetValue()
                
                enumerated_conversion = ( number, conversion_type, data )
                
                self._conversions.AddDatas( ( enumerated_conversion, ) )
                
            
        
        self._conversions.UpdateDatas() # need to refresh string after the insertion, so the new row can be included in the parsing calcs
        
        self._conversions.Sort()
        
    
    def _CanMoveDown( self ):
        
        selected_data = self._conversions.GetData( only_selected = True )
        
        if len( selected_data ) == 1:
            
            ( number, conversion_type, data ) = selected_data[0]
            
            if number < self._conversions.topLevelItemCount():
                
                return True
                
            
        
        return False
        
    
    def _CanMoveUp( self ):
        
        selected_data = self._conversions.GetData( only_selected = True )
        
        if len( selected_data ) == 1:
            
            ( number, conversion_type, data ) = selected_data[0]
            
            if number > 1:
                
                return True
                
            
        
        return False
        
    
    def _ConvertConversionToListCtrlTuples( self, conversion ):
        
        ( number, conversion_type, data ) = conversion
        
        pretty_number = HydrusData.ToHumanInt( number )
        pretty_conversion = ClientParsing.StringConverter.ConversionToString( ( conversion_type, data ) )
        
        string_converter = self._GetValue()
        
        try:
            
            pretty_result = ClientParsing.MakeParsedTextPretty( string_converter.Convert( self._example_string.text(), number ) )
            
        except HydrusExceptions.StringConvertException as e:
            
            pretty_result = str( e )
            
        
        display_tuple = ( pretty_number, pretty_conversion, pretty_result )
        sort_tuple = ( number, number, number )
        
        return ( display_tuple, sort_tuple )
        
    
    def _DeleteConversion( self ):
        
        if len( self._conversions.GetData( only_selected = True ) ) > 0:
            
            text = 'Delete all selected?'
            
            result = ClientGUIDialogsQuick.GetYesNo( self, text )
            
            if result == QW.QDialog.Accepted:
                
                self._conversions.DeleteSelected()
                
            
        
        # now we need to shuffle up any missing numbers
        
        num_rows = self._conversions.topLevelItemCount()
        
        i = 1
        search_i = i
        
        while i <= num_rows:
            
            try:
                
                conversion = self._GetConversion( search_i )
                
                if search_i != i:
                    
                    self._conversions.DeleteDatas( ( conversion, ) )
                    
                    ( search_i, conversion_type, data ) = conversion
                    
                    conversion = ( i, conversion_type, data )
                    
                    self._conversions.AddDatas( ( conversion, ) )
                    
                
                i += 1
                search_i = i
                
            except HydrusExceptions.DataMissing:
                
                search_i += 1
                
            
        
        self._conversions.UpdateDatas()
        
        self._conversions.Sort()
        
    
    def _EditConversion( self ):
        
        selected_data = self._conversions.GetData( only_selected = True )
        
        for enumerated_conversion in selected_data:
            
            ( number, conversion_type, data ) = enumerated_conversion
            
            try:
                
                string_converter = self._GetValue()
                
                example_string_at_this_point = string_converter.Convert( self._example_string.text(), number - 1 )
                
            except:
                
                example_string_at_this_point = self._example_string.text()
                
            
            with ClientGUITopLevelWindowsPanels.DialogEdit( self, 'edit conversion', frame_key = 'deeply_nested_dialog' ) as dlg:
                
                panel = self._ConversionPanel( dlg, conversion_type, data, example_string_at_this_point )
                
                dlg.SetPanel( panel )
                
                if dlg.exec() == QW.QDialog.Accepted:
                    
                    self._conversions.DeleteDatas( ( enumerated_conversion, ) )
                    
                    ( conversion_type, data ) = panel.GetValue()
                    
                    enumerated_conversion = ( number, conversion_type, data )
                    
                    self._conversions.AddDatas( ( enumerated_conversion, ) )
                    
                else:
                    
                    break
                    
                
            
        
        self._conversions.UpdateDatas()
        
        self._conversions.Sort()
        
    
    def _GetConversion( self, desired_number ):
        
        for conversion in self._conversions.GetData():
            
            ( number, conversion_type, data ) = conversion
            
            if number == desired_number:
                
                return conversion
                
            
        
        raise HydrusExceptions.DataMissing()
        
    
    def _GetValue( self ):
        
        enumerated_conversions = sorted( self._conversions.GetData() )
        
        conversions = [ ( conversion_type, data ) for ( number, conversion_type, data ) in enumerated_conversions ]
        
        example_string = self._example_string.text()
        
        string_converter = ClientParsing.StringConverter( conversions, example_string )
        
        return string_converter
        
    
    def _MoveDown( self ):
        
        selected_conversion = self._conversions.GetData( only_selected = True )[0]
        
        ( number, conversion_type, data ) = selected_conversion
        
        swap_conversion = self._GetConversion( number + 1 )
        
        self._SwapConversions( selected_conversion, swap_conversion )
        
        self._conversions.UpdateDatas()
        
        self._conversions.Sort()
        
    
    def _MoveUp( self ):
        
        selected_conversion = self._conversions.GetData( only_selected = True )[0]
        
        ( number, conversion_type, data ) = selected_conversion
        
        swap_conversion = self._GetConversion( number - 1 )
        
        self._SwapConversions( selected_conversion, swap_conversion )
        
        self._conversions.UpdateDatas()
        
        self._conversions.Sort()
        
    
    def _SwapConversions( self, one, two ):
        
        selected_data = self._conversions.GetData( only_selected = True )
        
        one_selected = one in selected_data
        two_selected = two in selected_data
        
        self._conversions.DeleteDatas( ( one, two ) )
        
        ( number_1, conversion_type_1, data_1 ) = one
        ( number_2, conversion_type_2, data_2 ) = two
        
        one = ( number_2, conversion_type_1, data_1 )
        two = ( number_1, conversion_type_2, data_2 )
        
        self._conversions.AddDatas( ( one, two ) )
        
        if one_selected:
            
            self._conversions.SelectDatas( ( one, ) )
            
        
        if two_selected:
            
            self._conversions.SelectDatas( ( two, ) )
            
        
    
    def EventUpdate( self, text ):
        
        self._conversions.UpdateDatas()
        
    
    def GetValue( self ):
        
        string_converter = self._GetValue()
        
        try:
            
            string_converter.Convert( self._example_string.text() )
            
        except HydrusExceptions.StringConvertException:
            
            raise HydrusExceptions.VetoException( 'Please enter an example text that can be converted!' )
            
        
        return string_converter
        
    
    class _ConversionPanel( ClientGUIScrolledPanels.EditPanel ):
        
        def __init__( self, parent, conversion_type, data, example_text ):
            
            ClientGUIScrolledPanels.EditPanel.__init__( self, parent )
            
            self._control_panel = ClientGUICommon.StaticBox( self, 'string conversion step' )
            
            self._conversion_type = ClientGUICommon.BetterChoice( self._control_panel )
            
            for t_type in ( ClientParsing.STRING_CONVERSION_REMOVE_TEXT_FROM_BEGINNING, ClientParsing.STRING_CONVERSION_REMOVE_TEXT_FROM_END, ClientParsing.STRING_CONVERSION_CLIP_TEXT_FROM_BEGINNING, ClientParsing.STRING_CONVERSION_CLIP_TEXT_FROM_END, ClientParsing.STRING_CONVERSION_PREPEND_TEXT, ClientParsing.STRING_CONVERSION_APPEND_TEXT, ClientParsing.STRING_CONVERSION_ENCODE, ClientParsing.STRING_CONVERSION_DECODE, ClientParsing.STRING_CONVERSION_REVERSE, ClientParsing.STRING_CONVERSION_REGEX_SUB, ClientParsing.STRING_CONVERSION_DATE_DECODE, ClientParsing.STRING_CONVERSION_DATE_ENCODE, ClientParsing.STRING_CONVERSION_INTEGER_ADDITION ):
                
                self._conversion_type.addItem( ClientParsing.conversion_type_str_lookup[ t_type ], t_type )
                
            
            self._data_text = QW.QLineEdit( self._control_panel )
            self._data_number = QP.MakeQSpinBox( self._control_panel, min=0, max=65535 )
            self._data_encoding = ClientGUICommon.BetterChoice( self._control_panel )
            self._data_decoding = ClientGUICommon.BetterChoice( self._control_panel )
            self._data_regex_repl = QW.QLineEdit( self._control_panel )
            self._data_date_link = ClientGUICommon.BetterHyperLink( self._control_panel, 'link to date info', 'https://docs.python.org/3/library/datetime.html#strftime-strptime-behavior' )
            self._data_timezone_decode = ClientGUICommon.BetterChoice( self._control_panel )
            self._data_timezone_encode = ClientGUICommon.BetterChoice( self._control_panel )
            self._data_timezone_offset = QP.MakeQSpinBox( self._control_panel, min=-86400, max=86400 )
            
            for e in ( 'hex', 'base64', 'url percent encoding', 'unicode escape characters', 'html entities' ):
                
                self._data_encoding.addItem( e, e )
                
            
            for e in ( 'url percent encoding', 'unicode escape characters', 'html entities' ):
                
                self._data_decoding.addItem( e, e )
                
            
            self._data_timezone_decode.addItem( 'UTC', HC.TIMEZONE_GMT )
            self._data_timezone_decode.addItem( 'Local', HC.TIMEZONE_LOCAL )
            self._data_timezone_decode.addItem( 'Offset', HC.TIMEZONE_OFFSET )
            
            self._data_timezone_encode.addItem( 'UTC', HC.TIMEZONE_GMT )
            self._data_timezone_encode.addItem( 'Local', HC.TIMEZONE_LOCAL )
            
            #
            
            self._example_panel = ClientGUICommon.StaticBox( self, 'test results' )
            
            self._example_string = QW.QLineEdit( self._example_panel )
            
            min_width = ClientGUIFunctions.ConvertTextToPixelWidth( self._example_string, 96 )
            
            self._example_string.setMinimumWidth( min_width )
            
            self._example_text = example_text
            
            if isinstance( self._example_text, bytes ):
                
                self._example_string.setText( repr( self._example_text ) )
                
            else:
                
                self._example_string.setText( self._example_text )
                
            
            self._example_conversion = QW.QLineEdit( self._example_panel )
            
            self._example_string.setReadOnly( True )
            self._example_conversion.setReadOnly( True )
            
            #
            
            self._conversion_type.SetValue( conversion_type )
            
            self._data_number.setValue( 1 )
            
            #
            
            if conversion_type == ClientParsing.STRING_CONVERSION_ENCODE:
                
                self._data_encoding.SetValue( data )
                
            elif conversion_type == ClientParsing.STRING_CONVERSION_DECODE:
                
                self._data_decoding.SetValue( data )
                
            elif conversion_type == ClientParsing.STRING_CONVERSION_REGEX_SUB:
                
                ( pattern, repl ) = data
                
                self._data_text.setText( pattern )
                self._data_regex_repl.setText( repl )
                
            elif conversion_type == ClientParsing.STRING_CONVERSION_DATE_DECODE:
                
                ( phrase, timezone_type, timezone_offset ) = data
                
                self._data_text.setText( phrase )
                self._data_timezone_decode.SetValue( timezone_type )
                self._data_timezone_offset.setValue( timezone_offset )
                
            elif conversion_type == ClientParsing.STRING_CONVERSION_DATE_ENCODE:
                
                ( phrase, timezone_type ) = data
                
                self._data_text.setText( phrase )
                self._data_timezone_encode.SetValue( timezone_type )
                
            elif data is not None:
                
                if isinstance( data, int ):
                    
                    self._data_number.setValue( data )
                    
                else:
                    
                    self._data_text.setText( data )
                    
                
            
            #
            
            rows = []
            
            # This mess needs to be all replaced with a nice QFormLayout subclass that can do row hide/show
            
            self._data_text_label = ClientGUICommon.BetterStaticText( self, 'string data: ' )
            self._data_number_label = ClientGUICommon.BetterStaticText( self, 'number data: ' )
            self._data_encoding_label = ClientGUICommon.BetterStaticText( self, 'encoding type: ' )
            self._data_decoding_label = ClientGUICommon.BetterStaticText( self, 'decoding type: ' )
            self._data_regex_repl_label = ClientGUICommon.BetterStaticText( self, 'regex replacement: ' )
            self._data_date_link_label = ClientGUICommon.BetterStaticText( self, 'date info: ' )
            self._data_timezone_decode_label = ClientGUICommon.BetterStaticText( self, 'date decode timezone: ' )
            self._data_timezone_offset_label = ClientGUICommon.BetterStaticText( self, 'timezone offset: ' )
            self._data_timezone_encode_label = ClientGUICommon.BetterStaticText( self, 'date encode timezone: ' )
            
            rows.append( ( 'conversion type: ', self._conversion_type ) )
            rows.append( ( self._data_text_label, self._data_text ) )
            rows.append( ( self._data_number_label, self._data_number ) )
            rows.append( ( self._data_encoding_label, self._data_encoding ) )
            rows.append( ( self._data_decoding_label, self._data_decoding ) )
            rows.append( ( self._data_regex_repl_label, self._data_regex_repl ) )
            rows.append( ( self._data_date_link_label, self._data_date_link ) )
            rows.append( ( self._data_timezone_decode_label, self._data_timezone_decode ) )
            rows.append( ( self._data_timezone_offset_label, self._data_timezone_offset ) )
            rows.append( ( self._data_timezone_encode_label, self._data_timezone_encode ) )
            
            self._control_gridbox = ClientGUICommon.WrapInGrid( self._control_panel, rows )
            
            self._control_panel.Add( self._control_gridbox, CC.FLAGS_EXPAND_SIZER_BOTH_WAYS )
            
            #
            
            rows = []
            
            rows.append( ( 'example string: ', self._example_string ) )
            rows.append( ( 'converted string: ', self._example_conversion ) )
            
            self._example_gridbox = ClientGUICommon.WrapInGrid( self._example_panel, rows )
            
            self._example_panel.Add( self._example_gridbox, CC.FLAGS_EXPAND_SIZER_BOTH_WAYS )
            
            #
            
            vbox = QP.VBoxLayout()
            
            QP.AddToLayout( vbox, self._control_panel, CC.FLAGS_EXPAND_SIZER_PERPENDICULAR )
            QP.AddToLayout( vbox, self._example_panel, CC.FLAGS_EXPAND_SIZER_PERPENDICULAR )
            vbox.addStretch( 1 )
            
            self.widget().setLayout( vbox )
            
            self._UpdateDataControls()
            
            #
            
            self._conversion_type.currentIndexChanged.connect( self._UpdateDataControls )
            self._conversion_type.currentIndexChanged.connect( self._UpdateExampleText )
            
            self._data_text.textEdited.connect( self._UpdateExampleText )
            self._data_number.valueChanged.connect( self._UpdateExampleText )
            self._data_encoding.currentIndexChanged.connect( self._UpdateExampleText )
            self._data_decoding.currentIndexChanged.connect( self._UpdateExampleText )
            self._data_regex_repl.textEdited.connect( self._UpdateExampleText )
            self._data_timezone_decode.currentIndexChanged.connect( self._UpdateExampleText )
            self._data_timezone_offset.valueChanged.connect( self._UpdateExampleText )
            self._data_timezone_encode.currentIndexChanged.connect( self._UpdateExampleText )
            
            self._data_timezone_decode.currentIndexChanged.connect( self._UpdateDataControls )
            self._data_timezone_encode.currentIndexChanged.connect( self._UpdateDataControls )
            
            self._UpdateExampleText()
            
        
        def _UpdateDataControls( self ):
            
            self._data_text_label.setVisible( False )
            self._data_number_label.setVisible( False )
            self._data_encoding_label.setVisible( False )
            self._data_decoding_label.setVisible( False )
            self._data_regex_repl_label.setVisible( False )
            self._data_date_link_label.setVisible( False )
            self._data_timezone_decode_label.setVisible( False )
            self._data_timezone_offset_label.setVisible( False )
            self._data_timezone_encode_label.setVisible( False )
            
            self._data_text.setVisible( False )
            self._data_number.setVisible( False )
            self._data_encoding.setVisible( False )
            self._data_decoding.setVisible( False )
            self._data_regex_repl.setVisible( False )
            self._data_date_link.setVisible( False )
            self._data_timezone_decode.setVisible( False )
            self._data_timezone_offset.setVisible( False )
            self._data_timezone_encode.setVisible( False )
            
            conversion_type = self._conversion_type.GetValue()
            
            if conversion_type == ClientParsing.STRING_CONVERSION_ENCODE:
                
                self._data_encoding_label.setVisible( True )
                self._data_encoding.setVisible( True )
                
            elif conversion_type == ClientParsing.STRING_CONVERSION_DECODE:
                
                self._data_decoding_label.setVisible( True )
                self._data_decoding.setVisible( True )
                
            elif conversion_type in ( ClientParsing.STRING_CONVERSION_PREPEND_TEXT, ClientParsing.STRING_CONVERSION_APPEND_TEXT, ClientParsing.STRING_CONVERSION_DATE_DECODE, ClientParsing.STRING_CONVERSION_DATE_ENCODE, ClientParsing.STRING_CONVERSION_REGEX_SUB ):
                
                self._data_text_label.setVisible( True )
                self._data_text.setVisible( True )
                
                data_text_label = 'string data: '
                
                if conversion_type == ClientParsing.STRING_CONVERSION_PREPEND_TEXT:
                    
                    data_text_label = 'text to prepend: '
                    
                elif conversion_type == ClientParsing.STRING_CONVERSION_APPEND_TEXT:
                    
                    data_text_label = 'text to append: '
                    
                elif conversion_type in ( ClientParsing.STRING_CONVERSION_DATE_DECODE, ClientParsing.STRING_CONVERSION_DATE_ENCODE ):
                    
                    self._data_date_link_label.setVisible( True )
                    self._data_date_link.setVisible( True )
                    
                    if conversion_type == ClientParsing.STRING_CONVERSION_DATE_DECODE:
                        
                        data_text_label = 'date decode phrase: '
                        
                        self._data_timezone_decode_label.setVisible( True )
                        self._data_timezone_decode.setVisible( True )
                        
                        if self._data_timezone_decode.GetValue() == HC.TIMEZONE_OFFSET:
                            
                            self._data_timezone_offset_label.setVisible( True )
                            self._data_timezone_offset.setVisible( True )
                            
                        
                    elif conversion_type == ClientParsing.STRING_CONVERSION_DATE_ENCODE:
                        
                        data_text_label = 'date encode phrase: '
                        
                        self._data_timezone_encode_label.setVisible( True )
                        self._data_timezone_encode.setVisible( True )
                        
                    
                elif conversion_type == ClientParsing.STRING_CONVERSION_REGEX_SUB:
                    
                    data_text_label = 'regex pattern: '
                    
                    self._data_regex_repl_label.setVisible( True )
                    self._data_regex_repl.setVisible( True )
                    
                
                self._data_text_label.setText( data_text_label )
                
            elif conversion_type in ( ClientParsing.STRING_CONVERSION_REMOVE_TEXT_FROM_BEGINNING, ClientParsing.STRING_CONVERSION_REMOVE_TEXT_FROM_END, ClientParsing.STRING_CONVERSION_CLIP_TEXT_FROM_BEGINNING, ClientParsing.STRING_CONVERSION_CLIP_TEXT_FROM_END, ClientParsing.STRING_CONVERSION_INTEGER_ADDITION ):
                
                self._data_number_label.setVisible( True )
                self._data_number.setVisible( True )
                
                if conversion_type == ClientParsing.STRING_CONVERSION_INTEGER_ADDITION:
                    
                    self._data_number.setMinimum( -65535 )
                    
                else:
                    
                    self._data_number.setMinimum( 0 )
                    
                
                data_number_label = 'number data: '
                
                if conversion_type == ClientParsing.STRING_CONVERSION_REMOVE_TEXT_FROM_BEGINNING:
                    
                    data_number_label = 'characters to remove: '
                    
                elif conversion_type == ClientParsing.STRING_CONVERSION_REMOVE_TEXT_FROM_END:
                    
                    data_number_label = 'characters to remove: '
                    
                elif conversion_type == ClientParsing.STRING_CONVERSION_CLIP_TEXT_FROM_BEGINNING:
                    
                    data_number_label = 'characters to take: '
                    
                elif conversion_type == ClientParsing.STRING_CONVERSION_CLIP_TEXT_FROM_END:
                    
                    data_number_label = 'characters to take: '
                    
                elif conversion_type == ClientParsing.STRING_CONVERSION_INTEGER_ADDITION:
                    
                    data_number_label = 'number to add: '
                    
                
                self._data_number_label.setText( data_number_label )
                
            
        
        def _UpdateExampleText( self ):
            
            try:
                
                conversions = [ self.GetValue() ]
                
                string_converter = ClientParsing.StringConverter( conversions, self._example_text )
                
                example_conversion = string_converter.Convert( self._example_text )
                
                try:
                    
                    self._example_conversion.setText( str( example_conversion ) )
                    
                except:
                    
                    self._example_conversion.setText( repr( example_conversion ) )
                    
                
            except Exception as e:
                
                self._example_conversion.setText( str( e ) )
                
            
        
        def GetValue( self ):
            
            conversion_type = self._conversion_type.GetValue()
            
            if conversion_type == ClientParsing.STRING_CONVERSION_ENCODE:
                
                data = self._data_encoding.GetValue()
                
            elif conversion_type == ClientParsing.STRING_CONVERSION_DECODE:
                
                data = self._data_decoding.GetValue()
                
            elif conversion_type in ( ClientParsing.STRING_CONVERSION_PREPEND_TEXT, ClientParsing.STRING_CONVERSION_APPEND_TEXT ):
                
                data = self._data_text.text()
                
            elif conversion_type in ( ClientParsing.STRING_CONVERSION_REMOVE_TEXT_FROM_BEGINNING, ClientParsing.STRING_CONVERSION_REMOVE_TEXT_FROM_END, ClientParsing.STRING_CONVERSION_CLIP_TEXT_FROM_BEGINNING, ClientParsing.STRING_CONVERSION_CLIP_TEXT_FROM_END, ClientParsing.STRING_CONVERSION_INTEGER_ADDITION ):
                
                data = self._data_number.value()
                
            elif conversion_type == ClientParsing.STRING_CONVERSION_REGEX_SUB:
                
                pattern = self._data_text.text()
                repl = self._data_regex_repl.text()
                
                data = ( pattern, repl )
                
            elif conversion_type == ClientParsing.STRING_CONVERSION_DATE_DECODE:
                
                phrase = self._data_text.text()
                timezone_time = self._data_timezone_decode.GetValue()
                timezone_offset = self._data_timezone_offset.value()
                
                data = ( phrase, timezone_time, timezone_offset )
                
            elif conversion_type == ClientParsing.STRING_CONVERSION_DATE_ENCODE:
                
                phrase = self._data_text.text()
                timezone_time = self._data_timezone_encode.GetValue()
                
                data = ( phrase, timezone_time )
                
            else:
                
                data = None
                
            
            return ( conversion_type, data )
            
        
    
class EditStringMatchPanel( ClientGUIScrolledPanels.EditPanel ):
    
    def __init__( self, parent: QW.QWidget, string_match: ClientParsing.StringMatch, test_data = typing.Optional[ ClientParsing.ParsingTestData ] ):
        
        ClientGUIScrolledPanels.EditPanel.__init__( self, parent )
        
        self._match_type = ClientGUICommon.BetterChoice( self )
        
        self._match_type.addItem( 'any characters', ClientParsing.STRING_MATCH_ANY )
        self._match_type.addItem( 'fixed characters', ClientParsing.STRING_MATCH_FIXED )
        self._match_type.addItem( 'character set', ClientParsing.STRING_MATCH_FLEXIBLE )
        self._match_type.addItem( 'regex', ClientParsing.STRING_MATCH_REGEX )
        
        self._match_value_fixed_input = QW.QLineEdit( self )
        self._match_value_regex_input = QW.QLineEdit( self )
        
        self._match_value_flexible_input = ClientGUICommon.BetterChoice( self )
        
        self._match_value_flexible_input.addItem( 'alphabetic characters (a-zA-Z)', ClientParsing.ALPHA )
        self._match_value_flexible_input.addItem( 'alphanumeric characters (a-zA-Z0-9)', ClientParsing.ALPHANUMERIC )
        self._match_value_flexible_input.addItem( 'numeric characters (0-9)', ClientParsing.NUMERIC )
        
        self._min_chars = ClientGUICommon.NoneableSpinCtrl( self, min = 1, max = 65535, unit = 'characters', none_phrase = 'no limit' )
        self._max_chars = ClientGUICommon.NoneableSpinCtrl( self, min = 1, max = 65535, unit = 'characters', none_phrase = 'no limit' )
        
        self._example_string = QW.QLineEdit( self )
        
        self._example_string_matches = ClientGUICommon.BetterStaticText( self )
        
        self._match_value_fixed_input_label = ClientGUICommon.BetterStaticText( self, 'fixed text: ' )
        self._match_value_regex_input_label = ClientGUICommon.BetterStaticText( self, 'regex: ' )
        self._match_value_flexible_input_label = ClientGUICommon.BetterStaticText( self, 'character set: ' )
        self._min_chars_label = ClientGUICommon.BetterStaticText( self, 'minimum allowed number of characters: ' )
        self._max_chars_label = ClientGUICommon.BetterStaticText( self, 'maximum allowed number of characters: ' )
        self._example_string_label = ClientGUICommon.BetterStaticText( self, 'example string: ' )
        
        #
        
        self.SetValue( string_match )
        
        #
        
        rows = []
        
        rows.append( ( 'match type: ', self._match_type ) )
        rows.append( ( self._match_value_fixed_input_label, self._match_value_fixed_input ) )
        rows.append( ( self._match_value_regex_input_label, self._match_value_regex_input ) )
        rows.append( ( self._match_value_flexible_input_label, self._match_value_flexible_input ) )
        rows.append( ( self._min_chars_label, self._min_chars ) )
        rows.append( ( self._max_chars_label, self._max_chars ) )
        rows.append( ( self._example_string_label, self._example_string ) )
        
        gridbox = ClientGUICommon.WrapInGrid( self, rows )
        
        vbox = QP.VBoxLayout()
        
        QP.AddToLayout( vbox, gridbox, CC.FLAGS_EXPAND_SIZER_PERPENDICULAR )
        QP.AddToLayout( vbox, self._example_string_matches, CC.FLAGS_EXPAND_PERPENDICULAR )
        
        self.widget().setLayout( vbox )
        
        #
        
        self._match_type.currentIndexChanged.connect( self._UpdateControlVisibility )
        self._match_value_fixed_input.textChanged.connect( self._UpdateTestResult )
        self._match_value_regex_input.textChanged.connect( self._UpdateTestResult )
        self._match_value_flexible_input.currentIndexChanged.connect( self._UpdateTestResult )
        self._min_chars.valueChanged.connect( self._UpdateTestResult )
        self._max_chars.valueChanged.connect( self._UpdateTestResult )
        self._example_string.textChanged.connect( self._UpdateTestResult )
        
    
    def _GetValue( self ):
        
        match_type = self._match_type.GetValue()
        
        if match_type == ClientParsing.STRING_MATCH_ANY:
            
            match_value = ''
            
        elif match_type == ClientParsing.STRING_MATCH_FLEXIBLE:
            
            match_value = self._match_value_flexible_input.GetValue()
            
        elif match_type == ClientParsing.STRING_MATCH_FIXED:
            
            match_value = self._match_value_fixed_input.text()
            
        elif match_type == ClientParsing.STRING_MATCH_REGEX:
            
            match_value = self._match_value_regex_input.text()
            
        
        if match_type == ClientParsing.STRING_MATCH_FIXED:
            
            min_chars = None
            max_chars = None
            example_string = match_value
            
        else:
            
            min_chars = self._min_chars.GetValue()
            max_chars = self._max_chars.GetValue()
            example_string = self._example_string.text()
            
        
        string_match = ClientParsing.StringMatch( match_type = match_type, match_value = match_value, min_chars = min_chars, max_chars = max_chars, example_string = example_string )
        
        return string_match
        
    
    def _UpdateControlVisibility( self ):
        
        match_type = self._match_type.GetValue()
        
        self._match_value_fixed_input_label.setVisible( False )
        self._match_value_regex_input_label.setVisible( False )
        self._match_value_flexible_input_label.setVisible( False )
        self._min_chars_label.setVisible( False )
        self._max_chars_label.setVisible( False )
        self._example_string_label.setVisible( False )
        
        self._match_value_fixed_input.setVisible( False )
        self._match_value_regex_input.setVisible( False )
        self._match_value_flexible_input.setVisible( False )
        self._min_chars.setVisible( False )
        self._max_chars.setVisible( False )
        self._example_string.setVisible( False )
        
        if match_type == ClientParsing.STRING_MATCH_FIXED:
            
            self._match_value_fixed_input_label.setVisible( True )
            self._match_value_fixed_input.setVisible( True )
            
        else:
            
            self._min_chars_label.setVisible( True )
            self._max_chars_label.setVisible( True )
            self._example_string_label.setVisible( True )
            
            self._min_chars.setVisible( True )
            self._max_chars.setVisible( True )
            self._example_string.setVisible( True )
            
            if match_type == ClientParsing.STRING_MATCH_FLEXIBLE:
                
                self._match_value_flexible_input_label.setVisible( True )
                self._match_value_flexible_input.setVisible( True )
                
            elif match_type == ClientParsing.STRING_MATCH_REGEX:
                
                self._match_value_regex_input_label.setVisible( True )
                self._match_value_regex_input.setVisible( True )
                
            
        
        self._UpdateTestResult()
        
    
    def _UpdateTestResult( self ):
        
        match_type = self._match_type.GetValue()
        
        if match_type == ClientParsing.STRING_MATCH_FIXED:
            
            self._example_string_matches.clear()
            
        else:
            
            string_match = self._GetValue()
            
            try:
                
                string_match.Test( self._example_string.text() )
                
                self._example_string_matches.setText( 'Example matches ok!' )
                self._example_string_matches.setObjectName( 'HydrusValid' )
                self._example_string_matches.style().polish( self._example_string_matches )
                
            except HydrusExceptions.StringMatchException as e:
                
                reason = str( e )
                
                self._example_string_matches.setText( 'Example does not match - '+reason )
                self._example_string_matches.setObjectName( 'HydrusInvalid' )
                self._example_string_matches.style().polish( self._example_string_matches )
                
            
        
    
    def GetValue( self ):
        
        string_match = self._GetValue()
        
        try:
            
            string_match.Test( string_match.GetExampleString() )
            
        except HydrusExceptions.StringMatchException:
            
            raise HydrusExceptions.VetoException( 'Please enter an example text that matches the given rules!' )
            
        
        return string_match
        
    
    def SetValue( self, string_match: ClientParsing.StringMatch ):
        
        ( match_type, match_value, min_chars, max_chars, example_string ) = string_match.ToTuple()
        
        self._match_type.SetValue( match_type )
        
        self._match_value_flexible_input.SetValue( ClientParsing.ALPHA )
        
        if match_type == ClientParsing.STRING_MATCH_FIXED:
            
            self._match_value_fixed_input.setText( match_value )
            
        elif match_type == ClientParsing.STRING_MATCH_FLEXIBLE:
            
            self._match_value_flexible_input.SetValue( match_value )
            
        elif match_type == ClientParsing.STRING_MATCH_REGEX:
            
            self._match_value_regex_input.setText( match_value )
            
        
        self._min_chars.SetValue( min_chars )
        self._max_chars.SetValue( max_chars )
        
        self._example_string.setText( example_string )
        
        self._UpdateControlVisibility()
        
    
SELECT_SINGLE = 0
SELECT_RANGE = 1

class EditStringSlicerPanel( ClientGUIScrolledPanels.EditPanel ):
    
    def __init__( self, parent, string_slicer: ClientParsing.StringSlicer, test_data: typing.Sequence[ str ] = [] ):
        
        ClientGUIScrolledPanels.EditPanel.__init__( self, parent )
        
        #
        
        self._controls_panel = ClientGUICommon.StaticBox( self, 'selector values' )
        
        self._select_type = ClientGUICommon.BetterChoice( self._controls_panel )
        
        self._select_type.addItem( 'select one item', SELECT_SINGLE )
        self._select_type.addItem( 'select range', SELECT_RANGE )
        
        self._single_panel = QW.QWidget( self._controls_panel )
        
        self._index_single = QP.MakeQSpinBox( self._single_panel, min = -65536, max = 65536 )
        
        self._range_panel = QW.QWidget( self._controls_panel )
        
        self._index_start = ClientGUICommon.NoneableSpinCtrl( self._range_panel, none_phrase = 'start at the beginning', min = -65536, max = 65536)
        self._index_end = ClientGUICommon.NoneableSpinCtrl( self._range_panel, none_phrase = 'finish at the end', min = -65536, max = 65536)
        
        self._summary_st = ClientGUICommon.BetterStaticText( self._controls_panel )
        
        #
        
        self._example_panel = ClientGUICommon.StaticBox( self, 'test results' )
        
        self._example_strings = QW.QListWidget( self._example_panel )
        self._example_strings.setSelectionMode( QW.QListWidget.NoSelection )
        
        self._example_strings_sliced = QW.QListWidget( self._example_panel )
        self._example_strings_sliced.setSelectionMode( QW.QListWidget.NoSelection )
        
        #
        
        for s in test_data:
            
            self._example_strings.addItem( s )
            
        
        self.SetValue( string_slicer )
        
        #
        
        rows = []
        
        rows.append( ( 'index to select: ', self._index_single ) )
        
        gridbox = ClientGUICommon.WrapInGrid( self._single_panel, rows )
        
        self._single_panel.setLayout( gridbox )
        
        rows = []
        
        rows.append( ( 'starting index: ', self._index_start ) )
        rows.append( ( 'ending index: ', self._index_end ) )
        
        gridbox = ClientGUICommon.WrapInGrid( self._range_panel, rows )
        
        self._range_panel.setLayout( gridbox )
        
        st = ClientGUICommon.BetterStaticText( self._controls_panel, label = 'Negative indices are ok! Check the summary text to make sure your numbers are correct!' )
        
        st.setWordWrap( True )
        
        self._controls_panel.Add( st, CC.FLAGS_EXPAND_PERPENDICULAR )
        self._controls_panel.Add( self._select_type, CC.FLAGS_EXPAND_PERPENDICULAR )
        self._controls_panel.Add( self._single_panel, CC.FLAGS_EXPAND_PERPENDICULAR )
        self._controls_panel.Add( self._range_panel, CC.FLAGS_EXPAND_PERPENDICULAR )
        self._controls_panel.Add( self._summary_st, CC.FLAGS_CENTER )
        
        hbox = QP.HBoxLayout()
        
        QP.AddToLayout( hbox, self._example_strings, CC.FLAGS_EXPAND_BOTH_WAYS )
        QP.AddToLayout( hbox, self._example_strings_sliced, CC.FLAGS_EXPAND_BOTH_WAYS )
        
        self._example_panel.Add( hbox, CC.FLAGS_EXPAND_SIZER_BOTH_WAYS )
        
        vbox = QP.VBoxLayout()
        
        QP.AddToLayout( vbox, self._controls_panel, CC.FLAGS_EXPAND_PERPENDICULAR )
        QP.AddToLayout( vbox, self._example_panel, CC.FLAGS_EXPAND_BOTH_WAYS )
        
        self.widget().setLayout( vbox )
        
        #
        
        self.SetValue( string_slicer )
        
        self._select_type.currentIndexChanged.connect( self._ShowHideControls )
        
        self._index_single.valueChanged.connect( self._UpdateControls )
        self._index_start.valueChanged.connect( self._UpdateControls )
        self._index_end.valueChanged.connect( self._UpdateControls )
        
    
    def _GetValue( self ):
        
        select_type = self._select_type.GetValue()
        
        if select_type == SELECT_SINGLE:
            
            index_start = self._index_single.value()
            
            if index_start == -1:
                
                index_end = None
                
            else:
                
                index_end = index_start + 1
                
            
        elif select_type == SELECT_RANGE:
            
            index_start = self._index_start.GetValue()
            index_end = self._index_end.GetValue()
            
        
        string_slicer = ClientParsing.StringSlicer( index_start = index_start, index_end = index_end )
        
        return string_slicer
        
    
    def _ShowHideControls( self ):
        
        select_type = self._select_type.GetValue()
        
        self._single_panel.setVisible( select_type == SELECT_SINGLE )
        self._range_panel.setVisible( select_type == SELECT_RANGE )
        
        self._UpdateControls()
        
    
    def _UpdateControls( self ):
        
        string_slicer = self._GetValue()
        
        self._summary_st.setText( string_slicer.ToString() )
        
        texts = [ self._example_strings.item( i ).text() for i in range( self._example_strings.count() ) ]
        
        try:
            
            sliced_texts = string_slicer.Slice( texts )
            
        except Exception as e:
            
            sliced_texts = [ 'Error: {}'.format( e ) ]
            
        
        self._example_strings_sliced.clear()
        
        for s in sliced_texts:
            
            self._example_strings_sliced.addItem( s )
            
        
    
    def GetValue( self ):
        
        string_slicer = self._GetValue()
        
        return string_slicer
        
    
    def SetValue( self, string_slicer: ClientParsing.StringSlicer ):
        
        ( index_start, index_end ) = string_slicer.GetIndexStartEnd()
        
        self._index_single.setValue( index_start if index_start is not None else 0 )
        
        self._index_start.SetValue( index_start )
        self._index_end.SetValue( index_end )
        
        if string_slicer.SelectsOne():
            
            self._select_type.SetValue( SELECT_SINGLE )
            
        else:
            
            self._select_type.SetValue( SELECT_RANGE )
            
        
        self._ShowHideControls()
        
    
class EditStringSorterPanel( ClientGUIScrolledPanels.EditPanel ):
    
    def __init__( self, parent, string_sorter: ClientParsing.StringSorter, test_data: typing.Sequence[ str ] = [] ):
        
        ClientGUIScrolledPanels.EditPanel.__init__( self, parent )
        
        #
        
        self._controls_panel = ClientGUICommon.StaticBox( self, 'sort values' )
        
        self._sort_type = ClientGUICommon.BetterChoice( self._controls_panel )
        
        self._sort_type.addItem( ClientParsing.sort_str_enum[ ClientParsing.CONTENT_PARSER_SORT_TYPE_HUMAN_SORT ], ClientParsing.CONTENT_PARSER_SORT_TYPE_HUMAN_SORT )
        self._sort_type.addItem( ClientParsing.sort_str_enum[ ClientParsing.CONTENT_PARSER_SORT_TYPE_LEXICOGRAPHIC ], ClientParsing.CONTENT_PARSER_SORT_TYPE_LEXICOGRAPHIC )
        
        tt = 'Human sort sorts numbers as you understand them. "image 2" comes before "image 10". Lexicographic compares each character in turn. "image 02" comes before "image 10", which comes before "image 2".'
        
        self._asc = QW.QCheckBox( self._controls_panel )
        
        self._regex = ClientGUICommon.NoneableTextCtrl( self._controls_panel, none_phrase = 'use whole string' )
        
        tt = 'If you want to sort by a substring, for instance a number in a longer string, you can place a regex here like \'\\d+\' just to capture and sort by that number. It does not affect the final strings, just what it compared for sort.'
        
        self._regex.setToolTip( tt )
        
        #
        
        self._example_panel = ClientGUICommon.StaticBox( self, 'test results' )
        
        self._example_strings = QW.QListWidget( self._example_panel )
        self._example_strings.setSelectionMode( QW.QListWidget.NoSelection )
        
        self._example_strings_sorted = QW.QListWidget( self._example_panel )
        self._example_strings_sorted.setSelectionMode( QW.QListWidget.NoSelection )
        
        #
        
        for s in test_data:
            
            self._example_strings.addItem( s )
            
        
        self.SetValue( string_sorter )
        
        #
        
        rows = []
        
        rows.append( ( 'sort type: ', self._sort_type ) )
        rows.append( ( 'ascending: ', self._asc ) )
        rows.append( ( 'regex for substring sorting: ', self._regex ) )
        
        gridbox = ClientGUICommon.WrapInGrid( self._controls_panel, rows )
        
        self._controls_panel.Add( gridbox, CC.FLAGS_EXPAND_SIZER_PERPENDICULAR )
        
        hbox = QP.HBoxLayout()
        
        QP.AddToLayout( hbox, self._example_strings, CC.FLAGS_EXPAND_BOTH_WAYS )
        QP.AddToLayout( hbox, self._example_strings_sorted, CC.FLAGS_EXPAND_BOTH_WAYS )
        
        self._example_panel.Add( hbox, CC.FLAGS_EXPAND_SIZER_BOTH_WAYS )
        
        vbox = QP.VBoxLayout()
        
        QP.AddToLayout( vbox, self._controls_panel, CC.FLAGS_EXPAND_PERPENDICULAR )
        QP.AddToLayout( vbox, self._example_panel, CC.FLAGS_EXPAND_BOTH_WAYS )
        
        self.widget().setLayout( vbox )
        
        #
        
        self._sort_type.currentIndexChanged.connect( self._UpdateControls )
        self._asc.stateChanged.connect( self._UpdateControls )
        self._regex.valueChanged.connect( self._UpdateControls )
        
    
    def _GetValue( self ):
        
        sort_type = self._sort_type.GetValue()
        asc = self._asc.isChecked()
        regex = self._regex.GetValue()
        
        string_sorter = ClientParsing.StringSorter( sort_type = sort_type, asc = asc, regex = regex )
        
        return string_sorter
        
    
    def _UpdateControls( self ):
        
        string_sorter = self._GetValue()
        
        texts = [ self._example_strings.item( i ).text() for i in range( self._example_strings.count() ) ]
        
        try:
            
            sorted_texts = string_sorter.Sort( texts )
            
        except Exception as e:
            
            sorted_texts = [ 'Error: {}'.format( e ) ]
            
        
        self._example_strings_sorted.clear()
        
        regex = self._regex.GetValue()
        
        for s in sorted_texts:
            
            if regex is not None:
                
                try:
                    
                    m = re.search( regex, s )
                    
                    if m is None:
                        
                        s = '{} (no regex match)'.format( s )
                        
                    else:
                        
                        s = '{} (regex: {})'.format( s, m.group() )
                        
                    
                except:
                    
                    pass
                    
                
            
            self._example_strings_sorted.addItem( s )
            
        
    
    def GetValue( self ):
        
        string_sorter = self._GetValue()
        
        return string_sorter
        
    
    def SetValue( self, string_sorter: ClientParsing.StringSorter ):
        
        sort_type = string_sorter.GetSortType()
        asc = string_sorter.GetAscending()
        regex = string_sorter.GetRegex()
        
        self._sort_type.SetValue( sort_type )
        self._asc.setChecked( asc )
        self._regex.SetValue( regex )
        
        self._UpdateControls()
        
    
class EditStringSplitterPanel( ClientGUIScrolledPanels.EditPanel ):
    
    def __init__( self, parent, string_splitter: ClientParsing.StringSplitter, example_string: str = '' ):
        
        ClientGUIScrolledPanels.EditPanel.__init__( self, parent )
        
        #
        
        self._controls_panel = ClientGUICommon.StaticBox( self, 'splitter values' )
        
        self._separator = QW.QLineEdit( self._controls_panel )
        self._max_splits = ClientGUICommon.NoneableSpinCtrl( self._controls_panel, min = 1, max = 65535, unit = 'splits', none_phrase = 'no limit' )
        
        #
        
        self._example_panel = ClientGUICommon.StaticBox( self, 'test results' )
        
        self._example_string = QW.QLineEdit( self._example_panel )
        
        self._example_string_splits = QW.QListWidget( self._example_panel )
        self._example_string_splits.setSelectionMode( QW.QListWidget.NoSelection )
        
        #
        
        self._example_string.setText( example_string )
        
        self.SetValue( string_splitter )
        
        #
        
        rows = []
        
        rows.append( ( 'separator: ', self._separator ) )
        rows.append( ( 'max splits: ', self._max_splits ) )
        
        gridbox = ClientGUICommon.WrapInGrid( self._controls_panel, rows )
        
        self._controls_panel.Add( gridbox, CC.FLAGS_EXPAND_SIZER_PERPENDICULAR )
        
        rows = []
        
        rows.append( ( 'example string: ', self._example_string ) )
        
        gridbox = ClientGUICommon.WrapInGrid( self._example_panel, rows )
        
        self._example_panel.Add( gridbox, CC.FLAGS_EXPAND_SIZER_PERPENDICULAR )
        self._example_panel.Add( ClientGUICommon.BetterStaticText( self, label = 'result:' ), CC.FLAGS_EXPAND_PERPENDICULAR )
        self._example_panel.Add( self._example_string_splits, CC.FLAGS_EXPAND_BOTH_WAYS )
        
        vbox = QP.VBoxLayout()
        
        QP.AddToLayout( vbox, self._controls_panel, CC.FLAGS_EXPAND_PERPENDICULAR )
        QP.AddToLayout( vbox, self._example_panel, CC.FLAGS_EXPAND_BOTH_WAYS )
        
        self.widget().setLayout( vbox )
        
        #
        
        self._separator.textChanged.connect( self._UpdateControls )
        self._max_splits.valueChanged.connect( self._UpdateControls )
        self._example_string.textChanged.connect( self._UpdateControls )
        
    
    def _GetValue( self ):
        
        separator = self._separator.text()
        max_splits = self._max_splits.GetValue()
        
        string_splitter = ClientParsing.StringSplitter( separator = separator, max_splits = max_splits )
        
        return string_splitter
        
    
    def _UpdateControls( self ):
        
        string_splitter = self._GetValue()
        
        results = string_splitter.Split( self._example_string.text() )
        
        self._example_string_splits.clear()
        
        for result in results:
            
            self._example_string_splits.addItem( result )
            
        
    
    def GetValue( self ):
        
        string_splitter = self._GetValue()
        
        return string_splitter
        
    
    def SetValue( self, string_splitter: ClientParsing.StringSplitter ):
        
        separator = string_splitter.GetSeparator()
        max_splits = string_splitter.GetMaxSplits()
        
        self._separator.setText( separator )
        self._max_splits.SetValue( max_splits )
        
        self._UpdateControls()
        
    
class EditStringProcessorPanel( ClientGUIScrolledPanels.EditPanel ):
    
    def __init__( self, parent, string_processor: ClientParsing.StringProcessor, test_data: ClientParsing.ParsingTestData ):
        
        ClientGUIScrolledPanels.EditPanel.__init__( self, parent )
        
        #
        
        self._controls_panel = ClientGUICommon.StaticBox( self, 'processing steps' )
        
        self._processing_steps = ClientGUIListBoxes.QueueListBox( self, 8, self._ConvertDataToListBoxString, add_callable = self._Add, edit_callable = self._Edit )
        
        #
        
        self._example_panel = ClientGUICommon.StaticBox( self, 'test results' )
        
        self._multiline_test_panel = MultilineStringConversionTestPanel( self._example_panel, string_processor )
        
        self._single_test_panel = SingleStringConversionTestPanel( self._example_panel, string_processor )
        
        #
        
        ( w, h ) = ClientGUIFunctions.ConvertTextToPixels( self._example_panel, ( 64, 24 ) )
        
        self._example_panel.setMinimumSize( w, h )
        
        #
        
        self._controls_panel.Add( self._processing_steps, CC.FLAGS_EXPAND_SIZER_BOTH_WAYS )
        
        #
        
        example_hbox = QP.HBoxLayout()
        
        QP.AddToLayout( example_hbox, self._multiline_test_panel, CC.FLAGS_EXPAND_BOTH_WAYS )
        QP.AddToLayout( example_hbox, self._single_test_panel, CC.FLAGS_EXPAND_SIZER_BOTH_WAYS )
        
        self._example_panel.Add( example_hbox, CC.FLAGS_EXPAND_SIZER_BOTH_WAYS )
        
        vbox = QP.VBoxLayout()
        
        QP.AddToLayout( vbox, self._controls_panel, CC.FLAGS_EXPAND_BOTH_WAYS )
        QP.AddToLayout( vbox, self._example_panel, CC.FLAGS_EXPAND_BOTH_WAYS )
        
        self.widget().setLayout( vbox )
        
        #
        
        self._processing_steps.listBoxChanged.connect( self._UpdateControls )
        
        self._multiline_test_panel.textSelected.connect( self._single_test_panel.SetExampleString )
        
        self._multiline_test_panel.SetTestData( test_data )
        
        self.SetValue( string_processor )
        
    
    def _Add( self ):
        
        choice_tuples = [
            ( 'String Match', ClientParsing.StringMatch, 'An object that filters strings.' ),
            ( 'String Converter', ClientParsing.StringConverter, 'An object that converts strings from one thing to another.' ),
            ( 'String Splitter', ClientParsing.StringSplitter, 'An object that breaks strings into smaller strings.' ),
            ( 'String Sorter', ClientParsing.StringSorter, 'An object that sorts strings.' ),
            ( 'String Selector/Slicer', ClientParsing.StringSlicer, 'An object that filter-selects from the list of strings. Either absolute index position or a range.' )
        ]
        
        try:
            
            string_processing_step_type = ClientGUIDialogsQuick.SelectFromListButtons( self, 'Which type of processing step?', choice_tuples )
            
        except HydrusExceptions.CancelledException:
            
            raise HydrusExceptions.VetoException()
            
        
        if string_processing_step_type == ClientParsing.StringMatch:
            
            example_text = self._single_test_panel.GetStartingText()
            
            string_processing_step = ClientParsing.StringMatch( example_string = example_text )
            
            example_text = self._GetExampleTextForStringProcessingStep( string_processing_step )
            
            string_processing_step = ClientParsing.StringMatch( example_string = example_text )
            
        else:
            
            string_processing_step = string_processing_step_type()
            
        
        return self._Edit( string_processing_step )
        
    
    def _Edit( self, string_processing_step: ClientParsing.StringProcessingStep ):
        
        example_text = self._GetExampleTextForStringProcessingStep( string_processing_step )
        
        with ClientGUITopLevelWindowsPanels.DialogEdit( self, 'edit processing step' ) as dlg:
            
            if isinstance( string_processing_step, ClientParsing.StringMatch ):
                
                test_data = ClientParsing.ParsingTestData( {}, ( example_text, ) )
                
                panel = EditStringMatchPanel( dlg, string_processing_step, test_data = test_data )
                
            elif isinstance( string_processing_step, ClientParsing.StringConverter ):
                
                panel = EditStringConverterPanel( dlg, string_processing_step, example_string_override = example_text )
                
            elif isinstance( string_processing_step, ClientParsing.StringSplitter ):
                
                panel = EditStringSplitterPanel( dlg, string_processing_step, example_string = example_text )
                
            elif isinstance( string_processing_step, ClientParsing.StringSorter ):
                
                test_data = self._GetExampleTextsForStringSorter( string_processing_step )
                
                panel = EditStringSorterPanel( dlg, string_processing_step, test_data = test_data )
                
            elif isinstance( string_processing_step, ClientParsing.StringSlicer ):
                
                test_data = self._GetExampleTextsForStringSorter( string_processing_step )
                
                panel = EditStringSlicerPanel( dlg, string_processing_step, test_data = test_data )
                
            
            dlg.SetPanel( panel )
            
            if dlg.exec() == QW.QDialog.Accepted:
                
                string_processing_step = panel.GetValue()
                
                return string_processing_step
                
            else:
                
                raise HydrusExceptions.VetoException()
                
            
        
    
    def _ConvertDataToListBoxString( self, string_processing_step: ClientParsing.StringProcessingStep ):
        
        return string_processing_step.ToString( with_type = True )
        
    
    def _GetExampleTextForStringProcessingStep( self, string_processing_step: ClientParsing.StringProcessingStep ):
        
        # ultimately rework this to multiline test_data m8, but the panels need it first
        
        current_string_processor = self._GetValue()
        
        current_string_processing_steps = current_string_processor.GetProcessingSteps()
        
        if string_processing_step in current_string_processing_steps:
            
            example_text_index = current_string_processing_steps.index( string_processing_step )
            
        else:
            
            example_text_index = len( current_string_processing_steps )
            
        
        example_text = self._single_test_panel.GetResultText( example_text_index )
        
        return example_text
        
    
    def _GetExampleTextsForStringSorter( self, string_processing_step: ClientParsing.StringProcessingStep ):
        
        # ultimately rework this to multiline test_data m8
        
        current_string_processor = self._GetValue()
        
        current_string_processing_steps = current_string_processor.GetProcessingSteps()
        
        if string_processing_step in current_string_processing_steps:
            
            example_text_index = current_string_processing_steps.index( string_processing_step )
            
        else:
            
            example_text_index = len( current_string_processing_steps )
            
        
        example_texts = self._multiline_test_panel.GetResultTexts( example_text_index )
        
        return example_texts
        
    
    def _GetValue( self ):
        
        processing_steps = self._processing_steps.GetData()
        
        string_processor = ClientParsing.StringProcessor()
        
        string_processor.SetProcessingSteps( processing_steps )
        
        return string_processor
        
    
    def _UpdateControls( self ):
        
        string_processor = self._GetValue()
        
        self._multiline_test_panel.SetStringProcessor( string_processor )
        self._single_test_panel.SetStringProcessor( string_processor )
        
    
    def GetValue( self ):
        
        string_processor = self._GetValue()
        
        return string_processor
        
    
    def SetValue( self, string_processor: ClientParsing.StringProcessor ):
        
        processing_steps = string_processor.GetProcessingSteps()
        
        self._processing_steps.AddDatas( processing_steps )
        
        self._UpdateControls()
        
    
