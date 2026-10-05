from django import forms
from .models import Category, Product, Quote, QuoteItem

# =====================================================================
# MÓDULO: forms.py
# Propósito: Declarar los formularios para validación y UI de datos.
# =====================================================================

class CalculatorForm(forms.Form):
    """
    Formulario NO vinculado a modelo.
    Sirve únicamente para recoger los datos de entrada en la vista
    del administrador y pasarlos a utils/calculator.py.
    """
    weight_grams = forms.FloatField(
        label="Peso del Filamento (g)",
        min_value=0.1,
        widget=forms.NumberInput(attrs={'class': 'form-input w-full rounded-md bg-gray-800 text-white border-gray-600 focus:border-cyan-500'})
    )
    hours = forms.IntegerField(
        label="Horas",
        min_value=0,
        initial=0,
        widget=forms.NumberInput(attrs={'class': 'form-input w-full rounded-md bg-gray-800 text-white border-gray-600 focus:border-cyan-500'})
    )
    minutes = forms.IntegerField(
        label="Minutos",
        min_value=0,
        max_value=59,
        initial=0,
        widget=forms.NumberInput(attrs={'class': 'form-input w-full rounded-md bg-gray-800 text-white border-gray-600 focus:border-cyan-500'})
    )
    other_materials_cost = forms.FloatField(
        label="Otros Materiales (€)",
        min_value=0.0,
        initial=0.0,
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-input w-full rounded-md bg-gray-800 text-white border-gray-600 focus:border-cyan-500'})
    )

class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True

class MultipleFileField(forms.FileField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput(attrs={
            'multiple': True,
            'class': 'form-input w-full rounded-md bg-gray-800 text-white border-gray-600 focus:border-cyan-500'
        }))
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single_file_clean = super().clean
        if isinstance(data, (list, tuple)):
            result = [single_file_clean(d, initial) for d in data]
        else:
            result = [single_file_clean(data, initial)]
        return result

class ProductFromCalcForm(forms.ModelForm):
    """
    Formulario vinculado a Product.
    Se utiliza para el "Botón de Acción Rápida" que guarda el cálculo
    directamente en la base de datos del catálogo.
    """
    new_category = forms.CharField(
        max_length=100, 
        required=False, 
        label="Nueva Categoría",
        help_text="Si seleccionas una existente, esto se ignorará.",
        widget=forms.TextInput(attrs={'class': 'form-input w-full rounded-md bg-gray-800 text-white border-gray-600 focus:border-cyan-500'})
    )
    
    category = forms.ModelChoiceField(
        queryset=Category.objects.all(),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select w-full rounded-md bg-gray-800 text-white border-gray-600 focus:border-cyan-500'})
    )
    
    gallery_images = MultipleFileField(
        label="Más imágenes (Galería)",
        required=False
    )
    
    class Meta:
        model = Product
        fields = ['title', 'category', 'new_category', 'description', 'price', 'is_on_sale', 'sale_price', 'is_active', 'weight_grams', 'print_time_hours', 'print_time_minutes', 'extra_costs', 'dimensions', 'makerworld_url', 'main_image', 'model_file']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-input w-full rounded-md bg-gray-800 text-white border-gray-600 focus:border-cyan-500'}),
            'category': forms.Select(attrs={'class': 'form-select w-full rounded-md bg-gray-800 text-white border-gray-600 focus:border-cyan-500', 'required': False}),
            'description': forms.Textarea(attrs={'class': 'form-textarea w-full rounded-md bg-gray-800 text-white border-gray-600 focus:border-cyan-500', 'rows': 3, 'required': False}),
            'price': forms.NumberInput(attrs={'class': 'form-input w-full rounded-md bg-gray-800 text-white border-gray-600 focus:border-cyan-500', 'step': '0.01'}),
            'is_on_sale': forms.CheckboxInput(attrs={'class': 'form-checkbox h-5 w-5 text-cyan-600 bg-gray-800 border-gray-600 rounded focus:ring-cyan-500 focus:ring-offset-gray-900', 'required': False}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-checkbox h-5 w-5 text-cyan-600 bg-gray-800 border-gray-600 rounded focus:ring-cyan-500 focus:ring-offset-gray-900', 'required': False}),
            'sale_price': forms.NumberInput(attrs={'class': 'form-input w-full rounded-md bg-gray-800 text-white border-gray-600 focus:border-cyan-500', 'step': '0.01', 'required': False}),
            'weight_grams': forms.NumberInput(attrs={'class': 'form-input w-full rounded-md bg-gray-800 text-white border-gray-600 focus:border-cyan-500', 'required': False}),
            'print_time_hours': forms.NumberInput(attrs={'class': 'form-input w-full rounded-md bg-gray-800 text-white border-gray-600 focus:border-cyan-500', 'step': '0.1', 'required': False}),
            'print_time_minutes': forms.NumberInput(attrs={'class': 'form-input w-full rounded-md bg-gray-800 text-white border-gray-600 focus:border-cyan-500', 'required': False}),
            'extra_costs': forms.NumberInput(attrs={'class': 'form-input w-full rounded-md bg-gray-800 text-white border-gray-600 focus:border-cyan-500', 'step': '0.01', 'required': False}),
            'dimensions': forms.TextInput(attrs={'class': 'form-input w-full rounded-md bg-gray-800 text-white border-gray-600 focus:border-cyan-500', 'required': False}),
            'makerworld_url': forms.URLInput(attrs={'class': 'form-input w-full rounded-md bg-gray-800 text-white border-gray-600 focus:border-cyan-500', 'required': False}),
            'main_image': forms.FileInput(attrs={'class': 'form-input w-full rounded-md bg-gray-800 text-white border-gray-600 focus:border-cyan-500', 'required': False}),
            'model_file': forms.FileInput(attrs={'class': 'form-input w-full rounded-md bg-gray-800 text-white border-gray-600 focus:border-cyan-500', 'required': False, 'accept': '.stl,.3mf,.step,.stp,.zip,.rar,.7z'}),
        }

