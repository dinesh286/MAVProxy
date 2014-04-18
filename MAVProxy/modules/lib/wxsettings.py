'''
Graphical editing of mp_settings object
'''
import os, wx, sys

class WXSettings(object):
    '''
    a graphical settings dialog for mavproxy
    '''
    def __init__(self, settings):
        import multiprocessing, threading
        self.settings  = settings
        self.parent_pipe,self.child_pipe = multiprocessing.Pipe()
        self.close_event = multiprocessing.Event()
        self.close_event.clear()
        self.child = multiprocessing.Process(target=self.child_task)
        self.child.start()
        t = threading.Thread(target=self.watch_thread)
        t.daemon = True
        t.start()

    def child_task(self):
        '''child process - this holds all the GUI elements'''
        import threading
        app = wx.PySimpleApp()
        dlg = SettingsDlg(self.settings)
        dlg.parent_pipe = self.parent_pipe
        dlg.ShowModal()
        dlg.Destroy()

    def watch_thread(self):
        '''watch for settings changes from child'''
        from mp_settings import MPSetting
        while True:
            setting = self.child_pipe.recv()
            if not isinstance(setting, MPSetting):
                break
            try:
                self.settings.set(setting.name, setting.value)
            except Exception:
                print("Unable to set %s to %s" % (setting.name, setting.value))

    def is_alive(self):
        '''check if child is still going'''
        return self.child.is_alive()

class TabbedDialog(wx.Dialog):
    def __init__(self, tab_names, title='Title', size=wx.DefaultSize):
        wx.Dialog.__init__(self, None, -1, title,
                           style=wx.DEFAULT_DIALOG_STYLE|wx.RESIZE_BORDER)
        self.tab_names = tab_names
        self.notebook = wx.Notebook(self, -1, size=size)
        self.panels = {}
        self.sizers = {}
        for t in tab_names:
            self.panels[t] = wx.Panel(self.notebook)
            self.notebook.AddPage(self.panels[t], t)
            self.sizers[t] = wx.BoxSizer(wx.VERTICAL)
            self.panels[t].SetSizer(self.sizers[t])
        self.dialog_sizer = wx.BoxSizer(wx.VERTICAL)
        self.dialog_sizer.Add(self.notebook, 1, wx.EXPAND|wx.ALL, 5)
        self.controls = {}
        self.browse_option_map = {}
        self.control_map = {}
        self.setting_map = {}
        button_box = wx.BoxSizer(wx.HORIZONTAL)
        self.button_apply = wx.Button(self, -1, "Apply")
        self.button_cancel = wx.Button(self, -1, "Cancel")
        button_box.Add(self.button_cancel, 0, wx.ALL)
        button_box.Add(self.button_apply, 0, wx.ALL)
        self.dialog_sizer.Add(button_box, 0, wx.GROW|wx.ALIGN_CENTER_VERTICAL|wx.ALL, 5)
        wx.EVT_BUTTON(self, self.button_cancel.GetId(), self.on_cancel)
        wx.EVT_BUTTON(self, self.button_apply.GetId(), self.on_apply)
        self.Centre()

    def on_cancel(self, event):
        '''called on cancel'''
        self.Destroy()
        sys.exit(0)
        
    def on_apply(self, event):
        '''called on apply'''
        for label in self.setting_map.keys():
            setting = self.setting_map[label]
            ctrl = self.controls[label]
            value = ctrl.GetValue()
            if str(value) != str(setting.value):
                oldvalue = setting.value
                if not setting.set(value):
                    print("Invalid value %s for %s" % (value, setting.name))
                    continue
                if str(oldvalue) != str(setting.value):
                    self.parent_pipe.send(setting)

    def panel(self, tab_name):
        '''return the panel for a named tab'''
        return self.panels[tab_name]

    def sizer(self, tab_name):
        '''return the sizer for a named tab'''
        return self.sizers[tab_name]

    def refit(self):
        '''refit after elements are added'''
        self.SetSizerAndFit(self.dialog_sizer)

    def _add_input(self, setting, ctrl, ctrl2=None, value=None):
        tab_name = setting.tab
        label = setting.label
        tab = self.panel(tab_name)
        box = wx.BoxSizer(wx.HORIZONTAL)
        labelctrl = wx.StaticText(tab, -1, label )
        box.Add(labelctrl, 0, wx.ALIGN_CENTRE|wx.ALL, 5)
        box.Add( ctrl, 1, wx.ALIGN_CENTRE|wx.ALL, 5 )
        if ctrl2 is not None:
            box.Add( ctrl2, 0, wx.ALIGN_CENTRE|wx.ALL, 5 )
        self.sizer(tab_name).Add(box, 0, wx.GROW|wx.ALIGN_CENTER_VERTICAL|wx.ALL, 5)
        self.controls[label] = ctrl
        if value is not None:
            ctrl.Value = value
        else:
            ctrl.Value = str(setting.value)
        self.control_map[ctrl.GetId()] = label
        self.setting_map[label] = setting

    def add_text(self, setting, width=300, height=100, multiline=False):
        '''add a text input line'''
        tab = self.panel(setting.tab)
        if multiline:
            ctrl = wx.TextCtrl(tab, -1, "", size=(width,height), style=wx.TE_MULTILINE|wx.TE_PROCESS_ENTER)
        else:
            ctrl = wx.TextCtrl(tab, -1, "", size=(width,-1) )
        self._add_input(setting, ctrl)

    def add_filechooser(self, setting, width=300, directory=False):
        '''add a file input line'''
        tab = self.panel(setting.tab)
        ctrl = wx.TextCtrl(tab, -1, "", size=(width,-1) )
        browse = wx.Button(tab, label='...')        
        wx.EVT_BUTTON(tab, browse.GetId(), self._on_select_path)
        self.browse_option_map[browse.GetId()] = label
        self._add_input(setting, ctrl, ctrl2=browse)

    def add_choice(self, setting, choices):
        '''add a choice input line'''
        tab = self.panel(setting.tab)
        default = setting.default
        if default is None:
            default = choices[0]
        ctrl = wx.ComboBox(tab, -1, choices=choices,
                           value = str(default),
                           style = wx.CB_DROPDOWN | wx.CB_READONLY | wx.CB_SORT )
        self._add_input(setting, ctrl)

    def add_intspin(self, setting):
        '''add a spin control'''
        tab = self.panel(setting.tab)
        default = setting.default
        (minv, maxv) = setting.range
        ctrl = wx.SpinCtrl(tab, -1,
                           initial = default,
                           min = minv,
                           max = maxv)
        self._add_input(setting, ctrl, value=default)

    def add_floatspin(self, setting):
        '''add a floating point spin control'''
        from wx.lib.agw.floatspin import FloatSpin
        tab = self.panel(setting.tab)
        default = setting.default
        (minv, maxv) = setting.range
        ctrl = FloatSpin(tab, -1,
                         value = default,
                         min_val = minv,
                         max_val = maxv,
                         increment = setting.increment)
        if setting.format is not None:
            ctrl.SetFormat(setting.format)
        if setting.digits is not None:
            ctrl.SetDigits(setting.digits)
        self._add_input(setting, ctrl, value=default)
        
    def _on_select_path(self, event):
        label = self.browse_option_map[event.GetId()]
        ctrl = self.controls[label]
        path = os.path.abspath(ctrl.Value)
        dlg = wx.FileDialog(self,
                            message = 'Select file for %s' % label,
                            defaultDir = os.path.dirname(path),
                            defaultFile = path)
        dlg_result = dlg.ShowModal()
        if wx.ID_OK != dlg_result:
            return
        ctrl.Value = dlg.GetPath()

