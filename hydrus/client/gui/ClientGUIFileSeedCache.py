import os

from qtpy import QtCore as QC
from qtpy import QtWidgets as QW
from qtpy import QtGui as QG

from hydrus.core import HydrusConstants as HC
from hydrus.core import HydrusData
from hydrus.core import HydrusExceptions
from hydrus.core import HydrusGlobals as HG
from hydrus.core import HydrusPaths
from hydrus.core import HydrusText

from hydrus.client import ClientConstants as CC
from hydrus.client import ClientData
from hydrus.client import ClientPaths
from hydrus.client import ClientSerialisable
from hydrus.client.gui import ClientGUICore as CGC
from hydrus.client.gui import ClientGUIDialogsQuick
from hydrus.client.gui import ClientGUIMenus
from hydrus.client.gui import ClientGUISerialisable
from hydrus.client.gui import ClientGUIScrolledPanels
from hydrus.client.gui import ClientGUITopLevelWindowsPanels
from hydrus.client.gui import QtPorting as QP
from hydrus.client.gui.lists import ClientGUIListConstants as CGLC
from hydrus.client.gui.lists import ClientGUIListCtrl
from hydrus.client.gui.widgets import ClientGUICommon
from hydrus.client.importing import ClientImportFileSeeds
from hydrus.client.importing import ClientImportOptions