class ScraperForm(forms.Form):
    """
    Formulario simple para pegar la URL de MakerWorld.
    """
    url = forms.URLField(
        label="URL de MakerWorld",
        required=True,
        widget=forms.URLInput(attrs={
            'class': 'form-input w-full rounded-md bg-gray-800 text-white border-gray-600 focus:border-cyan-500',
            'placeholder': 'https://makerworld.com/en/models/...'
        })
    )

class QuoteForm(forms.ModelForm):
    """
    Formulario para crear/editar la cabecera de un Presupuesto.
    """
    class Meta:
        model = Quote
        fields = ['client_name', 'client_contact', 'notes', 'include_tax', 'tax_name', 'tax_percentage']
        widgets = {
            'client_name': forms.TextInput(attrs={'class': 'form-input w-full rounded-md bg-gray-800 text-white border-gray-600 focus:border-cyan-500'}),
            'client_contact': forms.TextInput(attrs={'class': 'form-input w-full rounded-md bg-gray-800 text-white border-gray-600 focus:border-cyan-500'}),
            'notes': forms.Textarea(attrs={'class': 'form-textarea w-full rounded-md bg-gray-800 text-white border-gray-600 focus:border-cyan-500', 'rows': 3}),
            'include_tax': forms.CheckboxInput(attrs={'class': 'form-checkbox h-5 w-5 text-cyan-600 bg-gray-800 border-gray-600 rounded focus:ring-cyan-500 focus:ring-offset-gray-900', 'id': 'include-tax-checkbox'}),
            'tax_name': forms.TextInput(attrs={'class': 'form-input w-full rounded-md bg-gray-800 text-white border-gray-600 focus:border-cyan-500', 'id': 'tax-name-input'}),
            'tax_percentage': forms.NumberInput(attrs={'class': 'form-input w-full rounded-md bg-gray-800 text-white border-gray-600 focus:border-cyan-500', 'step': '0.01', 'id': 'tax-percent-input'}),
        }
