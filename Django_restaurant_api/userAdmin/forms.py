from orders.models import Product
from django import forms

class AddProductForm(forms.ModelForm):
    title = forms.CharField(widget=forms.TextInput(attrs={'placeholder': 'Enter product title', 'class': 'form-control'}))
    image = forms.ImageField(widget=forms.FileInput(attrs={'class': 'form-control'}))
    description = forms.CharField(widget=forms.Textarea(attrs={'placeholder': 'Product Description', 'class': 'form-control'}))
    price = forms.CharField(widget=forms.NumberInput(attrs={'placeholder': 'Sales Price', 'class': 'form-control'}))

    class Meta:
        model = Product
        fields = ['category', 'title', 'image', 'description', 'price', 'in_stock']