class EditFileSeedCachePanel( ClientGUIScrolledPanels.EditPanel ):
    
    def __init__( self, parent, controller, file_seed_cache ):
        
        ClientGUIScrolledPanels.EditPanel.__init__( self, parent )
        
        self._controller = controller
        self._file_seed_cache = file_seed_cache
        
        self._text = ClientGUICommon.BetterStaticText( self, 'initialising' )
        
        # add index control row here, hide it if needed and hook into showing/hiding and postsizechangedevent on file_seed add/remove
        
        self._list_ctrl = ClientGUIListCtrl.BetterListCtrl( self, CGLC.COLUMN_LIST_FILE_SEED_CACHE.ID, 30, self._ConvertFileSeedToListCtrlTuples, activation_callback = self._ShowSelectionInNewPage, delete_key_callback = self._DeleteSelected )
        
        #
        
        self._list_ctrl.AddDatas( self._file_seed_cache.GetFileSeeds() )
        
        self._list_ctrl.Sort()
        
        #
        
        vbox = QP.VBoxLayout()
        
        QP.AddToLayout( vbox, self._text, CC.FLAGS_EXPAND_PERPENDICULAR )
        QP.AddToLayout( vbox, self._list_ctrl, CC.FLAGS_EXPAND_BOTH_WAYS )
        
        self.widget().setLayout( vbox )
        
        self._list_ctrl.AddMenuCallable( self._GetListCtrlMenu )
        
        self._controller.sub( self, 'NotifyFileSeedsUpdated', 'file_seed_cache_file_seeds_updated' )
        
        QP.CallAfter( self._UpdateText )
        
    
    def _ConvertFileSeedToListCtrlTuples( self, file_seed ):
        
        try:
            
            file_seed_index = self._file_seed_cache.GetFileSeedIndex( file_seed )
            
            pretty_file_seed_index = HydrusData.ToHumanInt( file_seed_index )
            
        except:
            
            file_seed_index = '--'
            
            pretty_file_seed_index = '--'
            
        
        file_seed_data = file_seed.file_seed_data
        status = file_seed.status
        added = file_seed.created
        modified = file_seed.modified
        source_time = file_seed.source_time
        note = file_seed.note
        
        pretty_file_seed_data = str( file_seed_data )
        pretty_status = CC.status_string_lookup[ status ]
        pretty_added = ClientData.TimestampToPrettyTimeDelta( added )
        pretty_modified = ClientData.TimestampToPrettyTimeDelta( modified )
        
        if source_time is None:
            
            pretty_source_time = 'unknown'
            
        else:
            
            pretty_source_time = ClientData.TimestampToPrettyTimeDelta( source_time )
            
        
        sort_source_time = ClientGUIListCtrl.SafeNoneInt( source_time )
        
        pretty_note = note.split( os.linesep )[0]
        
        display_tuple = ( pretty_file_seed_index, pretty_file_seed_data, pretty_status, pretty_added, pretty_modified, pretty_source_time, pretty_note )
        sort_tuple = ( file_seed_index, file_seed_data, status, added, modified, sort_source_time, note )
        
        return ( display_tuple, sort_tuple )
        
    
    def _CopySelectedNotes( self ):
        
        notes = []
        
        for file_seed in self._list_ctrl.GetData( only_selected = True ):
            
            note = file_seed.note
            
            if note != '':
                
                notes.append( note )
                
            
        
        if len( notes ) > 0:
            
            separator = os.linesep * 2
            
            text = separator.join( notes )
            
            HG.client_controller.pub( 'clipboard', 'text', text )
            
        
    
    def _CopySelectedFileSeedData( self ):
        
        file_seeds = self._list_ctrl.GetData( only_selected = True )
        
        if len( file_seeds ) > 0:
            
            separator = os.linesep * 2
            
            text = separator.join( ( file_seed.file_seed_data for file_seed in file_seeds ) )
            
            HG.client_controller.pub( 'clipboard', 'text', text )
            
        
    
    def _DeleteSelected( self ):
        
        file_seeds_to_delete = self._list_ctrl.GetData( only_selected = True )
        
        if len( file_seeds_to_delete ) > 0:
            
            message = 'Are you sure you want to delete all the selected entries?'
            
            result = ClientGUIDialogsQuick.GetYesNo( self, message )
            
            if result == QW.QDialog.Accepted:
                
                self._file_seed_cache.RemoveFileSeeds( file_seeds_to_delete )
                
            
        
    
    def _GetListCtrlMenu( self ):
        
        selected_file_seeds = self._list_ctrl.GetData( only_selected = True )
        
        if len( selected_file_seeds ) == 0:
            
            raise HydrusExceptions.DataMissing()
            
        
        menu = QW.QMenu()
        
        can_show_files_in_new_page = True in ( file_seed.HasHash() for file_seed in selected_file_seeds )
        
        if can_show_files_in_new_page:
            
            ClientGUIMenus.AppendMenuItem( menu, 'open selected import files in a new page', 'Show all the known selected files in a new thumbnail page. This is complicated, so cannot always be guaranteed, even if the import says \'success\'.', self._ShowSelectionInNewPage )
            
            ClientGUIMenus.AppendSeparator( menu )

        ClientGUIMenus.AppendMenuItem( menu, 'copy sources', 'Copy all the selected sources to clipboard.', self._CopySelectedFileSeedData )
        ClientGUIMenus.AppendMenuItem( menu, 'copy notes', 'Copy all the selected notes to clipboard.', self._CopySelectedNotes )
        
        ClientGUIMenus.AppendSeparator( menu )

        ClientGUIMenus.AppendMenuItem( menu, 'open sources', 'Open all the selected sources in your file explorer or web browser.', self._OpenSelectedFileSeedData )
        
        ClientGUIMenus.AppendSeparator( menu )

        ClientGUIMenus.AppendMenuItem( menu, 'try again', 'Reset the progress of all the selected imports.', HydrusData.Call( self._SetSelected, CC.STATUS_UNKNOWN ) )
        ClientGUIMenus.AppendMenuItem( menu, 'skip', 'Skip all the selected imports.', HydrusData.Call( self._SetSelected, CC.STATUS_SKIPPED ) )
        ClientGUIMenus.AppendMenuItem( menu, 'delete from list', 'Remove all the selected imports.', self._DeleteSelected )
        
        return menu
        
    
    def _OpenSelectedFileSeedData( self ):
        
        file_seeds = self._list_ctrl.GetData( only_selected = True )
        
        if len( file_seeds ) > 0:
            
            if len( file_seeds ) > 10:
                
                message = 'You have many objects selected--are you sure you want to open them all?'
                
                result = ClientGUIDialogsQuick.GetYesNo( self, message )
                
                if result != QW.QDialog.Accepted:
                    
                    return
                    
                
            
            if file_seeds[0].file_seed_data.startswith( 'http' ):
                
                for file_seed in file_seeds:
                    
                    ClientPaths.LaunchURLInWebBrowser( file_seed.file_seed_data )
                    
                
            else:
                
                try:
                    
                    for file_seed in file_seeds:
                        
                        HydrusPaths.OpenFileLocation( file_seed.file_seed_data )
                        
                    
                except Exception as e:
                    
                    QW.QMessageBox.critical( self, 'Error', str(e) )
                    
                
            
        
    
    def _SetSelected( self, status_to_set ):
        
        file_seeds = self._list_ctrl.GetData( only_selected = True )
        
        if status_to_set == CC.STATUS_UNKNOWN:
            
            deleted_and_clearable_file_seeds = [ file_seed for file_seed in file_seeds if file_seed.IsDeleted() and file_seed.HasHash() ]
            
            if len( deleted_and_clearable_file_seeds ) > 0:
                
                message = 'One or more of these files did not import due to being previously deleted. They will likely fail again unless you erase those deletion records. Would you like to do this now?'
                
                result = ClientGUIDialogsQuick.GetYesNo( self, message )
                
                if result == QW.QDialog.DialogCode.Accepted:
                    
                    deletee_hashes = { file_seed.GetHash() for file_seed in deleted_and_clearable_file_seeds }
                    
                    content_update_erase_record = HydrusData.ContentUpdate( HC.CONTENT_TYPE_FILES, HC.CONTENT_UPDATE_ADVANCED, ( 'delete_deleted', deletee_hashes ) )
                    content_update_undelete_from_trash = HydrusData.ContentUpdate( HC.CONTENT_TYPE_FILES, HC.CONTENT_UPDATE_UNDELETE, deletee_hashes )
                    
                    service_keys_to_content_updates = { CC.COMBINED_LOCAL_FILE_SERVICE_KEY : [ content_update_erase_record, content_update_undelete_from_trash ] }
                    
                    HG.client_controller.WriteSynchronous( 'content_updates', service_keys_to_content_updates )
                    
                
            
        
        for file_seed in file_seeds:
            
            file_seed.SetStatus( status_to_set )
            
        
        self._file_seed_cache.NotifyFileSeedsUpdated( file_seeds )
        
    
    def _ShowSelectionInNewPage( self ):
        
        hashes = []
        
        for file_seed in self._list_ctrl.GetData( only_selected = True ):
            
            if file_seed.HasHash():
                
                hashes.append( file_seed.GetHash() )
                
            
        
        if len( hashes ) > 0:
            
            HG.client_controller.pub( 'new_page_query', CC.LOCAL_FILE_SERVICE_KEY, initial_hashes = hashes )
            
        
    
    def _UpdateListCtrl( self, file_seeds ):
        
        file_seeds_to_add = []
        file_seeds_to_update = []
        file_seeds_to_delete = []
        
        for file_seed in file_seeds:
            
            if self._file_seed_cache.HasFileSeed( file_seed ):
                
                if self._list_ctrl.HasData( file_seed ):
                    
                    file_seeds_to_update.append( file_seed )
                    
                else:
                    
                    file_seeds_to_add.append( file_seed )
                    
                
            else:
                
                if self._list_ctrl.HasData( file_seed ):
                    
                    file_seeds_to_delete.append( file_seed )
                    
                
            
        
        self._list_ctrl.DeleteDatas( file_seeds_to_delete )
        
        if len( file_seeds_to_add ) > 0:
            
            self._list_ctrl.AddDatas( file_seeds_to_add )
            
            # if file_seeds are inserted, then all subsequent indices need to be shuffled up, hence just update all here
            
            self._list_ctrl.UpdateDatas()
            
        else:
            
            self._list_ctrl.UpdateDatas( file_seeds_to_update )
            
        
    
    def _UpdateText( self ):
        
        file_seed_cache_status = self._file_seed_cache.GetStatus()
        
        self._text.setText( file_seed_cache_status.GetStatusText() )
        
    
    def GetValue( self ):
        
        return self._file_seed_cache
        
    
    def NotifyFileSeedsUpdated( self, file_seed_cache_key, file_seeds ):
        
        if file_seed_cache_key == self._file_seed_cache.GetFileSeedCacheKey():
            
            self._UpdateText()
            self._UpdateListCtrl( file_seeds )
            
        
    
