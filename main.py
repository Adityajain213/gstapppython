"""Invoice Extractor - Kivy desktop/Android application.

The app keeps Purchase and Sale workbooks separated by month. Bill images are
processed temporarily for OCR and are never saved as invoice records.
"""

from kivy.app import App
from kivy.lang import Builder
from kivy.properties import StringProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.popup import Popup
from kivy.uix.label import Label
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.clock import Clock
from datetime import datetime

from invoice_parser import parse_invoice
from excel_store import (
    save_invoice,
    get_excel_path,
    open_excel,
    list_workbooks,
    create_monthly_workbook,
)
from ocr_engine import extract_text

KV = r'''
#:import dp kivy.metrics.dp

<PrimaryButton@Button>:
    size_hint_y: None
    height: dp(56)
    font_size: dp(18)

<HomeScreen>:
    BoxLayout:
        orientation: 'vertical'
        padding: dp(24)
        spacing: dp(14)
        Label:
            text: 'Bill to Excel'
            font_size: dp(30)
            bold: True
            size_hint_y: None
            height: dp(70)
        Label:
            text: 'Select Purchase or Sale'
            font_size: dp(17)
            size_hint_y: None
            height: dp(35)
        PrimaryButton:
            text: 'PURCHASE'
            on_release: root.choose('purchase')
        PrimaryButton:
            text: 'SALE'
            on_release: root.choose('sale')
        PrimaryButton:
            text: 'VIEW EXCEL FILES'
            on_release: root.view_all_excel()
        Widget:
        Label:
            text: 'Bill photos are processed temporarily and are not stored.'
            font_size: dp(13)
            size_hint_y: None
            height: dp(45)

<WorkbookScreen>:
    BoxLayout:
        orientation: 'vertical'
        padding: dp(12)
        spacing: dp(10)
        BoxLayout:
            size_hint_y: None
            height: dp(55)
            Button:
                text: 'Back'
                size_hint_x: .25
                on_release: app.root.current = 'home'
            Label:
                id: title_label
                text: 'Select Monthly File'
                font_size: dp(20)
        Label:
            text: 'Select an existing month or create a new monthly Excel file.'
            size_hint_y: None
            height: dp(35)
        ScrollView:
            GridLayout:
                id: workbook_list
                cols: 1
                spacing: dp(8)
                padding: dp(8)
                size_hint_y: None
                height: self.minimum_height
        BoxLayout:
            size_hint_y: None
            height: dp(55)
            spacing: dp(8)
            TextInput:
                id: new_month
                hint_text: 'New month: YYYY-MM'
                text: app.default_month
                multiline: False
            Button:
                text: 'CREATE MONTH'
                size_hint_x: .35
                on_release: root.create_month()

<ExcelListScreen>:
    BoxLayout:
        orientation: 'vertical'
        padding: dp(12)
        spacing: dp(10)
        BoxLayout:
            size_hint_y: None
            height: dp(55)
            Button:
                text: 'Back'
                size_hint_x: .25
                on_release: app.root.current = 'home'
            Label:
                text: 'All Excel Files'
                font_size: dp(20)
        Label:
            text: 'All Purchase and Sale monthly files stored locally on this device.'
            size_hint_y: None
            height: dp(35)
        ScrollView:
            GridLayout:
                id: excel_list
                cols: 1
                spacing: dp(8)
                padding: dp(8)
                size_hint_y: None
                height: self.minimum_height

<PickScreen>:
    BoxLayout:
        orientation: 'vertical'
        BoxLayout:
            size_hint_y: None
            height: dp(55)
            Button:
                text: 'Back'
                size_hint_x: .25
                on_release: app.root.current = 'workbooks'
            Label:
                id: pick_title
                text: 'Select Bill'
                font_size: dp(20)
        FileChooserListView:
            id: chooser
            filters: ['*.png', '*.jpg', '*.jpeg', '*.webp']
        Button:
            text: 'Extract Data'
            size_hint_y: None
            height: dp(58)
            on_release: root.extract(chooser.selection)

<ReviewScreen>:
    BoxLayout:
        orientation: 'vertical'
        ScrollView:
            GridLayout:
                id: fields
                cols: 2
                spacing: dp(8)
                padding: dp(12)
                size_hint_y: None
                height: self.minimum_height
        BoxLayout:
            size_hint_y: None
            height: dp(58)
            Button:
                text: 'Back'
                on_release: app.root.current = 'pick'
            Button:
                text: 'Save to Excel'
                on_release: root.save()
'''

Builder.load_string(KV)


FIELD_LABELS = {
    'party_name': 'Party Name',
    'gstin': 'GSTIN',
    'invoice_no': 'Invoice No.',
    'invoice_date': 'Invoice Date',
    'place_of_supply': 'Place of Supply',
    'rate': 'GST Rate (%)',
    'taxable_amount': 'Taxable Amount (₹)',
    'igst': 'IGST Amount (₹)',
    'cgst': 'CGST Amount (₹)',
    'sgst': 'SGST Amount (₹)',
    'total': 'Invoice Total (₹)',
}