#----------------------------------------------------------------------
class SettingsDlg(TabbedDialog):
    def __init__(self, settings):
        title = "Resize the dialog and see how controls adapt!"
        self.settings = settings
        tabs = []
        for k in self.settings.list():
            setting = self.settings.get_setting(k)
            tab = setting.tab
            if tab is None:
                tab = 'Settings'
            if not tab in tabs:
                tabs.append(tab)
        title = self.settings.get_title()
        if title is None:
            title = 'Settings'
        TabbedDialog.__init__(self, tabs, title)
        for name in self.settings.list():
            setting = self.settings.get_setting(name)
            if setting.type == bool:
                self.add_choice(setting, ['True', 'False'])
            elif setting.choice is not None:
                self.add_choice(setting, setting.choice)                
            elif setting.type == int and setting.increment is not None and setting.range is not None:
                self.add_intspin(setting)
            elif setting.type == float and setting.increment is not None and setting.range is not None:
                self.add_floatspin(setting)
            else:
                self.add_text(setting)  
        self.refit()

if __name__ == "__main__":
    def test_callback(setting):
        '''callback on apply'''
        print("Changing %s to %s" % (setting.name, setting.value))

    # test the settings
    import mp_settings, time
    from mp_settings import MPSetting
    settings = mp_settings.MPSettings(
        [ MPSetting('link', int, 1, tab='TabOne'),
          MPSetting('altreadout', int, 10, range=(-30,1017), increment=1),
          MPSetting('pvalue', float, 0.3, range=(-3.0,1e6), increment=0.1, digits=2),
          MPSetting('enable', bool, True, tab='TabTwo'),
          MPSetting('colour', str, 'Blue', choice=['Red', 'Green', 'Blue']),
          MPSetting('foostr', str, 'blah', label='Foo String') ])
    settings.set_callback(test_callback)
    dlg = WXSettings(settings)
    while dlg.is_alive():
        time.sleep(0.1)