class FileSeedCacheButton( ClientGUICommon.BetterBitmapButton ):
    
    def __init__( self, parent, controller, file_seed_cache_get_callable, file_seed_cache_set_callable = None ):
        
        ClientGUICommon.BetterBitmapButton.__init__( self, parent, CC.global_pixmaps().listctrl, self._ShowFileSeedCacheFrame )
        
        self._controller = controller
        self._file_seed_cache_get_callable = file_seed_cache_get_callable
        self._file_seed_cache_set_callable = file_seed_cache_set_callable
        
        self.setToolTip( 'open detailed file import status--right-click for quick actions, if applicable' )
        
        self._widget_event_filter = QP.WidgetEventFilter( self )
        
    
    def _ClearFileSeeds( self, statuses_to_remove ):
        
        message = 'Are you sure you want to delete all the ' + '/'.join( ( CC.status_string_lookup[ status ] for status in statuses_to_remove ) ) + ' file import items? This is useful for cleaning up and de-laggifying a very large list, but be careful you aren\'t removing something you would want to revisit or what watcher/subscription may be using for future check time calculations.'
        
        result = ClientGUIDialogsQuick.GetYesNo( self, message )
        
        if result == QW.QDialog.DialogCode.Accepted:
            
            file_seed_cache = self._file_seed_cache_get_callable()
            
            file_seed_cache.RemoveFileSeedsByStatus( statuses_to_remove )
            
        
    
    def _GetExportableSourcesString( self ):
        
        file_seed_cache = self._file_seed_cache_get_callable()
        
        file_seeds = file_seed_cache.GetFileSeeds()
        
        sources = [ file_seed.file_seed_data for file_seed in file_seeds ]
        
        return os.linesep.join( sources )
        
    
    def _GetSourcesFromSourcesString( self, sources_string ):
        
        sources = HydrusText.DeserialiseNewlinedTexts( sources_string )
        
        return sources
        
    
    def _ImportFromClipboard( self ):
        
        try:
            
            raw_text = HG.client_controller.GetClipboardText()
            
        except HydrusExceptions.DataMissing as e:
            
            QW.QMessageBox.critical( self, 'Error', str(e) )
            
            return
            
        
        sources = self._GetSourcesFromSourcesString( raw_text )
        
        try:
            
            self._ImportSources( sources )
            
        except:
            
            QW.QMessageBox.critical( self, 'Error', 'Could not import!' )
            
            raise
            
        
    
    def _ImportFromPNG( self ):
        
        with QP.FileDialog( self, 'select the png with the sources', wildcard = 'PNG (*.png)' ) as dlg:
            
            if dlg.exec() == QW.QDialog.Accepted:
                
                path = dlg.GetPath()
                
                payload = ClientSerialisable.LoadFromPNG( path )
                
                try:
                    
                    sources = self._GetSourcesFromSourcesString( payload )
                    
                    self._ImportSources( sources )
                    
                except:
                    
                    QW.QMessageBox.critical( self, 'Error', 'Could not import!' )
                    
                    raise
                    
                
            
        
    
    def _ImportSources( self, sources ):
        
        file_seed_cache = self._file_seed_cache_get_callable()
        
        if sources[0].startswith( 'http' ):
            
            file_seed_type = ClientImportFileSeeds.FILE_SEED_TYPE_URL
            
        else:
            
            file_seed_type = ClientImportFileSeeds.FILE_SEED_TYPE_HDD
            
        
        file_seeds = [ ClientImportFileSeeds.FileSeed( file_seed_type, source ) for source in sources ]
        
        file_seed_cache.AddFileSeeds( file_seeds )
        
    
    def _ExportToPNG( self ):
        
        payload = self._GetExportableSourcesString()
        
        with ClientGUITopLevelWindowsPanels.DialogNullipotent( self, 'export to png' ) as dlg:
            
            panel = ClientGUISerialisable.PNGExportPanel( dlg, payload )
            
            dlg.SetPanel( panel )
            
            dlg.exec()
            
        
    
    def _ExportToClipboard( self ):
        
        payload = self._GetExportableSourcesString()
        
        HG.client_controller.pub( 'clipboard', 'text', payload )
        
    
    def _RetryErrors( self ):
        
        message = 'Are you sure you want to retry all the files that encountered errors?'
        
        result = ClientGUIDialogsQuick.GetYesNo( self, message )
        
        if result == QW.QDialog.DialogCode.Accepted:
            
            file_seed_cache = self._file_seed_cache_get_callable()
            
            file_seed_cache.RetryFailed()
            
        
    
    def _RetryIgnored( self ):
        
        message = 'Are you sure you want to retry all the files that were ignored/vetoed?'
        
        result = ClientGUIDialogsQuick.GetYesNo( self, message )
        
        if result == QW.QDialog.Accepted:
            
            file_seed_cache = self._file_seed_cache_get_callable()
            
            file_seed_cache.RetryIgnored()
            
        
    
    def _ShowFileSeedCacheFrame( self ):
        
        file_seed_cache = self._file_seed_cache_get_callable()
        
        tlw = self.window()
        
        if isinstance( tlw, QP.Dialog ):
            
            if self._file_seed_cache_set_callable is None: # throw up a dialog that edits the file_seed cache in place
                
                with ClientGUITopLevelWindowsPanels.DialogNullipotent( self, 'file import status' ) as dlg:
                    
                    panel = EditFileSeedCachePanel( dlg, self._controller, file_seed_cache )
                    
                    dlg.SetPanel( panel )
                    
                    dlg.exec()
                    
                
            else: # throw up a dialog that edits the file_seed cache but can be cancelled
                
                dupe_file_seed_cache = file_seed_cache.Duplicate()
                
                with ClientGUITopLevelWindowsPanels.DialogEdit( self, 'file import status' ) as dlg:
                    
                    panel = EditFileSeedCachePanel( dlg, self._controller, dupe_file_seed_cache )
                    
                    dlg.SetPanel( panel )
                    
                    if dlg.exec() == QW.QDialog.Accepted:
                        
                        self._file_seed_cache_set_callable( dupe_file_seed_cache )
                        
                    
                
            
        else: # throw up a frame that edits the file_seed cache in place
            
            title = 'file import status'
            frame_key = 'file_import_status'
            
            frame = ClientGUITopLevelWindowsPanels.FrameThatTakesScrollablePanel( self, title, frame_key )
            
            panel = EditFileSeedCachePanel( frame, self._controller, file_seed_cache )
            
            frame.SetPanel( panel )
            
        
    
    def _ShowFilesInNewPage( self, show = 'all' ):
        
        file_seed_cache = self._file_seed_cache_get_callable()
        
        if show == 'all':
            
            hashes = file_seed_cache.GetHashes()
            
        elif show == 'new':
            
            file_import_options = ClientImportOptions.FileImportOptions()
            
            file_import_options.SetPresentationOptions( True, False, False )
            
            hashes = file_seed_cache.GetPresentedHashes( file_import_options )
            
        
        if len( hashes ) > 0:
            
            HG.client_controller.pub( 'new_page_query', CC.LOCAL_FILE_SERVICE_KEY, initial_hashes = hashes )
            
        
    
    def contextMenuEvent( self, event ):
        
        if event.reason() == QG.QContextMenuEvent.Keyboard:
            
            self.ShowMenu()
            
        
    
    def mouseReleaseEvent( self, event ):
        
        if event.button() != QC.Qt.RightButton:
            
            ClientGUICommon.BetterBitmapButton.mouseReleaseEvent( self, event )
            
            return
            
        
        self.ShowMenu()
        
    
    def ShowMenu( self ):
        
        menu = QW.QMenu()
        
        file_seed_cache = self._file_seed_cache_get_callable()
        
        num_file_seeds = len( file_seed_cache )
        num_successful = file_seed_cache.GetFileSeedCount( CC.STATUS_SUCCESSFUL_AND_NEW ) + file_seed_cache.GetFileSeedCount( CC.STATUS_SUCCESSFUL_BUT_REDUNDANT )
        num_vetoed = file_seed_cache.GetFileSeedCount( CC.STATUS_VETOED )
        num_deleted_and_vetoed = file_seed_cache.GetFileSeedCount( CC.STATUS_DELETED ) + num_vetoed
        num_errors = file_seed_cache.GetFileSeedCount( CC.STATUS_ERROR )
        num_skipped = file_seed_cache.GetFileSeedCount( CC.STATUS_SKIPPED )
        
        if num_errors > 0:
            
            ClientGUIMenus.AppendMenuItem( menu, 'retry ' + HydrusData.ToHumanInt( num_errors ) + ' error failures', 'Tell this cache to reattempt all its error failures.', self._RetryErrors )
            
        
        if num_vetoed > 0:
            
            ClientGUIMenus.AppendMenuItem( menu, 'retry ' + HydrusData.ToHumanInt( num_vetoed ) + ' ignored', 'Tell this cache to reattempt all its ignored/vetoed results.', self._RetryIgnored )
            
        
        ClientGUIMenus.AppendSeparator( menu )
        
        if num_successful > 0:
            
            num_deletees = num_successful

            ClientGUIMenus.AppendMenuItem( menu, 'delete ' + HydrusData.ToHumanInt( num_deletees ) + ' successful file import items from the queue', 'Tell this cache to clear out successful files, reducing the size of the queue.', self._ClearFileSeeds, (CC.STATUS_SUCCESSFUL_AND_NEW, CC.STATUS_SUCCESSFUL_BUT_REDUNDANT) )
            
        
        if num_deleted_and_vetoed > 0:
            
            num_deletees = num_deleted_and_vetoed

            ClientGUIMenus.AppendMenuItem( menu, 'delete ' + HydrusData.ToHumanInt( num_deletees ) + ' deleted/ignored file import items from the queue', 'Tell this cache to clear out deleted and ignored files, reducing the size of the queue.', self._ClearFileSeeds, (CC.STATUS_DELETED, CC.STATUS_VETOED) )
            
        
        if num_errors + num_skipped > 0:
            
            num_deletees = num_errors + num_skipped

            ClientGUIMenus.AppendMenuItem( menu, 'delete ' + HydrusData.ToHumanInt( num_deletees ) + ' error/skipped file import items from the queue', 'Tell this cache to clear out errored and skipped files, reducing the size of the queue.', self._ClearFileSeeds, (CC.STATUS_ERROR, CC.STATUS_SKIPPED) )
            
        
        ClientGUIMenus.AppendSeparator( menu )
        
        ClientGUIMenus.AppendMenuItem( menu, 'show new files in a new page', 'Gather the new files in this import list and show them in a new page.', self._ShowFilesInNewPage, show = 'new' )
        ClientGUIMenus.AppendMenuItem( menu, 'show all files in a new page', 'Gather the files in this import list and show them in a new page.', self._ShowFilesInNewPage )
        
        ClientGUIMenus.AppendSeparator( menu )
        
        if len( file_seed_cache ) > 0:
            
            submenu = QW.QMenu( menu )

            ClientGUIMenus.AppendMenuItem( submenu, 'to clipboard', 'Copy all the sources in this list to the clipboard.', self._ExportToClipboard )
            ClientGUIMenus.AppendMenuItem( submenu, 'to png', 'Export all the sources in this list to a png file.', self._ExportToPNG )
            
            ClientGUIMenus.AppendMenu( menu, submenu, 'export all sources' )
            
        
        submenu = QW.QMenu( menu )

        ClientGUIMenus.AppendMenuItem( submenu, 'from clipboard', 'Import new urls or paths to this list from the clipboard.', self._ImportFromClipboard )
        ClientGUIMenus.AppendMenuItem( submenu, 'from png', 'Import new urls or paths to this list from a png file.', self._ImportFromPNG )
        
        ClientGUIMenus.AppendMenu( menu, submenu, 'import new sources' )
        
        CGC.core().PopupMenu( self, menu )
        
    