class HomeScreen(Screen):
    def choose(self, kind):
        """Open the monthly workbook selector for Purchase or Sale."""
        app = App.get_running_app()
        app.invoice_type = kind
        app.active_workbook = ''
        self.manager.current = 'workbooks'
        self.manager.get_screen('workbooks').refresh()

    def view_all_excel(self):
        """Open one combined screen showing every local Purchase/Sale workbook."""
        screen = self.manager.get_screen('excel_list')
        screen.refresh()
        self.manager.current = 'excel_list'


class WorkbookScreen(Screen):
    def refresh(self):
        """Display all existing monthly files for the currently selected type."""
        app = App.get_running_app()
        self.ids.title_label.text = f"{app.invoice_type.title()} - Select Month"
        container = self.ids.workbook_list
        container.clear_widgets()

        files = list_workbooks(app.invoice_type)
        if not files:
            container.add_widget(Label(
                text='No monthly file exists yet. Create one below.',
                size_hint_y=None,
                height=45,
            ))
        else:
            for item in files:
                button = Button(
                    text=f"{item['month_label']}   ({item['name']})",
                    size_hint_y=None,
                    height=55,
                )
                button.bind(on_release=lambda btn, path=str(item['path']): self.select_workbook(path))
                container.add_widget(button)

    def select_workbook(self, path):
        """Remember the selected monthly workbook and continue to bill upload."""
        app = App.get_running_app()
        app.active_workbook = path
        pick = self.manager.get_screen('pick')
        pick.ids.pick_title.text = f"Upload {app.invoice_type.title()} Bill"
        pick.ids.chooser.selection = []
        self.manager.current = 'pick'

    def create_month(self):
        """Create a YYYY-MM workbook and immediately select it."""
        month_key = self.ids.new_month.text.strip()
        try:
            datetime.strptime(month_key, '%Y-%m')
        except ValueError:
            Popup(
                title='Invalid month',
                content=Label(text='Enter the month as YYYY-MM, for example 2026-09.'),
                size_hint=(.9, .3),
            ).open()
            return

        try:
            path = create_monthly_workbook(App.get_running_app().invoice_type, month_key)
            self.select_workbook(str(path))
        except Exception as exc:
            Popup(title='Cannot create month', content=Label(text=str(exc)), size_hint=(.9, .35)).open()


class ExcelListScreen(Screen):
    def refresh(self):
        """Show every locally stored Purchase and Sale workbook."""
        container = self.ids.excel_list
        container.clear_widgets()
        files = list_workbooks()

        if not files:
            container.add_widget(Label(
                text='No Excel files have been created yet.',
                size_hint_y=None,
                height=45,
            ))
            return

        for item in files:
            button = Button(
                text=f"{item['type'].title()}  •  {item['month_label']}\n{item['name']}",
                size_hint_y=None,
                height=65,
            )
            button.bind(on_release=lambda btn, path=str(item['path']): self.open_selected(path))
            container.add_widget(button)

    def open_selected(self, path):
        try:
            open_excel(path)
        except Exception as exc:
            Popup(title='Cannot open Excel', content=Label(text=str(exc)), size_hint=(.9, .35)).open()


class PickScreen(Screen):
    def extract(self, selection):
        if not selection:
            Popup(
                title='Select bill',
                content=Label(text='Please select an image first.'),
                size_hint=(.9, .3),
            ).open()
            return

        app = App.get_running_app()
        try:
            text = extract_text(selection[0])
            data = parse_invoice(text, app.invoice_type)
            review = self.manager.get_screen('review')
            review.load_data(data, text)
            self.manager.current = 'review'
        except Exception as exc:
            Popup(title='Extraction error', content=Label(text=str(exc)), size_hint=(.9, .35)).open()