class FileSeedCacheStatusControl( QW.QFrame ):
    
    def __init__( self, parent, controller, page_key = None ):
        
        QW.QFrame.__init__( self, parent )
        
        self.setFrameStyle( QW.QFrame.Box | QW.QFrame.Raised )
        
        self._controller = controller
        self._page_key = page_key
        
        self._file_seed_cache = None
        
        self._import_summary_st = ClientGUICommon.BetterStaticText( self, ellipsize_end = True )
        self._progress_st = ClientGUICommon.BetterStaticText( self, ellipsize_end = True )
        
        self._file_seed_cache_button = FileSeedCacheButton( self, self._controller, self._GetFileSeedCache )
        
        self._progress_gauge = ClientGUICommon.Gauge( self )
        
        #
        
        self._Update()
        
        #
        
        hbox = QP.HBoxLayout()
        
        QP.AddToLayout( hbox, self._progress_st, CC.FLAGS_CENTER_PERPENDICULAR_EXPAND_DEPTH )
        QP.AddToLayout( hbox, self._file_seed_cache_button, CC.FLAGS_CENTER_PERPENDICULAR )
        
        vbox = QP.VBoxLayout()
        
        QP.AddToLayout( vbox, self._import_summary_st, CC.FLAGS_EXPAND_PERPENDICULAR )
        QP.AddToLayout( vbox, hbox, CC.FLAGS_EXPAND_SIZER_PERPENDICULAR )
        QP.AddToLayout( vbox, self._progress_gauge, CC.FLAGS_EXPAND_PERPENDICULAR )
        
        self.setLayout( vbox )
        
        #
        
        HG.client_controller.gui.RegisterUIUpdateWindow( self )
        
    
    def _GetFileSeedCache( self ):
        
        return self._file_seed_cache
        
    
    def _Update( self ):
        
        if self._file_seed_cache is None:
            
            self._import_summary_st.clear()
            self._progress_st.clear()
            self._progress_gauge.SetRange( 1 )
            self._progress_gauge.SetValue( 0 )
            
            if self._file_seed_cache_button.isEnabled():
                
                self._file_seed_cache_button.setEnabled( False )
                
            
        else:
            
            file_seed_cache_status = self._file_seed_cache.GetStatus()
            
            ( num_done, num_to_do ) = file_seed_cache_status.GetValueRange()
            
            self._import_summary_st.setText( file_seed_cache_status.GetStatusText() )
            
            if num_to_do == 0:
                
                self._progress_st.clear()
                
            else:
                
                self._progress_st.setText( HydrusData.ConvertValueRangeToPrettyString(num_done,num_to_do) )
                
            
            self._progress_gauge.SetRange( num_to_do )
            self._progress_gauge.SetValue( num_done )
            
            if not self._file_seed_cache_button.isEnabled():
                
                self._file_seed_cache_button.setEnabled( True )
                
            
        
    
    def SetFileSeedCache( self, file_seed_cache ):
        
        if not self or not QP.isValid( self ):
            
            return
            
        
        self._file_seed_cache = file_seed_cache
        
    
    def TIMERUIUpdate( self ):
        
        do_it_anyway = False
        
        if self._file_seed_cache is not None:
            
            file_seed_cache_status = self._file_seed_cache.GetStatus()
            
            ( num_done, num_to_do ) = file_seed_cache_status.GetValueRange()
            
            ( old_num_done, old_num_to_do ) = self._progress_gauge.GetValueRange()
            
            if old_num_done != num_done or old_num_to_do != num_to_do:
                
                if self._page_key is not None:
                    
                    do_it_anyway = True # to update the gauge
                    
                    HG.client_controller.pub( 'refresh_page_name', self._page_key )
                    
                
            
        
        if self._controller.gui.IShouldRegularlyUpdate( self ) or do_it_anyway:
            
            self._Update()
            
        
    