class ReviewScreen(Screen):
    def _add_field(self, key, value):
        """Add one editable invoice-level field."""
        label = Label(text=FIELD_LABELS.get(key, key), size_hint_y=None, height=42)
        inp = TextInput(
            text='' if value is None else str(value),
            multiline=False,
            size_hint_y=None,
            height=42,
        )
        self.ids.fields.add_widget(label)
        self.ids.fields.add_widget(inp)
        self.inputs[key] = inp

    def _add_sale_items(self, items):
        """Build an editable table for every Sale HSN/item row."""
        fields = self.ids.fields
        fields.add_widget(Label(text='SALE ITEMS', bold=True, size_hint_y=None, height=42))
        fields.add_widget(Label(text='', size_hint_y=None, height=42))

        columns = [
            ('hsn', 'HSN'), ('quantity', 'Qty'), ('taxable', 'Taxable'),
            ('igst', 'IGST'), ('cgst', 'CGST'), ('sgst', 'SGST'), ('total', 'Total')
        ]

        self.item_inputs = []
        for index, item in enumerate(items):
            row_widgets = {}
            fields.add_widget(Label(text=f'Item {index + 1}', size_hint_y=None, height=42))
            fields.add_widget(Label(text='', size_hint_y=None, height=42))

            for key, title in columns:
                fields.add_widget(Label(text=title, size_hint_y=None, height=38))
                inp = TextInput(
                    text='' if item.get(key) is None else str(item.get(key)),
                    multiline=False,
                    size_hint_y=None,
                    height=38,
                )
                fields.add_widget(inp)
                row_widgets[key] = inp

            fields.add_widget(Label(text='Description', size_hint_y=None, height=38))
            desc = TextInput(
                text=item.get('description', ''),
                multiline=False,
                size_hint_y=None,
                height=38,
            )
            fields.add_widget(desc)
            row_widgets['description'] = desc
            self.item_inputs.append(row_widgets)

    def load_data(self, data, raw_text):
        self.data = data
        self.raw_text = raw_text
        self.inputs = {}
        self.item_inputs = []
        self.ids.fields.clear_widgets()

        for key in data.get('invoice_fields', []):
            self._add_field(key, data.get(key))

        if App.get_running_app().invoice_type == 'sale':
            self._add_sale_items(data.get('items') or [])

    @staticmethod
    def _number(text):
        """Convert an editable numeric field to a float, or None when blank."""
        text = text.strip().replace(',', '')
        if not text:
            return None
        return float(text)

    def save(self):
        app = App.get_running_app()

        for key, widget in self.inputs.items():
            value = widget.text.strip()
            if key in {'rate', 'taxable_amount', 'igst', 'cgst', 'sgst', 'total'}:
                try:
                    value = self._number(value)
                except ValueError:
                    Popup(
                        title='Invalid value',
                        content=Label(text=f'Please enter a valid number for {FIELD_LABELS[key]}.'),
                        size_hint=(.9, .3),
                    ).open()
                    return
            self.data[key] = value

        if app.invoice_type == 'sale':
            items = []
            for row in self.item_inputs:
                try:
                    item = {
                        'description': row['description'].text.strip(),
                        'hsn': row['hsn'].text.strip(),
                        'quantity': self._number(row['quantity'].text),
                        'taxable': self._number(row['taxable'].text),
                        'igst': self._number(row['igst'].text),
                        'cgst': self._number(row['cgst'].text),
                        'sgst': self._number(row['sgst'].text),
                        'total': self._number(row['total'].text),
                    }
                except ValueError:
                    Popup(
                        title='Invalid item value',
                        content=Label(text='Please enter valid numbers in the Sale item table.'),
                        size_hint=(.9, .3),
                    ).open()
                    return
                items.append(item)
            self.data['items'] = items

        try:
            # Save to the workbook selected on the previous screen.
            if not app.active_workbook:
                Popup(
                    title='Select month',
                    content=Label(text='Please select or create a monthly Excel file first.'),
                    size_hint=(.9, .3),
                ).open()
                return

            save_invoice(app.invoice_type, self.data, app.active_workbook)
            self.show_save_success()

        except Exception as exc:
            Popup(title='Save error', content=Label(text=str(exc)), size_hint=(.9, .35)).open()

    def show_save_success(self):
        """Show success, clear the review form, and prepare the next bill."""

        # Android: use native Toast in the final APK.
        try:
            from jnius import autoclass

            Toast = autoclass('android.widget.Toast')
            PythonActivity = autoclass('org.kivy.android.PythonActivity')
            Toast.makeText(
                PythonActivity.mActivity,
                'Save successful',
                Toast.LENGTH_SHORT,
            ).show()
        except Exception:
            # Windows/Desktop fallback for testing.
            popup = Popup(
                title='Success',
                content=Label(text='Save successful'),
                size_hint=(.45, .22),
                auto_dismiss=True,
            )
            popup.open()
            Clock.schedule_once(lambda dt: popup.dismiss(), 1.2)

        # Clear all extracted fields and temporary OCR data.
        self.data = {}
        self.raw_text = ''
        self.inputs = {}
        self.item_inputs = []
        self.ids.fields.clear_widgets()

        # Clear the previous image selection. The image itself is never copied
        # into the app's permanent storage.
        pick_screen = self.manager.get_screen('pick')
        pick_screen.ids.chooser.selection = []

        # Keep the selected month and return directly to the next upload screen.
        self.manager.current = 'pick'


class InvoiceExtractorApp(App):
    invoice_type = StringProperty('purchase')
    active_workbook = StringProperty('')
    default_month = StringProperty(datetime.now().strftime('%Y-%m'))

    def build(self):
        sm = ScreenManager()
        sm.add_widget(HomeScreen(name='home'))
        sm.add_widget(WorkbookScreen(name='workbooks'))
        sm.add_widget(ExcelListScreen(name='excel_list'))
        sm.add_widget(PickScreen(name='pick'))
        sm.add_widget(ReviewScreen(name='review'))
        return sm


if __name__ == '__main__':
    InvoiceExtractorApp().run()
